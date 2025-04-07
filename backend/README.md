# HUST EDR Server Backend

The server component of the HUST EDR system, providing agent management, command execution, and status monitoring capabilities.

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

## Setup

1. **Install Dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Generate gRPC Code**:
   ```bash
   chmod +x regenerate_proto.sh
   ./regenerate_proto.sh
   ```

3. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

## Usage

1. **Start the Server**:
   ```bash
   python server.py
   ```

2. **Send Commands**:
   ```bash
   # List connected agents
   python send_command.py list

   # Delete a file
   python send_command.py delete --agent <agent_id> --path /path/to/file

   # Kill a process
   python send_command.py kill --agent <agent_id> --pid <process_id>

   # Block an IP
   python send_command.py block-ip --agent <agent_id> --ip <ip_address>

   # Isolate network
   python send_command.py isolate --agent <agent_id>
   ```

## Available Commands

- `list`: List all connected agents
- `delete`: Delete a file
- `kill`: Kill a process
- `kill-tree`: Kill a process and its children
- `block-ip`: Block an IP address
- `block-url`: Block a URL
- `isolate`: Isolate machine from network
- `restore`: Restore network connectivity

## Data Storage

The server stores data in JSON files:
- `data/agents.json`: Registered agent information
- `data/commands.json`: Pending commands
- `data/command_results.json`: Command execution results

## Protocol

The server uses gRPC for communication with agents. See `agent_commands.proto` for the protocol definition.

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.