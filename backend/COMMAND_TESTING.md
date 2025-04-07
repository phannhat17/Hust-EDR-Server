# Testing EDR Agent Commands

This document explains how to test the command functionality of the EDR agents.

## Prerequisites

- Python 3.8+
- Go 1.20+
- gRPC tools for Python: `pip install grpcio-tools`

## Setup

### 1. Update Proto Files

The agent's proto file has been updated to support command functionality. The new proto file is in `agent_commands.proto`.

To regenerate the Python gRPC code:

```bash
# Make the script executable
chmod +x regenerate_proto.sh

# Run the script
./regenerate_proto.sh
```

This will:
- Create backups of the existing gRPC files
- Generate new Python gRPC code from the updated proto file
- Fix import statements
- Rename files to match the expected imports

### 2. Start the Server

Start the EDR server:

```bash
python server.py
```

The server will listen for gRPC connections on the port specified in your configuration (default is 50051).

### 3. Build and Run the Agent

In a separate terminal, build and run the agent:

```bash
cd ../agent
go build -o edr-agent
./edr-agent -server=localhost:50051
```

The agent will register with the server and establish a command stream.

## Testing Commands

You can use the `send_command.py` script to send commands to the agent:

### List Connected Agents

```bash
python send_command.py list
```

This will display all registered agents with their IDs and status.

### Delete a File

```bash
python send_command.py delete --agent <agent_id> --path /path/to/file
```

This will send a command to delete the specified file.

### Kill a Process

```bash
python send_command.py kill --agent <agent_id> --pid 1234
```

This will send a command to kill the process with the specified PID.

### Kill a Process Tree

```bash
python send_command.py kill-tree --agent <agent_id> --pid 1234
```

This will send a command to kill the process tree with the specified root PID.

### Block an IP Address

```bash
python send_command.py block-ip --agent <agent_id> --ip 192.168.1.100
```

This will send a command to block the specified IP address.

### Block a URL

```bash
python send_command.py block-url --agent <agent_id> --url example.com
```

This will send a command to block the specified URL by adding it to the hosts file.

### Isolate Machine from Network

```bash
# Isolate with no exceptions
python send_command.py isolate --agent <agent_id>

# Isolate but allow specific IPs
python send_command.py isolate --agent <agent_id> --allowed-ips "192.168.1.1,8.8.8.8"
```

This will send a command to isolate the machine from the network, with optional exceptions for specific IPs.

### Restore Network Connectivity

```bash
python send_command.py restore --agent <agent_id>
```

This will send a command to restore network connectivity.

## Monitoring Command Results

The agent will execute the commands and report the results back to the server. The results will be stored in the `data/command_results.json` file.

To view the results, you can check the server logs or examine the JSON file:

```bash
cat data/command_results.json | python -m json.tool
```

## Troubleshooting

### Agent Not Receiving Commands

If the agent is not receiving commands, check the following:

1. Make sure the agent is registered with the server (check the server logs)
2. Make sure the agent has established a command stream (check the server logs)
3. Make sure the server is listening on the correct port

### Command Execution Errors

If the agent reports errors when executing commands, check the following:

1. Make sure the command parameters are correct
2. Make sure the agent has the necessary permissions
3. Check the agent logs for detailed error messages 