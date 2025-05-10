#!/bin/bash
# Generate a self-signed certificate for the gRPC server

set -e

CERT_DIR="./cert"
# mkdir -p $CERT_DIR

# Generate server key and self-signed certificate
echo "Generating server certificate..."
openssl req -x509 -newkey rsa:4096 -keyout $CERT_DIR/server.key -out $CERT_DIR/server.crt -days 3650 -nodes -subj "/CN=edr-server" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

echo "Certificate generation complete!"
echo "Server certificate: $CERT_DIR/server.crt"
echo "Server key: $CERT_DIR/server.key"

chmod +x $0 