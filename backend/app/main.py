import os
import json
import logging
from pathlib import Path
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from dotenv import load_dotenv
from app.elastalert import ElastAlertClient
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, 
            template_folder='../templates',
            static_folder='../static')

# Enable CORS
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Configuration
config = {
    'elasticsearch_host': os.getenv('ELASTICSEARCH_HOST', 'localhost'),
    'elasticsearch_port': os.getenv('ELASTICSEARCH_PORT', '9200'),
    'elasticsearch_user': os.getenv('ELASTICSEARCH_USER', ''),
    'elasticsearch_password': os.getenv('ELASTICSEARCH_PASSWORD', ''),
    'elasticsearch_use_ssl': os.getenv('ELASTICSEARCH_USE_SSL', 'false').lower() == 'true',
    'elasticsearch_ca_path': os.getenv('ELASTICSEARCH_CA_PATH', ''),
    'elastalert_index': os.getenv('ELASTALERT_INDEX', 'elastalert_status'),
    'elastalert_rules_dir': os.getenv('ELASTALERT_RULES_DIR', 'elastalert_rules'),
    'elastalert_docker': os.getenv('ELASTALERT_DOCKER', 'true').lower() == 'true',
    'elastalert_container': os.getenv('ELASTALERT_CONTAINER', 'elastalert')
}

# Initialize ElastAlert client
elastalert_client = ElastAlertClient(config)

# Web UI routes
@app.route('/')
def index():
    """Render the dashboard page."""
    return render_template('index.html')

@app.route('/alerts')
def alerts_page():
    """Render the alerts page."""
    return render_template('alerts.html')

@app.route('/rules')
def rules_page():
    """Render the rules page."""
    return render_template('rules.html')

