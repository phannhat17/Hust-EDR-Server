import logging
from flask import Blueprint, jsonify, request, current_app

# Set up logger
logger = logging.getLogger(__name__)

# Create alerts routes blueprint
alerts_bp = Blueprint('alerts', __name__, url_prefix='/api/alerts')

@alerts_bp.route('', methods=['GET'])
def get_alerts():
    """Get alerts from ElastAlert."""
    try:
        limit = request.args.get('limit', 100, type=int)
        logger.info(f"Getting alerts with limit {limit}")
        elastalert_client = current_app.config['elastalert_client']
        alerts = elastalert_client.get_alerts(limit=limit)
        logger.info(f"Found {len(alerts)} alerts")
        return jsonify(alerts)
    except Exception as e:
        logger.error(f"Error in get_alerts endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e), "alerts": []}), 500

@alerts_bp.route('/<alert_id>', methods=['PUT'])
def update_alert(alert_id):
    """Update an alert's status."""
    data = request.json
    status = data.get('status')
    notes = data.get('notes')
    assigned_to = data.get('assigned_to')
    
    if not status:
        return jsonify({'error': 'Status is required'}), 400
    
    elastalert_client = current_app.config['elastalert_client']
    success = elastalert_client.update_alert_status(
        alert_id=alert_id,
        status=status,
        notes=notes,
        assigned_to=assigned_to
    )
    
    if success:
        return jsonify({'message': 'Alert updated successfully'})
    else:
        return jsonify({'error': 'Failed to update alert'}), 500 