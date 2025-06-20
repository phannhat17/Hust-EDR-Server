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
        
        # Server-controlled ID assignment with collision protection
        if not agent_id:
            # Case 1: No agent ID provided → Generate new unique one
            max_attempts = 5
            for attempt in range(max_attempts):
                agent_id = str(uuid.uuid4())
                if agent_id not in self.storage.agents:
                    logger.info(f"Generated new unique agent ID: {agent_id}")
                    break
                else:
                    logger.warning(f"UUID collision detected (attempt {attempt + 1}): {agent_id}")
            else:
                # Virtually impossible scenario - all attempts failed
                raise Exception(f"Failed to generate unique agent ID after {max_attempts} attempts")
        elif agent_id in self.storage.agents:
            # Case 2: Agent ID exists → Re-registration, keep existing ID
            logger.info(f"Agent {agent_id} registered from {hostname}")
        
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
        
        # print(f"[DEBUG] UpdateStatus called: agent={agent_id}, status={status}")
        logger.info(f"Status update from agent {agent_id}: {status}")
        
        # Check if agent exists
        agent = self.storage.get_agent(agent_id)
        if agent:
            # Update agent status - ensure it's changed from REGISTERED to ONLINE
            if agent.get('status') == 'REGISTERED' and status == 'ONLINE':
                logger.info(f"Agent {agent_id} status changing from REGISTERED to ONLINE")
            
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
            logger.info(f"Updated agent {agent_id} status to {status}")
        else:
            logger.warning(f"Received status update for unknown agent {agent_id}")
        
        return agent_pb2.StatusResponse(
            server_message="Status update acknowledged",
            acknowledged=True,
            server_time=int(time.time())
        )
    
    def _check_ioc_update_needed(self, agent, agent_id):
        """Check if agent needs IOC update."""
        # Reload IOC data to ensure we have the latest version
        self.ioc_manager.reload_data()
        
        ioc_version_info = self.ioc_manager.get_version_info()
        current_agent_ioc_version = agent.get('ioc_version', 0)
        server_version = ioc_version_info['version']
        
        # Log IOC version check
        ioc_logger.debug(f"Checking if agent {agent_id} needs IOC update: agent version {current_agent_ioc_version}, server version {server_version}")
        
        if current_agent_ioc_version < server_version:
            with self.stream_lock:
                # Avoid duplicating UPDATE_IOCS commands
                if agent_id in self.pending_commands and any(
                    cmd.type == agent_pb2.CommandType.UPDATE_IOCS 
                    for cmd in self.pending_commands[agent_id]
                ):
                    ioc_logger.debug(f"Agent {agent_id} already has a pending IOC update command")
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
                ioc_logger.info(f"Agent {agent_id} needs IOC update: {current_agent_ioc_version} < {server_version}, queued command {command_id}")
        else:
            ioc_logger.debug(f"Agent {agent_id} IOC version is current: {current_agent_ioc_version} >= {server_version}")
    
    def CommandStream(self, request_iterator, context):
        """Bidirectional stream for agent-server communication."""
        agent_id = None
        agent = None
        
        # Create tracking variables for this connection
        last_command_time = int(time.time())
        last_status_update = 0
        check_counter = 0
        
        # Update interval in minutes, converted to seconds
        status_update_interval = 30 * 60  # 30 minutes in seconds
        
        conn_logger.info("New bidirectional command stream opened")
        
        try:
            # First handle the initial HELLO message
            for message in request_iterator:
                if message.message_type == agent_pb2.MessageType.AGENT_HELLO:
                    agent_id = message.agent_id
                    conn_logger.info(f"Bidirectional command stream initialized for agent {agent_id}")
                    
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
                        conn_logger.debug(f"Registered bidirectional command stream for agent {agent_id}")
                    
                    # Don't auto-set ONLINE - wait for explicit status update
                    agent['last_seen'] = int(time.time())
                    self.storage.save_agent(agent_id, agent)
                    logger.info(f"Agent {agent_id} connected - waiting for explicit ONLINE status")
                    
                    # Initial IOC check
                    self._check_ioc_update_needed(agent, agent_id)
                    
                    # Send acknowledgment
                    ack_msg = agent_pb2.CommandMessage(
                        agent_id=agent_id,
                        timestamp=int(time.time()),
                        message_type=agent_pb2.MessageType.AGENT_HELLO  # Reuse HELLO type for ack
                    )
                    hello = agent_pb2.AgentHello(
                        agent_id=agent_id,
                        timestamp=int(time.time())
                    )
                    ack_msg.hello.CopyFrom(hello)
                    yield ack_msg
                    break
                else:
                    # If first message is not HELLO, reject the stream
                    conn_logger.warning("First message in bidirectional stream not HELLO, rejecting")
                    return
            
            # Start the concurrent processing of messages and sending commands
            receive_thread = threading.Thread(target=self._process_agent_messages, args=(request_iterator, agent_id, context))
            receive_thread.daemon = True
            receive_thread.start()
            
            # Main thread will handle sending commands to the agent
            while context.is_active():
                current_time = int(time.time())
                check_counter += 1
                
                # No need for periodic status updates - ping monitor handles timeouts
                
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
                                
                                # Create command message
                                cmd_msg = agent_pb2.CommandMessage(
                                    agent_id=agent_id,
                                    timestamp=int(time.time()),
                                    message_type=agent_pb2.MessageType.SERVER_COMMAND
                                )
                                cmd_msg.command.CopyFrom(command)
                                
                                yield cmd_msg
                                last_command_time = max(last_command_time, command.timestamp)
                                sent_command_ids.append(command.command_id)
                                
                                # If this is an IOC update command, immediately send the IOC data
                                if command.type == agent_pb2.CommandType.UPDATE_IOCS:
                                    # Get current IOC data
                                    ioc_version_info = self.ioc_manager.get_version_info()
                                    server_version = ioc_version_info['version']
                                    
                                    # Debug log to show what version we're actually sending
                                    logger.info(f"IOC version info from manager: {ioc_version_info}")
                                    
                                    all_iocs = self.ioc_manager.get_all_iocs()
                                    iocs = all_iocs['iocs']
                                    
                                    # Debug log for all_iocs version
                                    logger.info(f"IOC version from get_all_iocs(): {all_iocs.get('version')}")
                                    
                                    # Make sure we're using the right version
                                    server_version = max(server_version, all_iocs.get('version', 0))
                                    logger.info(f"Using IOC version: {server_version} for sending to agent {agent_id}")
                                    
                                    # Create IOC response
                                    ioc_response = agent_pb2.IOCResponse(
                                        update_available=True,
                                        version=server_version,
                                        timestamp=int(time.time())
                                    )
                                    
                                    # Add IP addresses
                                    for ip, info in iocs.get('ip_addresses', {}).items():
                                        ioc_data = agent_pb2.IOCData(
                                            value=ip,
                                            description=info.get('description', ''),
                                            severity=info.get('severity', 'medium')
                                        )
                                        ioc_response.ip_addresses[ip].CopyFrom(ioc_data)
                                    
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
                                        ioc_response.file_hashes[file_hash].CopyFrom(ioc_data)
                                    
                                    # Add URLs
                                    for url, info in iocs.get('urls', {}).items():
                                        ioc_data = agent_pb2.IOCData(
                                            value=url,
                                            description=info.get('description', ''),
                                            severity=info.get('severity', 'medium')
                                        )
                                        ioc_response.urls[url].CopyFrom(ioc_data)
                                    
                                    # Send IOC data message
                                    ioc_msg = agent_pb2.CommandMessage(
                                        agent_id=agent_id,
                                        timestamp=int(time.time()),
                                        message_type=agent_pb2.MessageType.IOC_DATA
                                    )
                                    ioc_msg.ioc_data.CopyFrom(ioc_response)
                                    
                                    yield ioc_msg
                                    logger.info(f"Sent IOC data directly through command stream to agent {agent_id}: v{server_version}, {len(ioc_response.ip_addresses)} IPs, {len(ioc_response.file_hashes)} hashes, {len(ioc_response.urls)} URLs")
                                    
                                    # Update agent's IOC version in database
                                    agent['ioc_version'] = server_version
                                    self.storage.save_agent(agent_id, agent)
                                    logger.info(f"Updated agent {agent_id} IOC version to {server_version}")
                        
                        # Remove sent commands
                        if sent_command_ids:
                            self.pending_commands[agent_id] = [
                                cmd for cmd in pending if cmd.command_id not in sent_command_ids
                            ]
                
                time.sleep(0.05)
                
        except Exception as e:
            logger.warning(f"Bidirectional command stream for agent {agent_id} ended: {e}")
        finally:
            if agent_id and agent:
                # Update agent status and cleanup
                agent['last_seen'] = int(time.time())
                agent['status'] = 'OFFLINE'
                self.storage.save_agent(agent_id, agent)
                
                with self.stream_lock:
                    if agent_id in self.active_streams and self.active_streams[agent_id] == context:
                        del self.active_streams[agent_id]
                        conn_logger.debug(f"Unregistered bidirectional command stream for agent {agent_id}")
    
    def _process_agent_messages(self, request_iterator, agent_id, context):
        """Process incoming messages from the agent in a separate thread."""
        try:
            for message in request_iterator:
                # print(f"[DEBUG] Received message type: {message.message_type}")
                if message.message_type == agent_pb2.MessageType.AGENT_STATUS:
                    # Handle explicit status update (ONLINE/OFFLINE)
                    # print(f"[DEBUG] Processing AGENT_STATUS message from {agent_id}")
                    status_req = message.status
                    status = status_req.status
                    
                    # print(f"[DEBUG] Status extracted: {status}")
                    logger.info(f"Explicit status update from agent {agent_id}: {status}")
                    
                    # Check if agent exists
                    agent = self.storage.get_agent(agent_id)
                    if agent:
                        # Update agent status
                        agent.update({
                            'last_seen': status_req.timestamp,
                            'status': status
                        })
                        
                        # Update metrics if provided
                        if status_req.system_metrics:
                            agent.update({
                                'cpu_usage': status_req.system_metrics.cpu_usage,
                                'memory_usage': status_req.system_metrics.memory_usage,
                                'uptime': status_req.system_metrics.uptime
                            })
                        
                        self.storage.save_agent(agent_id, agent)
                        # Force save for status updates to ensure immediate persistence
                        self.storage.force_save()
                        # print(f"[DEBUG] Successfully saved agent {agent_id} with status {status}")
                        logger.info(f"Updated agent {agent_id} status to {status}")
                    else:
                        # print(f"[DEBUG] Unknown agent {agent_id} for status update")
                        logger.warning(f"Received status update for unknown agent {agent_id}")
                
                elif message.message_type == agent_pb2.MessageType.AGENT_RUNNING:
                    # Handle ping signal - only update last_seen and metrics, NOT status
                    running_signal = message.running
                    if running_signal:
                        logger.debug(f"Ping signal from agent {agent_id}")
                        
                        # Update agent last_seen and metrics (but not status)
                        agent = self.storage.get_agent(agent_id)
                        if agent:
                            agent.update({
                                'last_seen': running_signal.timestamp
                                # Do NOT update status here - let ping monitor handle timeouts
                            })
                            
                            # Update metrics if provided
                            if running_signal.system_metrics:
                                agent.update({
                                    'cpu_usage': running_signal.system_metrics.cpu_usage,
                                    'memory_usage': running_signal.system_metrics.memory_usage,
                                    'uptime': running_signal.system_metrics.uptime
                                })
                            
                            self.storage.save_agent(agent_id, agent)
                            debug_logger.debug(f"Updated last_seen for agent {agent_id} from ping")
                        else:
                            logger.warning(f"Received ping signal for unknown agent {agent_id}")
                    else:
                        logger.warning(f"Received AGENT_RUNNING message with no running payload from agent {agent_id}")
                
                elif message.message_type == agent_pb2.MessageType.AGENT_SHUTDOWN:
                    # Handle explicit shutdown signal
                    shutdown_signal = message.shutdown
                    if shutdown_signal:
                        logger.info(f"Shutdown signal from agent {agent_id}: {shutdown_signal.reason}")
                        
                        # Set agent to OFFLINE immediately
                        agent = self.storage.get_agent(agent_id)
                        if agent:
                            agent.update({
                                'last_seen': shutdown_signal.timestamp,
                                'status': 'OFFLINE'
                            })
                            self.storage.save_agent(agent_id, agent)
                            # Force save for shutdown status to ensure immediate persistence
                            self.storage.force_save()
                            logger.info(f"Set agent {agent_id} to OFFLINE due to shutdown signal")
                        else:
                            logger.warning(f"Received shutdown signal for unknown agent {agent_id}")
                    else:
                        logger.warning(f"Received AGENT_SHUTDOWN message with no shutdown payload from agent {agent_id}")
                
                elif message.message_type == agent_pb2.MessageType.COMMAND_RESULT:
                    # Handle command result
                    result = message.result
                    command_id = result.command_id
                    
                    # Log result
                    log_fn = logger.info if result.success else logger.warning
                    log_fn(f"Command result from {agent_id}: {command_id} - Success: {result.success}, Duration: {result.duration_ms}ms")
                    
                    # Don't store IOC update related commands in command_results
                    is_ioc_related = False
                    
                    # Check by command message
                    if "IOC update available" in result.message or "No IOC update available" in result.message:
                        is_ioc_related = True
                        logger.debug(f"Skipping IOC update result storage: {result.message}")
                    
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
                
        except Exception as e:
            logger.error(f"Error processing agent messages: {e}")
    
    def ReportCommandResult(self, request, context):
        """Handle command result from agent (legacy method)."""
        command_id = request.command_id
        agent_id = request.agent_id
        
        # Log result
        log_fn = logger.info if request.success else logger.warning
        log_fn(f"Command result from {agent_id}: {command_id} - Success: {request.success}, Duration: {request.duration_ms}ms (legacy method)")
        
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
            
            # Validate command params based on command type
            if command.type == agent_pb2.CommandType.DELETE_FILE and 'path' not in command.params:
                return agent_pb2.SendCommandResponse(
                    success=False, 
                    message="DELETE_FILE command missing required 'path' parameter"
                )
            
            # Check if agent is online
            agent_status = agent.get('status', 'UNKNOWN')
            is_ioc_update = command.type == agent_pb2.CommandType.UPDATE_IOCS

            # For IOC updates, only check the status field
            if is_ioc_update:
                agent_online = agent_status == 'ONLINE'
            else:
                # For other commands, use the timestamp check
                current_time = int(time.time())
                agent_online = (current_time - agent.get('last_seen', 0)) < 300  # 5 minutes
            
            if not agent_online:
                return agent_pb2.SendCommandResponse(
                    success=False, 
                    message=f"Agent {agent_id} is offline (status: {agent_status}). Cannot send command directly."
                )
            
            # Check for active stream
            with self.stream_lock:
                stream_active = agent_id in self.active_streams and self.active_streams[agent_id] is not None
                if not stream_active:
                    # For IOC updates, queue anyway if the agent is ONLINE in database
                    if is_ioc_update:
                        command.timestamp = int(time.time())
                        if agent_id not in self.pending_commands:
                            self.pending_commands[agent_id] = []
                        self.pending_commands[agent_id].append(command)
                        
                        logger.info(f"Queued IOC update for ONLINE agent {agent_id} without active stream")
                        return agent_pb2.SendCommandResponse(
                            success=True,
                            message=f"IOC update queued for agent {agent_id}"
                        )
                    else:
                        return agent_pb2.SendCommandResponse(
                            success=False, 
                            message=f"Agent {agent_id} is online but has no active command stream."
                        )
                
                # Add command to queue
                command.timestamp = int(time.time())
                if agent_id not in self.pending_commands:
                    self.pending_commands[agent_id] = []
                self.pending_commands[agent_id].append(command)
            
            # For IOC updates, don't wait for a response since they're handled asynchronously
            if is_ioc_update:
                logger.info(f"Queued IOC update command for agent {agent_id} (command ID: {command.command_id})")
                return agent_pb2.SendCommandResponse(
                    success=True,
                    message=f"IOC update command queued for delivery to agent {agent_id}"
                )
            
            # For other commands, also don't wait for response - just queue and return success
            logger.info(f"Queued {cmd_type_name} command for agent {agent_id} (command ID: {command.command_id})")
            return agent_pb2.SendCommandResponse(
                success=True,
                message=f"{cmd_type_name} command queued for delivery to agent {agent_id}"
            )
            
        except Exception as e:
            logger.error(f"Error in SendCommand: {e}")
            return agent_pb2.SendCommandResponse(success=False, message=str(e))
    
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
    if port is None:
        port = config.GRPC_PORT
    
    if use_tls is None:
        use_tls = config.GRPC_USE_TLS
        
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = EDRServicer()
    agent_pb2_grpc.add_EDRServiceServicer_to_server(servicer, server)
    
    # Configure TLS if enabled
    if use_tls:
        # Check for certificate files
        server_key_path = config.GRPC_SERVER_KEY
        server_cert_path = config.GRPC_SERVER_CERT
        
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
            
            # Create server credentials
            server_credentials = grpc.ssl_server_credentials(
                [(server_key, server_cert)]
            )
            
            # Add secure port
            server.add_secure_port(f'[::]:{port}', server_credentials)
            logger.info(f"EDR gRPC server started with TLS encryption on port {port}")
    else:
        # Start server without TLS
        server.add_insecure_port(f'[::]:{port}')
        logger.info(f"EDR gRPC server started on port {port} WITHOUT encryption")
    
    server.start()
    
    # Return both the server and servicer
    return server, servicer 