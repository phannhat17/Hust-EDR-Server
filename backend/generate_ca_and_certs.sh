#!/bin/bash
# Generate a CA and properly signed server certificates for mTLS

set -e

CERT_DIR="./cert"
mkdir -p $CERT_DIR

# Generate CA key and certificate
echo "Generating CA certificate..."
openssl genrsa -out $CERT_DIR/ca.key 4096
openssl req -x509 -new -nodes -key $CERT_DIR/ca.key -sha256 -days 3650 -out $CERT_DIR/ca.crt \
  -subj "/CN=EDR-Root-CA" \
  -addext "basicConstraints=critical,CA:true"

# Generate server private key
echo "Generating server private key..."
openssl genrsa -out $CERT_DIR/server.key 4096

# Create server certificate signing request (CSR)
echo "Creating server certificate signing request..."
openssl req -new -key $CERT_DIR/server.key -out $CERT_DIR/server.csr \
  -subj "/CN=edr-server" \
  -addext "subjectAltName=DNS:localhost,DNS:edr-server,IP:127.0.0.1"

# Create a config file for signing
cat > $CERT_DIR/server.ext << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = edr-server
IP.1 = 127.0.0.1
EOF

# Sign the server certificate with our CA
echo "Signing server certificate with CA..."
openssl x509 -req -in $CERT_DIR/server.csr -CA $CERT_DIR/ca.crt -CAkey $CERT_DIR/ca.key \
  -CAcreateserial -out $CERT_DIR/server.crt -days 365 \
  -extfile $CERT_DIR/server.ext

# Clean up CSR
rm $CERT_DIR/server.csr

echo ""
echo "Certificate generation complete!"
echo "CA certificate: $CERT_DIR/ca.crt"
echo "CA key: $CERT_DIR/ca.key"
echo "Server certificate: $CERT_DIR/server.crt"
echo "Server key: $CERT_DIR/server.key"
echo ""
echo "To use:"
echo "1. Configure the server to use $CERT_DIR/server.crt and $CERT_DIR/server.key"
echo "2. Distribute $CERT_DIR/ca.crt to clients for server verification"
echo ""

chmod +x $0 