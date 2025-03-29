package client

import (
	"context"
	"fmt"
	"time"

	"github.com/hustonpi/edr-agent/internal/system"
	pb "github.com/hustonpi/edr-agent/proto"
	"google.golang.org/grpc"
	"google.golang.org/grpc/connectivity"
	"google.golang.org/grpc/credentials/insecure"
)

// Client represents a gRPC client for the EDR server
type Client struct {
	conn        *grpc.ClientConn
	agentClient pb.AgentServiceClient
	serverAddr  string
}

// NewClient creates a new gRPC client connection to the EDR server
func NewClient(serverAddr string) (*Client, error) {
	// Create a connection to the server with insecure credentials (should use TLS in production)
	conn, err := grpc.Dial(serverAddr, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("failed to connect to server: %v", err)
	}

	// Create a client for the AgentService
	agentClient := pb.AgentServiceClient(conn)

	return &Client{
		conn:        conn,
		agentClient: agentClient,
		serverAddr:  serverAddr,
	}, nil
}

// Close closes the client connection
func (c *Client) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// CheckConnection verifies if the agent is connected to the server
func (c *Client) CheckConnection() (bool, error) {
	state := c.conn.GetState()
	
	if state != connectivity.Ready && state != connectivity.Idle {
		return false, fmt.Errorf("connection not ready: %s", state.String())
	}
	
	// Try a quick ping by sending a minimal machine info just to verify connectivity
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	
	hostname, err := system.GetHostname()
	if err != nil {
		hostname = "unknown"
	}
	
	// Send a minimal request just to check connection
	req := &pb.MachineInfoRequest{
		Hostname:  hostname,
		Timestamp: time.Now().Unix(),
	}
	
	resp, err := c.agentClient.SendMachineInfo(ctx, req)
	if err != nil {
		return false, fmt.Errorf("failed to send test message: %v", err)
	}
	
	return resp.Success, nil
}

// SendMachineInfo sends system information to the EDR server
func (c *Client) SendMachineInfo() error {
	// Get machine information
	machineInfo, err := system.GetMachineInfo()
	if err != nil {
		return fmt.Errorf("failed to get machine info: %v", err)
	}

	// Convert to protobuf message
	req := &pb.MachineInfoRequest{
		Hostname:     machineInfo.Hostname,
		OsVersion:    machineInfo.OSVersion,
		CpuInfo:      machineInfo.CPUInfo,
		TotalMemory:  machineInfo.TotalMemory,
		FreeMemory:   machineInfo.FreeMemory,
		IpAddress:    machineInfo.IPAddress,
		MacAddress:   machineInfo.MACAddress,
		AgentVersion: machineInfo.AgentVersion,
		Timestamp:    machineInfo.Timestamp,
		Disks:        make([]*pb.DiskInfo, 0, len(machineInfo.Disks)),
	}

	// Add disk information
	for _, disk := range machineInfo.Disks {
		req.Disks = append(req.Disks, &pb.DiskInfo{
			DriveLetter: disk.DriveLetter,
			FileSystem:  disk.FileSystem,
			TotalSize:   disk.TotalSize,
			FreeSpace:   disk.FreeSpace,
		})
	}

	// Create context with timeout
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	// Send the request to the server
	resp, err := c.agentClient.SendMachineInfo(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to send machine info: %v", err)
	}

	if !resp.Success {
		return fmt.Errorf("server rejected machine info: %s", resp.Message)
	}

	return nil
} 