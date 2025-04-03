"""
Flask application factory.
"""

import os
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS
from app.config.config import config
from app.elastalert import elastalert_client

# Set up logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Enable CORS
    CORS(app, resources={r"/*": {"origins": "*"}})
    
    # Add elastalert client to app config
    app.config['elastalert_client'] = elastalert_client
    
    # Import blueprints
    from app.api.routes.alerts import alerts_bp
    from app.api.routes.dashboard import dashboard_bp
    from app.api.routes.rules import rules_bp
    from app.api.routes.agents import agents_bp
    
    # Register blueprints
    app.register_blueprint(alerts_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(rules_bp)
    app.register_blueprint(agents_bp)

    # Health check routes (no API key required)
    @app.route('/health', methods=['GET'])
    @app.route('/', methods=['GET'])
    def health_check():
        return jsonify({'status': 'healthy'})
    
    # Add a before_request handler to ensure API key authentication for all /api routes
    @app.before_request
    def verify_api_key():
        # Skip health check routes and OPTIONS requests (for CORS)
        if request.path in ['/', '/health'] or request.method == 'OPTIONS':
            return None
            
        # Check if path starts with /api
        if request.path.startswith('/api'):
            api_key = request.headers.get(config.API_KEY_HEADER)
            logger.info(f"Before request handler checking API key for {request.path}")
            
            # If API key is invalid, return 401 immediately
            if api_key != config.API_KEY:
                logger.warning(f"Invalid API key in before_request handler: {api_key}")
                return jsonify({"error": "Invalid API key"}), 401
    
    # Start gRPC server
    from app.grpc.server import start_grpc_server
    grpc_server = start_grpc_server(port=config.GRPC_PORT)
    app.grpc_server = grpc_server
    
    logger.info("Flask application initialized with gRPC server and API routes")
    
    return app

__all__ = ['create_app'] 