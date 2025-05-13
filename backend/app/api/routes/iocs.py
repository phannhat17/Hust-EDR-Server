import os
import json
import logging
import time
from flask import Blueprint, jsonify, request
from app.iocs import IOCManager

# Configure logging
logger = logging.getLogger(__name__)

# Create IOCs routes blueprint
iocs_bp = Blueprint('iocs', __name__, url_prefix='/iocs')

# Initialize IOC manager
ioc_manager = IOCManager()

@iocs_bp.route('', methods=['GET'])
def get_all_iocs():
    """Get all IOCs in the system."""
    try:
        result = ioc_manager.get_all_iocs()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error retrieving IOCs: {str(e)}")
        return jsonify({"error": f"Failed to retrieve IOCs: {str(e)}"}), 500

@iocs_bp.route('/<ioc_type>', methods=['GET'])
def get_iocs_by_type(ioc_type):
    """Get IOCs by type."""
    valid_types = ['ip', 'hash', 'url']
    if ioc_type not in valid_types:
        return jsonify({"error": f"Invalid IOC type: {ioc_type}. Must be one of {valid_types}"}), 400
    
    try:
        result = ioc_manager.get_iocs_by_type(ioc_type)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error retrieving IOCs by type {ioc_type}: {str(e)}")
        return jsonify({"error": f"Failed to retrieve IOCs: {str(e)}"}), 500

@iocs_bp.route('/ip', methods=['POST'])
def add_ip_ioc():
    """Add an IP address to the IOC database."""
    data = request.json
    
    if not data or 'value' not in data:
        return jsonify({"success": False, "message": "Missing required field: value"}), 400
    
    try:
        success = ioc_manager.add_ip(
            ip=data['value'],
            description=data.get('description', ''),
            severity=data.get('severity', 'medium')
        )
        
        if not success:
            return jsonify({"success": False, "message": "Invalid IP format"}), 400
        
        # Force reload after adding IOC
        ioc_manager.reload_data()
        
        return jsonify({"success": True, "message": f"Added IP IOC: {data['value']}"})
    except Exception as e:
        logger.error(f"Error adding IP IOC: {str(e)}")
        return jsonify({"success": False, "message": f"Failed to add IP IOC: {str(e)}"}), 500

@iocs_bp.route('/hash', methods=['POST'])
def add_file_hash_ioc():
    """Add a file hash to the IOC database."""
    data = request.json
    
    if not data or 'value' not in data:
        return jsonify({"success": False, "message": "Missing required field: value"}), 400
    
    if 'hash_type' not in data:
        return jsonify({"success": False, "message": "Missing required field: hash_type"}), 400
    
    try:
        success = ioc_manager.add_file_hash(
            file_hash=data['value'],
            hash_type=data['hash_type'],
            description=data.get('description', ''),
            severity=data.get('severity', 'medium')
        )
        
        if not success:
            return jsonify({"success": False, "message": f"Invalid {data['hash_type']} hash format"}), 400
        
        # Force reload after adding IOC
        ioc_manager.reload_data()
        
        return jsonify({"success": True, "message": f"Added file hash IOC: {data['value']}"})
    except Exception as e:
        logger.error(f"Error adding file hash IOC: {str(e)}")
        return jsonify({"success": False, "message": f"Failed to add file hash IOC: {str(e)}"}), 500

@iocs_bp.route('/url', methods=['POST'])
def add_url_ioc():
    """Add a URL to the IOC database."""
    data = request.json
    
    if not data or 'value' not in data:
        return jsonify({"success": False, "message": "Missing required field: value"}), 400
    
    try:
        success = ioc_manager.add_url(
            url=data['value'],
            description=data.get('description', ''),
            severity=data.get('severity', 'medium')
        )
        
        # Force reload after adding IOC
        ioc_manager.reload_data()
        
        return jsonify({"success": True, "message": f"Added URL IOC: {data['value']}"})
    except Exception as e:
        logger.error(f"Error adding URL IOC: {str(e)}")
        return jsonify({"success": False, "message": f"Failed to add URL IOC: {str(e)}"}), 500

@iocs_bp.route('/remove', methods=['POST'])
def remove_ioc_post():
    """Remove an IOC from the database using POST method (more compatible than DELETE)."""
    data = request.json
    
    if not data or 'type' not in data or 'value' not in data:
        return jsonify({"success": False, "message": "Missing required fields: type and value"}), 400
    
    ioc_type = data['type']
    value = data['value']
    
    valid_types = ['ip', 'hash', 'url']
    if ioc_type not in valid_types:
        return jsonify({"success": False, "message": f"Invalid IOC type: {ioc_type}. Must be one of {valid_types}"}), 400
    
    try:
        success = ioc_manager.remove_ioc(ioc_type, value)
        
        if not success:
            return jsonify({"success": False, "message": f"IOC not found: {ioc_type}:{value}"}), 404
        
        # Force reload after removing IOC
        ioc_manager.reload_data()
        
        return jsonify({"success": True, "message": f"Removed {ioc_type} IOC: {value}"})
    except Exception as e:
        logger.error(f"Error removing IOC: {str(e)}")
        return jsonify({"success": False, "message": f"Failed to remove IOC: {str(e)}"}), 500

@iocs_bp.route('/send-updates', methods=['POST'])
def send_ioc_updates():
    """Send IOC updates to all connected agents."""
    try:
        # Force reload IOC data from disk first
        ioc_manager.reload_data()
        
        # Increment version number and save IOCs with new version
        ioc_manager._save_iocs(increment_version=True)
        
        logger.info(f"Incremented IOC version to {ioc_manager.get_version_info()['version']} before sending updates")
        
        # Implement a retry mechanism with backoff
        max_retries = 3
        retry_count = 0
        success = False
        last_message = ""
        last_count = 0
        
        while retry_count < max_retries and not success:
            if retry_count > 0:
                # Add increasing delay between retries
                delay = retry_count * 0.5
                logger.info(f"Retrying send_updates_to_agents (attempt {retry_count+1}/{max_retries}) after {delay}s delay")
                time.sleep(delay)
            
            count, message = ioc_manager.send_updates_to_agents()
            last_count = count
            last_message = message
            
            # Consider success if at least one agent was updated
            if count > 0:
                success = True
                break
            
            retry_count += 1
        
        # Log the final result
        if success:
            logger.info(f"Successfully sent IOC updates after {retry_count+1} attempts")
        else:
            logger.warning(f"Failed to send IOC updates after {max_retries} attempts")
        
        return jsonify({
            "success": True,
            "message": last_message,
            "agents_updated": last_count,
            "attempts": retry_count + 1
        })
    except Exception as e:
        logger.error(f"Error sending IOC updates: {str(e)}")
        return jsonify({
            "success": False, 
            "message": f"Failed to send IOC updates: {str(e)}"
        }), 500 