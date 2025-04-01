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

import grpc
from app.grpc import agent_pb2
from app.grpc import agent_pb2_grpc
from app.config.config import config

# Set up logging
logger = logging.getLogger(__name__)

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
                'status': 'active',
                'cpu_usage': 45.2,
                'memory_usage': 62.8,
                'uptime': 259200  # 3 days
            },
            {
                'agent_id': str(uuid.uuid4()),
                'hostname': 'linux-server-01',
                'ip_address': '192.168.1.102',
                'mac_address': '00:1A:2B:3C:4D:5F',
                'username': 'root',
                'os_version': 'Ubuntu 20.04 LTS',
                'agent_version': '1.0.0',
                'registration_time': int(time.time()) - 172800,  # 2 days ago
                'last_seen': int(time.time()) - 7200,  # 2 hours ago
                'status': 'active',
                'cpu_usage': 78.5,
                'memory_usage': 45.3,
                'uptime': 604800  # 1 week
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
                'status': 'offline',
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
        
        # Prepare agent data
        agent_data = {
            'agent_id': request.agent_id,
            'hostname': request.hostname,
            'ip_address': request.ip_address,
            'mac_address': request.mac_address,
            'username': request.username,
            'os_version': request.os_version,
            'agent_version': request.agent_version,
            'registration_time': request.registration_time,
            'last_seen': int(time.time()),
            'status': 'active'
        }
        
        # Save agent data
        self.storage.save_agent(request.agent_id, agent_data)
        
        # Return response
        return agent_pb2.RegisterResponse(
            server_message="Registration successful",
            success=True,
            assigned_id=request.agent_id,
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
    agent_pb2_grpc.add_EDRServiceServicer_to_server(EDRServicer(), server)
    
    # Listen on the specified port
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    
    logger.info(f"EDR gRPC server started on port {port}")
    
    return server 