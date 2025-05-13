package client

import (
	"context"
	"fmt"
	"io"
	"log"
	"math"
	"math/rand"
	"sync"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials"
	"google.golang.org/grpc/credentials/insecure"
	"crypto/tls"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/mem"
	"github.com/shirou/gopsutil/v3/host"

	pb "agent/proto"
)

// Initialize random number generator on package import
func init() {
	rand.Seed(time.Now().UnixNano())
}

// EDRClient represents a client for communicating with the EDR server
type EDRClient struct {
	serverAddress   string
	agentID         string
	conn            *grpc.ClientConn
	edrClient       pb.EDRServiceClient
	cmdHandler      *CommandHandler
	agentVersion    string
	dataDir         string
	useTLS          bool
	metricsInterval int
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

// SetMetricsInterval sets the system metrics update interval in minutes
func (c *EDRClient) SetMetricsInterval(interval int) {
	if interval <= 0 {
		c.metricsInterval = 2 // Default to 2 minutes
		log.Printf("WARNING: Invalid metrics interval %d specified, defaulting to %d minutes", interval, c.metricsInterval)
	} else {
		c.metricsInterval = interval
		log.Printf("Setting metrics interval to %d minutes", interval)
	}
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
	// Create system metrics - convert from 0-1 to 0-100 percentage scale for the API
	sysMetrics := &pb.SystemMetrics{
		CpuUsage:    metrics["cpu_usage"] * 100,
		MemoryUsage: metrics["memory_usage"] * 100,
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

// StartCommandStream starts a bidirectional stream for agent-server communication
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
			
			// Open bidirectional stream
			stream, err := c.edrClient.CommandStream(ctx)
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
			
			// Send initial HELLO message
			helloMsg := &pb.CommandMessage{
				AgentId:     c.agentID,
				Timestamp:   time.Now().Unix(),
				MessageType: pb.MessageType_AGENT_HELLO,
				Payload: &pb.CommandMessage_Hello{
					Hello: &pb.AgentHello{
						AgentId:   c.agentID,
						Timestamp: time.Now().Unix(),
					},
				},
			}
			
			if err := stream.Send(helloMsg); err != nil {
				log.Printf("Failed to send HELLO message: %v", err)
				stream.CloseSend()
				time.Sleep(5 * time.Second)
				continue
			}

			// Create a context that can be cancelled to coordinate goroutines
			streamCtx, cancelStream := context.WithCancel(ctx)
			defer cancelStream()
			
			// Create a WaitGroup to coordinate goroutines
			var wg sync.WaitGroup
			
			// Add streamWatcher to coordinate stream closure
			streamClosed := make(chan struct{})
			
			// Start goroutine to handle incoming messages
			wg.Add(1)
			go func() {
				defer wg.Done()
				defer close(streamClosed) // Signal that the stream is closed
				
				for {
					message, err := stream.Recv()
					if err != nil {
						if err == io.EOF {
							log.Println("Command stream closed by server")
						} else {
							log.Printf("Error receiving message: %v", err)
						}
						// Cancel the stream context to signal all goroutines to stop
						cancelStream()
						return
					}
					
					// Process different message types
					switch message.MessageType {
					case pb.MessageType_AGENT_HELLO:
						// Server acknowledgment of our HELLO
						log.Printf("Server acknowledged connection for agent %s", message.AgentId)
						
					case pb.MessageType_SERVER_COMMAND:
						// Handle command from server
						cmd := message.GetCommand()
						if cmd == nil {
							log.Println("Received SERVER_COMMAND message with no command payload")
							continue
						}
						
						log.Printf("Received command: %s (Type: %s)", cmd.CommandId, cmd.Type.String())
						
						// Process command in a separate goroutine
						go func(command *pb.Command) {
							// Execute command
							result := c.cmdHandler.HandleCommand(ctx, command)
							
							// Check if stream is still active before sending
							select {
							case <-streamClosed:
								log.Printf("Stream closed, command result for %s not sent", command.CommandId)
								return
							default:
								// Send result through bidirectional stream
								resultMsg := &pb.CommandMessage{
									AgentId:     c.agentID,
									Timestamp:   time.Now().Unix(),
									MessageType: pb.MessageType_COMMAND_RESULT,
									Payload: &pb.CommandMessage_Result{
										Result: result,
									},
								}
								
								if err := stream.Send(resultMsg); err != nil {
									log.Printf("Failed to send command result: %v", err)
								}
								
								// If this was an UPDATE_IOCS command and it was successful, trigger an IOC scan immediately
								if command.Type == pb.CommandType_UPDATE_IOCS && result.Success {
									log.Printf("IOCs updated successfully, triggering immediate scan")
									scanner := c.cmdHandler.GetScanner()
									if scanner != nil {
										go scanner.TriggerScan()
									} else {
										log.Printf("WARNING: Cannot trigger IOC scan, scanner not available")
									}
								}
							}
						}(cmd)
					}
				}
			}()
			
			// Start goroutine to send periodic status updates
			wg.Add(1)
			go func() {
				defer wg.Done()
				
				// Use the metrics interval from config (in minutes)
				log.Printf("Creating status ticker with interval of %d minutes", c.metricsInterval)
				statusTicker := time.NewTicker(time.Duration(c.metricsInterval) * time.Minute)
				defer statusTicker.Stop()
				
				// Send an initial status update immediately
				sendStatusUpdate(c, stream, streamClosed, cancelStream)
				
				for {
					select {
					case <-statusTicker.C:
						sendStatusUpdate(c, stream, streamClosed, cancelStream)
					case <-streamCtx.Done():
						return
					}
				}
			}()
			
			// Wait for all goroutines to finish (this happens when streamCtx is cancelled)
			wg.Wait()
			
			// Properly close the stream if it hasn't been closed already
			stream.CloseSend()
			
			// Check if the parent context was cancelled
			select {
			case <-ctx.Done():
				log.Println("Parent context cancelled, stopping reconnect attempts")
				return
			default:
				// Wait before reconnecting
				log.Println("Will attempt to reconnect command stream in 5 seconds")
				time.Sleep(5 * time.Second)
			}
		}
	}
}

