"""
gRPC client implementation for server-side communication with agents.
"""

import grpc
import logging
from app.grpc import agent_pb2, agent_pb2_grpc
from app.config.config import config

# Set up logging
logger = logging.getLogger('app.grpc.client')

def create_grpc_client():
    """Create a gRPC client for agent communication.
    
    Returns:
        EDRClient: The client object for agent communication
    """
    # Create channel
    host = "localhost"
    port = config.GRPC_PORT
    
    # Set up credentials if TLS is enabled
    if config.GRPC_USE_TLS:
        try:
            # Load server certificate
            with open(config.GRPC_SERVER_CERT, 'rb') as f:
                cert = f.read()
            
            # Create credentials
            creds = grpc.ssl_channel_credentials(root_certificates=cert)
            channel = grpc.secure_channel(f"{host}:{port}", creds)
            logger.debug(f"Connected to gRPC server with TLS")
        except Exception as e:
            logger.error(f"Failed to create secure channel: {e}")
            logger.warning("Falling back to insecure channel")
            channel = grpc.insecure_channel(f"{host}:{port}")
    else:
        channel = grpc.insecure_channel(f"{host}:{port}")
        logger.debug(f"Connected to gRPC server without TLS")
    
    # Create client
    return EDRClient(channel)

class EDRClient:
    """Client for interacting with agents via the gRPC server."""
    
    def __init__(self, channel):
        """Initialize the client.
        
        Args:
            channel: gRPC channel
        """
        self.stub = agent_pb2_grpc.EDRServiceStub(channel)
        self.channel = channel
    
    def SendCommand(self, command_data):
        """Send a command to an agent.
        
        Args:
            command_data (dict): Command data with agent_id, command_type, and params
            
        Returns:
            dict: Result with success, message, and command_id
        """
        try:
            agent_id = command_data.get('agent_id')
            command_type = command_data.get('command_type')
            params = command_data.get('params', {})
            
            # Talk directly to the EDRServicer
            from app.grpc.server import EDRServicer
            
            # Get servicer instance
            servicer = self._get_servicer()
            if not servicer:
                return {
                    'success': False,
                    'message': 'Could not access EDR servicer',
                    'command_id': None
                }
            
            # Call the SendCommand method directly
            result = servicer.SendCommand(command_data, None)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in SendCommand: {e}")
            return {
                'success': False,
                'message': f"Error: {str(e)}",
                'command_id': None
            }
    
    def _get_servicer(self):
        """Get the EDRServicer instance from the server.
        
        Returns:
            EDRServicer: The servicer instance or None
        """
        try:
            from app.grpc.server import active_servicer
            return active_servicer
        except ImportError:
            logger.error("Could not import active_servicer from server")
            return None 