# Dashboard API routes
@app.route('/api/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Get overall dashboard statistics."""
    try:
        logger.info("Getting dashboard statistics")
        
        # Get alerts for statistics
        all_alerts = elastalert_client.get_alerts(limit=1000)  # Get a large number to ensure accurate stats
        
        # Calculate alert statistics
        total_alerts = len(all_alerts)
        new_alerts = sum(1 for alert in all_alerts if alert.get('status') == 'new')
        resolved_alerts = sum(1 for alert in all_alerts if alert.get('status') == 'resolved')
        false_positives = sum(1 for alert in all_alerts if alert.get('status') == 'false_positive')
        
        # Get rule statistics
        rules = elastalert_client.get_rules()
        total_rules = len(rules)
        active_rules = sum(1 for rule in rules if not rule.get('is_disabled', False))
        
        # For active agents, we'll just use a placeholder number since agent functionality is not implemented yet
        active_agents = 0
        
        stats = {
            'total_alerts': total_alerts,
            'new_alerts': new_alerts,
            'resolved_alerts': resolved_alerts,
            'false_positives': false_positives,
            'active_agents': active_agents,
            'total_rules': total_rules,
            'active_rules': active_rules
        }
        
        logger.info(f"Dashboard stats: {stats}")
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error in get_dashboard_stats endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard/alerts-by-status', methods=['GET'])
def get_alerts_by_status():
    """Get alert counts grouped by status."""
    try:
        logger.info("Getting alerts by status")
        
        # Get all alerts
        alerts = elastalert_client.get_alerts(limit=1000)
        
        # Group by status
        status_counts = {
            'new': 0,
            'in_progress': 0,
            'resolved': 0,
            'false_positive': 0
        }
        
        for alert in alerts:
            status = alert.get('status', 'new')
            if status in status_counts:
                status_counts[status] += 1
            else:
                status_counts[status] = 1
        
        # Format for the frontend
        result = [
            {'status': status, 'count': count}
            for status, count in status_counts.items()
        ]
        
        logger.info(f"Alerts by status: {result}")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_alerts_by_status endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard/alerts-by-time', methods=['GET'])
def get_alerts_by_time():
    """Get alert counts grouped by time period."""
    try:
        logger.info("Getting alerts by time")
        
        # Get time range from query parameter (default to 7 days)
        range_param = request.args.get('range', '7d')
        
        # Parse time range
        days = 7  # default
        if range_param == '1d':
            days = 1
        elif range_param == '7d':
            days = 7
        elif range_param == '30d':
            days = 30
        elif range_param == '90d':
            days = 90
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # Get all alerts
        alerts = elastalert_client.get_alerts(limit=1000)
        
        # Group alerts by day
        date_counts = {}
        
        # Initialize all dates in the range with zero counts
        current_date = start_date.date()
        while current_date <= end_date.date():
            date_counts[current_date.isoformat()] = 0
            current_date += timedelta(days=1)
        
        # Count alerts by day
        for alert in alerts:
            try:
                # Parse the alert timestamp
                timestamp_str = alert.get('timestamp', '')
                if not timestamp_str:
                    continue
                
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                alert_date = timestamp.date()
                
                # Only count alerts within the requested range
                if start_date.date() <= alert_date <= end_date.date():
                    date_key = alert_date.isoformat()
                    date_counts[date_key] = date_counts.get(date_key, 0) + 1
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing alert timestamp: {e}")
                continue
        
        # Format for the frontend
        result = [
            {'date': date, 'count': count}
            for date, count in sorted(date_counts.items())
        ]
        
        logger.info(f"Alerts by time (range={range_param}): {len(result)} data points")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_alerts_by_time endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/dashboard/agents', methods=['GET'])
def get_agent_stats():
    """Get agent statistics."""
    try:
        logger.info("Getting agent statistics")
        
        # For now, we'll just return an empty list since agent functionality is not implemented yet
        result = {
            'agents': []
        }
        
        logger.info("Returning empty agent statistics (not implemented)")
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_agent_stats endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

# API routes
@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get alerts from ElastAlert."""
    try:
        limit = request.args.get('limit', 100, type=int)
        logger.info(f"Getting alerts with limit {limit}")
        alerts = elastalert_client.get_alerts(limit=limit)
        logger.info(f"Found {len(alerts)} alerts")
        return jsonify(alerts)
    except Exception as e:
        logger.error(f"Error in get_alerts endpoint: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e), "alerts": []}), 500

@app.route('/api/alerts/<alert_id>', methods=['PUT'])
def update_alert(alert_id):
    """Update an alert's status."""
    data = request.json
    status = data.get('status')
    notes = data.get('notes')
    assigned_to = data.get('assigned_to')
    
    if not status:
        return jsonify({'error': 'Status is required'}), 400
        
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

@app.route('/api/rules', methods=['GET'])
def get_rules():
    """Get all ElastAlert rules."""
    rules = elastalert_client.get_rules()
    return jsonify(rules)

@app.route('/api/rules/<filename>', methods=['GET'])
def get_rule(filename):
    """Get a specific ElastAlert rule."""
    rule = elastalert_client.get_rule(filename)
    
    if rule:
        return jsonify(rule)
    else:
        return jsonify({'error': 'Rule not found'}), 404

@app.route('/api/rules', methods=['POST'])
def create_rule():
    """Create a new ElastAlert rule."""
    rule_data = request.json
    
    if not rule_data:
        return jsonify({'error': 'No rule data provided'}), 400
        
    success, result = elastalert_client.save_rule(rule_data)
    
    if success:
        return jsonify({'message': 'Rule created successfully', 'filename': result})
    else:
        return jsonify({'error': f'Failed to create rule: {result}'}), 400

@app.route('/api/rules/<filename>', methods=['PUT'])
def update_rule(filename):
    """Update an existing ElastAlert rule."""
    rule_data = request.json
    
    if not rule_data:
        return jsonify({'error': 'No rule data provided'}), 400
        
    # Set the filename in the rule data
    rule_data['filename'] = filename
    
    success, result = elastalert_client.save_rule(rule_data)
    
    if success:
        return jsonify({'message': 'Rule updated successfully'})
    else:
        return jsonify({'error': f'Failed to update rule: {result}'}), 400

@app.route('/api/rules/<filename>', methods=['DELETE'])
def delete_rule(filename):
    """Delete an ElastAlert rule."""
    success = elastalert_client.delete_rule(filename)
    
    if success:
        return jsonify({'message': 'Rule deleted successfully'})
    else:
        return jsonify({'error': 'Failed to delete rule'}), 500

@app.route('/api/elastalert/restart', methods=['POST'])
def restart_elastalert():
    """Restart the ElastAlert Docker container."""
    success = elastalert_client._restart_elastalert()
    
    if success:
        return jsonify({'message': 'ElastAlert restarted successfully'})
    else:
        return jsonify({'error': 'Failed to restart ElastAlert'}), 500

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    
    logger.info(f"Starting EDR Web UI on port {port}")
    logger.info(f"Elasticsearch host: {config['elasticsearch_host']}:{config['elasticsearch_port']}")
    logger.info(f"ElastAlert index: {config['elastalert_index']}")
    logger.info(f"ElastAlert rules directory: {config['elastalert_rules_dir']}")
    
    app.run(host='0.0.0.0', port=port, debug=debug) 