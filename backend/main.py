import threading
from app import app
from services.agent_grpc_service import start_grpc_server

if __name__ == "__main__":
    # Start the gRPC server in a separate thread
    grpc_thread = threading.Thread(
        target=start_grpc_server, 
        args=(50051,),  # gRPC server port
        daemon=True    # Make thread daemon so it exits when the main program exits
    )
    grpc_thread.start()
    
    # Start the Flask application
    app.run(host="0.0.0.0", port=5000, debug=True) 