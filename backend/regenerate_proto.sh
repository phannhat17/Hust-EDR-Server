#!/bin/bash

# Make the script executable
chmod +x $0

# Create backup of existing gRPC files
echo "Creating backup of existing gRPC files..."
mkdir -p backup
cp app/grpc/agent_pb2*.py backup/ 2>/dev/null

# Remove existing gRPC generated files
echo "Removing existing gRPC generated files..."
rm -f app/grpc/agent_pb2.py app/grpc/agent_pb2_grpc.py

# Generate gRPC Python code from proto file
echo "Generating gRPC Python code from agent_commands.proto..."
source .venv/bin/activate
python3 -m grpc_tools.protoc -I. --python_out=./app/grpc --grpc_python_out=./app/grpc agent_commands.proto

# Fix import statement in the generated grpc file
echo "Fixing import statement in the generated grpc file..."
sed -i 's/import agent_commands_pb2 as agent_/from . import agent_pb2 as agent_/' app/grpc/agent_commands_pb2_grpc.py

# Rename the generated files to match expected imports
echo "Renaming generated files to match expected imports..."
mv app/grpc/agent_commands_pb2.py app/grpc/agent_pb2.py
mv app/grpc/agent_commands_pb2_grpc.py app/grpc/agent_pb2_grpc.py

echo "Proto files regenerated successfully!"
echo "You can now restart the server to apply the changes." 