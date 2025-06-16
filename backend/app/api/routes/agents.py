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
        
        # Convert dictionary to list and add 'id' field for frontend compatibility
        # No need for timeout checking - ping monitor service handles this
        agents_list = []
        for agent_id, agent in agents_data.items():
            
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
        
        # No need for timeout checking - ping monitor service handles this
        
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

@agents_bp.route('/<agent_id>/ioc-matches', methods=['GET'])
def get_agent_ioc_matches(agent_id):
    """Get IOC matches for a specific agent."""
    try:
        # Path to the IOC matches file
        data_dir = os.path.join(current_app.root_path, '..', 'data')
        ioc_matches_file = os.path.join(data_dir, 'ioc_matches.json')
        
        logger.info(f"Loading IOC matches from {ioc_matches_file}")
        
        if not os.path.exists(ioc_matches_file):
            logger.warning(f"IOC matches file not found at {ioc_matches_file}")
            return jsonify([])
        
        with open(ioc_matches_file, 'r') as f:
            all_matches = json.load(f)
        
        # Check if all_matches is a dictionary (new format) or list (old format)
        if isinstance(all_matches, dict):
            # New format: dictionary with match_id as keys
            agent_matches = [match_data for match_id, match_data in all_matches.items() 
                            if match_data.get('agent_id') == agent_id]
        else:
            # Old format: list of match objects
            agent_matches = [match for match in all_matches if match.get('agent_id') == agent_id]
        
        logger.info(f"Found {len(agent_matches)} IOC matches for agent {agent_id}")
        return jsonify(agent_matches)
        
    except Exception as e:
        logger.error(f"Error in get_agent_ioc_matches endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500 