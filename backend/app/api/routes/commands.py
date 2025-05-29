import logging
import os
import json
import time
import uuid
import grpc
from flask import Blueprint, jsonify, request, current_app
from app.grpc import agent_pb2, agent_pb2_grpc
from app.config.config import config
from app.utils.agent_commands import create_grpc_client, send_command_to_agent, get_online_agents

# Set up logger
logger = logging.getLogger(__name__)

# Create commands routes blueprint
commands_bp = Blueprint('commands', __name__, url_prefix='/api/commands')

@commands_bp.route('', methods=['GET'])
def get_commands():
    """Get all command history."""
    try:
        # Path to the command_results.json file
        data_dir = os.path.join(current_app.root_path, '..', 'data')
        results_file = os.path.join(data_dir, 'command_results.json')
        
        logger.info(f"Loading command results from {results_file}")
        
        if not os.path.exists(results_file):
            logger.warning(f"Command results file not found at {results_file}")
            return jsonify([])
        
        with open(results_file, 'r') as f:
            results_data = json.load(f)
        
        # Convert dictionary to list and format for frontend
        results_list = []
        for cmd_id, result in results_data.items():
            cmd_data = {
                'id': cmd_id,
                'agent_id': result.get('agent_id', 'Unknown'),
                'type': convert_command_type_to_string(result.get('type', 0)),
                'success': result.get('success', False),
                'message': result.get('message', ''),
                'execution_time': result.get('execution_time', 0) * 1000,  # Convert to milliseconds for JS
                'duration_ms': result.get('duration_ms', 0)
            }
            results_list.append(cmd_data)
        
        logger.info(f"Found {len(results_list)} command results")
        return jsonify(results_list)
        
    except Exception as e:
        logger.error(f"Error in get_commands endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@commands_bp.route('/<command_id>', methods=['GET'])
def get_command(command_id):
    """Get command result by ID."""
    try:
        # Path to the command_results.json file
        data_dir = os.path.join(current_app.root_path, '..', 'data')
        results_file = os.path.join(data_dir, 'command_results.json')
        
        if not os.path.exists(results_file):
            logger.warning(f"Command results file not found at {results_file}")
            return jsonify({"error": "Command not found"}), 404
        
        with open(results_file, 'r') as f:
            results_data = json.load(f)
        
        result = results_data.get(command_id)
        
        if not result:
            logger.warning(f"Command {command_id} not found")
            return jsonify({"error": "Command not found"}), 404
        
        # Format command data for frontend
        cmd_data = {
            'id': command_id,
            'agent_id': result.get('agent_id', 'Unknown'),
            'type': convert_command_type_to_string(result.get('type', 0)),
            'success': result.get('success', False),
            'message': result.get('message', ''),
            'execution_time': result.get('execution_time', 0) * 1000,  # Convert to milliseconds for JS
            'duration_ms': result.get('duration_ms', 0)
        }
        
        return jsonify(cmd_data)
        
    except Exception as e:
        logger.error(f"Error in get_command endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@commands_bp.route('/send', methods=['POST'])
def send_command():
    """Send a command to an agent."""
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Invalid request data"}), 400
        
        # Required fields
        agent_id = data.get('agent_id')
        command_type = convert_command_type_from_string(data.get('type'))
        params = data.get('params', {})
        
        if not agent_id:
            return jsonify({"error": "Missing required field: agent_id"}), 400
        
        if command_type == 0:  # UNKNOWN
            return jsonify({"error": "Invalid command type"}), 400
        
        # Verify the agent exists
        data_dir = os.path.join(current_app.root_path, '..', 'data')
        agents_file = os.path.join(data_dir, 'agents.json')
        
        if not os.path.exists(agents_file):
            return jsonify({"error": "No agents are registered"}), 400
            
        with open(agents_file, 'r') as f:
            agents_data = json.load(f)
            
        if agent_id not in agents_data:
            return jsonify({"error": f"Agent with ID {agent_id} does not exist"}), 404
        
        # Check if agent is online before sending command
        online_agents = get_online_agents()
        if agent_id not in online_agents:
            return jsonify({"error": f"Agent with ID {agent_id} is not online"}), 400
        
        # Get command type name for logging
        command_type_name = convert_command_type_to_string(command_type)
        logger.info(f"Sending {command_type_name} command to agent {agent_id}")
        
        # Implement a retry mechanism with backoff like IOC updates
        max_retries = 3
        retry_count = 0
        success = False
        last_message = ""
        last_command_id = None
        
        while retry_count < max_retries and not success:
            if retry_count > 0:
                # Add increasing delay between retries
                delay = retry_count * 0.5
                logger.info(f"Retrying send command to agent {agent_id} (attempt {retry_count+1}/{max_retries}) after {delay}s delay")
                time.sleep(delay)
            
            try:
                # Add a small delay to prevent race conditions
                time.sleep(0.2)
                
                success_result, message, command_id = send_command_to_agent(
                    agent_id=agent_id,
                    command_type=command_type,
                    params=params,
                    priority=data.get('priority', 1),
                    timeout=data.get('timeout', 60)
                )
                
                if success_result:
                    logger.info(f"{command_type_name} command queued for agent {agent_id} (command ID: {command_id})")
                    success = True
                    last_message = message
                    last_command_id = command_id
                    break
                else:
                    logger.warning(f"Failed to queue {command_type_name} command for agent {agent_id}: {message}")
                    last_message = message
                    
            except Exception as e:
                logger.error(f"Exception sending {command_type_name} command to agent {agent_id}: {e}")
                last_message = str(e)
            
            retry_count += 1
        
        # Log the final result
        if success:
            logger.info(f"Successfully sent {command_type_name} command after {retry_count+1} attempts")
            return jsonify({
                "success": True,
                "command_id": last_command_id,
                "message": last_message,
                "attempts": retry_count + 1,
                "command_type": command_type_name
            })
        else:
            logger.warning(f"Failed to send {command_type_name} command after {max_retries} attempts")
            return jsonify({
                "success": False,
                "message": f"Failed after {max_retries} attempts: {last_message}",
                "attempts": retry_count + 1,
                "command_type": command_type_name
            }), 500
            
    except Exception as e:
        logger.error(f"Error in send_command endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

def convert_command_type_to_string(type_value):
    """Convert command type enum to string."""
    command_types = {
        0: "UNKNOWN",
        1: "DELETE_FILE",
        2: "KILL_PROCESS",
        3: "KILL_PROCESS_TREE",
        4: "BLOCK_IP",
        5: "BLOCK_URL",
        6: "NETWORK_ISOLATE",
        7: "NETWORK_RESTORE",
        8: "UPDATE_IOCS"
    }
    return command_types.get(type_value, "UNKNOWN")

def convert_command_type_from_string(type_string):
    """Convert command type string to enum value."""
    command_types = {
        "DELETE_FILE": 1,
        "KILL_PROCESS": 2,
        "KILL_PROCESS_TREE": 3,
        "BLOCK_IP": 4,
        "BLOCK_URL": 5,
        "NETWORK_ISOLATE": 6,
        "NETWORK_RESTORE": 7,
        "UPDATE_IOCS": 8
    }
    return command_types.get(type_string, 0) 