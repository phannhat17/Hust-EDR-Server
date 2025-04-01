package main

import (
	"context"
	"flag"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"agent/client"
	"agent/collector"
	"agent/config"
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
	client, err := client.NewClient(cfg)
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
	
	response, err := client.RegisterAgent(ctx, info)
	if err != nil {
		log.Fatalf("Failed to register agent: %v", err)
	}
	
	log.Printf("Agent registered successfully. Server message: %s", response.ServerMessage)
	
	// If server assigned a different ID, update our agent ID
	if response.AssignedId != "" && response.AssignedId != info.AgentId {
		log.Printf("Server assigned new agent ID: %s", response.AssignedId)
		info.AgentId = response.AssignedId
	}

	// Start periodic status updates
	ticker := time.NewTicker(cfg.UpdateInterval)
	defer ticker.Stop()

	// Handle graceful shutdown
	shutdown := make(chan os.Signal, 1)
	signal.Notify(shutdown, syscall.SIGINT, syscall.SIGTERM)

	for {
		select {
		case <-ticker.C:
			// Collect current status
			status, err := sysCollector.CollectAgentStatus(info.AgentId)
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

		case <-shutdown:
			log.Println("Shutting down agent...")
			// Perform any cleanup
			return
		}
	}
} 