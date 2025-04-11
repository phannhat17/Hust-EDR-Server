"""
ElastAlert auto-response handler for sending automatic commands to agents based on alerts.
"""

import os
import json
import logging
import time
import uuid
import re
from app.config.config import config

# Import agent proto
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.grpc import agent_pb2

# Set up logger
logger = logging.getLogger(__name__)

class AutoResponseHandler:
    def __init__(self, grpc_server=None):
        """Initialize the auto-response handler.
        
        Args:
            grpc_server: The gRPC server instance to use for sending commands
        """
        self.grpc_server = grpc_server
        logger.info("AutoResponseHandler initialized")

    def process_alert(self, alert, rule):
        """Process an alert and execute auto-response actions if configured.
        
        Args:
            alert (dict): The alert data from ElastAlert
            rule (dict): The rule that triggered the alert
            
        Returns:
            dict: Information about actions taken
        """
        if not rule or 'auto_response' not in rule:
            logger.debug(f"No auto_response configured for rule: {rule.get('name', 'unknown')}")
            return {"success": False, "message": "No auto-response configured for this rule"}
        
        auto_response = rule['auto_response']
        
        # Check if auto-response is enabled
        if not auto_response.get('enabled', False):
            logger.debug(f"Auto-response disabled for rule: {rule.get('name', 'unknown')}")
            return {"success": False, "message": "Auto-response is disabled for this rule"}
            
        # Extract target hosts information
        target_info = self._extract_target_hosts(alert, auto_response)
        if not target_info["targets"]:
            logger.warning(f"No valid target hosts found for alert from rule: {rule.get('name', 'unknown')}")
            return {"success": False, "message": "No valid target hosts found"}
            
        # Execute actions
        actions = auto_response.get('actions', [])
        if not actions:
            logger.warning(f"No actions defined in auto_response for rule: {rule.get('name', 'unknown')}")
            return {"success": False, "message": "No actions defined in auto-response configuration"}
        
        results = []
        for action in actions:
            result = self._execute_action(action, target_info["targets"], alert)
            results.append(result)
        
        # Update alert with auto-response information
        response_info = {
            "auto_response_executed": True,
            "timestamp": int(time.time()),
            "targets": target_info["targets"],
            "actions": results
        }
        
        logger.info(f"Auto-response completed for rule '{rule.get('name', 'unknown')}': {json.dumps(response_info)}")
        return {"success": True, "response_info": response_info}
    
    def _extract_target_hosts(self, alert, auto_response):
        """Extract target hosts from the alert based on configuration.
        
        Args:
            alert (dict): The alert data
            auto_response (dict): The auto-response configuration
            
        Returns:
            dict: Information about target extraction
        """
        targets = []
        source = {}
        
        # Get the target specification
        target_spec = auto_response.get('targets', {})
        
        # Check for field selection method
        if 'field' in target_spec:
            field_name = target_spec['field']
            if field_name in alert.get('raw_data', {}):
                source_value = alert['raw_data'][field_name]
                source = {"field": field_name, "value": source_value}
                
                # If the field contains an agent ID directly
                if target_spec.get('field_type', 'agent_id') == 'agent_id':
                    if isinstance(source_value, list):
                        targets.extend(source_value)
                    else:
                        targets.append(source_value)
                        
                # If the field contains an IP address
                elif target_spec.get('field_type') == 'ip_address':
                    # Find agents with matching IP
                    if self.grpc_server and self.grpc_server.storage:
                        if isinstance(source_value, list):
                            for ip in source_value:
                                agents = self.grpc_server.storage.find_agents_by_ip(ip)
                                targets.extend([agent['agent_id'] for agent in agents])
                        else:
                            agents = self.grpc_server.storage.find_agents_by_ip(source_value)
                            targets.extend([agent['agent_id'] for agent in agents])
                
                # If the field contains a hostname
                elif target_spec.get('field_type') == 'hostname':
                    # Find agents with matching hostname
                    if self.grpc_server and self.grpc_server.storage:
                        if isinstance(source_value, list):
                            for hostname in source_value:
                                agents = self.grpc_server.storage.find_agents_by_hostname(hostname)
                                targets.extend([agent['agent_id'] for agent in agents])
                        else:
                            agents = self.grpc_server.storage.find_agents_by_hostname(source_value)
                            targets.extend([agent['agent_id'] for agent in agents])
        
        # Check for regex extraction method
        elif 'regex' in target_spec and 'from_field' in target_spec:
            field_name = target_spec['from_field']
            regex = target_spec['regex']
            
            if field_name in alert.get('raw_data', {}):
                field_value = alert['raw_data'][field_name]
                source = {"field": field_name, "value": field_value}
                
                if isinstance(field_value, str):
                    try:
                        matches = re.findall(regex, field_value)
                        if matches:
                            if target_spec.get('field_type', 'agent_id') == 'agent_id':
                                targets.extend(matches)
                            elif target_spec.get('field_type') == 'ip_address' and self.grpc_server and self.grpc_server.storage:
                                for ip in matches:
                                    agents = self.grpc_server.storage.find_agents_by_ip(ip)
                                    targets.extend([agent['agent_id'] for agent in agents])
                            elif target_spec.get('field_type') == 'hostname' and self.grpc_server and self.grpc_server.storage:
                                for hostname in matches:
                                    agents = self.grpc_server.storage.find_agents_by_hostname(hostname)
                                    targets.extend([agent['agent_id'] for agent in agents])
                    except re.error as e:
                        logger.error(f"Invalid regex in auto-response configuration: {e}")
        
        # Check for explicit list of targets
        elif 'agent_ids' in target_spec:
            targets = target_spec['agent_ids']
            source = {"explicit_agent_ids": True}
            
        # Apply filters to target list if any
        if 'filter' in target_spec and targets:
            filter_config = target_spec['filter']
            filtered_targets = []
            
            # Filter by agent status (online/offline)
            if 'status' in filter_config and self.grpc_server and self.grpc_server.storage:
                status = filter_config['status']
                for agent_id in targets:
                    agent = self.grpc_server.storage.get_agent(agent_id)
                    if agent:
                        is_online = (time.time() - agent.get('last_seen', 0)) < config.AGENT_TIMEOUT
                        if (status == 'online' and is_online) or (status == 'offline' and not is_online):
                            filtered_targets.append(agent_id)
            else:
                filtered_targets = targets
                
            targets = filtered_targets
            
        # Remove duplicates
        targets = list(set(targets))
        
        return {
            "targets": targets,
            "source": source
        }
        
    def _execute_action(self, action, targets, alert):
        """Execute a single action on all target hosts.
        
        Args:
            action (dict): Action configuration
            targets (list): List of agent IDs to target
            alert (dict): The original alert data
            
        Returns:
            dict: Result of the action execution
        """
        if not self.grpc_server:
            logger.error("Cannot execute auto-response action: gRPC server not available")
            return {
                "success": False,
                "action": action.get('type', 'unknown'),
                "message": "gRPC server not available for sending commands"
            }
            
        action_type = action.get('type', '').upper()
        if not action_type:
            return {
                "success": False,
                "action": "unknown",
                "message": "No action type specified"
            }
            
        # Map action type to CommandType enum
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
                "action": action_type,
                "message": f"Unsupported action type: {action_type}"
            }
            
        command_type = command_type_map[action_type]
        
        # Extract parameters
        params = {}
        for param_name, param_value in action.get('params', {}).items():
            # Check if this is a field reference (dynamic lookup from alert data)
            if isinstance(param_value, str) and param_value.startswith('$'):
                field_name = param_value[1:]  # Remove the $ prefix
                if field_name in alert.get('raw_data', {}):
                    params[param_name] = str(alert['raw_data'][field_name])
                else:
                    logger.warning(f"Field '{field_name}' not found in alert data")
                    params[param_name] = ""
            else:
                params[param_name] = str(param_value)
                
        # Get action settings
        priority = action.get('priority', 1)
        timeout = action.get('timeout', 60)
        
        # Send command to each target
        results = []
        for agent_id in targets:
            try:
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
                
                results.append({
                    "success": response.success,
                    "agent_id": agent_id,
                    "command_id": command_id,
                    "message": response.message,
                    "params": params
                })
                
                logger.info(f"Auto-response sent command to agent {agent_id}: {action_type}")
                
            except Exception as e:
                logger.error(f"Error sending auto-response command to agent {agent_id}: {e}")
                results.append({
                    "success": False,
                    "agent_id": agent_id,
                    "error": str(e)
                })
                
        return {
            "action": action_type,
            "targets": len(results),
            "results": results
        } 