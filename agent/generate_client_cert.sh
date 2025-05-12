#!/bin/bash
# Generate client certificates signed by the CA for mTLS

set -e

if [ -z "$1" ]; then
  echo "Usage: $0 <client-name>"
  echo "Example: $0 agent1"
  exit 1
fi

CLIENT_NAME="$1"
CERT_DIR="./cert"
CA_CERT_DIR="../backend/cert"  # Path to CA certificates

mkdir -p $CERT_DIR

# Check if CA exists
if [ ! -f "$CA_CERT_DIR/ca.crt" ] || [ ! -f "$CA_CERT_DIR/ca.key" ]; then
  echo "Error: CA certificate or key not found in $CA_CERT_DIR"
  echo "Please run the generate_ca_and_certs.sh script in the backend directory first."
  exit 1
fi

# Generate client private key
echo "Generating client private key for $CLIENT_NAME..."
openssl genrsa -out $CERT_DIR/${CLIENT_NAME}.key 4096

# Create client certificate signing request (CSR)
echo "Creating client certificate signing request..."
openssl req -new -key $CERT_DIR/${CLIENT_NAME}.key -out $CERT_DIR/${CLIENT_NAME}.csr \
  -subj "/CN=${CLIENT_NAME}"

# Create a config file for signing
cat > $CERT_DIR/${CLIENT_NAME}.ext << EOF
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
extendedKeyUsage = clientAuth
EOF

# Sign the client certificate with our CA
echo "Signing client certificate with CA..."
openssl x509 -req -in $CERT_DIR/${CLIENT_NAME}.csr -CA $CA_CERT_DIR/ca.crt -CAkey $CA_CERT_DIR/ca.key \
  -CAcreateserial -out $CERT_DIR/${CLIENT_NAME}.crt -days 365 \
  -extfile $CERT_DIR/${CLIENT_NAME}.ext

# Clean up CSR
rm $CERT_DIR/${CLIENT_NAME}.csr

# Copy CA certificate to client cert directory for convenience
cp $CA_CERT_DIR/ca.crt $CERT_DIR/

echo ""
echo "Client certificate generation complete!"
echo "Client certificate: $CERT_DIR/${CLIENT_NAME}.crt"
echo "Client key: $CERT_DIR/${CLIENT_NAME}.key"
echo "CA certificate: $CERT_DIR/ca.crt (copied for convenience)"
echo ""
echo "To use:"
echo "1. Run the agent with these arguments:"
echo "   --ca-cert=$CERT_DIR/ca.crt --client-cert=$CERT_DIR/${CLIENT_NAME}.crt --client-key=$CERT_DIR/${CLIENT_NAME}.key"
echo ""

chmod +x $0