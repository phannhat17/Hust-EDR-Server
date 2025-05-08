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
	"agent/config"
	"agent/ioc"
)

// Command-line arguments
var (
	serverAddr  = flag.String("server", "localhost:50051", "Server address")
	configFile  = flag.String("config", "config.yaml", "Configuration file")
	logFile     = flag.String("log", "", "Log file (default: stdout)")
	agentID     = flag.String("id", "", "Agent ID (generated if empty)")
	dataDir     = flag.String("data", "data", "Data directory")
	scanMinutes = flag.Int("scan-interval", 30, "IOC scan interval in minutes")
)

func main() {
	// Parse command-line flags
	flag.Parse()

	// Setup data directory
	if err := os.MkdirAll(*dataDir, 0755); err != nil {
		log.Fatalf("Failed to create data directory: %v", err)
	}

	// Setup logging
	if *logFile != "" {
		f, err := os.OpenFile(*logFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
		if err != nil {
			log.Fatalf("Failed to open log file: %v", err)
		}
		defer f.Close()
		log.SetOutput(f)
	}

	// Load configuration file
	cfg, err := config.LoadConfig(*configFile)
	if err != nil {
		if !os.IsNotExist(err) {
			log.Printf("Error loading config file: %v", err)
		}
		// Use default config or command-line values if file not found
		cfg = &config.Config{
			ServerAddress: *serverAddr,
			AgentID:       *agentID,
			LogFile:       *logFile,
			DataDir:       *dataDir,
		}
		log.Printf("Using default configuration")
	} else {
		log.Printf("Loaded configuration from %s", *configFile)
		
		// Override config with command-line flags if provided
		if *serverAddr != "localhost:50051" {
			cfg.ServerAddress = *serverAddr
		}
		if *agentID != "" {
			cfg.AgentID = *agentID
		}
		if *logFile != "" {
			cfg.LogFile = *logFile
		}
		if *dataDir != "data" {
			cfg.DataDir = *dataDir
		}
	}

	// Create and start the EDR client
	edrClient, err := client.NewEDRClient(cfg.ServerAddress, cfg.AgentID)
	if err != nil {
		log.Fatalf("Failed to create EDR client: %v", err)
	}

	// Start agent connection
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// Register with server
	agentInfo, err := edrClient.Register(ctx)
	if err != nil {
		log.Fatalf("Failed to register with server: %v", err)
	}

	log.Printf("Registered with server as agent ID: %s", agentInfo.AgentID)
	// If agent ID was newly assigned, save to config
	if cfg.AgentID == "" || cfg.AgentID != agentInfo.AgentID {
		cfg.AgentID = agentInfo.AgentID
		if err := config.SaveConfig(*configFile, cfg); err != nil {
			log.Printf("Failed to save updated config: %v", err)
		} else {
			log.Printf("Updated configuration with assigned agent ID")
		}
	}

	// Start command stream
	go edrClient.StartCommandStream(ctx)

	// Start status reporting
	go startStatusReporting(ctx, edrClient)
	
	// Get command handler to access IOC functionality
	commandHandler := edrClient.GetCommandHandler()
	
	// Configure and start IOC scanner
	scanner := ioc.NewScanner(
		commandHandler.GetIOCManager(),
		commandHandler.ReportIOCMatch,
		*scanMinutes,
	)
	
	// Start IOC scanning
	scanner.Start()
	
	log.Printf("EDR agent started (ID: %s, Server: %s)", agentInfo.AgentID, cfg.ServerAddress)
	log.Printf("IOC scanner started with %d minute interval", *scanMinutes)

	// Handle graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	log.Printf("Shutting down agent...")
	
	// Stop the IOC scanner
	scanner.Stop()
	
	// Cancel context to stop other goroutines
	cancel()
	
	// Allow time for cleanup
	time.Sleep(500 * time.Millisecond)
	log.Printf("Agent shutdown complete")
}

// startStatusReporting periodically sends status updates to the server
func startStatusReporting(ctx context.Context, edrClient *client.EDRClient) {
	ticker := time.NewTicker(1 * time.Minute)
	defer ticker.Stop()

	for {
		select {
		case <-ticker.C:
			metrics := collectSystemMetrics()
			if err := edrClient.UpdateStatus(ctx, "RUNNING", metrics); err != nil {
				log.Printf("Failed to send status update: %v", err)
			}
		case <-ctx.Done():
			return
		}
	}
}

// collectSystemMetrics collects system metrics
func collectSystemMetrics() map[string]float64 {
	// This is a simple placeholder - a real implementation would collect actual metrics
	return map[string]float64{
		"cpu_usage":    0.5,  // 50% CPU usage (placeholder)
		"memory_usage": 0.25, // 25% memory usage (placeholder)
		"uptime":       3600, // 1 hour uptime (placeholder)
	}
} 