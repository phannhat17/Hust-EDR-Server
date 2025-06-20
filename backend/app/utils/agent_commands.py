"""
Utility functions for sending commands to agents.
"""

import os
import logging
import time
import uuid
import grpc
from app.config.config import config
from app.grpc import agent_pb2, agent_pb2_grpc
import json
import threading

# Set up logger
logger = logging.getLogger(__name__)

# Add a lock for synchronizing agent data access
agent_data_lock = threading.Lock()

def create_grpc_client():
    """Create a gRPC client for command services."""
    # Path to the server certificate
    cert_path = config.GRPC_SERVER_CERT
    
    if os.path.exists(cert_path):
        with open(cert_path, 'rb') as f:
            server_cert = f.read()
        
        # Create SSL credentials with the server certificate
        creds = grpc.ssl_channel_credentials(root_certificates=server_cert)
        channel = grpc.secure_channel('localhost:50051', creds)
        logger.info("Created secure gRPC channel with server certificate")
    else:
        # Fall back to insecure channel if certificate not found
        logger.warning(f"Server certificate not found at {cert_path}, using insecure channel")
        channel = grpc.insecure_channel('localhost:50051')
    
    return agent_pb2_grpc.EDRServiceStub(channel)

def send_command_to_agent(agent_id, command_type, params=None, priority=1, timeout=60):
    """Send a command to an agent.
    
    Args:
        agent_id (str): Agent ID
        command_type (int): Command type enum value
        params (dict, optional): Command parameters. Defaults to None.
        priority (int, optional): Command priority. Defaults to 1.
        timeout (int, optional): Command timeout in seconds. Defaults to 60.
        
    Returns:
        tuple: (success, message, command_id)
    """
    if params is None:
        params = {}
    
    # Check if agent exists before sending command
    online_agents = get_online_agents()
    if agent_id not in online_agents:
        return False, f"Agent with ID {agent_id} does not exist or is not online", None
    
    try:
        # Create gRPC client
        client = create_grpc_client()
        
        # Create command
        command_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        command = agent_pb2.Command(
            command_id=command_id,
            agent_id=agent_id,
            timestamp=timestamp,
            type=command_type,
            params=params,
            priority=priority,
            timeout=timeout
        )
        
        # Send command to server
        request_obj = agent_pb2.SendCommandRequest(command=command)
        response = client.SendCommand(request_obj)
        
        return response.success, response.message, command_id
        
    except Exception as e:
        logger.error(f"Error sending command to agent {agent_id}: {e}")
        return False, str(e), None

def get_online_agents():
    """Get a list of online agent IDs.
    
    Returns:
        list: List of online agent IDs
    """
    try:
        # Use lock to prevent race conditions when reading agent data
        with agent_data_lock:
            # Get list of agents
            agents_file = os.path.join(config.DATA_DIR, 'agents.json')
            if not os.path.exists(agents_file):
                logger.warning("No agents file found")
                return []
            
            with open(agents_file, 'r') as f:
                agents_data = json.load(f)
            
            # Filter for online agents
            online_agents = []
            for agent_id, agent in agents_data.items():
                status = agent.get('status', 'UNKNOWN')
                if status == 'ONLINE':
                    online_agents.append(agent_id)
                    logger.debug(f"Agent {agent_id} status: {status} - considered ONLINE")
                else:
                    logger.debug(f"Agent {agent_id} status: {status} - NOT considered online")
            
            logger.info(f"Found {len(online_agents)} online agents for sending IOC updates")
            return online_agents
        
    except Exception as e:
        logger.error(f"Error getting online agents: {e}")
        return [] 