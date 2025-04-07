import logging
import os
import json
import time
import uuid
import grpc
from flask import Blueprint, jsonify, request, current_app
from app.grpc import agent_pb2, agent_pb2_grpc

# Set up logger
logger = logging.getLogger(__name__)

# Create commands routes blueprint
commands_bp = Blueprint('commands', __name__, url_prefix='/api/commands')

def create_grpc_client():
    """Create a gRPC client for command services."""
    channel = grpc.insecure_channel('localhost:50051')
    return agent_pb2_grpc.EDRServiceStub(channel)

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
        
        # Create client
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
            priority=data.get('priority', 1),
            timeout=data.get('timeout', 60)
        )
        
        # Send command to server
        request_obj = agent_pb2.SendCommandRequest(command=command)
        response = client.SendCommand(request_obj)
        
        if response.success:
            return jsonify({
                "success": True,
                "command_id": command_id,
                "message": response.message
            })
        else:
            return jsonify({
                "success": False,
                "message": response.message
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
        7: "NETWORK_RESTORE"
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
        "NETWORK_RESTORE": 7
    }
    return command_types.get(type_string, 0) 