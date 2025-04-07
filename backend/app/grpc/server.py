"""
gRPC server implementation for EDR agent communication.
"""

import time
import logging
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

# Set up logging
logger = logging.getLogger(__name__)

class FileStorage:
    """Storage for agent data."""
    
    def __init__(self, storage_dir='data'):
        self.storage_dir = storage_dir
        self.agents_file = os.path.join(storage_dir, 'agents.json')
        self.results_file = os.path.join(storage_dir, 'command_results.json')
        os.makedirs(storage_dir, exist_ok=True)
        
        # In-memory agent data
        self.agents = {}
        
        # Load existing agents
        self._load_agents()
        
        # Ensure command results file exists
        if not os.path.exists(self.results_file):
            with open(self.results_file, 'w') as f:
                json.dump({}, f)
    
    def _load_agents(self):
        """Load agents from file."""
        if os.path.exists(self.agents_file):
            with open(self.agents_file, 'r') as f:
                self.agents = json.load(f)
                logger.info(f"Loaded {len(self.agents)} agents from storage")
        else:
            logger.info("No existing agents found")
    
    def _save_agents(self):
        """Save agents to file."""
        with open(self.agents_file, 'w') as f:
            json.dump(self.agents, f, indent=2)
            
        logger.info(f"Saved {len(self.agents)} agents to storage")
    
    def get_agent(self, agent_id):
        """Get an agent by ID."""
        return self.agents.get(agent_id)
    
    def save_agent(self, agent_id, agent_data):
        """Save agent data."""
        self.agents[agent_id] = agent_data
        self._save_agents()
        
        logger.info(f"Agent {agent_id} saved to storage")
        return True

class EDRServicer(agent_pb2_grpc.EDRServiceServicer):
    """Implementation of EDRService service."""
    
    def __init__(self):
        self.storage = FileStorage()
        
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
            'status': 'REGISTERED'
        }
        
        self.storage.save_agent(agent_id, agent_data)
        
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
        
        self.storage.save_agent(agent_id, agent)
        
        return agent_pb2.StatusResponse(
            server_message="Status update acknowledged",
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
            logger.info(f"Registered command stream for agent {agent_id}")
        
        # Flag to track if we've sent all pending commands
        pending_sent = False
        
        # Keep the stream open and check for commands periodically
        try:
            while context.is_active():
                # If we haven't sent pending commands or we're checking for new ones
                if not pending_sent or (int(time.time()) % 2 == 0):  # Check every other second
                    with self.stream_lock:
                        # Get pending commands for this agent
                        if agent_id in self.pending_commands and self.pending_commands[agent_id]:
                            pending = self.pending_commands[agent_id]
                            if pending:
                                logger.info(f"Found {len(pending)} pending commands for agent {agent_id}")
                                for command in pending:
                                    if command.timestamp > last_command_time:
                                        # Add more detailed logging for command parameters
                                        cmd_type_name = agent_pb2.CommandType.Name(command.type)
                                        logger.info(f"Sending command {command.command_id} (Type: {cmd_type_name}) to agent {agent_id}")
                                        
                                        # Log detailed command parameters
                                        logger.info(f"Command details - ID: {command.command_id}, Type: {cmd_type_name}, Params: {command.params}")
                                        
                                        # For DELETE_FILE commands, specifically check the path
                                        if command.type == agent_pb2.CommandType.DELETE_FILE:
                                            if 'path' in command.params:
                                                logger.info(f"DELETE_FILE command path parameter: {command.params['path']}")
                                            else:
                                                logger.warning(f"DELETE_FILE command missing required 'path' parameter")
                                                
                                        yield command
                                        # Update last command time to avoid re-sending
                                        last_command_time = max(last_command_time, command.timestamp)
                                # Clear pending commands after sending
                                self.pending_commands[agent_id] = []
                            pending_sent = True
                
                # Sleep to avoid tight loop
                time.sleep(0.5)
                
        except Exception as e:
            logger.warning(f"Command stream for agent {agent_id} ended: {e}")
        finally:
            # Unregister stream
            with self.stream_lock:
                if agent_id in self.active_streams and self.active_streams[agent_id] == context:
                    del self.active_streams[agent_id]
                    logger.info(f"Unregistered command stream for agent {agent_id}")
    
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
        
        # Return acknowledgment
        return agent_pb2.CommandAck(
            command_id=command_id,
            received=True,
            message="Result received"
        )
    
    def SendCommand(self, request, context):
        """Send a command to an agent."""
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
            logger.info(f"Received command request: ID={command.command_id}, Type={cmd_type_name}, Agent={agent_id}")
            
            # Log command parameters
            logger.info(f"Command parameters: {command.params}")
            
            # Validate command parameters
            if command.type == agent_pb2.CommandType.DELETE_FILE:
                if 'path' not in command.params:
                    error_msg = "DELETE_FILE command missing required 'path' parameter"
                    logger.warning(error_msg)
                    return agent_pb2.SendCommandResponse(success=False, message=error_msg)
            
            # Add command to pending commands for the agent
            with self.stream_lock:
                if agent_id not in self.pending_commands:
                    self.pending_commands[agent_id] = []
                
                self.pending_commands[agent_id].append(command)
                
                if agent_id in self.active_streams:
                    logger.info(f"Agent {agent_id} is online, command will be delivered on next poll")
                else:
                    logger.info(f"Agent {agent_id} is not currently connected, command queued for later delivery")
            
            return agent_pb2.SendCommandResponse(success=True, message="Command queued for delivery")
            
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