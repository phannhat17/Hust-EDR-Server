package client

import (
	"context"
	"crypto/tls"
	"fmt"
	"log"
	"time"

	"agent/config"
	pb "agent/proto"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
)

// EDRClient represents the gRPC client for communicating with the EDR server
type EDRClient struct {
	client  pb.EDRServiceClient
	conn    *grpc.ClientConn
	config  *config.Config
}

// NewClient creates a new EDR client with the provided configuration
func NewClient(cfg *config.Config) (*EDRClient, error) {
	var opts []grpc.DialOption

	// Configure security options
	if cfg.TLSEnabled {
		// Configure TLS if enabled
		tlsConfig := &tls.Config{
			InsecureSkipVerify: cfg.InsecureSkipVerify,
		}
		creds := credentials.NewTLS(tlsConfig)
		opts = append(opts, grpc.WithTransportCredentials(creds))
	} else {
		// Use insecure connection if TLS not enabled
		opts = append(opts, grpc.WithTransportCredentials(insecure.NewCredentials()))
	}

	// Set connection timeout
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	opts = append(opts, grpc.WithBlock())

	// Log connection attempt
	log.Printf("Attempting to connect to server at %s...", cfg.ServerAddress)

	// Connect to the server
	conn, err := grpc.DialContext(ctx, cfg.ServerAddress, opts...)
	if err != nil {
		return nil, fmt.Errorf("failed to connect to server: %v", err)
	}

	// Create gRPC client
	client := pb.NewEDRServiceClient(conn)

	log.Printf("Successfully connected to server at %s", cfg.ServerAddress)

	return &EDRClient{
		client: client,
		conn:   conn,
		config: cfg,
	}, nil
}

// Close closes the client connection
func (c *EDRClient) Close() error {
	if c.conn != nil {
		return c.conn.Close()
	}
	return nil
}

// RegisterAgent registers the agent with the server
func (c *EDRClient) RegisterAgent(ctx context.Context, info *pb.AgentInfo) (*pb.RegisterResponse, error) {
	log.Printf("Registering agent %s with server...", info.AgentId)
	response, err := c.client.RegisterAgent(ctx, info)
	if err != nil {
		return nil, fmt.Errorf("failed to register agent: %v", err)
	}
	log.Printf("Agent registration successful: %s", response.ServerMessage)
	return response, nil
}

// UpdateStatus sends a status update to the server
func (c *EDRClient) UpdateStatus(ctx context.Context, status *pb.AgentStatus) (*pb.StatusResponse, error) {
	log.Printf("Sending status update for agent %s...", status.AgentId)
	response, err := c.client.UpdateStatus(ctx, status)
	if err != nil {
		return nil, fmt.Errorf("failed to send status update: %v", err)
	}
	log.Printf("Status update successful: %s", response.ServerMessage)
	return response, nil
} 