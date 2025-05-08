"""
gRPC server implementation for EDR agent communication.
"""

import time
import logging
import logging.handlers
import threading
import json
import os
import uuid
from concurrent import futures
from collections import defaultdict

import grpc
from app.grpc import agent_pb2
from app.grpc import agent_pb2_grpc
from app.config.config import config
from app.iocs import IOCManager

# Set up logging
logger = logging.getLogger(__name__)

# Configure reduced logging
def setup_reduced_logging():
    """Configure reduced logging for production deployment."""
    # Set the server logger to INFO level
    logger.setLevel(logging.INFO)
    
    # Lower the log level for agent connection operations to minimize noise
    conn_logger = logging.getLogger('app.grpc.server.connections')
    conn_logger.setLevel(logging.WARNING)
    
    # Create a debug logger for more verbose logs if needed
    debug_logger = logging.getLogger('app.grpc.server.debug')
    debug_logger.setLevel(logging.WARNING)
    
    # For IOC version checks, use a separate logger
    ioc_logger = logging.getLogger('app.grpc.server.ioc')
    ioc_logger.setLevel(logging.WARNING)
    
    # Ensure logs are saved to files, not console
    log_dir = config.LOG_DIR
    os.makedirs(log_dir, exist_ok=True)
    
    # Create file handlers for component-specific logs
    for logger_name, logger_obj in {
        'connections': conn_logger,
        'debug': debug_logger,
        'ioc': ioc_logger
    }.items():
        log_file = os.path.join(log_dir, f"grpc_{logger_name}.log")
        handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10485760, backupCount=5
        )
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        handler.setLevel(logger_obj.level)
        logger_obj.addHandler(handler)
        logger_obj.propagate = False  # Prevent duplicate logs
    
    return {
        'main': logger,
        'conn': conn_logger, 
        'debug': debug_logger,
        'ioc': ioc_logger
    }

# Initialize loggers
loggers = setup_reduced_logging()

