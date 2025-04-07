"""
gRPC server implementation for EDR agent communication.
"""

import time
import logging
import threading
import json
import os
import uuid
import queue
from concurrent import futures

import grpc
from app.grpc import agent_pb2
from app.grpc import agent_pb2_grpc
from app.config.config import config

# Set up logging
logger = logging.getLogger(__name__)

# Command storage
class CommandStorage:
    """Storage for agent commands and results."""
    
    def __init__(self, storage_dir='data'):
        self.storage_dir = storage_dir
        self.commands_file = os.path.join(storage_dir, 'commands.json')
        self.results_file = os.path.join(storage_dir, 'command_results.json')
        os.makedirs(storage_dir, exist_ok=True)
        
        # In-memory command queues for each agent
        self.command_queues = {}
        
        # In-memory command results
        self.command_results = {}
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
        # Load existing commands and results
        self._load_commands()
        self._load_results()
    
    def _load_commands(self):
        """Load commands from file."""
        if os.path.exists(self.commands_file):
            with open(self.commands_file, 'r') as f:
                commands = json.load(f)
                
                # Initialize command queues for each agent
                for cmd in commands.values():
                    agent_id = cmd.get('agent_id')
                    if agent_id not in self.command_queues:
                        self.command_queues[agent_id] = queue.Queue()
                    
                    # Add command to queue if not completed
                    cmd_id = cmd.get('command_id')
                    if cmd_id and not self._has_result(cmd_id):
                        self.command_queues[agent_id].put(cmd)
                
                logger.info(f"Loaded {len(commands)} commands from storage")
        else:
            logger.info("No existing commands found")
    
    def _load_results(self):
        """Load command results from file."""
        if os.path.exists(self.results_file):
            with open(self.results_file, 'r') as f:
                self.command_results = json.load(f)
                logger.info(f"Loaded {len(self.command_results)} command results from storage")
        else:
            logger.info("No existing command results found")
    
    def _save_commands(self):
        """Save commands to file."""
        # Collect all commands from all queues
        commands = {}
        
        for agent_id, agent_queue in self.command_queues.items():
            # Get commands without removing them
            queue_size = agent_queue.qsize()
            temp_commands = []
            
            # Get commands temporarily
            for _ in range(queue_size):
                try:
                    cmd = agent_queue.get_nowait()
                    temp_commands.append(cmd)
                except queue.Empty:
                    break
            
            # Put commands back
            for cmd in temp_commands:
                commands[cmd['command_id']] = cmd
                agent_queue.put(cmd)
        
        # Save to file
        with open(self.commands_file, 'w') as f:
            json.dump(commands, f, indent=2)
            
        logger.info(f"Saved {len(commands)} commands to storage")
    
    def _save_results(self):
        """Save command results to file."""
        with open(self.results_file, 'w') as f:
            json.dump(self.command_results, f, indent=2)
            
        logger.info(f"Saved {len(self.command_results)} command results to storage")
    
    def _has_result(self, command_id):
        """Check if a command has a result."""
        return command_id in self.command_results
    
    def add_command(self, command):
        """Add a command to an agent's queue."""
        with self.lock:
            # Convert Command protobuf to dict for storage
            cmd_dict = self._command_to_dict(command)
            
            # Get or create agent queue
            agent_id = command.agent_id
            if agent_id not in self.command_queues:
                self.command_queues[agent_id] = queue.Queue()
            
            # Add command to queue
            self.command_queues[agent_id].put(cmd_dict)
            
            # Save commands
            self._save_commands()
            
            logger.info(f"Added command {command.command_id} for agent {agent_id}")
    
    def get_commands(self, agent_id, last_command_time=0):
        """Get all pending commands for an agent."""
        with self.lock:
            # Get or create agent queue
            if agent_id not in self.command_queues:
                self.command_queues[agent_id] = queue.Queue()
                return []
            
            # Get all commands from queue
            commands = []
            queue_size = self.command_queues[agent_id].qsize()
            
            # Get commands temporarily
            for _ in range(queue_size):
                try:
                    cmd = self.command_queues[agent_id].get_nowait()
                    
                    # Only return commands newer than last_command_time
                    if cmd.get('timestamp', 0) > last_command_time:
                        commands.append(cmd)
                    
                    # Put command back in queue (we'll remove it when result received)
                    self.command_queues[agent_id].put(cmd)
                except queue.Empty:
                    break
            
            return commands
    
    def add_result(self, result):
        """Add a command result."""
        with self.lock:
            command_id = result.command_id
            
            # Convert CommandResult protobuf to dict for storage
            result_dict = self._result_to_dict(result)
            
            # Store result
            self.command_results[command_id] = result_dict
            
            # Save results
            self._save_results()
            
            # Remove command from queue if it exists
            self._remove_command(result.agent_id, command_id)
            
            logger.info(f"Added result for command {command_id}")
            return True
    
    def _remove_command(self, agent_id, command_id):
        """Remove a command from an agent's queue."""
        if agent_id not in self.command_queues:
            return
        
        # Get all commands from queue
        commands = []
        queue_size = self.command_queues[agent_id].qsize()
        
        # Get commands temporarily
        for _ in range(queue_size):
            try:
                cmd = self.command_queues[agent_id].get_nowait()
                
                # Keep command if it's not the one we're removing
                if cmd.get('command_id') != command_id:
                    commands.append(cmd)
            except queue.Empty:
                break
        
        # Put commands back
        for cmd in commands:
            self.command_queues[agent_id].put(cmd)
        
        # Save commands
        self._save_commands()
    
    def get_result(self, command_id):
        """Get a command result."""
        with self.lock:
            return self.command_results.get(command_id)
    
    def _command_to_dict(self, command):
        """Convert Command protobuf to dict."""
        return {
            'command_id': command.command_id,
            'agent_id': command.agent_id,
            'timestamp': command.timestamp,
            'type': command.type,
            'params': dict(command.params),
            'priority': command.priority,
            'timeout': command.timeout
        }
    
    def _result_to_dict(self, result):
        """Convert CommandResult protobuf to dict."""
        return {
            'command_id': result.command_id,
            'agent_id': result.agent_id,
            'success': result.success,
            'message': result.message,
            'execution_time': result.execution_time,
            'duration_ms': result.duration_ms
        }
    
    def _dict_to_command(self, cmd_dict):
        """Convert dict to Command protobuf."""
        return agent_pb2.Command(
            command_id=cmd_dict['command_id'],
            agent_id=cmd_dict['agent_id'],
            timestamp=cmd_dict['timestamp'],
            type=cmd_dict['type'],
            params=cmd_dict['params'],
            priority=cmd_dict['priority'],
            timeout=cmd_dict['timeout']
        )

