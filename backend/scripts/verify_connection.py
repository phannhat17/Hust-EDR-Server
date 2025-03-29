#!/usr/bin/env python3
import grpc
import sys
import os
import time

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the generated protobuf code
from proto.generated import agent_pb2, agent_pb2_grpc

def check_server_connection(server_address='localhost:50051'):
    """Check if the gRPC server is running and accepting connections."""
    print(f"Checking connection to gRPC server at {server_address}...")
    
    try:
        # Create an insecure channel
        channel = grpc.insecure_channel(server_address)
        
        # Set a deadline of 5 seconds
        try:
            grpc.channel_ready_future(channel).result(timeout=5)
        except grpc.FutureTimeoutError:
            print("❌ Error: gRPC server is not available or not responding")
            return False
        
        # Create a stub
        stub = agent_pb2_grpc.AgentServiceStub(channel)
        
        # Create a simple request
        request = agent_pb2.MachineInfoRequest(
            hostname="test-server",
            timestamp=int(time.time())
        )
        
        # Send the request
        response = stub.SendMachineInfo(request, timeout=5)
        
        # Check the response
        if response.success:
            print(f"✅ Successfully connected to gRPC server: {response.message}")
            return True
        else:
            print(f"❌ Connection test failed: {response.message}")
            return False
            
    except grpc.RpcError as e:
        print(f"❌ RPC error: {e.code()}: {e.details()}")
        return False
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    # Get server address from command line arguments or use default
    server_address = sys.argv[1] if len(sys.argv) > 1 else 'localhost:50051'
    
    if check_server_connection(server_address):
        sys.exit(0)
    else:
        sys.exit(1) 