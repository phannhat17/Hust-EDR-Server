import os
import logging
from app import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    # Get configuration from environment
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    
    # Log application startup
    logger.info(f"Starting EDR Web UI on port {port}")
    logger.info(f"Debug mode: {debug}")
    logger.info(f"Health check available at: http://0.0.0.0:{port}/health")
    
    # Run the application
    app.run(host='0.0.0.0', port=port, debug=debug) 