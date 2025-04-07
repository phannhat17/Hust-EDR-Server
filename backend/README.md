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