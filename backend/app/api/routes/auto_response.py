"""
Routes for auto-response functionality.
"""

import logging
from flask import Blueprint, jsonify, request, current_app

logger = logging.getLogger('app.api.auto_response')

auto_response_bp = Blueprint('auto_response', __name__)

@auto_response_bp.route('/status', methods=['GET'])
def get_auto_response_status():
    """Get the status of the auto-response system."""
    from app.config.config import config
    
    status = {
        "enabled": config.AUTO_RESPONSE_ENABLED,
        "interval": config.AUTO_RESPONSE_INTERVAL,
        "supported_actions": [
            "DELETE_FILE",
            "KILL_PROCESS",
            "KILL_PROCESS_TREE",
            "BLOCK_IP",
            "BLOCK_URL",
            "NETWORK_ISOLATE",
            "NETWORK_RESTORE"
        ]
    }
    
    return jsonify(status)

@auto_response_bp.route('/process', methods=['POST'])
def process_pending_alerts():
    """Manually trigger processing of pending alerts."""
    try:
        elastalert_client = current_app.config['elastalert_client']
        data = request.json or {}
        
        # Get parameters from request
        limit = int(data.get('limit', 20))
        include_processed = bool(data.get('include_processed', False))
        
        # Process pending alerts
        results = elastalert_client.process_pending_alerts(
            limit=limit, 
            include_processed=include_processed
        )
        
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error processing pending alerts: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@auto_response_bp.route('/test', methods=['POST'])
def test_auto_response():
    """Test auto-response functionality with a sample alert."""
    try:
        elastalert_client = current_app.config['elastalert_client']
        data = request.json or {}
        
        if not data:
            return jsonify({"error": "No alert data provided"}), 400
            
        # Create a test alert ID
        import uuid
        alert_id = str(uuid.uuid4())
        
        # Add minimal required fields if not present
        if not data.get('rule_name'):
            data['rule_name'] = 'Test Rule'
            
        # Construct alert object
        alert = {
            'id': alert_id,
            'timestamp': data.get('@timestamp', ''),
            'rule_name': data.get('rule_name', 'Test Rule'),
            'raw_data': data
        }
        
        # Process the alert
        result = elastalert_client.process_alert_auto_response(alert_id, alert)
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error testing auto-response: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500 