class FileStorage:
    """Simple file-based storage for agent data."""
    
    def __init__(self, storage_dir='data'):
        self.storage_dir = storage_dir
        self.agents_file = os.path.join(storage_dir, 'agents.json')
        os.makedirs(storage_dir, exist_ok=True)
        self._load_agents()
        
        # Create mock data if no agents exist
        if not self.agents:
            self._create_mock_data()
    
    def _load_agents(self):
        """Load agents from file."""
        if os.path.exists(self.agents_file):
            with open(self.agents_file, 'r') as f:
                self.agents = json.load(f)
                logger.info(f"Loaded {len(self.agents)} agents from storage")
        else:
            self.agents = {}
            logger.info("No existing agents found, starting with empty storage")
    
    def _save_agents(self):
        """Save agents to file."""
        with open(self.agents_file, 'w') as f:
            json.dump(self.agents, f, indent=2)
        logger.info(f"Saved {len(self.agents)} agents to storage")
    
    def get_agent(self, agent_id):
        """Get agent by ID."""
        return self.agents.get(agent_id)
    
    def save_agent(self, agent_id, data):
        """Save or update agent data."""
        self.agents[agent_id] = data
        self._save_agents()
        logger.info(f"Saved/Updated agent {agent_id}")
    
    def _create_mock_data(self):
        """Create mock data for demonstration."""
        logger.info("Creating mock agent data for demonstration")
        
        # Create three mock agents
        mock_agents = [
            {
                'agent_id': str(uuid.uuid4()),
                'hostname': 'win-desktop-01',
                'ip_address': '192.168.1.101',
                'mac_address': '00:1A:2B:3C:4D:5E',
                'username': 'admin',
                'os_version': 'Windows 10 Pro',
                'agent_version': '1.0.0',
                'registration_time': int(time.time()) - 86400,  # 1 day ago
                'last_seen': int(time.time()) - 60,  # 1 minute ago
                'status': 'ONLINE',
                'cpu_usage': 45.2,
                'memory_usage': 62.8,
                'uptime': 259200  # 3 days
            },
            {
                'agent_id': str(uuid.uuid4()),
                'hostname': 'win-laptop-01',
                'ip_address': '192.168.1.103',
                'mac_address': '00:1A:2B:3C:4D:60',
                'username': 'user',
                'os_version': 'Windows 11 Home',
                'agent_version': '1.0.0',
                'registration_time': int(time.time()) - 259200,  # 3 days ago
                'last_seen': int(time.time()) - 86400,  # 1 day ago
                'status': 'OFFLINE',
                'cpu_usage': 0,
                'memory_usage': 0,
                'uptime': 0
            }
        ]
        
        # Add agents to storage
        for agent in mock_agents:
            self.agents[agent['agent_id']] = agent
        
        # Save to disk
        self._save_agents()
        logger.info(f"Created {len(mock_agents)} mock agents")

