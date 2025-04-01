# Hust-EDR Windows Agent

This is a Windows agent for the Hust-EDR system, written in Go. The agent collects system information and sends it to the EDR management server via gRPC.

## Features

- Collects system information (hostname, IP address, MAC address, username, Windows version)
- Secure communication with the server using gRPC
- Periodic status updates
- Low overhead operation

## Requirements

- Go 1.20 or later
- Windows operating system
- Network connectivity to the EDR management server

## Building the Agent

### Generate gRPC code

Before building the agent, you need to generate the gRPC code from the Protocol Buffers definition:

```bash
cd proto
protoc --go_out=. --go_opt=paths=source_relative --go-grpc_out=. --go-grpc_opt=paths=source_relative agent.proto
cd ..
```

### Build the Agent

```bash
go build -o edr-agent.exe
```

## Running the Agent

```bash
# Basic usage
./edr-agent.exe

# Custom server address
./edr-agent.exe -server=edr-server.example.com:50051

# Custom update interval (in seconds)
./edr-agent.exe -interval=30
```

## Command-line Options

- `-server`: Server address in the format of host:port (default: localhost:50051)
- `-interval`: Status update interval in seconds (default: 60)

## Integration with EDR Server

The agent communicates with the EDR management server via gRPC. It registers with the server upon startup and sends periodic status updates.

To integrate the agent with the server:

1. Configure the server to accept gRPC connections on the specified port
2. Implement the EDRService interface on the server side

## Security

- All communication is encrypted using TLS
- The agent uses a machine-specific ID for authentication
- For production use, consider implementing additional authentication mechanisms 