import logging
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta

# Set up logger
logger = logging.getLogger(__name__)

# Create dashboard routes blueprint
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

@dashboard_bp.route('/stats', methods=['GET'])
def get_dashboard_stats():
    """Get overall dashboard statistics."""
    try:
        logger.info("Getting dashboard statistics")
        elastalert_client = current_app.config['elastalert_client']
        
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

@dashboard_bp.route('/alerts-by-status', methods=['GET'])
def get_alerts_by_status():
    """Get alert counts grouped by status."""
    try:
        logger.info("Getting alerts by status")
        elastalert_client = current_app.config['elastalert_client']
        
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

@dashboard_bp.route('/alerts-by-time', methods=['GET'])
def get_alerts_by_time():
    """Get alert counts grouped by time period."""
    try:
        logger.info("Getting alerts by time")
        elastalert_client = current_app.config['elastalert_client']
        
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

@dashboard_bp.route('/agents', methods=['GET'])
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