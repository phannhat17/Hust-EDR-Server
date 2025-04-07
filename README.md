# HUST EDR Server

A comprehensive Endpoint Detection and Response (EDR) system consisting of a server and agent components. The system provides real-time security monitoring, command execution capabilities, and network isolation features.

## Project Structure

```
Hust-EDR-Server/
├── backend/           # Server component
│   ├── app/          # Server application code
│   ├── data/         # Data storage
│   └── proto/        # Protocol definitions
└── agent/            # Agent component
    ├── client/       # Agent client code
    ├── proto/        # Protocol definitions
    └── syscollector/ # System information collection
```

## Features

- Real-time agent status monitoring
- System metrics collection (CPU, memory, disk, network)
- Remote command execution
- File operations (delete)
- Process management (kill process, kill process tree)
- Network control (block IP, block URL, network isolation)
- Secure communication using gRPC
- Command result reporting and logging

## Prerequisites

- Python 3.8+
- Docker compose
- Node.js 16+ and npm & pnpm
- Elasticsearch instance
- ElastAlert container (optional, for rule execution)
- Go lang for agent compile or you can use the prebuilt executable available in the Releases section.
- Go 1.20+
- gRPC tools for Python
- Windows or Linux operating system

## Quick Start

1. Navigate to the backend directory
   ```
   cd backend
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

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details. 
