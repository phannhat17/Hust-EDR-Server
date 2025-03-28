import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Application configuration
config = {
    'elasticsearch_host': os.getenv('ELASTICSEARCH_HOST', 'localhost'),
    'elasticsearch_port': os.getenv('ELASTICSEARCH_PORT', '9200'),
    'elasticsearch_user': os.getenv('ELASTICSEARCH_USER', ''),
    'elasticsearch_password': os.getenv('ELASTICSEARCH_PASSWORD', ''),
    'elasticsearch_use_ssl': os.getenv('ELASTICSEARCH_USE_SSL', 'false').lower() == 'true',
    'elasticsearch_ca_path': os.getenv('ELASTICSEARCH_CA_PATH', ''),
    'elastalert_index': os.getenv('ELASTALERT_INDEX', 'elastalert_status'),
    'elastalert_rules_dir': os.getenv('ELASTALERT_RULES_DIR', 'elastalert_rules'),
    'elastalert_docker': os.getenv('ELASTALERT_DOCKER', 'true').lower() == 'true',
    'elastalert_container': os.getenv('ELASTALERT_CONTAINER', 'elastalert')
} 