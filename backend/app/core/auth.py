from functools import wraps
from flask import request, jsonify
from app.core.config import config

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get(config['api_key_header'])
        if api_key and api_key == config['api_key']:
            return f(*args, **kwargs)
        return jsonify({"error": "Invalid API key"}), 401
    return decorated_function