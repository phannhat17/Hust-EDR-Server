# EDR Server Backend

The backend component of the Hust-EDR-Server provides the API, command handling, and agent management functionality for the EDR system.

## Key Components

### 1. Server API

RESTful API for the frontend to interact with the EDR system:
- Agent management
- Command dispatch
- Event monitoring
- Dashboard data

### 2. gRPC Service

Bi-directional communication with the EDR agents:
- Agent registration and heartbeat
- Command streaming to agents
- Status updates from agents
- Event reporting from agents

### 3. Data Storage

- Agent information
- Command results
- Events and alerts
- System configuration

## Real-time Command System

The system now features a true real-time command delivery mechanism that eliminates the need for disk-based command storage:

- Commands are sent directly to agents via active streaming connections
- For offline agents, commands are stored in memory until the agent reconnects
- Each agent maintains a long-running gRPC stream to receive commands immediately
- Command results are stored for historical reference

## Setup Instructions

### Prerequisites

- Python 3.8+
- pip
- virtualenv (recommended)

### Installation

1. Create and activate a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   # or
   .venv\Scripts\activate     # Windows
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Copy the configuration template:
   ```
   cp .env.example .env
   ```

4. Edit the `.env` file with your configuration settings

### Regenerating Protocol Buffers

If you update the protocol buffer definitions in `unified_edr.proto`, you need to regenerate the code:

```
./regenerate_proto.sh
```

### Running the Server

Start the backend server:

```
python server.py
```

## Testing Commands

1. List registered agents:
   ```
   python send_command.py list
   ```

2. Send a command to an agent:
   ```
   python send_command.py delete --agent [AGENT_ID] --path [FILE_PATH]
   ```

### Additional Commands

- `kill`: Kill a process by PID
- `kill-tree`: Kill a process and its children
- `block-ip`: Block an IP address
- `block-url`: Block access to a URL
- `isolate`: Isolate the machine from the network
- `restore`: Restore network connectivity

## Implementation Notes for Developers

### New Real-time Command Flow

1. **Frontend to Backend**:
   When a user sends a command from the frontend, it calls the `/api/commands/send` endpoint, which in turn calls the gRPC `SendCommand` method.

2. **Command Processing**:
   - The server checks if the target agent has an active command stream
   - If active, the command is stored in the agent's pending commands list
   - When the agent reconnects its stream, all pending commands are sent immediately

3. **Agent Processing**:
   - The agent maintains a continuous gRPC stream with the server
   - When a new command is received, it is processed immediately
   - Results are sent back to the server and stored for historical reference

### Advantages of the New System

- **Real-time Delivery**: Commands are delivered to agents without delay
- **No Disk I/O Overhead**: Commands are kept in memory until delivered
- **Better Synchronization**: The server knows exactly which agents have received which commands
- **Improved Reliability**: Command state is always clear and consistent

## Features

- Agent registration and management
- Real-time status monitoring
- Command execution and result reporting
- System metrics collection
- Secure gRPC communication

## Directory Structure

```
backend/
├── app/                # Application code
│   ├── grpc/          # gRPC server implementation
│   └── config/        # Configuration files
├── data/              # Data storage
│   ├── agents.json    # Registered agents
│   ├── commands.json  # Pending commands
│   └── command_results.json  # Command execution results
├── agent_commands.proto  # Protocol definitions
├── send_command.py    # Command-line tool
└── server.py          # Server entry point
```

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

# Auto-Response

The EDR system now features a simplified auto-response implementation that automatically executes commands on agents when specific security alerts are detected.

## How It Works

1. ElastAlert generates alerts with special `auto_response_*` fields
2. The EDR backend processes these alerts and performs the specified actions
3. Each alert is processed exactly once (no retries)
4. Alert status is updated in Elasticsearch based on action results

## Key Files

- `backend/app/elastalert_auto_response.py`: Core auto-response handler
- `backend/app/elastalert.py`: Alert processing logic
- `backend/elastalert_modules/enhance_auto_response.py`: Example enhancement for adding auto-response fields to alerts
- `backend/docs/AUTO_RESPONSE_GUIDE.md`: Comprehensive documentation

## Required Fields

For an alert to trigger an auto-response, it must include the following field:

- `auto_response_type`: Action type (e.g., DELETE_FILE, KILL_PROCESS)

Other required fields depend on the action type. See `AUTO_RESPONSE_GUIDE.md` for details.

## Configuration

Auto-response settings can be configured in the `.env` file:

```
AUTO_RESPONSE_ENABLED=true
AUTO_RESPONSE_INTERVAL=30
```

## Testing Auto-Response

Use the API endpoint to test auto-response manually:

```
POST /api/auto-response/test

{
  "rule_name": "Test Rule",
  "auto_response_type": "DELETE_FILE",
  "auto_response_file_path": "/path/to/file.txt",
  "host": {
    "hostname": "example-host-01"
  }
}
```

# Logging System

The EDR server now features a modular logging system that writes different types of logs to separate files. This makes debugging and monitoring much easier.

## Log Files

- `app.log`: Main application logs
- `api.log`: API endpoint access and operations
- `grpc.log`: gRPC server interactions with agents
- `elastalert.log`: ElastAlert rule processing and alerts
- `auto_response.log`: Auto-response actions and results
- `db.log`: Database interactions
- `error.log`: All error-level logs from all components

## Configuration

Configure the logging system in your `.env` file:

```
LOG_LEVEL=INFO
LOG_DIR=logs
```

See [LOGGING.md](docs/LOGGING.md) for detailed documentation.