// Helper function to send status updates
func sendStatusUpdate(c *EDRClient, stream pb.EDRService_CommandStreamClient, streamClosed chan struct{}, cancelStream context.CancelFunc) {
	// Check if stream is still active before sending status
	select {
	case <-streamClosed:
		return
	default:
		// Collect system metrics
		metrics := map[string]float64{
			"cpu_usage":    getCPUUsage(),
			"memory_usage": getMemoryUsage(),
			"uptime":       float64(getUptime()),
		}
		
		// Log that we're sending status update with proper percentage formatting
		log.Printf("Sending status update with metrics: CPU: %.2f%%, Memory: %.2f%%, Uptime: %.0fs", 
			metrics["cpu_usage"]*100, metrics["memory_usage"]*100, metrics["uptime"])
		
		// Create status message - note that ServerMetrics expects values as percentages (0-100)
		statusReq := &pb.StatusRequest{
			AgentId:   c.agentID,
			Timestamp: time.Now().Unix(),
			Status:    "ONLINE",
			SystemMetrics: &pb.SystemMetrics{
				CpuUsage:    metrics["cpu_usage"]*100,  // Convert from 0-1 to 0-100 scale
				MemoryUsage: metrics["memory_usage"]*100, // Convert from 0-1 to 0-100 scale
				Uptime:      int64(metrics["uptime"]),
			},
		}
		
		statusMsg := &pb.CommandMessage{
			AgentId:     c.agentID,
			Timestamp:   time.Now().Unix(),
			MessageType: pb.MessageType_AGENT_STATUS,
			Payload: &pb.CommandMessage_Status{
				Status: statusReq,
			},
		}
		
		if err := stream.Send(statusMsg); err != nil {
			log.Printf("Failed to send status update: %v", err)
			cancelStream() // Cancel context to signal all goroutines to stop
			return
		}
	}
}

// Global variable for tracking start time
var (
	processStartTime time.Time
	startTimeOnce    sync.Once
)

// Helper functions for system metrics
func getCPUUsage() float64 {
	// Get actual CPU usage using gopsutil
	percentages, err := cpu.Percent(time.Second/2, false)  // 500ms sample, average across all cores
	if err != nil || len(percentages) == 0 {
		log.Printf("Warning: failed to get CPU usage: %v", err)
		return 0.1 // Default fallback value if monitoring fails
	}
	
	// Return as decimal (0.0-1.0) instead of percentage
	return percentages[0] / 100.0
}

func getMemoryUsage() float64 {
	// Get actual memory usage using gopsutil
	vmStat, err := mem.VirtualMemory()
	if err != nil {
		log.Printf("Warning: failed to get memory usage: %v", err)
		return 0.2 // Default fallback value if monitoring fails
	}
	
	// Return as decimal (0.0-1.0)
	return float64(vmStat.UsedPercent) / 100.0
}

func getUptime() int64 {
	// Get actual system uptime using gopsutil
	uptime, err := host.Uptime()
	if err != nil {
		// Fall back to process uptime if system uptime fails
		log.Printf("Warning: failed to get system uptime: %v", err)
		// Initialize start time only once (original behavior)
		startTimeOnce.Do(func() {
			processStartTime = time.Now()
		})
		
		// Return process uptime in seconds
		return int64(time.Since(processStartTime).Seconds())
	}
	
	return int64(uptime)
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