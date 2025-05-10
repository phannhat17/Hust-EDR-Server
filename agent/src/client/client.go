package client

import (
	"context"
	"fmt"
	"io"
	"log"
	"math"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"crypto/tls"

	pb "agent/proto"
)

// EDRClient represents a client for communicating with the EDR server
type EDRClient struct {
	serverAddress string
	agentID       string
	conn          *grpc.ClientConn
	edrClient     pb.EDRServiceClient
	cmdHandler    *CommandHandler
	agentVersion  string
	dataDir       string
	useTLS        bool
}

// NewEDRClient creates a new EDR client
func NewEDRClient(serverAddress, agentID string, dataDir string) (*EDRClient, error) {
	return NewEDRClientWithTLS(serverAddress, agentID, dataDir, false)
}

// NewEDRClientWithTLS creates a new EDR client with TLS enabled
func NewEDRClientWithTLS(serverAddress, agentID string, dataDir string, useTLS bool) (*EDRClient, error) {
	var conn *grpc.ClientConn
	var err error

	if useTLS {
		// Create the credentials and skip certificate verification for self-signed certs
		creds := credentials.NewTLS(&tls.Config{
			InsecureSkipVerify: true, // Skip certificate verification for testing
		})

		conn, err = grpc.Dial(serverAddress, grpc.WithTransportCredentials(creds))
		if err != nil {
			return nil, fmt.Errorf("failed to connect to server with TLS: %v", err)
		}
		
		log.Printf("Connected to server %s with TLS encryption (insecure mode)", serverAddress)
	} else {
		// Connect without TLS (insecure)
		conn, err = grpc.Dial(serverAddress, grpc.WithTransportCredentials(insecure.NewCredentials()))
		if err != nil {
			return nil, fmt.Errorf("failed to connect to server: %v", err)
		}
		
		log.Printf("Connected to server %s without encryption (not recommended)", serverAddress)
	}

	// Create client
	client := &EDRClient{
		serverAddress: serverAddress,
		agentID:       agentID,
		conn:          conn,
		edrClient:     pb.NewEDRServiceClient(conn),
		agentVersion:  "1.0.0", // Default version
		dataDir:       dataDir,
		useTLS:        useTLS,
	}

	// Create command handler
	client.cmdHandler = NewCommandHandler(client)

	return client, nil
}

// SetAgentVersion sets the agent version
func (c *EDRClient) SetAgentVersion(version string) {
	c.agentVersion = version
}

// Register registers the agent with the server
func (c *EDRClient) Register(ctx context.Context) (*AgentInfo, error) {
	// Gather system information
	hostname, err := getHostname()
	if err != nil {
		return nil, fmt.Errorf("failed to get hostname: %v", err)
	}

	ipAddress, err := getIPAddress()
	if err != nil {
		log.Printf("Warning: failed to get IP address: %v", err)
		ipAddress = "unknown"
	}

	macAddress, err := getMACAddress()
	if err != nil {
		log.Printf("Warning: failed to get MAC address: %v", err)
		macAddress = "unknown"
	}

	username, err := getUsername()
	if err != nil {
		log.Printf("Warning: failed to get username: %v", err)
		username = "unknown"
	}

	osVersion, err := getOSVersion()
	if err != nil {
		log.Printf("Warning: failed to get OS version: %v", err)
		osVersion = "unknown"
	}

	// Create registration request
	req := &pb.RegisterRequest{
		AgentId:         c.agentID,
		Hostname:        hostname,
		IpAddress:       ipAddress,
		MacAddress:      macAddress,
		Username:        username,
		OsVersion:       osVersion,
		AgentVersion:    c.agentVersion,
		RegistrationTime: time.Now().Unix(),
	}

	// Send registration request
	resp, err := c.edrClient.RegisterAgent(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("failed to register with server: %v", err)
	}

	// If server assigned a new ID, update our agent ID
	if resp.AssignedId != "" {
		c.agentID = resp.AssignedId
	}

	// Return agent info
	return &AgentInfo{
		AgentID:       c.agentID,
		Hostname:      hostname,
		IPAddress:     ipAddress,
		MACAddress:    macAddress,
		Username:      username,
		OSVersion:     osVersion,
		AgentVersion:  c.agentVersion,
		RegisteredAt:  time.Now(),
		ServerMessage: resp.ServerMessage,
	}, nil
}

