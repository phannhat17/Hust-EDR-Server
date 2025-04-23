"""
API module for frontend communication
"""

from flask import Blueprint

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Import routes - these imports must be after creating api_bp
from .routes import agents, commands, alerts, dashboard, rules 