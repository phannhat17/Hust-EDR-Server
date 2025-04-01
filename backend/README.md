# EDR Backend

This is the backend server for the Endpoint Detection and Response (EDR) system.

## Features

- RESTful API for managing alerts and rules
- gRPC server for agent communication
- Elasticsearch integration for alert storage
- Agent metrics collection and monitoring

## Getting Started

### Prerequisites

- Python 3.8+
- Elasticsearch (optional)
- Docker (optional, for ElastAlert)

### Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure environment variables in `.env` file (see `.env.example`)

### Running the Application

Use the single entry point to run the application:

```bash
python server.py
```

The server will start:
- Flask API server on port 5000 (default)
- gRPC server on port 50051 (default)

## Configuration

All configuration is now in a single place: `app/config/config.py`

Important configuration options:
- `PORT`: Flask server port (default: 5000)
- `GRPC_PORT`: gRPC server port (default: 50051)
- `API_KEY`: API key for securing API endpoints

## API Endpoints

- `/health`: Health check endpoint
- `/api/alerts`: Manage alerts
- `/api/rules`: Manage ElastAlert rules
- `/api/dashboard`: Dashboard data

## gRPC Services

The gRPC server provides:
- Agent registration
- Status updates
- System metrics collection

## Development

The application structure:

```
backend/
├── app/
│   ├── api/
│   │   ├── routes/        # API route handlers
│   │   └── models/        # Data models
│   ├── config/            # Configuration
│   ├── core/              # Core utilities
│   ├── grpc/              # gRPC server implementation
│   ├── __init__.py        # Flask application factory
│   └── elastalert.py      # ElastAlert client
├── data/                  # Agent data storage
├── rules/                 # ElastAlert rules
├── server.py              # Main entry point
└── requirements.txt       # Python dependencies
```

python -m grpc_tools.protoc -I../agent/proto --python_out=. --grpc_python_out=. ../agent/proto/agent.proto