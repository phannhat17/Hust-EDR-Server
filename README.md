# HUST EDR Server

A modern Endpoint Detection and Response (EDR) system with a beautiful React frontend and Flask backend.

## Features

- Real-time security alerts from ElastAlert
- Rule management for detection and alerting
- Modern UI built with React, TanStack Router, and Shadcn UI components
- Secure API integration

## Project Structure

- `agent/`: EDR agent
   - Updating

- `backend/`: Flask API server
  - Connects to Elasticsearch for alerts and rule management
  - Manages ElastAlert rules and configuration
  - Provides RESTful API endpoints

- `frontend/`: React application built with Vite
  - Modern UI with Shadcn components
  - TanStack Router for routing
  - TanStack Query for API data fetching
  - Type-safe integration with backend

## Setup and Installation

### Prerequisites

- Python 3.8+
- Docker compose
- Node.js 16+ and npm & pnpm
- Elasticsearch instance
- ElastAlert container (optional, for rule execution)
- Go lang for agent compile or you can use the prebuilt executable available in the Releases section.

### Backend Setup

1. Navigate to the backend directory
   ```
   cd backend
   ```

2. Create a virtual environment
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies
   ```
   pip install -r requirements.txt
   ```

4. Compile proto for python gRPC
   ```
   python -m grpc_tools.protoc -I../agent/proto --python_out=./app/grpc --grpc_python_out=./app/grpc ../agent/proto/agent.proto
   ```
   Then You need to modify the import line in the generated `backend/app/grpc/agent_pb2_grpc.py` file from:
   ```
   import agent_pb2 as agent__pb2
   ```
   To
   ```
   from . import agent_pb2 as agent__pb2
   ```
   This is necessary because the file is used within a Python package and requires a relative import.
   Or you can use this command with the current directory is `backend`
   ```
   sed -i 's/import agent_pb2 as agent__pb2/from . import agent_pb2 as agent__pb2/' ./app/grpc/agent_pb2_grpc.py
   ```


5. Configure environment variables in `.env` file (copy from `.env.example`)
   ```
   cp .env.example .env
   # Edit .env file with your configuration
   ```
   If your Elasticsearch instance uses a self-signed SSL certificate (which is the default for new Elasticsearch instances), you will need to manually copy that certificate into `backend/cacert.pem` file.

   > If you follow the default Elasticsearch installation method on Ubuntu, the certificate will be located at `/etc/elasticsearch/certs/http_ca.crt`


6. Run the Flask development server
   ```
   python server.py
   ```

> **Security Note**: The frontend is currently making direct API calls from the browser, which may lead to CORS policy violations and prevent successful communication with the backend. As a temporary workaround, CORS has been disabled to allow these requests. This will be addressed and properly configured in future versions (hopefully 😅).

### Frontend Setup

1. Navigate to the frontend directory
   ```
   cd frontend
   ```

2. Install dependencies
   ```
   pnpm install
   ```

3. Configure environment variables in `.env` file (copy from `.env.example`)
   ```
   cp .env.example .env
   # Edit .env file with your configuration
   ```

4. Run the development server
   ```
   npm run dev -- --host
   ``` 

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
