# EDR Agent Backend Integration Guide

This document explains how to integrate the Windows EDR agent with your Flask backend.

## Overview

The Windows agent communicates with the EDR server using gRPC. To integrate it with your backend, you need to:

1. Set up a gRPC server in your Flask application
2. Implement the EDR service interface
3. Store and process the data received from agents

## Required Python Packages

Add these to your `requirements.txt`:

```
grpcio==1.54.0
grpcio-tools==1.54.0
protobuf==4.22.3
```

## Generate Python Code from Protocol Buffers

Copy the `agent.proto` file from `agent/proto/` to your backend directory, then generate the Python code:

```bash
cd backend
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. agent.proto
```

This will generate two files:
- `agent_pb2.py`: Contains message classes
- `agent_pb2_grpc.py`: Contains service classes

## Implementing the gRPC Server

Create a new file `grpc_server.py` in your backend:

```python
import time
import logging
import threading
from concurrent import futures

import grpc
import agent_pb2
import agent_pb2_grpc
from app.api.models.agent import Agent  # Your database model
from app.extensions import db

logger = logging.getLogger(__name__)

class EDRServicer(agent_pb2_grpc.EDRServiceServicer):
    """Implementation of EDRService service."""
    
    def RegisterAgent(self, request, context):
        """Handle agent registration."""
        logger.info(f"Agent registration from {request.hostname} ({request.ip_address})")
        
        # Check if agent already exists in the database
        agent = Agent.query.filter_by(agent_id=request.agent_id).first()
        
        if agent:
            # Update existing agent
            agent.hostname = request.hostname
            agent.ip_address = request.ip_address
            agent.mac_address = request.mac_address
            agent.username = request.username
            agent.os_version = request.os_version
            agent.agent_version = request.agent_version
            agent.last_seen = time.time()
        else:
            # Create new agent
            agent = Agent(
                agent_id=request.agent_id,
                hostname=request.hostname,
                ip_address=request.ip_address,
                mac_address=request.mac_address,
                username=request.username,
                os_version=request.os_version,
                agent_version=request.agent_version,
                registration_time=request.registration_time,
                last_seen=time.time()
            )
            db.session.add(agent)
            
        db.session.commit()
        
        # Return response
        return agent_pb2.RegisterResponse(
            server_message="Registration successful",
            success=True,
            assigned_id=agent.agent_id,
            server_time=int(time.time())
        )
    
    def UpdateStatus(self, request, context):
        """Handle status update from agent."""
        agent_id = request.agent_id
        
        # Find agent in the database
        agent = Agent.query.filter_by(agent_id=agent_id).first()
        
        if not agent:
            logger.warning(f"Status update from unknown agent: {agent_id}")
            return agent_pb2.StatusResponse(
                server_message="Unknown agent",
                acknowledged=False,
                server_time=int(time.time())
            )
        
        # Update agent status
        agent.last_seen = time.time()
        agent.status = request.status
        
        # Save metrics to database or event log
        # This depends on your schema design
        
        db.session.commit()
        
        # Return response
        return agent_pb2.StatusResponse(
            server_message="Status update received",
            acknowledged=True,
            server_time=int(time.time())
        )


def start_grpc_server(port=50051):
    """Start the gRPC server in a background thread."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    agent_pb2_grpc.add_EDRServiceServicer_to_server(EDRServicer(), server)
    
    # Listen on port 50051
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    
    logger.info(f"EDR gRPC server started on port {port}")
    
    return server
```

## Create Database Models

Create a model for storing agent information in `app/api/models/agent.py`:

```python
from app.extensions import db
from datetime import datetime

class Agent(db.Model):
    __tablename__ = 'agents'
    
    id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.String(64), unique=True, index=True)
    hostname = db.Column(db.String(255))
    ip_address = db.Column(db.String(45))
    mac_address = db.Column(db.String(17))
    username = db.Column(db.String(255))
    os_version = db.Column(db.String(255))
    agent_version = db.Column(db.String(20))
    registration_time = db.Column(db.Integer)
    last_seen = db.Column(db.Integer)
    status = db.Column(db.String(20), default='UNKNOWN')
    
    def __repr__(self):
        return f'<Agent {self.hostname}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'agent_id': self.agent_id,
            'hostname': self.hostname,
            'ip_address': self.ip_address,
            'mac_address': self.mac_address, 
            'username': self.username,
            'os_version': self.os_version,
            'agent_version': self.agent_version,
            'registration_time': datetime.fromtimestamp(self.registration_time).isoformat() if self.registration_time else None,
            'last_seen': datetime.fromtimestamp(self.last_seen).isoformat() if self.last_seen else None,
            'status': self.status
        }
```

## Integrate with Flask App

Modify your `app/__init__.py` or `wsgi.py` to start the gRPC server:

```python
from app.grpc_server import start_grpc_server

# Start gRPC server when the Flask app starts
grpc_server = None

def create_app(config_name=None):
    # ... existing Flask app creation code ...

    # Start gRPC server
    global grpc_server
    grpc_server = start_grpc_server()
    
    return app
```

## API Endpoints for Agent Management

Add API endpoints for querying agent information in `app/api/routes/agents.py`:

```python
from flask import Blueprint, jsonify, request
from app.api.models.agent import Agent
from app.extensions import db

agents_bp = Blueprint('agents', __name__)

@agents_bp.route('/agents', methods=['GET'])
def get_agents():
    """Get all registered agents."""
    agents = Agent.query.all()
    return jsonify({
        'agents': [agent.to_dict() for agent in agents]
    })

@agents_bp.route('/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """Get a specific agent by ID."""
    agent = Agent.query.filter_by(agent_id=agent_id).first_or_404()
    return jsonify(agent.to_dict())

# Register the blueprint in your app
# app.register_blueprint(agents_bp, url_prefix='/api')
```

## Security Considerations

For production use, consider implementing:

1. TLS encryption for gRPC communication
2. Authentication for agent verification
3. Agent identity verification using certificates or API keys 