import time
import threading
import logging
from concurrent import futures
import grpc

# Import the generated protobuf code
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from proto.generated import agent_pb2, agent_pb2_grpc

# Dictionary to store connected agents
connected_agents = {}

class AgentServicer(agent_pb2_grpc.AgentServiceServicer):
    """Implementation of AgentService service."""

    def SendMachineInfo(self, request, context):
        """Receives machine information from agents."""
        logging.info(f"Received machine info from agent: {request.hostname} ({request.ip_address})")
        
        # Store agent information
        agent_info = {
            'hostname': request.hostname,
            'ip_address': request.ip_address,
            'mac_address': request.mac_address,
            'os_version': request.os_version,
            'cpu_info': request.cpu_info,
            'total_memory': request.total_memory,
            'free_memory': request.free_memory,
            'agent_version': request.agent_version,
            'last_seen': time.time(),
            'disks': []
        }
        
        # Process disk information
        for disk in request.disks:
            disk_info = {
                'drive_letter': disk.drive_letter,
                'file_system': disk.file_system,
                'total_size': disk.total_size,
                'free_space': disk.free_space
            }
            agent_info['disks'].append(disk_info)
            logging.info(f"Disk {disk.drive_letter}: {disk.file_system}, "
                        f"Total: {disk.total_size} bytes, Free: {disk.free_space} bytes")
        
        # Use MAC address as a unique identifier for the agent
        connected_agents[request.mac_address] = agent_info
        
        return agent_pb2.MachineInfoResponse(
            success=True,
            message=f"Successfully received machine info from {request.hostname}"
        )


def get_connected_agents():
    """Returns a list of connected agents, removing those that haven't been seen in 10 minutes."""
    threshold = time.time() - 600  # 10 minutes
    agents = []
    
    for mac_addr, agent in list(connected_agents.items()):
        if agent['last_seen'] < threshold:
            del connected_agents[mac_addr]
        else:
            agents.append(agent)
    
    return agents


def serve(port=50051):
    """Start the gRPC server."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    agent_pb2_grpc.add_AgentServiceServicer_to_server(AgentServicer(), server)
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logging.info(f"gRPC server started on port {port}")
    return server


def start_grpc_server(port=50051):
    """Start the gRPC server in a separate thread."""
    logging.basicConfig(level=logging.INFO)
    server = serve(port)
    
    # Keep the thread alive
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        server.stop(0) 