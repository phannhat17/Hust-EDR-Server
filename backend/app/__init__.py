"""
Flask application factory.
"""

import os
import threading
import time
from pathlib import Path
from flask import Flask, jsonify, request, abort
from flask_cors import CORS
from app.config.config import config
from app.logging_setup import setup_logging, get_logger
from app.elastalert import ElastAlertClient

# Initialize logging system
setup_logging(include_console=config.DEBUG)

# Get main application logger
logger = get_logger('app')

# Global variables
grpc_server = None
grpc_servicer = None

def api_key_required(f):
    """Decorator to require API key for routes."""
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get(config.API_KEY_HEADER)
        if api_key != config.API_KEY:
            logger.warning(f"Unauthorized access attempt from {request.remote_addr} - invalid API key")
            abort(401, description="Invalid API key")
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__)
    
    # Enable CORS
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # Load config settings
    app.config.from_object(config)
    
    # Initialize ElastAlert client
    from app.grpc.server import EDRServicer, start_grpc_server
    from app.services.ping_monitor import ping_monitor
    
    # Start the gRPC server in a separate thread
    global grpc_server, grpc_servicer
    grpc_port = config.GRPC_PORT
    grpc_server, grpc_servicer = start_grpc_server(grpc_port)
    logger.info(f"gRPC server started on port {grpc_port}")
    
    # Start ping monitor service
    ping_monitor.start()
    logger.info("Agent ping monitor service started")
    
    elastalert_client = ElastAlertClient(grpc_servicer)
    app.config['elastalert_client'] = elastalert_client
    
    # Register API blueprints
    from app.api.routes.rules import rules_bp
    from app.api.routes.agents import agents_bp
    from app.api.routes.alerts import alerts_bp
    from app.api.routes.install import install_bp
    from app.api.routes.dashboard import dashboard_bp
    from app.api.routes.commands import commands_bp
    from app.api.routes.logs import logs_bp
    from app.api.routes.iocs import iocs_bp

    app.register_blueprint(rules_bp, url_prefix='/api/rules')
    app.register_blueprint(agents_bp, url_prefix='/api/agents')
    app.register_blueprint(alerts_bp, url_prefix='/api/alerts')
    app.register_blueprint(install_bp, url_prefix='/api/install')
    app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    app.register_blueprint(commands_bp, url_prefix='/api/commands')
    app.register_blueprint(logs_bp, url_prefix='/api/logs')
    app.register_blueprint(iocs_bp, url_prefix='/api/iocs')
    
    # API key middleware for all API routes
    @app.before_request
    def check_api_key():
        security_logger = get_logger('app.security')
        
        # Skip API key check for health check endpoint and root
        if request.path == '/health' or request.path == '/':
            return
            
        # Skip API key check for install endpoints (needed for agent installation)
        if request.path.startswith('/api/install'):
            return
            
        # Skip OPTIONS requests (for CORS preflight)
        if request.method == 'OPTIONS':
            return
            
        # Check API key for all other API endpoints
        if request.path.startswith('/api/'):
            api_key = request.headers.get(config.API_KEY_HEADER)
            if api_key != config.API_KEY:
                security_logger.warning(f"Unauthorized access attempt from {request.remote_addr} - invalid API key")
                return jsonify({"error": "Unauthorized - Invalid API key"}), 401
    
    # Health check endpoint (no auth required)
    @app.route('/health')
    def health_check():
        return jsonify({
            "status": "healthy",
            "timestamp": int(time.time())
        })
    
    # Default route
    @app.route('/')
    def index():
        return jsonify({
            "status": "ok",
            "service": "EDR Backend API",
            "grpc_server": "running" if grpc_server else "not running",
            "grpc_port": config.GRPC_PORT
        })
        
    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404
        
    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Unauthorized"}), 401
        
    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"Internal server error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
        
    return app

def shutdown_background_threads():
    """Shutdown background threads gracefully."""
    global grpc_server, grpc_servicer
    
    # Stop ping monitor service
    from app.services.ping_monitor import ping_monitor
    ping_monitor.stop()
    logger.info("Agent ping monitor service stopped")
    
    if grpc_server:
        logger.info("Shutting down gRPC server...")
        
        # Force save any pending agent data
        if hasattr(grpc_servicer, 'storage'):
            logger.info("Saving pending agent data...")
            grpc_servicer.storage.force_save()
            
        grpc_server.stop(grace=5)
        logger.info("gRPC server stopped")

__all__ = ['create_app']