// UpdateStatus sends a status update to the server
func (c *EDRClient) UpdateStatus(ctx context.Context, status string, metrics map[string]float64) error {
	// Create system metrics
	sysMetrics := &pb.SystemMetrics{
		CpuUsage:    metrics["cpu_usage"],
		MemoryUsage: metrics["memory_usage"],
		Uptime:      int64(metrics["uptime"]),
	}

	// Create status request
	req := &pb.StatusRequest{
		AgentId:       c.agentID,
		Timestamp:     time.Now().Unix(),
		Status:        status,
		SystemMetrics: sysMetrics,
	}

	// Send status update
	resp, err := c.edrClient.UpdateStatus(ctx, req)
	if err != nil {
		return fmt.Errorf("failed to update status: %v", err)
	}

	if !resp.Acknowledged {
		return fmt.Errorf("status update not acknowledged: %s", resp.ServerMessage)
	}

	return nil
}

// StartCommandStream starts a stream to receive commands from the server
func (c *EDRClient) StartCommandStream(ctx context.Context) {
	// Track failed connection attempts for backoff strategy
	consecutiveFailures := 0
	maxBackoff := 60 * time.Second
	
	for {
		select {
		case <-ctx.Done():
			log.Println("Command stream stopped due to context cancellation")
			return
		default:
			// Calculate backoff time based on consecutive failures
			backoffTime := time.Duration(math.Min(float64(5*consecutiveFailures), float64(maxBackoff.Seconds()))) * time.Second
			
			// Create command stream request
			req := &pb.CommandRequest{
				AgentId:   c.agentID,
				Timestamp: time.Now().Unix(),
			}

			// Start command stream
			stream, err := c.edrClient.ReceiveCommands(ctx, req)
	if err != nil {
				consecutiveFailures++
				log.Printf("Failed to start command stream (attempt #%d): %v", consecutiveFailures, err)
				log.Printf("Will retry in %v seconds", backoffTime.Seconds())
				time.Sleep(backoffTime) // Wait with exponential backoff
				continue
			}
			
			// Reset failure counter on successful connection
			consecutiveFailures = 0
			log.Println("Command stream established")

			// Process commands from stream
			for {
				cmd, err := stream.Recv()
				if err != nil {
					if err == io.EOF {
						log.Println("Command stream ended by server")
					} else {
						log.Printf("Command stream error: %v", err)
					}
					break
				}

				log.Printf("Received command: %s (Type: %s)", cmd.CommandId, cmd.Type.String())

				// Process command in a separate goroutine
				go func(command *pb.Command) {
					// Execute command
					result := c.cmdHandler.HandleCommand(ctx, command)

					// Report result
					_, err := c.edrClient.ReportCommandResult(ctx, result)
	if err != nil {
						log.Printf("Failed to report command result: %v", err)
	}
				}(cmd)
			}

			// Wait before reconnecting
			time.Sleep(5 * time.Second)
		}
	}
}

// GetCommandHandler returns the command handler
func (c *EDRClient) GetCommandHandler() *CommandHandler {
	return c.cmdHandler
}

// Close closes the client connection
func (c *EDRClient) Close() error {
	return c.conn.Close()
}

// AgentInfo represents information about the agent
type AgentInfo struct {
	AgentID       string
	Hostname      string
	IPAddress     string
	MACAddress    string
	Username      string
	OSVersion     string
	AgentVersion  string
	RegisteredAt  time.Time
	ServerMessage string
} 