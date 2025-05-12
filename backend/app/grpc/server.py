"""
gRPC server implementation for EDR agent communication.
"""

import time
import json
import os
import uuid
import threading
from concurrent import futures
from collections import defaultdict

import grpc
from app.grpc import agent_pb2
from app.grpc import agent_pb2_grpc
from app.config.config import config
from app.logging_setup import get_logger, PerformanceLogger
from app.iocs import IOCManager
from app.storage import FileStorage

# Set up logging
logger = get_logger('app.grpc')
conn_logger = get_logger('app.grpc.connections')
debug_logger = get_logger('app.grpc.debug')
ioc_logger = get_logger('app.grpc.ioc')

# Define a dictionary for easy access to loggers
loggers = {
    'main': logger,
    'conn': conn_logger,
    'debug': debug_logger,
    'ioc': ioc_logger
}

# Global variable to store the active servicer instance
active_servicer = None

class EDRServicer(agent_pb2_grpc.EDRServiceServicer):
    """Implementation of EDRService service."""
    
    def __init__(self):
        self.storage = FileStorage()
        
        # Initialize IOC manager
        self.ioc_manager = IOCManager()
        
        # Active bidirectional streams by agent ID
        self.active_streams = {}
        self.stream_lock = threading.Lock()
        
        # Command results storage (in-memory with file backup)
        self.command_results = {}
        self.results_lock = threading.Lock()
        self.load_command_results()
        
        # Pending commands for offline agents
        self.pending_commands = defaultdict(list)
    
    def load_command_results(self):
        """Load command results from file."""
        results_file = os.path.join(self.storage.storage_dir, 'command_results.json')
        if os.path.exists(results_file):
            try:
                with open(results_file, 'r') as f:
                    self.command_results = json.load(f)
                    logger.info(f"Loaded {len(self.command_results)} command results from storage")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse command results file, using empty results")
                self.command_results = {}
                # Backup the corrupted file and create a new empty one
                backup_file = f"{results_file}.corrupted.{int(time.time())}"
                try:
                    os.rename(results_file, backup_file)
                    logger.info(f"Backed up corrupted file to {backup_file}")
                    with open(results_file, 'w') as f:
                        json.dump({}, f)
                except Exception as e:
                    logger.error(f"Error backing up corrupted file: {e}")
            except Exception as e:
                logger.error(f"Error loading command results: {e}")
                self.command_results = {}
        else:
            logger.info("No existing command results found")
            self.command_results = {}
    
    def save_command_results(self):
        """Save command results to file."""
        results_file = os.path.join(self.storage.storage_dir, 'command_results.json')
        with open(results_file, 'w') as f:
            json.dump(self.command_results, f, indent=2)
            
        logger.info(f"Saved {len(self.command_results)} command results to storage")
    
    def RegisterAgent(self, request, context):
        """Handle agent registration."""
        logger.info(f"New Agent Registration - ID: {request.agent_id}, Hostname: {request.hostname}")
        debug_logger.info(f"Registration details - OS: {request.os_version}, Agent version: {request.agent_version}")
        
        agent_id = request.agent_id
        hostname = request.hostname
        
        # Generate or validate agent ID
        if not agent_id:
            agent_id = str(uuid.uuid4())
            logger.info(f"Empty agent ID, generated new unique ID: {agent_id}")
        elif agent_id in self.storage.agents:
            existing_agent = self.storage.agents[agent_id]
            if existing_agent['hostname'] != hostname:
                old_id = agent_id
                agent_id = str(uuid.uuid4())
                logger.info(f"Agent ID {old_id} exists with different hostname. Generated new ID: {agent_id}")
        
        # Store agent information
        agent_data = {
            'agent_id': agent_id,
            'hostname': hostname,
            'ip_address': request.ip_address,
            'mac_address': request.mac_address,
            'username': request.username,
            'os_version': request.os_version,
            'agent_version': request.agent_version,
            'registration_time': request.registration_time,
            'last_seen': int(time.time()),
            'status': 'REGISTERED',
            'ioc_version': 0
        }
        
        self.storage.save_agent(agent_id, agent_data)
        logger.info(f"Registration successful for {hostname} with ID {agent_id}")
        
        # Return response with assigned ID
        return agent_pb2.RegisterResponse(
            server_message=f"Registration successful for {hostname}",
            success=True,
            assigned_id=agent_id,
            server_time=int(time.time())
        )
    
    def UpdateStatus(self, request, context):
        """Handle status update from agent."""
        agent_id = request.agent_id
        timestamp = request.timestamp
        status = request.status
        
        logger.info(f"Status update from agent {agent_id}: {status}")
        
        # Check if agent exists
        agent = self.storage.get_agent(agent_id)
        if not agent:
            logger.warning(f"Status update from unknown agent: {agent_id}")
            return agent_pb2.StatusResponse(
                server_message="Unknown agent",
                acknowledged=False,
                server_time=int(time.time())
            )
        
        # Update agent status
        agent.update({
            'last_seen': timestamp,
            'status': status
        })
        
        # Update metrics if provided
        if request.system_metrics:
            agent.update({
                'cpu_usage': request.system_metrics.cpu_usage,
                'memory_usage': request.system_metrics.memory_usage,
                'uptime': request.system_metrics.uptime
            })
        
        self.storage.save_agent(agent_id, agent)
        
        return agent_pb2.StatusResponse(
            server_message="Status update acknowledged",
            acknowledged=True,
            server_time=int(time.time())
        )
    
    def _check_ioc_update_needed(self, agent, agent_id):
        # Check if agent needs an IOC update
        current_agent_ioc_version = agent.get('ioc_version', 0)
        ioc_version_info = self.ioc_manager.get_version_info()
        
        if current_agent_ioc_version < ioc_version_info['version']:
            # Create and queue UPDATE_IOCS command
            command_id = str(uuid.uuid4())
            command = agent_pb2.Command(
                command_id=command_id,
                agent_id=agent_id,
                timestamp=int(time.time() * 1000),
                type=agent_pb2.CommandType.UPDATE_IOCS,
                params={},
                priority=5,  # High priority
                timeout=30   # 30 second timeout
            )
            
            with self.stream_lock:
                if agent_id not in self.pending_commands:
                    self.pending_commands[agent_id] = []
                self.pending_commands[agent_id].append(command)
                ioc_logger.info(f"Agent {agent_id} needs IOC update: {current_agent_ioc_version} < {ioc_version_info['version']}")
    
    def CommandStream(self, request_iterator, context):
        """Bidirectional stream for commands and results.
        
        This is the bidirectional streaming implementation that handles
        both command distribution and result collection in a single stream.
        """
        agent_id = None
        conn_logger.info(f"Bidirectional command stream opened from {context.peer()}")
        
        # Track the stream so we can manage it independently
        stream_active = True
        
        # Track when we last received a message from the agent
        last_activity_time = int(time.time())
        last_command_time = 0
        last_heartbeat_time = 0
        heartbeat_interval = 60  # seconds

        try:
            # Process the first message to get agent ID
            try:
                first_message = next(request_iterator)
                if hasattr(first_message, 'payload'):
                    if first_message.HasField('ping'):
                        agent_id = first_message.ping.agent_id
                        last_activity_time = first_message.ping.timestamp
                        conn_logger.info(f"Bidirectional stream identified agent {agent_id} via ping")
                    elif first_message.HasField('result'):
                        agent_id = first_message.result.agent_id
                        conn_logger.info(f"Bidirectional stream identified agent {agent_id} via result")
                    else:
                        conn_logger.warning(f"Unexpected first message type in bidirectional stream")
                        return
                else:
                    conn_logger.warning(f"Invalid first message format in bidirectional stream")
                    return
            except StopIteration:
                conn_logger.warning(f"Bidirectional stream ended before first message")
                return
            
            # Get or auto-register agent
            agent = self.storage.get_agent(agent_id)
            if not agent:
                agent = {
                    'agent_id': agent_id,
                    'hostname': 'unknown',
                    'ip_address': context.peer().split(':')[-1] if ':' in context.peer() else 'unknown',
                    'mac_address': 'unknown',
                    'username': 'unknown',
                    'os_version': 'unknown',
                    'agent_version': 'unknown',
                    'registration_time': int(time.time()),
                    'last_seen': int(time.time()),
                    'status': 'PENDING_REGISTRATION',
                    'ioc_version': 0
                }
                self.storage.save_agent(agent_id, agent)
                logger.info(f"Auto-registering unknown agent in bidirectional stream: {agent_id}")
            
            # Register stream in active_streams for command distribution
            with self.stream_lock:
                self.active_streams[agent_id] = context
                conn_logger.debug(f"Registered bidirectional command stream for agent {agent_id}")
            
            # Initial IOC check
            self._check_ioc_update_needed(agent, agent_id)
            
            # Set up thread for processing incoming messages
            def process_incoming_messages():
                nonlocal stream_active, last_activity_time
                
                try:
                    for message in request_iterator:
                        if not stream_active:
                            break
                            
                        # Update last activity time
                        last_activity_time = int(time.time())
                        
                        # Process incoming message based on type
                        if message.HasField('ping'):
                            # Update last activity time and agent status
                            ping = message.ping
                            debug_logger.debug(f"Received heartbeat from agent {agent_id}")
                            
                            # Update agent status
                            agent['last_seen'] = current_time = int(time.time())
                            agent['status'] = 'ONLINE'
                            self.storage.save_agent(agent_id, agent)
                            
                        elif message.HasField('result'):
                            # Process command result
                            result = message.result
                            command_id = result.command_id
                            
                            # Log result
                            log_fn = logger.info if result.success else logger.warning
                            log_fn(f"Command result from {agent_id}: {command_id} - Success: {result.success}, Duration: {result.duration_ms}ms")
                            
                            # Store result (similar to ReportCommandResult)
                            is_ioc_related = False
                            if "IOC update available" in result.message or "No IOC update available" in result.message:
                                is_ioc_related = True
                            
                            # Check by command type in pending commands
                            if not is_ioc_related:
                                for cmds in self.pending_commands.values():
                                    for cmd in cmds:
                                        if cmd.command_id == command_id and cmd.type == agent_pb2.CommandType.UPDATE_IOCS:
                                            is_ioc_related = True
                                            break
                                    if is_ioc_related:
                                        break
                            
                            # Update agent's IOC version if this was a successful IOC update
                            if is_ioc_related and "IOC update available" in result.message and result.success:
                                agent = self.storage.get_agent(agent_id)
                                if agent:
                                    agent['ioc_version'] = self.ioc_manager.get_version_info()['version']
                                    self.storage.save_agent(agent_id, agent)
                                    logger.info(f"Updated agent {agent_id} IOC version to {agent['ioc_version']}")
                            
                            # Store result only if not IOC related
                            if not is_ioc_related:
                                with self.results_lock:
                                    result_dict = {
                                        'command_id': result.command_id,
                                        'agent_id': result.agent_id,
                                        'success': result.success,
                                        'message': result.message,
                                        'execution_time': result.execution_time,
                                        'duration_ms': result.duration_ms
                                    }
                                    
                                    self.command_results[command_id] = result_dict
                                    self.save_command_results()
                            
                            # Remove from pending if present
                            with self.stream_lock:
                                if agent_id in self.pending_commands:
                                    self.pending_commands[agent_id] = [
                                        cmd for cmd in self.pending_commands[agent_id] 
                                        if cmd.command_id != command_id
                                    ]
                        
                        elif message.HasField('status'):
                            # Process status update
                            status = message.status
                            logger.info(f"Status update from agent {agent_id} via stream: {status.status}")
                            
                            # Update agent status
                            agent.update({
                                'last_seen': status.timestamp,
                                'status': status.status
                            })
                            
                            # Update metrics if provided
                            if status.system_metrics:
                                agent.update({
                                    'cpu_usage': status.system_metrics.cpu_usage,
                                    'memory_usage': status.system_metrics.memory_usage,
                                    'uptime': status.system_metrics.uptime
                                })
                            
                            self.storage.save_agent(agent_id, agent)
                            debug_logger.debug(f"Updated agent {agent_id} status from stream")
                        
                        elif message.HasField('ioc_match'):
                            # Process IOC match report
                            report = message.ioc_match
                            report_id = report.report_id
                            
                            # Log match details
                            logger.info(f"IOC match from agent {agent_id} via stream: {agent_pb2.IOCType.Name(report.type)} - {report.ioc_value}")
                            debug_logger.info(f"Match details: {report.matched_value}, Severity: {report.severity}")
                            
                            if report.action_taken != agent_pb2.CommandType.UNKNOWN:
                                action_name = agent_pb2.CommandType.Name(report.action_taken)
                                logger.info(f"Action taken: {action_name} - Success: {report.action_success}")
                            
                            # Store the match report
                            match_data = {
                                'report_id': report_id,
                                'agent_id': agent_id,
                                'timestamp': report.timestamp,
                                'type': agent_pb2.IOCType.Name(report.type),
                                'ioc_value': report.ioc_value,
                                'matched_value': report.matched_value,
                                'context': report.context,
                                'severity': report.severity,
                                'action_taken': agent_pb2.CommandType.Name(report.action_taken) if report.action_taken != agent_pb2.CommandType.UNKNOWN else None,
                                'action_success': report.action_success,
                                'action_message': report.action_message,
                                'server_received': int(time.time())
                            }
                            
                            self.storage.save_ioc_match(report_id, match_data)
                            
                            # Update agent with latest alert information
                            agent = self.storage.get_agent(agent_id)
                            if agent:
                                agent['last_ioc_match'] = {
                                    'timestamp': report.timestamp,
                                    'type': agent_pb2.IOCType.Name(report.type),
                                    'ioc_value': report.ioc_value,
                                    'severity': report.severity
                                }
                                self.storage.save_agent(agent_id, agent)
                            
                            # Send acknowledgment
                            try:
                                # Create base acknowledgment
                                ack = agent_pb2.IOCMatchAck(
                                    report_id=report_id,
                                    received=True,
                                    message="IOC match report received"
                                )
                                
                                # Check if additional action is needed based on IOC severity or type
                                # This is where you could implement automatic response policies
                                # For now, we're not implementing any automatic actions
                                
                                # Create message with IOC ack payload
                                ack_msg = agent_pb2.CommandMessage(
                                    ioc_ack=ack
                                )
                                
                                # Send the acknowledgment
                                yield ack_msg
                                logger.debug(f"Sent IOC match acknowledgment for report {report_id}")
                            except Exception as e:
                                logger.error(f"Failed to send IOC match acknowledgment: {e}")
                            
                        else:
                            logger.warning(f"Received unknown message type from agent {agent_id}")
                except Exception as e:
                    logger.error(f"Error processing bidirectional stream messages: {e}")
                    stream_active = False
            
            # Start a thread to process incoming messages
            message_thread = threading.Thread(target=process_incoming_messages)
            message_thread.daemon = True
            message_thread.start()
            
            # Main loop - send commands and heartbeats
            check_counter = 0
            while context.is_active() and stream_active:
                current_time = int(time.time())
                check_counter += 1
                
                # Check for inactive stream
                if current_time - last_activity_time > 180:  # 3 minutes without any message
                    logger.warning(f"Bidirectional stream for agent {agent_id} inactive for too long, closing")
                    stream_active = False
                    break
                
                # Send periodic heartbeat
                if current_time - last_heartbeat_time > heartbeat_interval:
                    try:
                        ping_message = agent_pb2.CommandMessage(
                            ping=agent_pb2.PingMessage(
                                agent_id="server",
                                timestamp=current_time
                            )
                        )
                        yield ping_message
                        last_heartbeat_time = current_time
                        debug_logger.debug(f"Sent heartbeat to agent {agent_id}")
                    except Exception as e:
                        logger.error(f"Error sending heartbeat to agent {agent_id}: {e}")
                        stream_active = False
                        break
                
                # Periodic IOC check (every ~15 seconds)
                if check_counter % 30 == 0:
                    self._check_ioc_update_needed(agent, agent_id)
                
                # Process pending commands
                with self.stream_lock:
                    pending = self.pending_commands.get(agent_id, [])
                    if pending:
                        # Sort by priority/timestamp
                        pending.sort(key=lambda cmd: cmd.timestamp, reverse=True)
                        debug_logger.info(f"Found {len(pending)} pending commands for agent {agent_id}")
                        
                        sent_command_ids = []
                        for command in pending:
                            if command.timestamp > last_command_time:
                                cmd_type_name = agent_pb2.CommandType.Name(command.type)
                                logger.info(f"Sending command {command.command_id} (Type: {cmd_type_name}) to agent {agent_id}")
                                
                                # Create command message
                                try:
                                    command_message = agent_pb2.CommandMessage(
                                        command=command
                                    )
                                    yield command_message
                                    last_command_time = max(last_command_time, command.timestamp)
                                    sent_command_ids.append(command.command_id)
                                except Exception as e:
                                    logger.error(f"Error sending command to agent {agent_id}: {e}")
                                    stream_active = False
                                    break
                        
                        # Remove sent commands
                        if sent_command_ids:
                            self.pending_commands[agent_id] = [
                                cmd for cmd in pending if cmd.command_id not in sent_command_ids
                            ]
                
                time.sleep(0.5)  # Slower check interval than legacy stream
                
        except Exception as e:
            logger.warning(f"Bidirectional command stream for agent {agent_id} ended: {e}")
        finally:
            # Update agent status and cleanup
            if agent_id:
                agent['last_seen'] = int(time.time())
                agent['status'] = 'OFFLINE'
                self.storage.save_agent(agent_id, agent)
                
                with self.stream_lock:
                    if agent_id in self.active_streams:
                        del self.active_streams[agent_id]
                        conn_logger.debug(f"Unregistered bidirectional command stream for agent {agent_id}")
    
    def SendCommand(self, request, context):
        """Create and queue a command for an agent."""
        command_id = str(uuid.uuid4())
        agent_id = request.agent_id
        command_type = request.command_type
        params = request.params
        
        logger.info(f"Creating command: Type={agent_pb2.CommandType.Name(command_type)}, Agent={agent_id}")
        
        # Validate agent
        agent = self.storage.get_agent(agent_id)
        if not agent:
            return {
                'success': False,
                'message': f"Agent with ID {agent_id} does not exist",
                'command_id': command_id
            }
        
        # Validate command params based on type
        if command_type == agent_pb2.CommandType.DELETE_FILE and 'path' not in params:
            return {
                'success': False,
                'message': "DELETE_FILE command missing required 'path' parameter",
                'command_id': command_id
            }
        
        # Check if agent is reachable
        current_time = int(time.time())
        agent_online = (current_time - agent.get('last_seen', 0)) < 300  # 5 minutes
        
        if not agent_online:
            return {
                'success': False,
                'message': f"Agent {agent_id} is offline. Cannot send command.",
                'command_id': command_id
            }
        
        # Check for active stream
        with self.stream_lock:
            if agent_id not in self.active_streams:
                return {
                    'success': False,
                    'message': f"Agent {agent_id} is online but has no active command stream.",
                    'command_id': command_id
                }
            
            # Create the command
            command = agent_pb2.Command(
                command_id=command_id,
                agent_id=agent_id,
                timestamp=int(time.time() * 1000),
                type=command_type,
                params=params,
                priority=1,
                timeout=60
            )
            
            # Add command to queue
            if agent_id not in self.pending_commands:
                self.pending_commands[agent_id] = []
            self.pending_commands[agent_id].append(command)
        
        # Wait for result
        start_time = time.time()
        timeout = 10  # seconds
        while (time.time() - start_time) < timeout:
            with self.results_lock:
                if command_id in self.command_results:
                    result = self.command_results[command_id]
                    return {
                        'success': result.get('success', False),
                        'message': result.get('message', ''),
                        'command_id': command_id
                    }
            
            time.sleep(0.1)
        
        return {
            'success': False,
            'message': f"Command execution timed out after {timeout} seconds.",
            'command_id': command_id
        }
    
    def GetIOCs(self, request, context):
        """Handle IOC request from agent."""
        agent_id = request.agent_id
        current_version = request.current_version
        
        logger.info(f"IOC request from agent {agent_id}, current version: {current_version}")
        
        # Check if agent exists
        agent = self.storage.get_agent(agent_id)
        if not agent:
            logger.warning(f"IOC request from unknown agent: {agent_id}")
            context.abort(grpc.StatusCode.NOT_FOUND, "Unknown agent")
            return agent_pb2.IOCResponse()
        
        # Update agent last seen
        agent['last_seen'] = int(time.time())
        self.storage.save_agent(agent_id, agent)
        
        # Get current IOC database version
        ioc_version_info = self.ioc_manager.get_version_info()
        server_version = ioc_version_info['version']
        
        # Check if update is needed
        if current_version >= server_version:
            return agent_pb2.IOCResponse(
                update_available=False,
                version=server_version,
                timestamp=int(time.time())
            )
        
        # Get IOCs to send
        all_iocs = self.ioc_manager.get_all_iocs()
        iocs = all_iocs['iocs']
        
        # Create response
        response = agent_pb2.IOCResponse(
            update_available=True,
            version=server_version,
            timestamp=int(time.time())
        )
        
        # Add IP addresses - using proper protobuf map field assignment
        for ip, info in iocs.get('ip_addresses', {}).items():
            ioc_data = agent_pb2.IOCData(
                value=ip,
                description=info.get('description', ''),
                severity=info.get('severity', 'medium')
            )
            response.ip_addresses[ip].CopyFrom(ioc_data)
        
        # Add file hashes
        for file_hash, info in iocs.get('file_hashes', {}).items():
            metadata = {}
            if 'hash_type' in info:
                metadata['hash_type'] = info['hash_type']
            
            ioc_data = agent_pb2.IOCData(
                value=file_hash,
                description=info.get('description', ''),
                severity=info.get('severity', 'medium'),
                metadata=metadata
            )
            response.file_hashes[file_hash].CopyFrom(ioc_data)
        
        # Add URLs
        for url, info in iocs.get('urls', {}).items():
            ioc_data = agent_pb2.IOCData(
                value=url,
                description=info.get('description', ''),
                severity=info.get('severity', 'medium')
            )
            response.urls[url].CopyFrom(ioc_data)
        
        # Update agent in storage with new IOC version
        agent['ioc_version'] = server_version
        self.storage.save_agent(agent_id, agent)
        
        logger.info(f"Sent IOC update to agent {agent_id}: v{server_version}, {len(response.ip_addresses)} IPs, {len(response.file_hashes)} hashes, {len(response.urls)} URLs")
        
        return response
    
    def ReportIOCMatch(self, request, context):
        """Handle IOC match report from agent."""
        report_id = request.report_id
        agent_id = request.agent_id
        
        # Log match details
        logger.info(f"IOC match from agent {agent_id}: {agent_pb2.IOCType.Name(request.type)} - {request.ioc_value}")
        debug_logger.info(f"Match details: {request.matched_value}, Severity: {request.severity}")
        
        if request.action_taken != agent_pb2.CommandType.UNKNOWN:
            action_name = agent_pb2.CommandType.Name(request.action_taken)
            logger.info(f"Action taken: {action_name} - Success: {request.action_success}")
        
        # Store the match report
        match_data = {
            'report_id': report_id,
            'agent_id': agent_id,
            'timestamp': request.timestamp,
            'type': agent_pb2.IOCType.Name(request.type),
            'ioc_value': request.ioc_value,
            'matched_value': request.matched_value,
            'context': request.context,
            'severity': request.severity,
            'action_taken': agent_pb2.CommandType.Name(request.action_taken) if request.action_taken != agent_pb2.CommandType.UNKNOWN else None,
            'action_success': request.action_success,
            'action_message': request.action_message,
            'server_received': int(time.time())
        }
        
        self.storage.save_ioc_match(report_id, match_data)
        
        # Update agent with latest alert information
        agent = self.storage.get_agent(agent_id)
        if agent:
            agent['last_ioc_match'] = {
                'timestamp': request.timestamp,
                'type': agent_pb2.IOCType.Name(request.type),
                'ioc_value': request.ioc_value,
                'severity': request.severity
            }
            self.storage.save_agent(agent_id, agent)
        
        return agent_pb2.IOCMatchAck(
            report_id=report_id,
            received=True,
            message="IOC match report received"
        )

