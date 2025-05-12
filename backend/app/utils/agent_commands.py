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
from app.grpc.client import create_grpc_client

# Set up logger
logger = logging.getLogger(__name__)

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
    
    try:
        # Create gRPC client
        client = create_grpc_client()
        
        # Generate a new command ID
        command_id = str(uuid.uuid4())
        
        # Send command to server
        response = client.SendCommand({
            'agent_id': agent_id,
            'command_type': command_type,
            'params': params
        })
        
        return response['success'], response['message'], response['command_id']
        
    except Exception as e:
        logger.error(f"Error sending command to agent {agent_id}: {e}")
        return False, str(e), None

def block_ip(agent_id, ip_address):
    """Block an IP address on the agent.
    
    Args:
        agent_id (str): Agent ID
        ip_address (str): IP address to block
        
    Returns:
        tuple: (success, message, command_id)
    """
    return send_command_to_agent(
        agent_id, 
        agent_pb2.CommandType.BLOCK_IP,
        {'ip': ip_address}
    )

def block_url(agent_id, url):
    """Block a URL on the agent.
    
    Args:
        agent_id (str): Agent ID
        url (str): URL to block
        
    Returns:
        tuple: (success, message, command_id)
    """
    return send_command_to_agent(
        agent_id, 
        agent_pb2.CommandType.BLOCK_URL,
        {'url': url}
    )

def delete_file(agent_id, file_path):
    """Delete a file on the agent.
    
    Args:
        agent_id (str): Agent ID
        file_path (str): Path to the file to delete
        
    Returns:
        tuple: (success, message, command_id)
    """
    return send_command_to_agent(
        agent_id, 
        agent_pb2.CommandType.DELETE_FILE,
        {'path': file_path}
    )

def kill_process(agent_id, pid=None, process_name=None):
    """Kill a process on the agent.
    
    Args:
        agent_id (str): Agent ID
        pid (str, optional): Process ID to kill
        process_name (str, optional): Name of the process to kill
        
    Returns:
        tuple: (success, message, command_id)
    """
    if pid is None and process_name is None:
        return False, "Either pid or process_name must be provided", None
        
    params = {}
    if pid is not None:
        params['pid'] = str(pid)
    if process_name is not None:
        params['process_name'] = process_name
        
    return send_command_to_agent(
        agent_id, 
        agent_pb2.CommandType.KILL_PROCESS,
        params
    )

def kill_process_tree(agent_id, pid):
    """Kill a process tree on the agent.
    
    Args:
        agent_id (str): Agent ID
        pid (str): Process ID to kill
        
    Returns:
        tuple: (success, message, command_id)
    """
    return send_command_to_agent(
        agent_id, 
        agent_pb2.CommandType.KILL_PROCESS_TREE,
        {'pid': str(pid)}
    )

def network_isolate(agent_id, allowed_ips=None):
    """Isolate the agent from the network.
    
    Args:
        agent_id (str): Agent ID
        allowed_ips (str, optional): Comma-separated list of IPs to allow
        
    Returns:
        tuple: (success, message, command_id)
    """
    params = {}
    if allowed_ips:
        params['allowed_ips'] = allowed_ips
        
    return send_command_to_agent(
        agent_id, 
        agent_pb2.CommandType.NETWORK_ISOLATE,
        params
    )

def network_restore(agent_id):
    """Restore network connectivity for the agent.
    
    Args:
        agent_id (str): Agent ID
        
    Returns:
        tuple: (success, message, command_id)
    """
    return send_command_to_agent(
        agent_id, 
        agent_pb2.CommandType.NETWORK_RESTORE,
        {}
    )

def update_iocs(agent_id):
    """Update IOCs on the agent.
    
    Args:
        agent_id (str): Agent ID
        
    Returns:
        tuple: (success, message, command_id)
    """
    return send_command_to_agent(
        agent_id, 
        agent_pb2.CommandType.UPDATE_IOCS,
        {}
    )

def get_online_agents():
    """Get a list of online agent IDs.
    
    Returns:
        list: List of online agent IDs
    """
    try:
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
            if agent.get('status') == 'ONLINE':
                online_agents.append(agent_id)
        
        return online_agents
        
    except Exception as e:
        logger.error(f"Error getting online agents: {e}")
        return [] 