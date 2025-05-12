#!/bin/bash
# Install EDR Agent with mTLS certificate setup for Linux
# This script downloads all necessary certificates and configures the agent for mTLS

set -e

# Default parameters
SERVER_ADDRESS="localhost:50051"
CA_CERT_URL=""
CLIENT_CERT_URL=""
CLIENT_KEY_URL=""
AGENT_NAME="agent1"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --server)
      SERVER_ADDRESS="$2"
      shift 2
      ;;
    --ca-cert-url)
      CA_CERT_URL="$2"
      shift 2
      ;;
    --client-cert-url)
      CLIENT_CERT_URL="$2"
      shift 2
      ;;
    --client-key-url)
      CLIENT_KEY_URL="$2"
      shift 2
      ;;
    --agent-name)
      AGENT_NAME="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Directory setup
EDR_DIR="/opt/hust-edr"
CERT_DIR="$EDR_DIR/cert"
CONFIG_DIR="/etc/hust-edr"
CA_CERT_PATH="$CERT_DIR/ca.crt"
CLIENT_CERT_PATH="$CERT_DIR/$AGENT_NAME.crt"
CLIENT_KEY_PATH="$CERT_DIR/$AGENT_NAME.key"
CONFIG_PATH="$CONFIG_DIR/config.yaml"

# Create directories
mkdir -p "$EDR_DIR" "$CERT_DIR" "$CONFIG_DIR"

echo "Setting up directories..."
echo "EDR directory: $EDR_DIR"
echo "Certificate directory: $CERT_DIR"
echo "Configuration directory: $CONFIG_DIR"

# Function to download a file
download_file() {
  local url="$1"
  local output_file="$2"
  
  if [ -z "$url" ]; then
    echo "No URL provided for $output_file"
    return 1
  fi
  
  echo "Downloading $url to $output_file..."
  if command -v curl >/dev/null 2>&1; then
    curl -sSL "$url" -o "$output_file"
  elif command -v wget >/dev/null 2>&1; then
    wget -q "$url" -O "$output_file"
  else
    echo "Error: Neither curl nor wget is available. Please install one of them." >&2
    exit 1
  fi
  
  if [ $? -eq 0 ]; then
    echo "Download successful."
    return 0
  else
    echo "Download failed."
    return 1
  fi
}

# Try downloading certificates if URLs are provided
CA_SUCCESS=false
CLIENT_CERT_SUCCESS=false
CLIENT_KEY_SUCCESS=false

if [ -n "$CA_CERT_URL" ]; then
  if download_file "$CA_CERT_URL" "$CA_CERT_PATH"; then
    CA_SUCCESS=true
  fi
fi

if [ -n "$CLIENT_CERT_URL" ]; then
  if download_file "$CLIENT_CERT_URL" "$CLIENT_CERT_PATH"; then
    CLIENT_CERT_SUCCESS=true
  fi
fi

if [ -n "$CLIENT_KEY_URL" ]; then
  if download_file "$CLIENT_KEY_URL" "$CLIENT_KEY_PATH"; then
    CLIENT_KEY_SUCCESS=true
  fi
fi

# Check if we have everything for mTLS
MTLS_READY=false
if $CA_SUCCESS && $CLIENT_CERT_SUCCESS && $CLIENT_KEY_SUCCESS; then
  MTLS_READY=true
  echo "Successfully downloaded all certificates for mTLS"
else
  echo "Not all certificate files could be downloaded."
  
  # Check if we got at least the CA certificate
  if $CA_SUCCESS; then
    echo "CA certificate downloaded, will use it for server verification only."
  else
    echo "Failed to download CA certificate. TLS will not be enabled."
  fi
fi

# Create config.yaml
echo "Configuring EDR agent..."

# Start with base configuration
cat > "$CONFIG_PATH" << EOF
server_address: $SERVER_ADDRESS
agent_id: ""
data_dir: "$EDR_DIR/data"
version: "1.0.1"
EOF

# Add certificate configuration
if $CA_SUCCESS; then
  cat >> "$CONFIG_PATH" << EOF

# TLS Configuration
use_tls: true
ca_cert_path: "$CA_CERT_PATH"
EOF
  
  if $MTLS_READY; then
    cat >> "$CONFIG_PATH" << EOF

# mTLS Configuration
client_cert_path: "$CLIENT_CERT_PATH"
client_key_path: "$CLIENT_KEY_PATH"
EOF
  fi
else
  cat >> "$CONFIG_PATH" << EOF

# TLS Configuration
use_tls: false
EOF
fi

echo "Configuration written to $CONFIG_PATH"

# Set permissions
chmod 600 "$CONFIG_PATH"
if [ -f "$CLIENT_KEY_PATH" ]; then
  chmod 600 "$CLIENT_KEY_PATH"
fi

# Print configuration summary
echo
echo "EDR Agent Configuration Summary:"
echo "--------------------------------"
echo "Server Address: $SERVER_ADDRESS"

if $CA_SUCCESS; then
  echo "TLS Enabled: Yes"
  echo "CA Certificate: $CA_CERT_PATH"
  
  if $MTLS_READY; then
    echo "mTLS Enabled: Yes"
    echo "Client Certificate: $CLIENT_CERT_PATH"
    echo "Client Key: $CLIENT_KEY_PATH"
  else
    echo "mTLS Enabled: No (only server verification)"
  fi
else
  echo "TLS Enabled: No"
fi

echo
echo "Installation preparation completed. You can now run the agent with this configuration."
echo "./edr-agent -config=\"$CONFIG_PATH\"" 