#!/bin/bash

# Make the script executable
chmod +x $0

# Remove existing gRPC generated files
echo "Removing existing gRPC generated files..."
rm -f app/grpc/agent_pb2.py app/grpc/agent_pb2_grpc.py

# Generate gRPC Python code from proto file
echo "Generating gRPC Python code from agent_commands.proto..."
source .venv/bin/activate
python3 -m grpc_tools.protoc -I../agent/proto --python_out=./app/grpc --grpc_python_out=./app/grpc ../agent/proto/agent.proto

# Fix import statement in the generated grpc file
echo "Fixing import statement in the generated grpc file..."
sed -i 's/import agent_pb2 as agent__pb2/from . import agent_pb2 as agent__pb2/' ./app/grpc/agent_pb2_grpc.py

echo "Proto files regenerated successfully!"
echo "You can now restart the server to apply the changes." 