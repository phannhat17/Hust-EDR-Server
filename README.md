# HUST EDR Server

A comprehensive Endpoint Detection and Response (EDR) system consisting of a server and agent components. The system provides security monitoring, command execution capabilities, and network isolation features.

## Features

- System metrics collection (CPU, memory, disk, network)
- File operations (delete)
- Process management (kill process, kill process tree)
- Network control (block IP, block URL, network isolation)
- Secure communication using gRPC with bidirectional streaming
- Command result reporting and logging

## Prerequisites

- Python 3.8+
- Docker compose
- Node.js 16+ and npm & pnpm
- [Elasticsearch](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/installing-elasticsearch) and [Kibana](https://www.elastic.co/docs/deploy-manage/deploy/self-managed/install-kibana) instance.
- ElastAlert container (for rule execution)
- Go lang
- gRPC

## Quick Start

### Backend Setup

1. Install dependencies
   ```
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python -m grpc_tools.protoc -I../agent/proto --python_out=./app/grpc --grpc_python_out=./app/grpc ../agent/proto/agent.proto
   sed -i 's/import agent_pb2 as agent__pb2/from . import agent_pb2 as agent__pb2/' ./app/grpc/agent_pb2_grpc.py
   ```

2. Configure environment variables in `.env` file (copy from `.env.example`)
   ```
   cp .env.example .env
   # Edit .env file with your configuration
   ```

3. Run the development server
   ```
   python server.py
   ``` 

### Frontend Setup

> Demo UI [here](./frontend/README.md)

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
   npm run dev
   ``` 

### Agent Setup

1. Generate gRPC Code:
   ```bash
   protoc --go_out=. --go_opt=paths=source_relative --go-grpc_out=. --go-grpc_opt=paths=source_relative proto/agent.proto
   ```

2. Build the Agent:
   ```bash
   go mod tidy
   go build -o edr-agent.exe
   ```

3. Run agent:
   ```bash
   edr-agent.exe -server="IP:PORT"
   ```

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details. 
