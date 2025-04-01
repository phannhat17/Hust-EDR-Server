"""
Example gRPC server implementation for EDR agent communication.
This demonstrates how to implement the server side in Python for the Flask backend.
"""

import time
import logging
import signal
import threading
from concurrent import futures

import grpc
import agent_pb2
import agent_pb2_grpc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EDRServicer(agent_pb2_grpc.EDRServiceServicer):
    """Implementation of EDRService service."""
    
    def __init__(self):
        self.agents = {}  # Store registered agents
    
    def RegisterAgent(self, request, context):
        """Handle agent registration."""
        logger.info(f"Agent registration request from {request.hostname} ({request.ip_address})")
        
        # Log agent details
        logger.info(f"Agent details:")
        logger.info(f"  Agent ID: {request.agent_id}")
        logger.info(f"  Hostname: {request.hostname}")
        logger.info(f"  IP Address: {request.ip_address}")
        logger.info(f"  MAC Address: {request.mac_address}")
        logger.info(f"  Username: {request.username}")
        logger.info(f"  OS Version: {request.os_version}")
        logger.info(f"  Agent Version: {request.agent_version}")
        
        # Store agent information (in a real system, this would go to database)
        self.agents[request.agent_id] = {
            'info': request,
            'last_seen': time.time(),
            'status': 'REGISTERED'
        }
        
        # Return response
        return agent_pb2.RegisterResponse(
            server_message="Registration successful",
            success=True,
            assigned_id=request.agent_id,  # Use the same ID for simplicity
            server_time=int(time.time())
        )
    
    def UpdateStatus(self, request, context):
        """Handle status update from agent."""
        agent_id = request.agent_id
        
        if agent_id not in self.agents:
            logger.warning(f"Status update from unknown agent: {agent_id}")
            return agent_pb2.StatusResponse(
                server_message="Unknown agent",
                acknowledged=False,
                server_time=int(time.time())
            )
        
        # Update agent status
        self.agents[agent_id]['last_seen'] = time.time()
        self.agents[agent_id]['status'] = request.status
        
        # Log metrics
        logger.info(f"Status update from agent {agent_id}:")
        logger.info(f"  Status: {request.status}")
        logger.info(f"  CPU Usage: {request.system_metrics.cpu_usage:.1f}%")
        logger.info(f"  Memory Usage: {request.system_metrics.memory_usage:.1f}%")
        logger.info(f"  Uptime: {request.system_metrics.uptime} seconds")
        
        # Return response
        return agent_pb2.StatusResponse(
            server_message="Status update received",
            acknowledged=True,
            server_time=int(time.time())
        )


def serve():
    """Start the gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    agent_pb2_grpc.add_EDRServiceServicer_to_server(EDRServicer(), server)
    
    # Listen on port 50051
    server.add_insecure_port('[::]:50051')
    server.start()
    
    logger.info("EDR gRPC server started on port 50051")
    
    # Handle graceful shutdown
    stop_event = threading.Event()
    
    def signal_handler(sig, frame):
        logger.info("Shutting down server...")
        stop_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    stop_event.wait()
    
    # Stop the server
    server.stop(0)
    logger.info("Server stopped")


if __name__ == '__main__':
    # Generate gRPC code with:
    # python -m grpc_tools.protoc -I./proto --python_out=. --grpc_python_out=. ./proto/agent.proto
    serve() 