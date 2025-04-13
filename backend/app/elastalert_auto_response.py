"""
ElastAlert auto-response handler for sending automatic commands to agents based on alerts.
Simplified implementation with fixed fields and single-attempt command execution.
"""

import os
import json
import logging
import time
import uuid
from app.config.config import config

# Import agent proto
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.grpc import agent_pb2

# Set up logger
logger = logging.getLogger('app.elastalert_auto_response')

class AutoResponseHandler:
    def __init__(self, grpc_server=None):
        """Initialize the auto-response handler.
        
        Args:
            grpc_server: The gRPC server instance to use for sending commands
        """
        self.grpc_server = grpc_server
        logger.info("AutoResponseHandler initialized")

    def execute_action(self, alert_data):
        """Execute a single auto-response action based on alert data.
        
        Args:
            alert_data: Dictionary containing the alert data with fixed fields for auto-response
            
        Returns:
            dict: Result of the auto-response action
        """
        if not self.grpc_server:
            logger.error("Cannot execute auto-response action: gRPC server not available")
            return {
                "success": False,
                "message": "gRPC server not available for sending commands"
            }
        
        # Extract fixed auto-response fields
        auto_response_type = alert_data.get('auto_response_type')
        if not auto_response_type:
            return {
                "success": False,
                "message": "No auto_response_type field specified in alert"
            }
        
        # Extract target agent ID
        agent_id = alert_data.get('auto_response_agent_id')
        if not agent_id:
            # Try to get from hostname if agent_id is not specified
            hostname = alert_data.get('host', {}).get('hostname') or alert_data.get('host.hostname')
            if hostname and self.grpc_server and self.grpc_server.storage:
                agents = self._find_agents_by_hostname(hostname)
                if agents:
                    agent_id = agents[0]['agent_id']
        
        if not agent_id:
            return {
                "success": False,
                "message": "No agent_id or hostname found in alert data"
            }
        
        # Map action type to CommandType enum
        action_type = auto_response_type.upper()
        command_type_map = {
            'DELETE_FILE': agent_pb2.CommandType.DELETE_FILE,
            'KILL_PROCESS': agent_pb2.CommandType.KILL_PROCESS,
            'KILL_PROCESS_TREE': agent_pb2.CommandType.KILL_PROCESS_TREE,
            'BLOCK_IP': agent_pb2.CommandType.BLOCK_IP,
            'BLOCK_URL': agent_pb2.CommandType.BLOCK_URL,
            'NETWORK_ISOLATE': agent_pb2.CommandType.NETWORK_ISOLATE,
            'NETWORK_RESTORE': agent_pb2.CommandType.NETWORK_RESTORE
        }
        
        if action_type not in command_type_map:
            return {
                "success": False,
                "message": f"Unsupported action type: {action_type}"
            }
        
        command_type = command_type_map[action_type]
        
        # Extract required parameters based on action type
        params = {}
        if action_type == 'DELETE_FILE':
            path = alert_data.get('auto_response_file_path')
            if not path:
                return {"success": False, "message": "No file path provided for DELETE_FILE action"}
            params['path'] = path
            
        elif action_type == 'KILL_PROCESS' or action_type == 'KILL_PROCESS_TREE':
            pid = alert_data.get('auto_response_pid')
            if not pid:
                return {"success": False, "message": f"No PID provided for {action_type} action"}
            params['pid'] = str(pid)
            
        elif action_type == 'BLOCK_IP':
            ip = alert_data.get('auto_response_ip')
            if not ip:
                return {"success": False, "message": "No IP provided for BLOCK_IP action"}
            params['ip'] = ip
            
        elif action_type == 'BLOCK_URL':
            url = alert_data.get('auto_response_url')
            if not url:
                return {"success": False, "message": "No URL provided for BLOCK_URL action"}
            params['url'] = url
            
        elif action_type == 'NETWORK_ISOLATE':
            allowed_ips = alert_data.get('auto_response_allowed_ips', '')
            params['allowed_ips'] = allowed_ips
        
        # Get standard command settings
        priority = int(alert_data.get('auto_response_priority', 1))
        timeout = int(alert_data.get('auto_response_timeout', 60))
        
        # Log the action we're about to take
        logger.info(f"Executing {action_type} command to agent {agent_id} with params: {params}")
        
        try:
            # Create and send the command
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
            
            response = self.grpc_server.SendCommand(
                agent_pb2.SendCommandRequest(command=command),
                None  # Context is None for internal calls
            )
            
            result = {
                "success": response.success,
                "message": response.message,
                "command_id": command_id,
                "agent_id": agent_id,
                "action": action_type,
                "params": params
            }
            
            if response.success:
                logger.info(f"Auto-response command succeeded: {action_type} on agent {agent_id}")
            else:
                logger.error(f"Auto-response command failed: {action_type} on agent {agent_id}, message: {response.message}")
            
            return result
            
        except Exception as e:
            error_msg = f"Error executing auto-response command: {str(e)}"
            logger.exception(error_msg)
            return {
                "success": False,
                "message": error_msg,
                "action": action_type,
                "agent_id": agent_id
            }
    
    def _find_agents_by_hostname(self, hostname):
        """Find agents by hostname with flexible matching.
        
        Args:
            hostname (str): Hostname to search for
            
        Returns:
            list: List of matching agents
        """
        if not self.grpc_server or not self.grpc_server.storage:
            return []
            
        # Direct lookup in agent storage
        agents = []
        
        # Try different ways to find by hostname
        for agent_id, agent in self.grpc_server.storage.agents.items():
            agent_hostname = agent.get('hostname', '').lower()
            if agent_hostname == hostname.lower():
                agents.append(agent)
                continue
                
            # Try partial matching
            if hostname.lower() in agent_hostname or agent_hostname in hostname.lower():
                agents.append(agent)
                
        if agents:
            logger.info(f"Found {len(agents)} agents matching hostname '{hostname}'")
        else:
            logger.warning(f"No agents found matching hostname '{hostname}'")
            
        return agents 