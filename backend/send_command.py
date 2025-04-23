#!/usr/bin/env python3
"""
Command-line tool to send commands to EDR agents.
"""

import os
import sys
import time
import uuid
import argparse
import logging
import json
import grpc

# Add the directory containing this script to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the generated gRPC modules
from app.grpc import agent_pb2, agent_pb2_grpc

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_client():
    """Create a gRPC client connection to the server."""
    channel = grpc.insecure_channel('localhost:50051')
    return agent_pb2_grpc.EDRServiceStub(channel)

def list_agents():
    """List all registered agents."""
    try:
        # Create client
        client = create_client()
        
        # Get list of agents from server
        request = agent_pb2.ListAgentsRequest()
        response = client.ListAgents(request)
        
        # Print agent information
        print("\nRegistered Agents:")
        print("==================")
        
        for agent in response.agents:
            print(f"ID: {agent.agent_id}")
            print(f"Hostname: {agent.hostname}")
            print(f"IP Address: {agent.ip_address}")
            print(f"Status: {agent.status}")
            print(f"Last Seen: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(agent.last_seen))}")
            print("------------------")
        
        return True
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        return False

def send_command(agent_id, command_type, params=None, priority=1, timeout=60):
    """Send a command to an agent."""
    try:
        # Create client
        client = create_client()
        
        # Create command
        command_id = str(uuid.uuid4())
        timestamp = int(time.time())
        
        command = agent_pb2.Command(
            command_id=command_id,
            agent_id=agent_id,
            timestamp=timestamp,
            type=command_type,
            params={} if params is None else params,
            priority=priority,
            timeout=timeout
        )
        
        # Send command to server
        request = agent_pb2.SendCommandRequest(command=command)
        response = client.SendCommand(request)
        
        if response.success:
            print(f"\nCommand sent successfully:")
            print(f"Command ID: {command_id}")
            print(f"Agent ID: {agent_id}")
            print(f"Command Type: {agent_pb2.CommandType.Name(command_type)}")
            print(f"Parameters: {json.dumps(params, indent=2) if params else '{}'}")
            print(f"Priority: {priority}")
            print(f"Timeout: {timeout} seconds")
            return True
        else:
            logger.error(f"Failed to send command: {response.message}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        return False

def main():
    """Main entry point for the command-line tool."""
    parser = argparse.ArgumentParser(description="EDR Agent Command Tool")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List agents command
    list_parser = subparsers.add_parser("list", help="List connected agents")
    
    # Delete file command
    delete_parser = subparsers.add_parser("delete", help="Delete a file")
    delete_parser.add_argument("--agent", required=True, help="Agent ID")
    delete_parser.add_argument("--path", required=True, help="Path to the file to delete")
    delete_parser.add_argument("--timeout", type=int, default=60, help="Command timeout in seconds")
    
    # Kill process command
    kill_parser = subparsers.add_parser("kill", help="Kill a process")
    kill_parser.add_argument("--agent", required=True, help="Agent ID")
    kill_parser.add_argument("--pid", required=True, help="Process ID to kill")
    kill_parser.add_argument("--timeout", type=int, default=60, help="Command timeout in seconds")
    
    # Kill process tree command
    kill_tree_parser = subparsers.add_parser("kill-tree", help="Kill a process tree")
    kill_tree_parser.add_argument("--agent", required=True, help="Agent ID")
    kill_tree_parser.add_argument("--pid", required=True, help="Root process ID to kill")
    kill_tree_parser.add_argument("--timeout", type=int, default=60, help="Command timeout in seconds")
    
    # Block IP command
    block_ip_parser = subparsers.add_parser("block-ip", help="Block an IP address")
    block_ip_parser.add_argument("--agent", required=True, help="Agent ID")
    block_ip_parser.add_argument("--ip", required=True, help="IP address to block")
    block_ip_parser.add_argument("--timeout", type=int, default=60, help="Command timeout in seconds")
    
    # Block URL command
    block_url_parser = subparsers.add_parser("block-url", help="Block a URL")
    block_url_parser.add_argument("--agent", required=True, help="Agent ID")
    block_url_parser.add_argument("--url", required=True, help="URL to block")
    block_url_parser.add_argument("--timeout", type=int, default=60, help="Command timeout in seconds")
    
    # Network isolate command
    isolate_parser = subparsers.add_parser("isolate", help="Isolate machine from network")
    isolate_parser.add_argument("--agent", required=True, help="Agent ID")
    isolate_parser.add_argument("--allowed-ips", help="Comma-separated list of IPs to allow")
    isolate_parser.add_argument("--timeout", type=int, default=120, help="Command timeout in seconds")
    
    # Network restore command
    restore_parser = subparsers.add_parser("restore", help="Restore network connectivity")
    restore_parser.add_argument("--agent", required=True, help="Agent ID")
    restore_parser.add_argument("--timeout", type=int, default=60, help="Command timeout in seconds")
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_agents()
    
    elif args.command == "delete":
        send_command(
            args.agent,
            agent_pb2.CommandType.DELETE_FILE,
            {"path": args.path},
            timeout=args.timeout
        )
    
    elif args.command == "kill":
        send_command(
            args.agent,
            agent_pb2.CommandType.KILL_PROCESS,
            {"pid": args.pid},
            timeout=args.timeout
        )
    
    elif args.command == "kill-tree":
        send_command(
            args.agent,
            agent_pb2.CommandType.KILL_PROCESS_TREE,
            {"pid": args.pid},
            timeout=args.timeout
        )
    
    elif args.command == "block-ip":
        send_command(
            args.agent,
            agent_pb2.CommandType.BLOCK_IP,
            {"ip": args.ip},
            timeout=args.timeout
        )
    
    elif args.command == "block-url":
        send_command(
            args.agent,
            agent_pb2.CommandType.BLOCK_URL,
            {"url": args.url},
            timeout=args.timeout
        )
    
    elif args.command == "isolate":
        params = {}
        if args.allowed_ips:
            params["allowed_ips"] = args.allowed_ips
            
        send_command(
            args.agent,
            agent_pb2.CommandType.NETWORK_ISOLATE,
            params,
            timeout=args.timeout
        )
    
    elif args.command == "restore":
        send_command(
            args.agent,
            agent_pb2.CommandType.NETWORK_RESTORE,
            {},
            timeout=args.timeout
        )
    
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main() 