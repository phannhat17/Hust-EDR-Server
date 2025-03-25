#!/bin/bash
# Script to set up ElastAlert 2 with Docker for the EDR System

set -e

# Default values
ELASTICSEARCH_HOST="192.168.133.134"
ELASTICSEARCH_PORT="9200"
ELASTICSEARCH_USER="elastic"
ELASTICSEARCH_PASSWORD="Z1ILMKtVy_3PFRU9Dlpm"
ELASTICSEARCH_USE_SSL="true"
RULES_DIR="elastalert_rules"

# Banner
echo "======================================================================"
echo "          EDR System - ElastAlert 2 Docker Setup Script                "
echo "======================================================================"
echo

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if the ElastAlert rules directory exists
if [ ! -d "$RULES_DIR" ]; then
    echo "Creating ElastAlert rules directory..."
    mkdir -p "$RULES_DIR"
fi

# Get parameters
read -p "Elasticsearch Host [$ELASTICSEARCH_HOST]: " input
ELASTICSEARCH_HOST=${input:-$ELASTICSEARCH_HOST}

read -p "Elasticsearch Port [$ELASTICSEARCH_PORT]: " input
ELASTICSEARCH_PORT=${input:-$ELASTICSEARCH_PORT}

read -p "Elasticsearch Username (leave empty if no auth) [$ELASTICSEARCH_USER]: " input
ELASTICSEARCH_USER=${input:-$ELASTICSEARCH_USER}

if [ -n "$ELASTICSEARCH_USER" ]; then
    read -s -p "Elasticsearch Password: " input
    echo
    ELASTICSEARCH_PASSWORD=${input:-$ELASTICSEARCH_PASSWORD}
fi

read -p "Use SSL for Elasticsearch? (true/false) [$ELASTICSEARCH_USE_SSL]: " input
ELASTICSEARCH_USE_SSL=${input:-$ELASTICSEARCH_USE_SSL}

# Create required directories
echo "Creating ElastAlert configuration directories..."
mkdir -p elastalert/config
mkdir -p elastalert/rules

# Copy sample rules
echo "Copying sample rules..."
cp -r "$RULES_DIR"/* elastalert/rules/ 2>/dev/null || echo "No sample rules to copy."

# Create ElastAlert config file
echo "Creating ElastAlert configuration file..."
cat > elastalert/config/config.yaml << EOL
# ElastAlert 2 Configuration

# Rule directory
rules_folder: rules

# How often ElastAlert will query Elasticsearch
run_every:
  seconds: 30

# Maximum number of alerts to send (0 = unlimited)
max_query_size: 10000

# How far back to check for alerts (1 day by default)
buffer_time:
  days: 1

# ES connection settings
es_host: $ELASTICSEARCH_HOST
es_port: $ELASTICSEARCH_PORT
EOL

# Add authentication if provided
if [ -n "$ELASTICSEARCH_USER" ]; then
    cat >> elastalert/config/config.yaml << EOL
es_username: $ELASTICSEARCH_USER
es_password: $ELASTICSEARCH_PASSWORD
EOL
fi

# Add SSL if enabled
if [ "$ELASTICSEARCH_USE_SSL" = "true" ]; then
    cat >> elastalert/config/config.yaml << EOL
use_ssl: true
verify_certs: true
ca_certs: /opt/cacert.pem
EOL
fi

# Add additional settings
cat >> elastalert/config/config.yaml << EOL
# Alert settings
writeback_index: elastalert_status
alert_time_limit:
  days: 7

run_every:
  seconds: 10

buffer_time:
  minutes: 15
EOL

# Pull the ElastAlert Docker image
echo "Pulling ElastAlert 2 Docker image..."
docker pull jertel/elastalert2

# Check if the container is already running
if docker ps -a | grep -q "elastalert"; then
    echo "Stopping existing ElastAlert container..."
    docker stop elastalert 2>/dev/null || true
    docker rm elastalert 2>/dev/null || true
fi

# Run ElastAlert in Docker
echo "Starting ElastAlert container..."
DOCKER_CMD="docker run --net="host" -d --name elastalert --restart=always \
-v $(pwd)/elastalert/config/config.yaml:/opt/elastalert/config.yaml \
-v $(pwd)/elastalert/rules:/opt/elastalert/rules \
-v $(pwd)/cacert.pem:/opt/cacert.pem \
jertel/elastalert2 --verbose"

echo "Running command: $DOCKER_CMD"
eval $DOCKER_CMD

# echo
# echo "ElastAlert 2 has been set up and started in Docker."
# echo "Configuration: $(pwd)/elastalert/config/config.yaml"
# echo "Rules directory: $(pwd)/elastalert/rules"
# echo 
# echo "To check the logs:"
# echo "  docker logs elastalert"
# echo
# echo "To stop ElastAlert:"
# echo "  docker stop elastalert"
# echo
# echo "To restart ElastAlert:"
# echo "  docker restart elastalert"
# echo
# echo "Make sure to update the .env file of your EDR application with these settings:"
# echo "  ELASTALERT_INDEX=elastalert_status"
# echo "  ELASTALERT_RULES_DIR=$(pwd)/elastalert/rules"
# echo "  ELASTALERT_DOCKER=true"
# echo "  ELASTALERT_CONTAINER=elastalert"
# echo
# echo "Setup complete!" 