class EDRServicer(agent_pb2_grpc.EDRServiceServicer):
    """Implementation of EDRService service."""
    
    def __init__(self):
        self.storage = FileStorage()
        self.command_storage = CommandStorage()
        
        # Active command streams by agent ID
        self.active_streams = {}
        self.stream_lock = threading.Lock()
    
    def RegisterAgent(self, request, context):
        """Handle agent registration."""
        logger.info("=== New Agent Registration ===")
        logger.info(f"Agent ID: {request.agent_id}")
        logger.info(f"Hostname: {request.hostname}")
        logger.info(f"IP Address: {request.ip_address}")
        logger.info(f"MAC Address: {request.mac_address}")
        logger.info(f"Username: {request.username}")
        logger.info(f"OS Version: {request.os_version}")
        logger.info(f"Agent Version: {request.agent_version}")
        logger.info(f"Registration Time: {request.registration_time}")
        logger.info("=============================")
        
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
        
        # Check for hostname collision with different agent ID
        hostname_exists = False
        for existing_id, agent_data in self.storage.agents.items():
            if agent_data['hostname'] == hostname and existing_id != agent_id:
                hostname_exists = True
                logger.warning(f"Hostname {hostname} already registered with different agent ID {existing_id}")
                break
        
        if hostname_exists:
            logger.info(f"Hostname collision detected, but using provided/generated agent ID: {agent_id}")
        
        # Prepare agent data
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
            'status': 'ONLINE'
        }
        
        # Save agent data
        self.storage.save_agent(agent_id, agent_data)
        
        # Return response
        return agent_pb2.RegisterResponse(
            server_message="Registration successful",
            success=True,
            assigned_id=agent_id,
            server_time=int(time.time())
        )
    
    def UpdateStatus(self, request, context):
        """Handle status update from agent."""
        agent_id = request.agent_id
        
        # Get agent data
        agent = self.storage.get_agent(agent_id)
        
        if not agent:
            logger.warning(f"Status update from unknown agent: {agent_id}")
            return agent_pb2.StatusResponse(
                server_message="Unknown agent",
                acknowledged=False,
                server_time=int(time.time())
            )
        
        logger.info("=== Agent Status Update ===")
        logger.info(f"Agent ID: {agent_id}")
        logger.info(f"Status: {request.status}")
        logger.info(f"CPU Usage: {request.system_metrics.cpu_usage}%")
        logger.info(f"Memory Usage: {request.system_metrics.memory_usage}%")
        logger.info(f"Uptime: {request.system_metrics.uptime} seconds")
        logger.info("==========================")
        
        # Update agent data
        agent['last_seen'] = int(time.time())
        agent['status'] = request.status
        agent['cpu_usage'] = request.system_metrics.cpu_usage
        agent['memory_usage'] = request.system_metrics.memory_usage
        agent['uptime'] = request.system_metrics.uptime
        
        # Save updated data
        self.storage.save_agent(agent_id, agent)
        
        # Return response
        return agent_pb2.StatusResponse(
            server_message="Status update received",
            acknowledged=True,
            server_time=int(time.time())
        )
    
    def ReceiveCommands(self, request, context):
        """Stream commands to agent."""
        agent_id = request.agent_id
        last_command_time = request.last_command_time
        
        logger.info(f"Agent {agent_id} established command stream (last command time: {last_command_time})")
        
        # Check if agent exists
        agent = self.storage.get_agent(agent_id)
        if not agent:
            logger.warning(f"Command stream request from unknown agent: {agent_id}")
            context.abort(grpc.StatusCode.NOT_FOUND, "Unknown agent")
            return
        
        # Update agent status
        agent['last_seen'] = int(time.time())
        agent['status'] = 'ONLINE'
        self.storage.save_agent(agent_id, agent)
        
        # Register this stream
        with self.stream_lock:
            self.active_streams[agent_id] = context
        
        # Send any pending commands immediately
        pending_commands = self.command_storage.get_commands(agent_id, last_command_time)
        for cmd_dict in pending_commands:
            # Convert dict to Command protobuf
            command = self._dict_to_command(cmd_dict)
            logger.info(f"Sending pending command {command.command_id} to agent {agent_id}")
            yield command
        
        # Keep the stream open for new commands
        try:
            while context.is_active():
                time.sleep(1)  # Avoid tight loop
        except Exception as e:
            logger.warning(f"Command stream for agent {agent_id} ended: {e}")
        finally:
            # Unregister stream
            with self.stream_lock:
                if agent_id in self.active_streams and self.active_streams[agent_id] == context:
                    del self.active_streams[agent_id]
            
            logger.info(f"Command stream for agent {agent_id} closed")
    
    def ReportCommandResult(self, request, context):
        """Handle command result from agent."""
        command_id = request.command_id
        agent_id = request.agent_id
        
        logger.info(f"Received command result for {command_id} from agent {agent_id}")
        logger.info(f"Success: {request.success}")
        logger.info(f"Message: {request.message}")
        logger.info(f"Execution time: {request.execution_time}")
        logger.info(f"Duration: {request.duration_ms}ms")
        
        # Store result
        self.command_storage.add_result(request)
        
        # Return acknowledgment
        return agent_pb2.CommandAck(
            command_id=command_id,
            received=True,
            message="Result received"
        )
    
    def _dict_to_command(self, cmd_dict):
        """Convert dict to Command protobuf."""
        return agent_pb2.Command(
            command_id=cmd_dict['command_id'],
            agent_id=cmd_dict['agent_id'],
            timestamp=cmd_dict['timestamp'],
            type=cmd_dict['type'],
            params=cmd_dict['params'],
            priority=cmd_dict['priority'],
            timeout=cmd_dict['timeout']
        )
    
    def add_command(self, command):
        """Add a command to be sent to an agent."""
        agent_id = command.agent_id
        
        # Store command
        self.command_storage.add_command(command)
        
        # If agent has an active stream, send command immediately
        with self.stream_lock:
            if agent_id in self.active_streams:
                try:
                    context = self.active_streams[agent_id]
                    if context.is_active():
                        logger.info(f"Sending command {command.command_id} to agent {agent_id} immediately")
                        context.send(command)
                except Exception as e:
                    logger.error(f"Error sending command to agent {agent_id}: {e}")
    
    def ListAgents(self, request, context):
        """List all registered agents."""
        try:
            agents = []
            for agent_id, agent_data in self.storage.agents.items():
                agent = agent_pb2.AgentInfo(
                    agent_id=agent_id,
                    hostname=agent_data.get('hostname', ''),
                    ip_address=agent_data.get('ip_address', ''),
                    status=agent_data.get('status', ''),
                    last_seen=agent_data.get('last_seen', 0)
                )
                agents.append(agent)
            
            return agent_pb2.ListAgentsResponse(agents=agents)
        except Exception as e:
            logger.error(f"Error listing agents: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return agent_pb2.ListAgentsResponse()
    
    def SendCommand(self, request, context):
        """Send a command to an agent."""
        try:
            command = request.command
            self.command_storage.add_command(command)
            return agent_pb2.SendCommandResponse(success=True, message="Command sent successfully")
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return agent_pb2.SendCommandResponse(success=False, message=str(e))

def start_grpc_server(port=None):
    """Start the gRPC server in a background thread.
    
    Args:
        port (int, optional): Port number to listen on. Defaults to config.GRPC_PORT.
    
    Returns:
        grpc.Server: The running server instance
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
    logger.info(f"Agent information is stored at {servicer.storage.agents_file}")
    
    return server 