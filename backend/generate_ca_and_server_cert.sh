#!/bin/bash
# Generate a CA certificate and server certificate signed by the CA

set -e

CERT_DIR="./cert"
mkdir -p $CERT_DIR

echo "=== Generating CA Certificate ==="

# Generate CA private key
echo "Generating CA private key..."
openssl genrsa -out $CERT_DIR/ca.key 4096

# Generate CA certificate
echo "Generating CA certificate..."
openssl req -new -x509 -key $CERT_DIR/ca.key -sha256 -subj "/C=VN/ST=Hanoi/L=Hanoi/O=EDR-System/OU=Security/CN=EDR-CA" -days 3650 -out $CERT_DIR/ca.crt

echo "=== Generating Server Certificate ==="

# Generate server private key
echo "Generating server private key..."
openssl genrsa -out $CERT_DIR/server.key 4096

# Generate server certificate signing request
echo "Generating server certificate signing request..."
openssl req -new -key $CERT_DIR/server.key -out $CERT_DIR/server.csr -subj "/C=VN/ST=Hanoi/L=Hanoi/O=EDR-System/OU=Security/CN=edr-server"

# Create extensions file for server certificate
cat > $CERT_DIR/server.ext << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = localhost
DNS.2 = edr-server
IP.1 = 127.0.0.1
IP.2 = ::1
IP.3 = 192.168.133.145
EOF

# Generate server certificate signed by CA
echo "Generating server certificate signed by CA..."
openssl x509 -req -in $CERT_DIR/server.csr -CA $CERT_DIR/ca.crt -CAkey $CERT_DIR/ca.key -CAcreateserial -out $CERT_DIR/server.crt -days 365 -sha256 -extfile $CERT_DIR/server.ext

# Clean up temporary files
rm $CERT_DIR/server.csr $CERT_DIR/server.ext

echo "=== Certificate Generation Complete! ==="
echo "CA certificate: $CERT_DIR/ca.crt"
echo "CA private key: $CERT_DIR/ca.key"
echo "Server certificate: $CERT_DIR/server.crt"
echo "Server private key: $CERT_DIR/server.key"

# Set proper permissions
chmod 600 $CERT_DIR/ca.key $CERT_DIR/server.key
chmod 644 $CERT_DIR/ca.crt $CERT_DIR/server.crt

echo ""
echo "=== Certificate Information ==="
echo "CA Certificate:"
openssl x509 -in $CERT_DIR/ca.crt -text -noout | grep -A 2 "Subject:"

echo ""
echo "Server Certificate:"
openssl x509 -in $CERT_DIR/server.crt -text -noout | grep -A 2 "Subject:"
openssl x509 -in $CERT_DIR/server.crt -text -noout | grep -A 5 "Subject Alternative Name"

echo ""
echo "Certificates generated successfully!"
echo "Copy ca.crt to agent machines for certificate verification"

chmod +x $0 