"""
Unified configuration for the Flask application.
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Get the base directory of the application
BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Config:
    """Base configuration for the application."""
    
    # Get base directory
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    # Data directory for storage
    DATA_DIR = os.environ.get('DATA_DIR', os.path.join(BASE_DIR, 'data'))
    
    # TLS Certificates directory
    CERT_DIR = os.environ.get('CERT_DIR', os.path.join(BASE_DIR, 'cert'))

    # Script directory for installation
    SCRIPT_DIR = os.environ.get('SCRIPT_DIR', os.path.join(BASE_DIR, 'install_agent_script'))
    
    # TLS configuration
    GRPC_USE_TLS = os.environ.get('GRPC_USE_TLS', 'false').lower() == 'true'
    GRPC_SERVER_KEY = os.path.join(CERT_DIR, 'server.key')
    GRPC_SERVER_CERT = os.path.join(CERT_DIR, 'server.crt')
    
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-key-please-change-in-production')
    DEBUG = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    PORT = int(os.environ.get('FLASK_PORT', '5000'))
    
    # API Key authentication
    API_KEY = os.environ.get('API_KEY', 'your-secret-api-key-here')
    API_KEY_HEADER = 'X-API-Key'
    
    # Elasticsearch configuration
    ELASTICSEARCH_HOST = os.environ.get('ELASTICSEARCH_HOST', 'localhost')
    ELASTICSEARCH_PORT = os.environ.get('ELASTICSEARCH_PORT', '9200')
    ELASTICSEARCH_USER = os.environ.get('ELASTICSEARCH_USER', '')
    ELASTICSEARCH_PASSWORD = os.environ.get('ELASTICSEARCH_PASSWORD', '')
    ELASTICSEARCH_USE_SSL = os.environ.get('ELASTICSEARCH_USE_SSL', 'false').lower() == 'true'
    ELASTICSEARCH_CA_PATH = os.environ.get('ELASTICSEARCH_CA_PATH', '')
    
    # ElastAlert configuration
    ELASTALERT_INDEX = os.environ.get('ELASTALERT_INDEX', 'elastalert_status')
    ELASTALERT_RULES_DIR = os.path.join(BASE_DIR, os.environ.get('ELASTALERT_RULES_DIR', 'elastalert/rules'))
    ELASTALERT_DOCKER = os.environ.get('ELASTALERT_DOCKER', 'true').lower() == 'true'
    ELASTALERT_CONTAINER = os.environ.get('ELASTALERT_CONTAINER', 'elastalert')
    
    # Auto-response configuration
    AUTO_RESPONSE_ENABLED = os.environ.get('AUTO_RESPONSE_ENABLED', 'true').lower() == 'true'
    AUTO_RESPONSE_INTERVAL = int(os.environ.get('AUTO_RESPONSE_INTERVAL', '30'))
    
    # Logging configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_DIR = os.environ.get('LOG_DIR', os.path.join(BASE_DIR, 'logs'))
    
    # gRPC server configuration
    GRPC_PORT = int(os.environ.get('GRPC_PORT', '50051'))
    
    # Agent configuration
    AGENT_HEARTBEAT_INTERVAL = int(os.environ.get('AGENT_HEARTBEAT_INTERVAL', '60'))
    AGENT_TIMEOUT = int(os.environ.get('AGENT_TIMEOUT', '600'))  # 10 minutes

    @classmethod
    def get_elasticsearch_config(cls):
        """Get Elasticsearch configuration as a dictionary for client initialization."""
        es_config = {
            'hosts': [f"{cls.ELASTICSEARCH_HOST}:{cls.ELASTICSEARCH_PORT}"]
        }
        
        # Add authentication if provided
        if cls.ELASTICSEARCH_USER and cls.ELASTICSEARCH_PASSWORD:
            es_config['http_auth'] = (cls.ELASTICSEARCH_USER, cls.ELASTICSEARCH_PASSWORD)
            
        # Add SSL settings if enabled
        if cls.ELASTICSEARCH_USE_SSL:
            es_config['use_ssl'] = True
            es_config['verify_certs'] = True
            if cls.ELASTICSEARCH_CA_PATH:
                es_config['ca_certs'] = cls.ELASTICSEARCH_CA_PATH
                
        return es_config


# Create a config instance for easy access
config = Config() 