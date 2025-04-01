"""
Authentication utilities for the API.
"""

import logging
from functools import wraps
from flask import request, jsonify
from app.config.config import config

logger = logging.getLogger(__name__)

def require_api_key(f):
    """Decorator to require API key for a route."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get API key from header
        api_key = request.headers.get(config.API_KEY_HEADER)
        
        # Check API key
        if api_key != config.API_KEY:
            logger.warning(f"Invalid API key provided: {api_key}")
            return jsonify({"error": "Invalid API key"}), 401
            
        return f(*args, **kwargs)
    return decorated_function