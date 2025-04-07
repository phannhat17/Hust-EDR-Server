package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"agent/client"
	"agent/collector"
	"agent/config"
	pb "agent/proto"
)

var (
	serverAddr = flag.String("server", "", "The server address in the format of host:port")
	interval   = flag.Int("interval", 0, "Status update interval in seconds")
)

func main() {
	flag.Parse()

	// Initialize configuration
	cfg := config.DefaultConfig()

	// Override defaults with command line flags if provided
	if *serverAddr != "" {
		cfg.ServerAddress = *serverAddr
	}
	if *interval > 0 {
		cfg.UpdateInterval = time.Duration(*interval) * time.Second
	}

	// Initialize system information collector
	sysCollector := collector.NewSystemCollector()
	
	// Initialize gRPC client
	edrClient, err := client.NewClient(cfg)
	if err != nil {
		log.Fatalf("Failed to create client: %v", err)
	}

	// Collect initial system information
	info, err := sysCollector.CollectAgentInfo()
	if err != nil {
		log.Fatalf("Failed to collect system information: %v", err)
	}

	// Register agent with server
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	
	response, err := edrClient.RegisterAgent(ctx, info)
	if err != nil {
		log.Fatalf("Failed to register agent: %v", err)
	}
	
	log.Printf("Agent registered successfully. Server message: %s", response.ServerMessage)
	
	// If server assigned a different ID, update our agent ID
	if response.AssignedId != "" && response.AssignedId != info.AgentId {
		log.Printf("Server assigned new agent ID: %s", response.AssignedId)
		info.AgentId = response.AssignedId
	}

	// Initialize command handler
	cmdHandler := client.NewCommandHandler(edrClient)

	// Start periodic status updates in a separate goroutine
	var wg sync.WaitGroup
	wg.Add(2)  // One for status updates, one for command handling

	// Handle graceful shutdown
	shutdown := make(chan os.Signal, 1)
	signal.Notify(shutdown, syscall.SIGINT, syscall.SIGTERM)
	
	// Channel to communicate shutdown to goroutines
	done := make(chan struct{})

	// Start status update goroutine
	go func() {
		defer wg.Done()
		statusUpdater(edrClient, sysCollector, info.AgentId, cfg.UpdateInterval, done)
	}()

	// Start command handling goroutine
	go func() {
		defer wg.Done()
		commandHandler(edrClient, cmdHandler, info.AgentId, done)
	}()

	// Wait for shutdown signal
	<-shutdown
	log.Println("Shutting down agent...")
	
	// Signal goroutines to shut down
	close(done)

	// Wait for goroutines to complete
	wg.Wait()
	
	log.Println("Agent shutdown complete")
}

// statusUpdater periodically sends status updates to the server
func statusUpdater(client *client.EDRClient, collector *collector.SystemCollector, agentID string, interval time.Duration, done <-chan struct{}) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			// Collect current status
			status, err := collector.CollectAgentStatus(agentID)
			if err != nil {
				log.Printf("Error collecting status: %v", err)
				continue
			}

			// Send status update
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			statusResp, err := client.UpdateStatus(ctx, status)
			cancel()
			
			if err != nil {
				log.Printf("Failed to send status update: %v", err)
			} else {
				log.Printf("Status update sent. Acknowledged: %v", statusResp.Acknowledged)
			}

		case <-done:
			log.Println("Status updater shutting down")
			return
		}
	}
}

// commandHandler listens for commands from the server and executes them
func commandHandler(client *client.EDRClient, handler *client.CommandHandler, agentID string, done <-chan struct{}) {
	log.Println("Starting command handler")
	
	// Track last command time to avoid reprocessing commands
	var lastCommandTime int64 = 0
	
	// Backoff for reconnections
	backoff := time.Millisecond * 100
	maxBackoff := 30 * time.Second
	
	for {
		select {
		case <-done:
			log.Println("Command handler shutting down")
			return
		default:
			// Create a background context with cancel for the stream
			ctx, cancel := context.WithCancel(context.Background())
			
			// Set up a goroutine to cancel the context when done
			streamDone := make(chan struct{})
			go func() {
				select {
				case <-done:
					cancel()
				case <-streamDone:
					// Stream is already done
				}
			}()
			
			// Establish command stream
			stream, err := client.ReceiveCommands(ctx, agentID, lastCommandTime)
			if err != nil {
				log.Printf("Failed to establish command stream: %v. Retrying in %v...", err, backoff)
				cancel()
				close(streamDone)
				select {
				case <-time.After(backoff):
					// Exponential backoff with jitter
					backoff = time.Duration(float64(backoff) * 1.5)
					if backoff > maxBackoff {
						backoff = maxBackoff
					}
				case <-done:
					return
				}
				continue
			}
			
			// Reset backoff on successful connection
			backoff = time.Millisecond * 100
			
			log.Printf("Command stream established, listening for commands...")
			
			// Process command stream
			streamActive := true
			for streamActive {
				select {
				case <-done:
					cancel()
					close(streamDone)
					return
				default:
					// Receive next command with a timeout
					recvDone := make(chan struct{})
					var cmd *pb.Command
					var recvErr error
					
					go func() {
						cmd, recvErr = stream.Recv()
						close(recvDone)
					}()
					
					select {
					case <-recvDone:
						if recvErr != nil {
							log.Printf("Command stream error: %v. Reconnecting...", recvErr)
							cancel()
							close(streamDone)
							streamActive = false
							break
						}
						
						// Print detailed debug info about received command
						log.Printf("DEBUG: Received command - ID: %s, Type: %s, Timestamp: %d", 
							cmd.CommandId, cmd.Type.String(), cmd.Timestamp)
						log.Printf("DEBUG: Command params: %+v", cmd.Params)
						
						// Process command if newer than last one
						if cmd.Timestamp > lastCommandTime {
							log.Printf("Received command: %s (Type: %s)", cmd.CommandId, cmd.Type.String())
							
							// Update last command time
							lastCommandTime = cmd.Timestamp
							
							// Handle command asynchronously
							go func(command *pb.Command) {
								// Create context with timeout for command execution
								cmdCtx, cmdCancel := context.WithTimeout(context.Background(), 
									time.Duration(command.Timeout)*time.Second)
								defer cmdCancel()
								
								log.Printf("DEBUG: Executing command with timeout: %d seconds", command.Timeout)
								
								// Process command
								result := handler.HandleCommand(cmdCtx, command)
								
								log.Printf("DEBUG: Command executed, success: %v, message: %s", 
									result.Success, result.Message)
								
								// Report result back to server
								reportCtx, reportCancel := context.WithTimeout(context.Background(), 5*time.Second)
								_, err := client.ReportCommandResult(reportCtx, result)
								reportCancel()
								
								if err != nil {
									log.Printf("Failed to report command result: %v", err)
								} else {
									log.Printf("Command result for %s reported successfully", command.CommandId)
								}
							}(cmd)
						} else {
							log.Printf("Ignoring old command: %s (Timestamp: %d, Last: %d)",
								cmd.CommandId, cmd.Timestamp, lastCommandTime)
						}
					case <-done:
						cancel()
						close(streamDone)
						return
					}
				}
			}
		}
	}
} 