def start_grpc_server(port=None, use_tls=None):
    """Start the gRPC server in a background thread.
    
    Args:
        port (int, optional): Port number to listen on. Defaults to config.GRPC_PORT.
        use_tls (bool, optional): Whether to use TLS encryption. Defaults to config.GRPC_USE_TLS.
    
    Returns:
        tuple: The running server instance and servicer
    """
    global active_servicer
    
    if port is None:
        port = config.GRPC_PORT
    
    if use_tls is None:
        use_tls = config.GRPC_USE_TLS
        
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = EDRServicer()
    agent_pb2_grpc.add_EDRServiceServicer_to_server(servicer, server)
    
    # Store the active servicer for direct access
    active_servicer = servicer
    
    # Configure TLS if enabled
    if use_tls:
        # Check for certificate files
        server_key_path = config.GRPC_SERVER_KEY
        server_cert_path = config.GRPC_SERVER_CERT
        ca_cert_path = getattr(config, 'GRPC_CA_CERT', None)
        use_mtls = getattr(config, 'GRPC_USE_MTLS', False)
        
        # Make sure the certificates exist
        if not all(os.path.exists(f) for f in [server_key_path, server_cert_path]):
            logger.error("TLS certificates not found. Run scripts/generate_server_cert.sh to generate them.")
            logger.warning("Falling back to insecure connection!")
            server.add_insecure_port(f'[::]:{port}')
            logger.info(f"EDR gRPC server started on port {port} WITHOUT encryption")
        else:
            # Read certificate files
            with open(server_key_path, 'rb') as f:
                server_key = f.read()
            with open(server_cert_path, 'rb') as f:
                server_cert = f.read()
            
            # Create server credentials - handle mTLS option
            if use_mtls and ca_cert_path and os.path.exists(ca_cert_path):
                # Read CA cert for client verification
                with open(ca_cert_path, 'rb') as f:
                    ca_cert = f.read()
                    
                # Create server credentials with client certificate verification
                server_credentials = grpc.ssl_server_credentials(
                    [(server_key, server_cert)],
                    root_certificates=ca_cert,
                    require_client_auth=True
                )
                logger.info(f"EDR gRPC server started with mTLS (mutual authentication) on port {port}")
            else:
                # Create server credentials without client verification
                server_credentials = grpc.ssl_server_credentials(
                    [(server_key, server_cert)]
                )
                logger.info(f"EDR gRPC server started with TLS encryption on port {port}")
            
            # Add secure port
            server.add_secure_port(f'[::]:{port}', server_credentials)
    else:
        # Start server without TLS
        server.add_insecure_port(f'[::]:{port}')
        logger.info(f"EDR gRPC server started on port {port} WITHOUT encryption")
    
    server.start()
    
    # Return both the server and servicer
    return server, servicer 