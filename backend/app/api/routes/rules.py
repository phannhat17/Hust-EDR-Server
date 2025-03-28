import os
import yaml
import logging
from flask import Blueprint, jsonify, request, current_app

# Set up logger
logger = logging.getLogger(__name__)

# Create rules routes blueprint
rules_bp = Blueprint('rules', __name__, url_prefix='/api')

@rules_bp.route('/rules', methods=['GET'])
def get_rules():
    """Get all ElastAlert rules."""
    elastalert_client = current_app.config['elastalert_client']
    rules = elastalert_client.get_rules()
    return jsonify(rules)

@rules_bp.route('/rules/<filename>', methods=['GET'])
def get_rule(filename):
    """Get a specific ElastAlert rule."""
    elastalert_client = current_app.config['elastalert_client']
    rule = elastalert_client.get_rule(filename)
    
    if rule:
        return jsonify(rule)
    else:
        return jsonify({'error': 'Rule not found'}), 404

@rules_bp.route('/rules/<filename>/yaml', methods=['GET'])
def get_rule_yaml(filename):
    """Get a specific ElastAlert rule as raw YAML."""
    elastalert_client = current_app.config['elastalert_client']
    config = current_app.config['elastalert_client'].config
    rule_path = os.path.join(config['elastalert_rules_dir'], filename)
    
    if not os.path.exists(rule_path):
        return jsonify({'error': 'Rule not found'}), 404
        
    try:
        with open(rule_path, 'r') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        logger.error(f"Error reading rule file {rule_path}: {e}")
        return jsonify({'error': f'Error reading rule file: {e}'}), 500

@rules_bp.route('/rules', methods=['POST'])
def create_rule():
    """Create a new ElastAlert rule."""
    rule_data = request.json
    elastalert_client = current_app.config['elastalert_client']
    
    if not rule_data:
        return jsonify({'error': 'No rule data provided'}), 400
        
    success, result = elastalert_client.save_rule(rule_data)
    
    if success:
        return jsonify({'message': 'Rule created successfully', 'filename': result})
    else:
        return jsonify({'error': f'Failed to create rule: {result}'}), 400

@rules_bp.route('/rules/yaml', methods=['POST'])
def create_rule_from_yaml():
    """Create a new ElastAlert rule from raw YAML content."""
    data = request.json
    elastalert_client = current_app.config['elastalert_client']
    config = elastalert_client.config
    
    if not data or 'content' not in data:
        return jsonify({'error': 'No YAML content provided'}), 400
    
    try:
        # Parse the YAML content to get the rule name
        rule_data = yaml.safe_load(data['content'])
        
        if not rule_data or not isinstance(rule_data, dict) or 'name' not in rule_data:
            return jsonify({'error': 'Invalid YAML: missing or invalid rule name'}), 400
            
        # Generate filename from rule name
        rule_name = rule_data['name']
        filename = f"{rule_name.lower().replace(' ', '_')}.yaml"
        
        # Write the YAML content to a new file
        rule_path = os.path.join(config['elastalert_rules_dir'], filename)
        
        # Check if file already exists
        if os.path.exists(rule_path):
            return jsonify({'error': f'Rule with filename {filename} already exists'}), 400
            
        with open(rule_path, 'w') as f:
            f.write(data['content'])
            
        # Restart ElastAlert if running in Docker
        if config.get('elastalert_docker', False):
            elastalert_client._restart_elastalert()
            
        return jsonify({'message': 'Rule created successfully', 'filename': filename})
    except yaml.YAMLError as e:
        return jsonify({'error': f'Invalid YAML syntax: {str(e)}'}), 400
    except Exception as e:
        logger.error(f"Error creating rule from YAML: {e}")
        return jsonify({'error': f'Error creating rule: {str(e)}'}), 500

@rules_bp.route('/rules/<filename>', methods=['PUT'])
def update_rule(filename):
    """Update an existing ElastAlert rule."""
    rule_data = request.json
    elastalert_client = current_app.config['elastalert_client']
    
    if not rule_data:
        return jsonify({'error': 'No rule data provided'}), 400
        
    # Set the filename in the rule data
    rule_data['filename'] = filename
    
    success, result = elastalert_client.save_rule(rule_data)
    
    if success:
        return jsonify({'message': 'Rule updated successfully'})
    else:
        return jsonify({'error': f'Failed to update rule: {result}'}), 400

@rules_bp.route('/rules/<filename>/yaml', methods=['PUT'])
def update_rule_yaml(filename):
    """Update an existing ElastAlert rule with raw YAML content."""
    data = request.json
    elastalert_client = current_app.config['elastalert_client']
    config = elastalert_client.config
    
    if not data or 'content' not in data:
        return jsonify({'error': 'No YAML content provided'}), 400
        
    rule_path = os.path.join(config['elastalert_rules_dir'], filename)
    
    if not os.path.exists(rule_path):
        return jsonify({'error': 'Rule not found'}), 404
        
    try:
        # Write the raw YAML content to the file
        with open(rule_path, 'w') as f:
            f.write(data['content'])
            
        # Restart ElastAlert if running in Docker
        if config.get('elastalert_docker', False):
            elastalert_client._restart_elastalert()
            
        return jsonify({'message': 'Rule YAML updated successfully'})
    except Exception as e:
        logger.error(f"Error writing rule file {rule_path}: {e}")
        return jsonify({'error': f'Error writing rule file: {e}'}), 500

@rules_bp.route('/rules/<filename>', methods=['DELETE'])
def delete_rule(filename):
    """Delete an ElastAlert rule."""
    elastalert_client = current_app.config['elastalert_client']
    success = elastalert_client.delete_rule(filename)
    
    if success:
        return jsonify({'message': 'Rule deleted successfully'})
    else:
        return jsonify({'error': 'Failed to delete rule'}), 500

@rules_bp.route('/elastalert/restart', methods=['POST'])
def restart_elastalert():
    """Restart the ElastAlert Docker container."""
    elastalert_client = current_app.config['elastalert_client']
    success = elastalert_client._restart_elastalert()
    
    if success:
        return jsonify({'message': 'ElastAlert restarted successfully'})
    else:
        return jsonify({'error': 'Failed to restart ElastAlert'}), 500 