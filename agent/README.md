# HUST EDR Agent

The agent component of the HUST EDR system, providing system monitoring, command execution, and network control capabilities.

## Features

- System information collection
- Real-time status reporting
- Command execution
- File operations
- Process management
- Network control
- Secure gRPC communication

## Directory Structure

```
agent/
├── client/           # gRPC client implementation
├── proto/           # Protocol definitions
├── syscollector/    # System information collection
├── config/          # Configuration
└── main.go          # Agent entry point
```

## Requirements

- Go 1.20+
- Windows or Linux operating system
- Administrative privileges for certain operations

## Building

1. **Generate gRPC Code**:
   ```bash
   protoc --go_out=. --go_opt=paths=source_relative \
       --go-grpc_out=. --go-grpc_opt=paths=source_relative \
       proto/agent.proto
   ```

2. **Build the Agent**:
   ```bash
   go mod tidy
   go build -o edr-agent
   ```

## Usage

Run the agent with the following options:

```bash
./edr-agent.exe [options]
```

Options:
- `-server`: Server address (default: localhost:50051)
- `-interval`: Status update interval in seconds (default: 60)
- `-tls`: Enable TLS (default: false)
- `-insecure`: Skip TLS verification (default: false)

Example:
```bash
./edr-agent.exe -server=localhost:50051 -interval=30
```

## Supported Commands

The agent can execute the following commands:

1. **File Operations**:
   - Delete file

2. **Process Management**:
   - Kill process
   - Kill process tree

3. **Network Control**:
   - Block IP address
   - Block URL
   - Network isolation
   - Network restoration

## System Information Collection

The agent collects:
- CPU usage
- Memory usage
- Disk usage
- Network traffic
- System information (hostname, OS, etc.)

## Security

- All communication with the server is done via gRPC
- TLS support for secure communication
- Administrative privileges required for certain operations

## Protocol

The agent uses gRPC for communication with the server. See `proto/agent.proto` for the protocol definition.

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details. 