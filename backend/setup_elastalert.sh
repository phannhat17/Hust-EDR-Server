#!/bin/bash
# Run ElastAlert in Docker
echo "Starting ElastAlert container..."
DOCKER_CMD="docker run --net="host" -d --name elastalert --restart=always \
-v $(pwd)/elastalert/config/config.yaml:/opt/elastalert/config.yaml \
-v $(pwd)/elastalert/rules:/opt/elastalert/rules \
-v $(pwd)/cert/elasticsearch.crt:/opt/elasticsearch.crt \
jertel/elastalert2 --verbose"

echo "Running command: $DOCKER_CMD"
eval $DOCKER_CMD

echo
echo "ElastAlert 2 has been set up and started in Docker."
echo "Configuration: $(pwd)/elastalert/config/config.yaml"
echo "Rules directory: $(pwd)/elastalert/rules/"
echo 
echo "Setup complete!" 