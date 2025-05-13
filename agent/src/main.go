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

// Define version constant
const AGENT_VERSION = "fix-iocs"

// Command-line arguments
var (
	serverAddr  = flag.String("server", "localhost:50051", "Server address")
	configFile  = flag.String("config", "config.yaml", "Configuration file")
	logFile     = flag.String("log", "", "Log file (default: stdout)")
	agentID     = flag.String("id", "", "Agent ID (generated if empty)")
	dataDir     = flag.String("data", "data", "Data directory")
	scanMinutes = flag.Int("scan-interval", 0, "IOC scan interval in minutes")
	useTLS      = flag.Bool("tls", true, "Use TLS for server connection")
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
			Version:       AGENT_VERSION,
			UseTLS:        *useTLS,
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
		
		// Simple approach: command line flag takes precedence over config file
		cfg.UseTLS = *useTLS
		
		// Always update the version in config to current version
		if cfg.Version != AGENT_VERSION {
			cfg.Version = AGENT_VERSION
			log.Printf("Updating agent version in config to %s", AGENT_VERSION)
			if err := config.SaveConfig(*configFile, cfg); err != nil {
				log.Printf("Failed to save updated version: %v", err)
			}
		}
	}

	// Create and start the EDR client
	edrClient, err := client.NewEDRClientWithTLS(cfg.ServerAddress, cfg.AgentID, cfg.DataDir, cfg.UseTLS)
	if err != nil {
		log.Fatalf("Failed to create EDR client: %v", err)
	}
	
	// Set the agent version
	edrClient.SetAgentVersion(cfg.Version)
	
	// Set metrics interval
	edrClient.SetMetricsInterval(cfg.MetricsInterval)
	log.Printf("Setting metrics interval to %d minutes from config", cfg.MetricsInterval)

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
	
	// Get command handler for IOC Scanner configuration
	commandHandler := edrClient.GetCommandHandler()
	
	// Start bidirectional command stream - IOC updates will come through this channel
	log.Printf("Starting bidirectional gRPC streaming - IOC updates will be received through this channel")
	go edrClient.StartCommandStream(ctx)
	
	// Request IOC updates on startup
	go requestIOCUpdatesOnStartup(ctx, edrClient)
	
	// Use config scan interval if command-line flag wasn't explicitly set
	intervalMinutes := *scanMinutes
	if flag.Lookup("scan-interval").DefValue == flag.Lookup("scan-interval").Value.String() {
		intervalMinutes = cfg.ScanInterval
		log.Printf("Using scan interval from config: %d minutes", intervalMinutes)
	}
	
	// Configure and start IOC scanner
	scanner := ioc.NewScanner(
		commandHandler.GetIOCManager(),
		commandHandler.ReportIOCMatch,
		intervalMinutes,
	)
	
	// Set scanner in command handler
	commandHandler.SetScanner(scanner)
	
	// Start IOC scanning
	scanner.Start()
	
	log.Printf("EDR agent started (ID: %s, Server: %s)", agentInfo.AgentID, cfg.ServerAddress)
	log.Printf("IOC scanner started with %d minute interval", intervalMinutes)

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

// requestIOCUpdatesOnStartup sends a request to the server for IOC updates
func requestIOCUpdatesOnStartup(ctx context.Context, edrClient *client.EDRClient) {
	// Give time for the command stream to establish
	time.Sleep(3 * time.Second)
	
	log.Printf("Requesting IOC updates from server...")
	edrClient.RequestIOCUpdates(ctx)
} 