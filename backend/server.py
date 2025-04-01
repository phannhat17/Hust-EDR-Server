#!/usr/bin/env python
"""
Main entry point for the EDR backend application.
"""

import logging
from app import create_app
from app.config.config import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# Create the Flask application
app = create_app()

if __name__ == '__main__':
    # Log application startup
    logger.info(f"Starting EDR backend server on port {config.PORT}")
    logger.info(f"Debug mode: {config.DEBUG}")
    logger.info(f"gRPC server running on port {config.GRPC_PORT}")
    logger.info(f"Health check available at: http://0.0.0.0:{config.PORT}/health")
    
    # Run the application
    app.run(
        host='0.0.0.0',
        port=config.PORT,
        debug=config.DEBUG
    ) 