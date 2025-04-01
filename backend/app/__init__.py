"""
Flask application factory.
"""

import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from app.config.config import config
from app.core.auth import require_api_key
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
    
    # Apply API key protection to all blueprints
    for blueprint in [alerts_bp, dashboard_bp, rules_bp]:
        for endpoint, view_func in blueprint.view_functions.items():
            blueprint.view_functions[endpoint] = require_api_key(view_func)
    
    # Register blueprints
    app.register_blueprint(alerts_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(rules_bp)

    # Health check routes (no API key required)
    @app.route('/health', methods=['GET'])
    @app.route('/', methods=['GET'])
    def health_check():
        return jsonify({'status': 'healthy'})
    
    # Start gRPC server
    from app.grpc.server import start_grpc_server
    grpc_server = start_grpc_server(port=config.GRPC_PORT)
    app.grpc_server = grpc_server
    
    logger.info("Flask application initialized with gRPC server and API routes")
    
    return app

__all__ = ['create_app'] 