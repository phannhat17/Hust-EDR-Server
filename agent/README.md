# EDR Agent

This is the EDR (Endpoint Detection and Response) agent for Windows systems. The agent collects system information and sends it to the EDR server using gRPC.

## Features

- Collects Windows machine information (hostname, OS, CPU, memory, disk, network)
- Communicates with the EDR server using gRPC
- Periodically sends machine information updates

## Prerequisites

- Go 1.21 or later
- Protocol Buffers compiler (protoc)
- Go plugins for Protocol Buffers:
  - `go install google.golang.org/protobuf/cmd/protoc-gen-go@latest`
  - `go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest`

## Building

### Windows

Run the build script:

```
build_windows.bat
```

This will generate the gRPC code and build the agent executable.

## Running

```
edr-agent.exe --server <server-address> --interval <update-interval>
```

Options:
- `--server`: EDR server address (default: "localhost:50051")
- `--interval`: Interval between machine info updates (default: 5m)

Example:
```
edr-agent.exe --server edr-server.example.com:50051 --interval 1m
```

## Verifying Connection

To verify that the agent can connect to the server, use the `--check` flag:

```
edr-agent.exe --server <server-address> --check
```

This will:
1. Try to establish a connection to the server
2. Send a minimal machine info request
3. Print the result and exit with code 0 if successful, 1 if failed

For testing, you can use the provided test server:

```
go run cmd/server/main.go
```

Then verify the connection with:

```
go run cmd/agent/main.go --check
```

## Development

### Project Structure

- `cmd/agent/`: Main application entry point
- `cmd/server/`: Test server for development
- `internal/system/`: System information collection
- `internal/client/`: gRPC client implementation
- `proto/`: Protocol Buffers definitions

### Generating gRPC Code

```
protoc --go_out=. --go_opt=paths=source_relative --go-grpc_out=. --go-grpc_opt=paths=source_relative proto/agent.proto
```