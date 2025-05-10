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

class EDRServicer(agent_pb2_grpc.EDRServiceServicer):
    """Implementation of EDRService service."""
    
    def __init__(self):
        self.storage = FileStorage()
        
        # Initialize IOC manager
        self.ioc_manager = IOCManager()
        
        # Active command streams by agent ID
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
        """Check if agent needs IOC update."""
        ioc_version_info = self.ioc_manager.get_version_info()
        current_agent_ioc_version = agent.get('ioc_version', 0)
        
        if current_agent_ioc_version < ioc_version_info['version']:
            with self.stream_lock:
                # Avoid duplicating UPDATE_IOCS commands
                if agent_id in self.pending_commands and any(
                    cmd.type == agent_pb2.CommandType.UPDATE_IOCS 
                    for cmd in self.pending_commands[agent_id]
                ):
                    return
                
                # Create a new UPDATE_IOCS command
                command_id = str(uuid.uuid4())
                command = agent_pb2.Command(
                    command_id=command_id,
                    agent_id=agent_id,
                    timestamp=int(time.time()),
                    type=agent_pb2.CommandType.UPDATE_IOCS,
                    params={},
                    priority=1,
                    timeout=120
                )
                
                if agent_id not in self.pending_commands:
                    self.pending_commands[agent_id] = []
                    
                self.pending_commands[agent_id].append(command)
                ioc_logger.info(f"Agent {agent_id} needs IOC update: {current_agent_ioc_version} < {ioc_version_info['version']}")
    
    def ReceiveCommands(self, request, context):
        """Stream commands to agent."""
        agent_id = request.agent_id
        
        with PerformanceLogger("receive_commands", {"agent_id": agent_id}):
            conn_logger.info(f"Command stream opened for agent {agent_id}")
            
            last_command_time = 0
            last_status_update = 0
            status_update_interval = 60  # seconds
            
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
                last_status_update = int(time.time())
                logger.info(f"Auto-registering unknown agent: {agent_id}")
            
            # Register stream
            with self.stream_lock:
                self.active_streams[agent_id] = context
                conn_logger.debug(f"Registered command stream for agent {agent_id}")
            
            # Initial IOC check
            self._check_ioc_update_needed(agent, agent_id)
            
            # Stream commands
            try:
                check_counter = 0
                while context.is_active():
                    current_time = int(time.time())
                    check_counter += 1
                    
                    # Update agent status periodically
                    if current_time - last_status_update >= status_update_interval:
                        agent['last_seen'] = current_time
                        agent['status'] = 'ONLINE'
                        self.storage.save_agent(agent_id, agent)
                        last_status_update = current_time
                        debug_logger.debug(f"Updated agent {agent_id} status")
                    
                    # Periodic IOC check
                    if check_counter % 60 == 0:
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
                                    
                                    # Log command details
                                    if command.type == agent_pb2.CommandType.DELETE_FILE and 'path' not in command.params:
                                        logger.warning(f"DELETE_FILE command missing required 'path' parameter")
                                    
                                    yield command
                                    last_command_time = max(last_command_time, command.timestamp)
                                    sent_command_ids.append(command.command_id)
                            
                            # Remove sent commands
                            if sent_command_ids:
                                self.pending_commands[agent_id] = [
                                    cmd for cmd in pending if cmd.command_id not in sent_command_ids
                                ]
                    
                    time.sleep(0.05)
                    
            except Exception as e:
                logger.warning(f"Command stream for agent {agent_id} ended: {e}")
            finally:
                # Update agent status and cleanup
                agent['last_seen'] = int(time.time())
                agent['status'] = 'OFFLINE'
                self.storage.save_agent(agent_id, agent)
                
                with self.stream_lock:
                    if agent_id in self.active_streams and self.active_streams[agent_id] == context:
                        del self.active_streams[agent_id]
                        conn_logger.debug(f"Unregistered command stream for agent {agent_id}")
    
    def ReportCommandResult(self, request, context):
        """Handle command result from agent."""
        command_id = request.command_id
        agent_id = request.agent_id
        
        # Log result
        log_fn = logger.info if request.success else logger.warning
        log_fn(f"Command result from {agent_id}: {command_id} - Success: {request.success}, Duration: {request.duration_ms}ms")
        
        # Don't store IOC update related commands in command_results
        is_ioc_related = False
        
        # Check by command message
        if "IOC update available" in request.message or "No IOC update available" in request.message:
            is_ioc_related = True
            logger.debug(f"Skipping IOC update result storage: {request.message}")
        
        # Check by command type in pending commands
        if not is_ioc_related:
            for cmds in self.pending_commands.values():
                for cmd in cmds:
                    if cmd.command_id == command_id and cmd.type == agent_pb2.CommandType.UPDATE_IOCS:
                        is_ioc_related = True
                        logger.debug(f"Skipping IOC update command result storage by command type")
                        break
                if is_ioc_related:
                    break
        
        # Update agent's IOC version if this was a successful IOC update
        if is_ioc_related and "IOC update available" in request.message and request.success:
            agent = self.storage.get_agent(agent_id)
            if agent:
                agent['ioc_version'] = self.ioc_manager.get_version_info()['version']
                self.storage.save_agent(agent_id, agent)
                logger.info(f"Updated agent {agent_id} IOC version to {agent['ioc_version']}")
        
        # Store result only if not IOC related
        if not is_ioc_related:
            with self.results_lock:
                result_dict = {
                    'command_id': request.command_id,
                    'agent_id': request.agent_id,
                    'success': request.success,
                    'message': request.message,
                    'execution_time': request.execution_time,
                    'duration_ms': request.duration_ms
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
        
        return agent_pb2.CommandAck(
            command_id=command_id,
            received=True,
            message="Result received"
        )
    
    def SendCommand(self, request, context):
        """Send a command to an agent synchronously and wait for results."""
        try:
            command = request.command
            agent_id = command.agent_id
            cmd_type_name = agent_pb2.CommandType.Name(command.type)
            
            # Validate agent
            agent = self.storage.get_agent(agent_id)
            if not agent:
                return agent_pb2.SendCommandResponse(
                    success=False, 
                    message=f"Agent with ID {agent_id} does not exist"
                )
            
            logger.info(f"Sending command: ID={command.command_id}, Type={cmd_type_name}, Agent={agent_id}")
            
            # Validate command params
            if command.type == agent_pb2.CommandType.DELETE_FILE and 'path' not in command.params:
                return agent_pb2.SendCommandResponse(
                    success=False, 
                    message="DELETE_FILE command missing required 'path' parameter"
                )
            
            # Check if agent is reachable
            current_time = int(time.time())
            agent_online = (current_time - agent.get('last_seen', 0)) < 300  # 5 minutes
            
            if not agent_online:
                return agent_pb2.SendCommandResponse(
                    success=False, 
                    message=f"Agent {agent_id} is offline. Cannot send command directly."
                )
            
            # Check for active stream
            with self.stream_lock:
                stream_active = agent_id in self.active_streams and self.active_streams[agent_id] is not None
                if not stream_active:
                    return agent_pb2.SendCommandResponse(
                        success=False, 
                        message=f"Agent {agent_id} is online but has no active command stream."
                    )
                
                # Add command to queue
                command.timestamp = int(time.time() * 1000)
                if agent_id not in self.pending_commands:
                    self.pending_commands[agent_id] = []
                self.pending_commands[agent_id].append(command)
            
            # Wait for result
            start_time = time.time()
            timeout = 10  # seconds
            while (time.time() - start_time) < timeout:
                with self.results_lock:
                    if command.command_id in self.command_results:
                        result = self.command_results[command.command_id]
                        return agent_pb2.SendCommandResponse(
                            success=result.get('success', False),
                            message=f"Command {'succeeded' if result.get('success', False) else 'failed'} in {result.get('duration_ms', 0)}ms: {result.get('message', '')}"
                        )
                
                time.sleep(0.1)
            
            return agent_pb2.SendCommandResponse(
                success=False,
                message=f"Command execution timed out after {timeout} seconds."
            )
            
        except Exception as e:
            logger.error(f"Error in SendCommand: {e}")
            return agent_pb2.SendCommandResponse(success=False, message=str(e))
    
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

def start_grpc_server(port=None):
    """Start the gRPC server in a background thread.
    
    Args:
        port (int, optional): Port number to listen on. Defaults to config.GRPC_PORT.
    
    Returns:
        tuple: The running server instance and servicer
    """
    if port is None:
        port = config.GRPC_PORT
        
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = EDRServicer()
    agent_pb2_grpc.add_EDRServiceServicer_to_server(servicer, server)
    
    # Listen on the specified port
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    
    logger.info(f"EDR gRPC server started on port {port}")
    
    # Return both the server and servicer
    return server, servicer 