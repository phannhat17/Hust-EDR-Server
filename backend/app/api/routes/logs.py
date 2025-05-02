import os
import logging
import re
from pathlib import Path
from datetime import datetime
from app.config.config import config
from flask import Blueprint, jsonify, request, current_app

# Configure logging
logger = logging.getLogger(__name__)

# Create logs routes blueprint
logs_bp = Blueprint('logs', __name__, url_prefix='/logs')

# Define log files
LOG_FILES = {
    'app': 'app.log',
    'api': 'api.log',
    'grpc': 'grpc.log',
    'elastalert': 'elastalert.log',
    'error': 'error.log',
    'grpc_connections': 'grpc_connections.log',
    'grpc_debug': 'grpc_debug.log',
    'grpc_ioc': 'grpc_ioc.log'
}

def get_log_path(log_type):
    """Get the path to the log file."""
    # Logs directory is at backend/logs
    logs_dir = Path(config.LOG_DIR)
    log_file = LOG_FILES.get(log_type, 'app.log')
    return os.path.join(logs_dir, log_file)

@logs_bp.route('/types', methods=['GET'])
def get_log_types():
    """Get available log types."""
    return jsonify(list(LOG_FILES.keys()))

@logs_bp.route('/<log_type>', methods=['GET'])
def get_logs(log_type):
    """Get logs by type with filtering options."""
    # Validate log type
    if log_type not in LOG_FILES:
        return jsonify({"error": f"Invalid log type: {log_type}"}), 400
    
    # Get query parameters for filtering
    lines = request.args.get('lines', default=100, type=int)
    search = request.args.get('search', default=None, type=str)
    level = request.args.get('level', default=None, type=str)
    since = request.args.get('since', default=None, type=str)
    
    # Max lines limit to prevent excessive memory usage
    if lines > 1000:
        lines = 1000
    
    try:
        log_path = get_log_path(log_type)
        
        if not os.path.exists(log_path):
            return jsonify({"error": f"Log file not found: {LOG_FILES.get(log_type)}"}), 404
        
        # Read logs, applying filters
        logs = []
        with open(log_path, 'r', encoding='utf-8') as file:
            all_lines = file.readlines()
            
            # Apply filtering
            filtered_lines = []
            for line in all_lines:
                # Skip empty lines
                if not line.strip():
                    continue
                
                # Apply search filter
                if search and search.lower() not in line.lower():
                    continue
                    
                # Apply level filter if provided
                if level:
                    level_pattern = r'\[(DEBUG|INFO|WARNING|ERROR|CRITICAL)\]'
                    match = re.search(level_pattern, line)
                    if not match or match.group(1).lower() != level.lower():
                        continue
                
                # Apply timestamp filter if provided
                if since:
                    try:
                        # Extract timestamp from log line, assuming format like "2023-04-26 12:30:45"
                        timestamp_pattern = r'(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})'
                        match = re.search(timestamp_pattern, line)
                        
                        if match:
                            line_time = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
                            since_time = datetime.strptime(since, '%Y-%m-%d %H:%M:%S')
                            
                            if line_time < since_time:
                                continue
                        else:
                            # If timestamp not found in the line, skip it
                            continue
                    except ValueError:
                        # If date parsing fails, include the line
                        pass
                
                filtered_lines.append(line)
            
            # Take the last N lines after filtering
            logs = filtered_lines[-lines:]
        
        return jsonify({
            "log_type": log_type,
            "lines": lines,
            "count": len(logs),
            "content": logs
        })
        
    except Exception as e:
        logger.error(f"Error retrieving logs for {log_type}: {str(e)}")
        return jsonify({"error": f"Failed to retrieve logs: {str(e)}"}), 500 