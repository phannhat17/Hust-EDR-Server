#!/bin/bash

# Create the directory if it doesn't exist
mkdir -p proto/generated

# Generate Python code from the proto file
python -m grpc_tools.protoc -I. --python_out=proto/generated --grpc_python_out=proto/generated proto/agent.proto

echo "Python gRPC code generated in proto/generated directory" 