class FileStorage:
    """Storage for agent data."""
    
    def __init__(self, storage_dir='data'):
        self.storage_dir = storage_dir
        self.agents_file = os.path.join(storage_dir, 'agents.json')
        self.results_file = os.path.join(storage_dir, 'command_results.json')
        self.ioc_matches_file = os.path.join(storage_dir, 'ioc_matches.json')
        
        # Create storage directory
        os.makedirs(storage_dir, exist_ok=True)
        
        # In-memory data structures
        self.agents = {}
        self.ioc_matches = {}
        
        # For optimized saving
        self.dirty_agents = False
        self.last_save_time = 0
        self.save_interval = 60  # Save at most once per minute
        self.agent_mutex = threading.RLock()
        
        # Load existing data
        self._load_data()
    
    def _load_data(self):
        """Load all data from storage files."""
        self._load_agents()
        self._load_ioc_matches()
        
        # Ensure command results file exists
        if not os.path.exists(self.results_file):
            self._save_json({}, self.results_file)
    
    def _load_agents(self):
        """Load agents from file."""
        self.agents = self._load_json(self.agents_file, "agents")
    
    def _load_ioc_matches(self):
        """Load IOC matches from file."""
        self.ioc_matches = self._load_json(self.ioc_matches_file, "IOC matches")
        if self.ioc_matches is None:
            self.ioc_matches = {}
            self._save_json(self.ioc_matches, self.ioc_matches_file)
    
    def _load_json(self, file_path, data_type="data"):
        """Generic JSON file loader with error handling."""
        if not os.path.exists(file_path):
            logger.info(f"No existing {data_type} found")
            return {}
            
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse {data_type} file, using empty database")
            return {}
        except Exception as e:
            logger.error(f"Error loading {data_type}: {e}")
            return {}
    
    def _save_json(self, data, file_path):
        """Generic JSON file saver with error handling."""
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving to {file_path}: {e}")
            return False
    
    def _save_agents(self, force=False):
        """Save agents to file with batching.
        
        Args:
            force (bool): Force save regardless of time elapsed
        """
        with self.agent_mutex:
            current_time = time.time()
            elapsed = current_time - self.last_save_time
            
            # Only save if dirty and either forced or enough time has passed
            if self.dirty_agents and (force or elapsed >= self.save_interval):
                success = self._save_json(self.agents, self.agents_file)
                if success:
                    self.dirty_agents = False
                    self.last_save_time = current_time
                    loggers['debug'].debug(f"Saved {len(self.agents)} agents to storage (elapsed: {int(elapsed)}s)")
                return success
            return True  # No save needed
    
    def save_ioc_match(self, match_id, match_data):
        """Save IOC match data."""
        self.ioc_matches[match_id] = match_data
        success = self._save_json(self.ioc_matches, self.ioc_matches_file)
        if success:
            loggers['debug'].info(f"Saved IOC match {match_id} to storage")
        return success
    
    def get_agent(self, agent_id):
        """Get an agent by ID."""
        with self.agent_mutex:
            return self.agents.get(agent_id)
    
    def save_agent(self, agent_id, agent_data):
        """Save agent data with optimized writes."""
        with self.agent_mutex:
            self.agents[agent_id] = agent_data
            self.dirty_agents = True
            
            # Perform actual save based on time throttling
            return self._save_agents(force=False)

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
            with open(results_file, 'r') as f:
                self.command_results = json.load(f)
                logger.info(f"Loaded {len(self.command_results)} command results from storage")
        else:
            logger.info("No existing command results found")
    
    def save_command_results(self):
        """Save command results to file."""
        results_file = os.path.join(self.storage.storage_dir, 'command_results.json')
        with open(results_file, 'w') as f:
            json.dump(self.command_results, f, indent=2)
            
        logger.info(f"Saved {len(self.command_results)} command results to storage")
    
    def RegisterAgent(self, request, context):
        """Handle agent registration."""
        # Log basic registration info
        logger.info(f"New Agent Registration - ID: {request.agent_id}, Hostname: {request.hostname}, IP: {request.ip_address}")
        loggers['debug'].info(f"Registration details - OS: {request.os_version}, Agent version: {request.agent_version}")
        
        agent_id = request.agent_id
        hostname = request.hostname
        
        # Check if agent ID is empty, generate a new one
        if not agent_id or agent_id == "":
            agent_id = str(uuid.uuid4())
            logger.info(f"Empty agent ID, generated new unique ID: {agent_id}")
        elif agent_id in self.storage.agents:
            # Agent ID exists, check if it's the same host trying to re-register
            existing_agent = self.storage.agents[agent_id]
            if existing_agent['hostname'] == hostname:
                logger.info(f"Agent with ID {agent_id} and hostname {hostname} already registered, updating existing record")
                # Use the existing agent ID, just update the data
            else:
                # Different hostname with same ID, generate a new ID
                old_id = agent_id
                agent_id = str(uuid.uuid4())
                logger.info(f"Agent ID {old_id} exists but with different hostname. Generated new ID: {agent_id}")
        
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
            'ioc_version': 0  # Initialize IOC version tracking
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
        agent['last_seen'] = timestamp
        agent['status'] = status
        
        # Update metrics if provided
        if request.system_metrics:
            agent['cpu_usage'] = request.system_metrics.cpu_usage
            agent['memory_usage'] = request.system_metrics.memory_usage
            agent['uptime'] = request.system_metrics.uptime
        
        # Save agent (optimized saving will happen based on time interval)
        self.storage.save_agent(agent_id, agent)
        
        return agent_pb2.StatusResponse(
            server_message="Status update acknowledged",
            acknowledged=True,
            server_time=int(time.time())
        )
    
    def ReceiveCommands(self, request, context):
        """Stream commands to agent."""
        agent_id = request.agent_id
        
        # Use connection logger at lower level to reduce spam
        loggers['conn'].info(f"Command stream opened for agent {agent_id}")
        
        # Track the last command time to avoid re-sending
        last_command_time = 0
        
        # For status update throttling
        last_status_update = 0
        status_update_interval = 60  # Update agent status every 60 seconds
        
        # Check if agent exists
        agent = self.storage.get_agent(agent_id)
        if not agent:
            # Instead of aborting, try to auto-register this agent with basic info
            logger.info(f"Auto-registering unknown agent: {agent_id}")
            agent_data = {
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
            self.storage.save_agent(agent_id, agent_data)
            agent = agent_data
            # We just created this agent, set the last update time
            last_status_update = int(time.time())
        else:
            # Update status only if the agent exists (new agents handled above)
            current_time = int(time.time())
            # Only update status once per minute to avoid excessive saves
            if current_time - last_status_update >= status_update_interval:
                agent['last_seen'] = current_time
                agent['status'] = 'ONLINE'
                self.storage.save_agent(agent_id, agent)
                last_status_update = current_time
                loggers['debug'].debug(f"Updated agent {agent_id} status (throttled)")
        
        # Register this stream
        with self.stream_lock:
            self.active_streams[agent_id] = context
            loggers['conn'].debug(f"Registered command stream for agent {agent_id}")
        
        # Counter for IOC check throttling
        ioc_check_count = 0

        # Function to check IOC status (to reduce code duplication)
        def check_and_queue_ioc_update():
            # Check if agent needs IOC update
            ioc_version_info = self.ioc_manager.get_version_info()
            current_agent_ioc_version = agent.get('ioc_version', 0)
            
            if current_agent_ioc_version < ioc_version_info['version']:
                # Only log this once every 10 times to reduce spam
                nonlocal ioc_check_count
                ioc_check_count += 1
                if ioc_check_count % 10 == 1:  # Log on 1, 11, 21, etc.
                    loggers['ioc'].info(f"Agent {agent_id} needs IOC update: {current_agent_ioc_version} < {ioc_version_info['version']}")
                
                # Only queue the command if we haven't already
                with self.stream_lock:
                    if agent_id in self.pending_commands:
                        # Check if we already have an UPDATE_IOCS command
                        has_update_cmd = any(cmd.type == agent_pb2.CommandType.UPDATE_IOCS 
                                            for cmd in self.pending_commands[agent_id])
                        if has_update_cmd:
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
                    
                    # Add command to pending commands
                    if agent_id not in self.pending_commands:
                        self.pending_commands[agent_id] = []
                    self.pending_commands[agent_id].append(command)
        
        # Initial IOC check
        check_and_queue_ioc_update()
        
        # Keep the stream open and check for commands periodically
        try:
            check_counter = 0
            while context.is_active():
                current_time = int(time.time())
                check_counter += 1
                
                # Check if time to update agent status
                if current_time - last_status_update >= status_update_interval:
                    agent['last_seen'] = current_time
                    agent['status'] = 'ONLINE'
                    self.storage.save_agent(agent_id, agent)
                    last_status_update = current_time
                    loggers['debug'].debug(f"Updated agent {agent_id} status (throttled)")
                
                # Check for commands - reduced polling interval to be more responsive
                # IMPORTANT: We always check for new commands, not only on certain iterations
                # Remove the unused variable
                # pending_sent = False
                
                # Throttled IOC check (only once every 30 seconds)
                if check_counter % 60 == 0:
                    check_and_queue_ioc_update()
                
                # Always check for new commands
                with self.stream_lock:
                    # Get pending commands for this agent
                    if agent_id in self.pending_commands and self.pending_commands[agent_id]:
                        pending = self.pending_commands[agent_id]
                        if pending:
                            # Sort commands by timestamp descending to prioritize newer commands
                            pending.sort(key=lambda cmd: cmd.timestamp, reverse=True)
                            
                            loggers['debug'].info(f"Found {len(pending)} pending commands for agent {agent_id}")
                            
                            # Track which commands were sent successfully
                            sent_command_ids = []
                            
                            for command in pending:
                                if command.timestamp > last_command_time:
                                    # Add more detailed logging for command parameters
                                    cmd_type_name = agent_pb2.CommandType.Name(command.type)
                                    logger.info(f"Sending command {command.command_id} (Type: {cmd_type_name}) to agent {agent_id}")
                                    
                                    # Log detailed command parameters at debug level
                                    loggers['debug'].info(f"Command details - ID: {command.command_id}, Type: {cmd_type_name}, Params: {command.params}")
                                    
                                    # For DELETE_FILE commands, specifically check the path
                                    if command.type == agent_pb2.CommandType.DELETE_FILE:
                                        if 'path' in command.params:
                                            loggers['debug'].info(f"DELETE_FILE command path parameter: {command.params['path']}")
                                        else:
                                            logger.warning(f"DELETE_FILE command missing required 'path' parameter")
                                                    
                                    yield command
                                    # Update last command time to avoid re-sending
                                    last_command_time = max(last_command_time, command.timestamp)
                                    # Track which command was sent
                                    sent_command_ids.append(command.command_id)
                            
                            # Only remove commands that were sent, not all commands
                            if sent_command_ids:
                                # Keep commands that weren't sent
                                self.pending_commands[agent_id] = [cmd for cmd in pending if cmd.command_id not in sent_command_ids]
                                loggers['debug'].info(f"Removed {len(sent_command_ids)} sent commands from queue, {len(self.pending_commands[agent_id])} commands remain")
                
                # Sleep to avoid tight loop, but use shorter interval for more responsiveness
                time.sleep(0.05)  # Reduced from 0.1 to 0.05 seconds for faster command delivery
                
        except Exception as e:
            logger.warning(f"Command stream for agent {agent_id} ended: {e}")
        finally:
            # Update agent status one last time
            current_time = int(time.time())
            agent['last_seen'] = current_time
            agent['status'] = 'OFFLINE'
            self.storage.save_agent(agent_id, agent)
            
            # Unregister stream
            with self.stream_lock:
                if agent_id in self.active_streams and self.active_streams[agent_id] == context:
                    del self.active_streams[agent_id]
                    loggers['conn'].debug(f"Unregistered command stream for agent {agent_id}")
    
    def ReportCommandResult(self, request, context):
        """Handle command result from agent."""
        command_id = request.command_id
        agent_id = request.agent_id
        
        # Log at appropriate level based on success
        log_fn = logger.info if request.success else logger.warning
        log_fn(f"Command result from {agent_id}: {command_id} - Success: {request.success}, Duration: {request.duration_ms}ms")
        
        # Log message details at debug level
        loggers['debug'].info(f"Command {command_id} message: {request.message}")
        
        # Store result
        with self.results_lock:
            # Convert CommandResult protobuf to dict for storage
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
        
        # Make sure command is removed from pending commands if it's still there
        with self.stream_lock:
            if agent_id in self.pending_commands:
                # Filter out the command that just completed
                original_count = len(self.pending_commands[agent_id])
                self.pending_commands[agent_id] = [cmd for cmd in self.pending_commands[agent_id] 
                                                if cmd.command_id != command_id]
                new_count = len(self.pending_commands[agent_id])
                
                if original_count != new_count:
                    loggers['debug'].debug(f"Removed completed command {command_id} from pending queue")
        
        # If this was an IOC update command, update the agent's IOC version
        cmd_type = None
        for cmd in self.pending_commands.get(agent_id, []):
            if cmd.command_id == command_id:
                cmd_type = cmd.type
                break
        
        if cmd_type == agent_pb2.CommandType.UPDATE_IOCS and request.success:
            agent = self.storage.get_agent(agent_id)
            if agent:
                agent['ioc_version'] = self.ioc_manager.get_version_info()['version']
                self.storage.save_agent(agent_id, agent)
                logger.info(f"Updated agent {agent_id} IOC version to {agent['ioc_version']}")
        
        # Return acknowledgment
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
            
            # Check if the agent exists
            agent = self.storage.get_agent(agent_id)
            if not agent:
                error_msg = f"Agent with ID {agent_id} does not exist"
                logger.warning(error_msg)
                return agent_pb2.SendCommandResponse(success=False, message=error_msg)
            
            cmd_type_name = agent_pb2.CommandType.Name(command.type)
            logger.info(f"Sending command: ID={command.command_id}, Type={cmd_type_name}, Agent={agent_id}")
            
            # Validate command parameters
            if command.type == agent_pb2.CommandType.DELETE_FILE:
                if 'path' not in command.params:
                    error_msg = "DELETE_FILE command missing required 'path' parameter"
                    logger.warning(error_msg)
                    return agent_pb2.SendCommandResponse(success=False, message=error_msg)
            
            # Check if agent is online
            current_time = int(time.time())
            agent_online = (current_time - agent.get('last_seen', 0)) < 300  # 5 minutes
            
            if not agent_online:
                return agent_pb2.SendCommandResponse(
                    success=False, 
                    message=f"Agent {agent_id} is offline. Cannot send command directly."
                )
            
            # Check if agent has active stream
            stream_active = False
            with self.stream_lock:
                stream_active = agent_id in self.active_streams and self.active_streams[agent_id] is not None
            
            if not stream_active:
                return agent_pb2.SendCommandResponse(
                    success=False, 
                    message=f"Agent {agent_id} is online but has no active command stream. Cannot send command directly."
                )
            
            # If we get here, agent is online with active stream
            logger.info(f"Agent {agent_id} is online and has active stream - sending command directly")
            
            # Add command to pending commands queue
            with self.stream_lock:
                if agent_id not in self.pending_commands:
                    self.pending_commands[agent_id] = []
                    
                # Use millisecond precision timestamp for immediate processing
                command.timestamp = int(time.time() * 1000)
                self.pending_commands[agent_id].append(command)
            
            # Wait for command to be executed with timeout
            start_time = time.time()
            timeout = 10  # seconds
            while (time.time() - start_time) < timeout:
                # Check if command result is available
                with self.results_lock:
                    if command.command_id in self.command_results:
                        result = self.command_results[command.command_id]
                        success = result.get('success', False)
                        message = result.get('message', '')
                        duration = result.get('duration_ms', 0)
                        
                        status = "succeeded" if success else "failed"
                        response_msg = f"Command {status} in {duration}ms: {message}"
                        logger.info(f"Command {command.command_id} completed: {response_msg}")
                        
                        return agent_pb2.SendCommandResponse(
                            success=success,
                            message=response_msg
                        )
                
                # Still waiting for result
                time.sleep(0.1)
            
            # If we get here, command timed out
            logger.warning(f"Command {command.command_id} execution timed out after {timeout}s")
            return agent_pb2.SendCommandResponse(
                success=False,
                message=f"Command execution timed out after {timeout} seconds. The agent may still be processing it."
            )
            
        except Exception as e:
            logger.error(f"Error in SendCommand: {e}")
            return agent_pb2.SendCommandResponse(success=False, message=str(e))
    
    def ListAgents(self, request, context):
        """List all registered agents."""
        try:
            agents = []
            for agent_id, agent_data in self.storage.agents.items():
                agent = agent_pb2.AgentInfo(
                    agent_id=agent_id,
                    hostname=agent_data.get('hostname', ''),
                    ip_address=agent_data.get('ip_address', ''),
                    mac_address=agent_data.get('mac_address', ''),
                    username=agent_data.get('username', ''),
                    os_version=agent_data.get('os_version', ''),
                    agent_version=agent_data.get('agent_version', ''),
                    registration_time=agent_data.get('registration_time', 0)
                )
                agents.append(agent)
            
            return agent_pb2.ListAgentsResponse(agents=agents)
        except Exception as e:
            logger.error(f"Error listing agents: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return agent_pb2.ListAgentsResponse()
    
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
            return agent_pb2.IOCResponse(
                update_available=False,
                version=0,
                timestamp=int(time.time())
            )
        
        # Update agent last seen
        agent['last_seen'] = int(time.time())
        self.storage.save_agent(agent_id, agent)
        
        # Get current IOC database version
        ioc_version_info = self.ioc_manager.get_version_info()
        server_version = ioc_version_info['version']
        
        # Check if update is needed
        if current_version >= server_version:
            logger.info(f"Agent {agent_id} has current IOC version {current_version}, no update needed")
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
        
        # Add IP addresses
        for ip, info in iocs['ip_addresses'].items():
            ioc_data = agent_pb2.IOCData(
                value=ip,
                description=info.get('description', ''),
                severity=info.get('severity', 'medium')
            )
            response.ip_addresses[ip] = ioc_data
        
        # Add file hashes
        for file_hash, info in iocs['file_hashes'].items():
            metadata = {}
            if 'hash_type' in info:
                metadata['hash_type'] = info['hash_type']
            
            ioc_data = agent_pb2.IOCData(
                value=file_hash,
                description=info.get('description', ''),
                severity=info.get('severity', 'medium'),
                metadata=metadata
            )
            response.file_hashes[file_hash] = ioc_data
        
        # Add URLs
        for url, info in iocs['urls'].items():
            ioc_data = agent_pb2.IOCData(
                value=url,
                description=info.get('description', ''),
                severity=info.get('severity', 'medium')
            )
            response.urls[url] = ioc_data
        
        # Process names are no longer included
        
        # Update agent in storage with new IOC version
        agent['ioc_version'] = server_version
        self.storage.save_agent(agent_id, agent)
        
        logger.info(f"Sent IOC update to agent {agent_id}: version {server_version}, {len(response.ip_addresses)} IPs, {len(response.file_hashes)} hashes, {len(response.urls)} URLs")
        
        return response
    
    def ReportIOCMatch(self, request, context):
        """Handle IOC match report from agent."""
        report_id = request.report_id
        agent_id = request.agent_id
        timestamp = request.timestamp
        ioc_type = request.type
        ioc_value = request.ioc_value
        matched_value = request.matched_value
        context_info = request.context
        severity = request.severity
        action_taken = request.action_taken
        action_success = request.action_success
        action_message = request.action_message
        
        logger.info(f"IOC match report from agent {agent_id}: {agent_pb2.IOCType.Name(ioc_type)} - {ioc_value}")
        logger.info(f"Matched value: {matched_value}")
        logger.info(f"Context: {context_info}")
        logger.info(f"Severity: {severity}")
        
        if action_taken != agent_pb2.CommandType.UNKNOWN:
            action_name = agent_pb2.CommandType.Name(action_taken)
            logger.info(f"Action taken: {action_name} - Success: {action_success}")
            logger.info(f"Action message: {action_message}")
        
        # Store the match report
        match_data = {
            'report_id': report_id,
            'agent_id': agent_id,
            'timestamp': timestamp,
            'type': agent_pb2.IOCType.Name(ioc_type),
            'ioc_value': ioc_value,
            'matched_value': matched_value,
            'context': context_info,
            'severity': severity,
            'action_taken': agent_pb2.CommandType.Name(action_taken) if action_taken != agent_pb2.CommandType.UNKNOWN else None,
            'action_success': action_success,
            'action_message': action_message,
            'server_received': int(time.time())
        }
        
        self.storage.save_ioc_match(report_id, match_data)
        
        # Get agent information
        agent = self.storage.get_agent(agent_id)
        if agent:
            # Update agent with latest alert information
            agent['last_ioc_match'] = {
                'timestamp': timestamp,
                'type': agent_pb2.IOCType.Name(ioc_type),
                'ioc_value': ioc_value,
                'severity': severity
            }
            self.storage.save_agent(agent_id, agent)
        
        # Determine if additional action is needed
        perform_additional_action = False
        additional_action = agent_pb2.CommandType.UNKNOWN
        action_params = {}
        
        # For high severity IOCs that didn't have an action, suggest one
        if severity == 'high' and action_taken == agent_pb2.CommandType.UNKNOWN:
            # IP blocking is now handled automatically by the agent
            if ioc_type == agent_pb2.IOCType.IOC_HASH:
                # For file hash matches, we could suggest additional actions if needed
                pass
        
        return agent_pb2.IOCMatchAck(
            report_id=report_id,
            received=True,
            message="IOC match report received",
            perform_additional_action=perform_additional_action,
            additional_action=additional_action,
            action_params=action_params
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
    logger.info(f"Agent information is stored at {servicer.storage.storage_dir}")
    
    # Register graceful shutdown handler
    def shutdown_handler(*args, **kwargs):
        logger.info("Performing graceful shutdown...")
        
        # Force save any pending agent data
        servicer.storage._save_agents(force=True)
        
        # Stop the server
        logger.info("Stopping gRPC server...")
        server.stop(0)
        logger.info("Server shutdown complete")
    
    # Return both the server and servicer
    return server, servicer 