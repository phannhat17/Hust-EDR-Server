import logging
from flask import Flask, jsonify
from flask_cors import CORS
from app.core.config import config
from app.core.auth import require_api_key
from app.elastalert import ElastAlertClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_app():
    """Create and configure the Flask application."""
    
    # Initialize Flask app (without template_folder)
    app = Flask(__name__, static_folder='../static')

    # Enable CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    
    # Initialize ElastAlert client
    elastalert_client = ElastAlertClient(config)
    
    # Store the client in app config for access in route handlers
    app.config['elastalert_client'] = elastalert_client
    
    # Health check route (no API key required)
    @app.route('/health')
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "ok",
            "service": "edr-backend",
            "version": "1.0.0"
        })
    
    # Register blueprints with API key protection
    from app.api.routes.dashboard import dashboard_bp
    from app.api.routes.alerts import alerts_bp
    from app.api.routes.rules import rules_bp
    # from app.api.routes.agents import agents_bp
    
    # Apply API key protection to all blueprints
    for blueprint in [dashboard_bp, alerts_bp, rules_bp]:
        for endpoint, view_func in blueprint.view_functions.items():
            blueprint.view_functions[endpoint] = require_api_key(view_func)
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(rules_bp)
    # app.register_blueprint(agents_bp, url_prefix='/api')
    
    return app