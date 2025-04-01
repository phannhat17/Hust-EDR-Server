#!/bin/bash

echo "Building EDR Agent..."

# Check if protoc is installed
if ! command -v protoc &> /dev/null; then
    echo "Error: protoc (Protocol Buffers compiler) is not installed"
    echo "Please install it using your package manager or from https://github.com/protocolbuffers/protobuf/releases"
    exit 1
fi

# Check if Go is installed
if ! command -v go &> /dev/null; then
    echo "Error: Go is not installed"
    echo "Please install it from https://golang.org/dl/ or using your package manager"
    exit 1
fi

# Install protoc-gen-go and protoc-gen-go-grpc if not already installed
go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.6
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1

# Ensure Go bin directory is in PATH
export PATH=$PATH:$(go env GOPATH)/bin

# Generate Go code from Protocol Buffers definition
echo "Generating gRPC code..."
cd proto
protoc --go_out=. --go_opt=paths=source_relative --go-grpc_out=. --go-grpc_opt=paths=source_relative agent.proto
if [ $? -ne 0 ]; then
    echo "Error: Failed to generate gRPC code"
    exit 1
fi
cd ..

# Download dependencies
echo "Downloading dependencies..."
go mod tidy
if [ $? -ne 0 ]; then
    echo "Error: Failed to download dependencies"
    exit 1
fi

# Build agent for Windows
echo "Building agent executable for Windows..."
GOOS=windows GOARCH=amd64 go build -o edr-agent.exe .
if [ $? -ne 0 ]; then
    echo "Error: Build failed"
    exit 1
fi

echo "Build completed successfully."
echo "Windows executable: edr-agent.exe" 