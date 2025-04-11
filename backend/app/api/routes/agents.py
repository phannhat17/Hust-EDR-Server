import logging
import os
import json
import time
from flask import Blueprint, jsonify, request, current_app
from app.config.config import config

# Set up logger
logger = logging.getLogger(__name__)

# Create agents routes blueprint
agents_bp = Blueprint('agents', __name__, url_prefix='/api/agents')

@agents_bp.route('', methods=['GET'])
def get_agents():
    """Get all registered agents."""
    try:
        # Path to the agents.json file
        data_dir = os.path.join(current_app.root_path, '..', 'data')
        agents_file = os.path.join(data_dir, 'agents.json')
        
        logger.info(f"Loading agents from {agents_file}")
        
        if not os.path.exists(agents_file):
            logger.warning(f"Agents file not found at {agents_file}")
            return jsonify([])
        
        with open(agents_file, 'r') as f:
            agents_data = json.load(f)
        
        # Get current time and calculate timeout threshold
        current_time = int(time.time())
        timeout_threshold = current_time - config.AGENT_TIMEOUT
        
        # Flag to track if we need to update the agents file
        need_update = False
        
        # Convert dictionary to list and add 'id' field for frontend compatibility
        agents_list = []
        for agent_id, agent in agents_data.items():
            # Check if agent has timed out
            last_seen = agent.get('last_seen', 0)
            if last_seen < timeout_threshold and agent.get('status') != 'OFFLINE':
                agent['status'] = 'OFFLINE'
                # Update the agent in the data
                agents_data[agent_id] = agent
                need_update = True
            
            # Get the OS version and create a simplified version for the table
            full_os_version = agent.get('os_version', 'Unknown')
            simplified_os = full_os_version
            
            # For Windows, extract just the main version
            if 'Windows' in full_os_version:
                if 'Windows 10' in full_os_version:
                    simplified_os = 'Windows 10'
                    if 'Pro' in full_os_version:
                        simplified_os += ' Pro'
                    elif 'Home' in full_os_version:
                        simplified_os += ' Home'
                elif 'Windows 11' in full_os_version:
                    simplified_os = 'Windows 11'
                    if 'Pro' in full_os_version:
                        simplified_os += ' Pro'
                    elif 'Home' in full_os_version:
                        simplified_os += ' Home'
            # For Ubuntu, simplify to main version
            elif 'Ubuntu' in full_os_version:
                simplified_os = ' '.join(full_os_version.split()[:2])
                if 'LTS' in full_os_version:
                    simplified_os += ' LTS'
            
            agent_info = {
                'id': agent_id,
                'hostname': agent.get('hostname', 'Unknown'),
                'ip_address': agent.get('ip_address', 'Unknown'),
                'mac_address': agent.get('mac_address', 'Unknown'),
                'username': agent.get('username', 'Unknown'),
                'os_info': simplified_os,
                'os_version_full': full_os_version,
                'version': agent.get('agent_version', 'Unknown'),
                'status': agent.get('status', 'Unknown'),
                'cpu_usage': agent.get('cpu_usage', 0),
                'memory_usage': agent.get('memory_usage', 0),
                'uptime': agent.get('uptime', 0),
                'last_seen': agent.get('last_seen', 0) * 1000,  # Convert to milliseconds for JS
                'registered_at': agent.get('registration_time', 0) * 1000  # Convert to milliseconds for JS
            }
            agents_list.append(agent_info)
        
        # If any agents were updated to OFFLINE, save the changes
        if need_update:
            with open(agents_file, 'w') as f:
                json.dump(agents_data, f, indent=2)
            logger.info("Updated agents with offline status")
            
        logger.info(f"Found {len(agents_list)} agents")
        return jsonify(agents_list)
        
    except Exception as e:
        logger.error(f"Error in get_agents endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@agents_bp.route('/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """Get agent by ID."""
    try:
        # Path to the agents.json file
        data_dir = os.path.join(current_app.root_path, '..', 'data')
        agents_file = os.path.join(data_dir, 'agents.json')
        
        if not os.path.exists(agents_file):
            logger.warning(f"Agents file not found at {agents_file}")
            return jsonify({"error": "Agent not found"}), 404
        
        with open(agents_file, 'r') as f:
            agents_data = json.load(f)
        
        agent = agents_data.get(agent_id)
        
        if not agent:
            logger.warning(f"Agent {agent_id} not found")
            return jsonify({"error": "Agent not found"}), 404
        
        # Check if agent has timed out
        current_time = int(time.time())
        timeout_threshold = current_time - config.AGENT_TIMEOUT
        
        last_seen = agent.get('last_seen', 0)
        if last_seen < timeout_threshold and agent.get('status') != 'OFFLINE':
            agent['status'] = 'OFFLINE'
            # Update the agent in the data
            agents_data[agent_id] = agent
            
            # Save the updated status
            with open(agents_file, 'w') as f:
                json.dump(agents_data, f, indent=2)
            logger.info(f"Updated agent {agent_id} to offline status")
        
        # Get the OS version and create a simplified version for the table
        full_os_version = agent.get('os_version', 'Unknown')
        simplified_os = full_os_version
        
        # For Windows, extract just the main version
        if 'Windows' in full_os_version:
            if 'Windows 10' in full_os_version:
                simplified_os = 'Windows 10'
                if 'Pro' in full_os_version:
                    simplified_os += ' Pro'
                elif 'Home' in full_os_version:
                    simplified_os += ' Home'
            elif 'Windows 11' in full_os_version:
                simplified_os = 'Windows 11'
                if 'Pro' in full_os_version:
                    simplified_os += ' Pro'
                elif 'Home' in full_os_version:
                    simplified_os += ' Home'
        
        # Format agent data for frontend
        agent_info = {
            'id': agent_id,
            'hostname': agent.get('hostname', 'Unknown'),
            'ip_address': agent.get('ip_address', 'Unknown'),
            'mac_address': agent.get('mac_address', 'Unknown'),
            'username': agent.get('username', 'Unknown'),
            'os_info': simplified_os,
            'os_version_full': full_os_version,
            'version': agent.get('agent_version', 'Unknown'),
            'status': agent.get('status', 'Unknown'),
            'cpu_usage': agent.get('cpu_usage', 0),
            'memory_usage': agent.get('memory_usage', 0),
            'uptime': agent.get('uptime', 0),
            'last_seen': agent.get('last_seen', 0) * 1000,  # Convert to milliseconds for JS
            'registered_at': agent.get('registration_time', 0) * 1000  # Convert to milliseconds for JS
        }
        
        return jsonify(agent_info)
        
    except Exception as e:
        logger.error(f"Error in get_agent endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500 