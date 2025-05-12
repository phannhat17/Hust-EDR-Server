package client

import (
	"context"
	"fmt"
	"io"
	"log"
	"math"
	"os"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"crypto/tls"
	"crypto/x509"

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
	stream        pb.EDRService_CommandStreamClient // Added to store active stream reference
	streamLock    sync.RWMutex                     // Lock for stream access
	lastPingTime  time.Time                        // Track last ping time
	isConnected   bool                             // Track connection status
}

// NewEDRClient creates a new EDR client
func NewEDRClient(serverAddress, agentID string, dataDir string) (*EDRClient, error) {
	return NewEDRClientWithTLS(serverAddress, agentID, dataDir, false, "", "", "")
}

// NewEDRClientWithTLS creates a new EDR client with TLS enabled
func NewEDRClientWithTLS(serverAddress, agentID string, dataDir string, useTLS bool, 
	caCertPath string, clientCertPath string, clientKeyPath string) (*EDRClient, error) {
	var conn *grpc.ClientConn
	var err error

	if useTLS {
		var tlsConfig *tls.Config

		// If CA cert path is provided, load it and verify server
		if caCertPath != "" {
			// Load CA cert
			caCert, err := os.ReadFile(caCertPath)
			if err != nil {
				return nil, fmt.Errorf("failed to read CA certificate: %v", err)
			}

			// Create cert pool and add the CA cert
			certPool := x509.NewCertPool()
			if !certPool.AppendCertsFromPEM(caCert) {
				return nil, fmt.Errorf("failed to add CA certificate to pool")
			}

			// Configure TLS with verification
			tlsConfig = &tls.Config{
				RootCAs: certPool,
			}
			
			// Check if client certificate and key are provided for mTLS
			if clientCertPath != "" && clientKeyPath != "" {
				// Load client certificate and key
				clientCert, err := tls.LoadX509KeyPair(clientCertPath, clientKeyPath)
				if err != nil {
					return nil, fmt.Errorf("failed to load client certificate and key: %v", err)
				}
				
				// Add client certificate to TLS config
				tlsConfig.Certificates = []tls.Certificate{clientCert}
				
				log.Printf("Using secure TLS configuration with server verification and client authentication (mTLS)")
			} else {
				log.Printf("Using secure TLS configuration with server certificate verification")
			}
		} else {
			// No CA cert provided, use insecure mode for backward compatibility
			tlsConfig = &tls.Config{
				InsecureSkipVerify: true, // Skip verification only if no CA cert provided
			}
			log.Printf("WARNING: No CA certificate provided - using insecure TLS mode")
		}

		// Create the credentials
		creds := credentials.NewTLS(tlsConfig)

		conn, err = grpc.Dial(serverAddress, grpc.WithTransportCredentials(creds))
		if err != nil {
			if caCertPath != "" {
				return nil, fmt.Errorf("failed to connect to server with TLS verification: %v (check if CA certificate is valid and server certificate is signed by this CA)", err)
			} else {
				return nil, fmt.Errorf("failed to connect to server with TLS: %v", err)
			}
		}
		
		if caCertPath != "" {
			if clientCertPath != "" && clientKeyPath != "" {
				log.Printf("Connected to server %s with mTLS (mutual authentication)", serverAddress)
			} else {
				log.Printf("Connected to server %s with TLS encryption and certificate verification", serverAddress)
			}
		} else {
			log.Printf("Connected to server %s with TLS encryption (INSECURE: no certificate verification)", serverAddress)
		}
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

// UpdateStatus sends a status update to the server (legacy method)
func (c *EDRClient) UpdateStatus(ctx context.Context, status string, metrics map[string]float64) error {
	// If we have an active stream, send status through the stream
	if c.HasActiveStream() {
		return c.SendStatusViaStream(ctx, status, metrics)
	}

	// Otherwise, use the legacy RPC method
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

// HasActiveStream checks if there is an active stream connection
func (c *EDRClient) HasActiveStream() bool {
	c.streamLock.RLock()
	defer c.streamLock.RUnlock()
	return c.isConnected && c.stream != nil
}

// SendStatusViaStream sends a status update through the bidirectional stream
func (c *EDRClient) SendStatusViaStream(ctx context.Context, status string, metrics map[string]float64) error {
	c.streamLock.RLock()
	stream := c.stream
	c.streamLock.RUnlock()
	
	if stream == nil {
		return fmt.Errorf("no active stream")
	}
	
	// Create system metrics
	sysMetrics := &pb.SystemMetrics{
		CpuUsage:    metrics["cpu_usage"],
		MemoryUsage: metrics["memory_usage"],
		Uptime:      int64(metrics["uptime"]),
	}

	// Create status request
	statusReq := &pb.StatusRequest{
		AgentId:       c.agentID,
		Timestamp:     time.Now().Unix(),
		Status:        status,
		SystemMetrics: sysMetrics,
	}

	// Create command message with status payload
	statusMsg := &pb.CommandMessage{
		Payload: &pb.CommandMessage_Status{
			Status: statusReq,
		},
	}

	// Send status update through stream
	err := stream.Send(statusMsg)
	if err != nil {
		c.markStreamDisconnected()
		return fmt.Errorf("failed to send status update through stream: %v", err)
	}

	log.Printf("Sent status update through stream: %s", status)
	return nil
}

// ReportIOCMatch sends an IOC match report through the bidirectional stream
func (c *EDRClient) ReportIOCMatchViaStream(ctx context.Context, iocType pb.IOCType, iocValue string, 
	matchedValue string, matchContext string, severity string) error {
	
	c.streamLock.RLock()
	stream := c.stream
	c.streamLock.RUnlock()
	
	if stream == nil {
		return fmt.Errorf("no active stream")
	}
	
	reportID := fmt.Sprintf("%s-%d", c.agentID, time.Now().UnixNano())
	
	// Create IOC match report
	report := &pb.IOCMatchReport{
		ReportId:       reportID,
		AgentId:        c.agentID,
		Timestamp:      time.Now().Unix(),
		Type:           iocType,
		IocValue:       iocValue,
		MatchedValue:   matchedValue,
		Context:        matchContext,
		Severity:       severity,
	}

	// Create command message with IOC match payload
	iocMsg := &pb.CommandMessage{
		Payload: &pb.CommandMessage_IocMatch{
			IocMatch: report,
		},
	}

	// Send IOC match report through stream
	err := stream.Send(iocMsg)
	if err != nil {
		c.markStreamDisconnected()
		return fmt.Errorf("failed to send IOC match report through stream: %v", err)
	}

	log.Printf("Sent IOC match report through stream: %s - %s (severity: %s)", 
		pb.IOCType_name[int32(iocType)], iocValue, severity)
	return nil
}

// StartCommandStream is now a wrapper around StartBidirectionalCommandStream for backward compatibility
func (c *EDRClient) StartCommandStream(ctx context.Context) {
	c.StartBidirectionalCommandStream(ctx)
}

// StartBidirectionalCommandStream starts a bidirectional stream for commands and results
func (c *EDRClient) StartBidirectionalCommandStream(ctx context.Context) {
	// Track failed connection attempts for backoff strategy
	consecutiveFailures := 0
	maxBackoff := 60 * time.Second
	
	for {
		select {
		case <-ctx.Done():
			log.Println("Bidirectional command stream stopped due to context cancellation")
			return
		default:
			// Calculate backoff time based on consecutive failures
			backoffTime := time.Duration(math.Min(float64(5*consecutiveFailures), float64(maxBackoff.Seconds()))) * time.Second
			
			// Start bidirectional stream
			stream, err := c.edrClient.CommandStream(ctx)
			if err != nil {
				consecutiveFailures++
				log.Printf("Failed to start bidirectional command stream (attempt #%d): %v", consecutiveFailures, err)
				log.Printf("Will retry in %v seconds", backoffTime.Seconds())
				time.Sleep(backoffTime) // Wait with exponential backoff
				continue
			}
			
			// Reset failure counter on successful connection
			consecutiveFailures = 0
			log.Println("Bidirectional command stream established")
			
			// Store the stream reference
			c.streamLock.Lock()
			c.stream = stream
			c.isConnected = true
			c.lastPingTime = time.Now()
			c.streamLock.Unlock()
			
			// Create a wait group for the goroutines
			var wg sync.WaitGroup
			wg.Add(3) // Added a third goroutine for status updates
			
			// Create a context that will be cancelled when the function returns
			streamCtx, streamCancel := context.WithCancel(ctx)
			defer streamCancel()
			
			// Start a goroutine to send heartbeats
			go func() {
				defer wg.Done()
				ticker := time.NewTicker(30 * time.Second) // Send heartbeat every 30 seconds
				defer ticker.Stop()
				
				for {
					select {
					case <-streamCtx.Done():
						return
					case <-ticker.C:
						// Check if we haven't received a ping from server in too long
						c.streamLock.RLock()
						lastPing := c.lastPingTime
						c.streamLock.RUnlock()
						
						if time.Since(lastPing) > 90*time.Second {
							log.Printf("No ping received from server in 90 seconds, reconnecting...")
							streamCancel()
							return
						}
						
						// Send heartbeat
						pingMsg := &pb.CommandMessage{
							Payload: &pb.CommandMessage_Ping{
								Ping: &pb.PingMessage{
									AgentId:   c.agentID,
									Timestamp: time.Now().Unix(),
								},
							},
						}
						
						if err := stream.Send(pingMsg); err != nil {
							log.Printf("Failed to send heartbeat: %v", err)
							c.markStreamDisconnected()
							streamCancel()
							return
						}
					}
				}
			}()
			
			// Start a goroutine to send status updates
			go func() {
				defer wg.Done()
				statusTicker := time.NewTicker(1 * time.Minute) // Send status every minute
				defer statusTicker.Stop()
				
				for {
					select {
					case <-streamCtx.Done():
						return
					case <-statusTicker.C:
						metrics := collectSystemMetrics()
						if err := c.SendStatusViaStream(streamCtx, "RUNNING", metrics); err != nil {
							log.Printf("Failed to send status update: %v", err)
							// Don't cancel the stream for status failures
						}
					}
				}
			}()
			
			// Start a goroutine to receive and process messages
			go func() {
				defer wg.Done()
				
				for {
					msg, err := stream.Recv()
					if err != nil {
						if err == io.EOF {
							log.Println("Bidirectional stream ended by server")
						} else {
							log.Printf("Bidirectional stream error: %v", err)
						}
						c.markStreamDisconnected()
						streamCancel()
						return
					}
					
					// Process message based on type
					switch payload := msg.Payload.(type) {
					case *pb.CommandMessage_Command:
						// Process command
						cmd := payload.Command
						log.Printf("Received command: %s (Type: %s)", cmd.CommandId, cmd.Type.String())
						
						// Process command
						result := c.cmdHandler.HandleCommand(streamCtx, cmd)
						
						// Send result back through the same stream
						resultMsg := &pb.CommandMessage{
							Payload: &pb.CommandMessage_Result{
								Result: result,
							},
						}
						
						if err := stream.Send(resultMsg); err != nil {
							log.Printf("Failed to send command result: %v", err)
							c.markStreamDisconnected()
							streamCancel()
							return
						}
					
					case *pb.CommandMessage_Ping:
						// Server heartbeat, update lastPingTime
						c.streamLock.Lock()
						c.lastPingTime = time.Now()
						c.streamLock.Unlock()
						log.Printf("Received server heartbeat at %d", payload.Ping.Timestamp)
					
					case *pb.CommandMessage_IocAck:
						// Server acknowledged an IOC match
						ack := payload.IocAck
						log.Printf("Received IOC match acknowledgment for report %s: %s", 
							ack.ReportId, ack.Message)
						
						// Check if server requested additional action
						if ack.PerformAdditionalAction && ack.AdditionalAction != pb.CommandType_UNKNOWN {
							log.Printf("Server requested additional action: %s", 
								pb.CommandType_name[int32(ack.AdditionalAction)])
							
							// Create a command to execute locally
							cmd := &pb.Command{
								CommandId: fmt.Sprintf("%s-auto-%d", ack.ReportId, time.Now().UnixNano()),
								AgentId:   c.agentID,
								Timestamp: time.Now().Unix(),
								Type:      ack.AdditionalAction,
								Params:    ack.ActionParams,
							}
							
							// Execute the command
							result := c.cmdHandler.HandleCommand(streamCtx, cmd)
							
							// Send the result
							resultMsg := &pb.CommandMessage{
								Payload: &pb.CommandMessage_Result{
									Result: result,
								},
							}
							
							if err := stream.Send(resultMsg); err != nil {
								log.Printf("Failed to send additional action result: %v", err)
							}
						}
					
					default:
						log.Printf("Received unknown message type")
					}
				}
			}()
			
			// Wait for all goroutines to finish
			wg.Wait()
			
			// Mark stream as disconnected
			c.markStreamDisconnected()
			
			// Wait before reconnecting
			time.Sleep(5 * time.Second)
		}
	}
}

// markStreamDisconnected marks the stream as disconnected
func (c *EDRClient) markStreamDisconnected() {
	c.streamLock.Lock()
	defer c.streamLock.Unlock()
	c.isConnected = false
	c.stream = nil
}

// Send a system status update through the bidirectional stream
func (c *EDRClient) sendStatusPing(ctx context.Context, stream pb.EDRService_CommandStreamClient) error {
	metrics := collectSystemMetrics()
	
	pingMsg := &pb.CommandMessage{
		Payload: &pb.CommandMessage_Ping{
			Ping: &pb.PingMessage{
				AgentId:   c.agentID,
				Timestamp: time.Now().Unix(),
			},
		},
	}
	
	return stream.Send(pingMsg)
}

// Helper function to collect system metrics
func collectSystemMetrics() map[string]float64 {
	// This is a simple placeholder - a real implementation would collect actual metrics
	return map[string]float64{
		"cpu_usage":    0.5,  // 50% CPU usage (placeholder)
		"memory_usage": 0.25, // 25% memory usage (placeholder)
		"uptime":       3600, // 1 hour uptime (placeholder)
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