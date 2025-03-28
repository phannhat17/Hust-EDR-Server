import logging
from flask import Flask, jsonify
from flask_cors import CORS
from app.core.config import config
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
    
    # Health check route
    @app.route('/health')
    def health():
        """Health check endpoint."""
        return jsonify({
            "status": "ok",
            "service": "edr-backend",
            "version": "1.0.0"
        })
    
    # Register blueprints
    from app.api.routes.dashboard import dashboard_bp
    from app.api.routes.alerts import alerts_bp
    from app.api.routes.rules import rules_bp
    
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(rules_bp)
    
    return app