"""
Flask application factory.
"""

import os
import logging
import logging.handlers
import threading
import time
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS
from app.config.config import config
from app.elastalert import ElastAlertClient

# Set up logging directory
log_dir = Path(config.LOG_DIR)
log_dir.mkdir(parents=True, exist_ok=True)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(getattr(logging, config.LOG_LEVEL))

# Define log formatters
standard_formatter = logging.Formatter(config.LOG_FORMAT)
detailed_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(threadName)s - %(filename)s:%(lineno)d - %(message)s')

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(standard_formatter)
console_handler.setLevel(logging.INFO)
root_logger.addHandler(console_handler)

# Create file handlers for different components
def create_component_handler(component_name, level=logging.INFO):
    log_file = log_dir / f"{component_name}.log"
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10485760, backupCount=5  # 10MB files, keep 5 backups
    )
    handler.setLevel(level)
    handler.setFormatter(detailed_formatter)
    return handler

# Add handlers for specific components
components = {
    'app': logging.getLogger('app'),
    'api': logging.getLogger('app.api'),
    'grpc': logging.getLogger('app.grpc'),
    'elastalert': logging.getLogger('app.elastalert'),
    'auto_response': logging.getLogger('app.elastalert_auto_response'),
    'db': logging.getLogger('app.db'),
}

for name, logger in components.items():
    logger.addHandler(create_component_handler(name))
    logger.propagate = False  # Prevent duplicate logs in parent loggers

# Create special handlers for error logs (across all components)
error_handler = logging.handlers.RotatingFileHandler(
    log_dir / "error.log", maxBytes=10485760, backupCount=5
)
error_handler.setLevel(logging.ERROR)
error_handler.setFormatter(detailed_formatter)
root_logger.addHandler(error_handler)

# Get main application logger
logger = logging.getLogger('app')
logger.info(f"Logging initialized with level {config.LOG_LEVEL} in directory {log_dir}")

# Global flag to control the background thread
auto_response_running = False
auto_response_thread = None

def alert_processor_thread(elastalert_client, interval=30):
    """Background thread to periodically process alerts with auto-response."""
    global auto_response_running
    
    auto_logger = logging.getLogger('app.elastalert_auto_response')
    auto_logger.info(f"Alert processor thread started (interval: {interval}s)")
    last_check_time = 0
    
    while auto_response_running:
        try:
            current_time = time.time()
            elapsed = current_time - last_check_time
            
            # Only check periodically to avoid excessive processing
            if elapsed >= interval:
                auto_logger.info(f"Checking for alerts to auto-process (last check: {int(elapsed)}s ago)")
                
                # Process alerts
                results = elastalert_client.process_pending_alerts(limit=20)
                
                if results.get('processed', 0) > 0:
                    auto_logger.info(f"Auto-processed {results.get('processed')} alerts: "
                                f"success={results.get('success', 0)}, failed={results.get('failed', 0)}")
                else:
                    auto_logger.debug("No new alerts to process")
                    
                last_check_time = current_time
        except Exception as e:
            auto_logger.error(f"Error in alert processor thread: {e}")
            import traceback
            auto_logger.error(traceback.format_exc())
            
        # Sleep to avoid tight loop
        time.sleep(5)
        
    auto_logger.info("Alert processor thread stopped")

def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__)
    
    # Enable CORS
    CORS(app)
    
    # Load config settings
    app.config.from_object(config)
    
    # Initialize ElastAlert client
    from app.grpc.server import EDRServicer
    grpc_servicer = EDRServicer()
    elastalert_client = ElastAlertClient(grpc_servicer)
    app.config['elastalert_client'] = elastalert_client
    
    # Register API blueprints
    from app.api.routes.rules import rules_bp
    from app.api.routes.agents import agents_bp
    from app.api.routes.alerts import alerts_bp
    from app.api.routes.auto_response import auto_response_bp
    
    app.register_blueprint(rules_bp, url_prefix='/api/rules')
    app.register_blueprint(agents_bp, url_prefix='/api/agents')
    app.register_blueprint(alerts_bp, url_prefix='/api/alerts')
    app.register_blueprint(auto_response_bp, url_prefix='/api/auto-response')
    
    # Start auto-response background thread if enabled
    global auto_response_running, auto_response_thread
    if config.AUTO_RESPONSE_ENABLED:
        auto_response_running = True
        auto_response_thread = threading.Thread(
            target=alert_processor_thread,
            args=(elastalert_client, config.AUTO_RESPONSE_INTERVAL),
            daemon=True
        )
        auto_response_thread.start()
        logger.info(f"Auto-response background thread started (interval: {config.AUTO_RESPONSE_INTERVAL}s)")
    
    # Default route
    @app.route('/')
    def index():
        return jsonify({
            "status": "ok",
            "service": "EDR Backend API",
            "auto_response": "enabled" if config.AUTO_RESPONSE_ENABLED else "disabled"
        })
        
    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404
        
    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500
        
    return app

def shutdown_background_threads():
    """Shutdown background threads gracefully."""
    global auto_response_running, auto_response_thread
    
    if auto_response_running and auto_response_thread:
        logger.info("Shutting down auto-response background thread...")
        auto_response_running = False
        auto_response_thread.join(timeout=10)
        logger.info("Auto-response background thread stopped")

__all__ = ['create_app'] 