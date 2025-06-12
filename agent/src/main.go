package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"agent/client"
	"agent/config"
	"agent/ioc"
	"agent/logging"
)

// Command-line flags
var (
	serverAddr      = flag.String("server", "", "Server address (overrides config)")
	configFile      = flag.String("config", config.DefaultConfigFile, "Configuration file")
	logFile         = flag.String("log", "", "Log file (default: stdout)")
	agentID         = flag.String("id", "", "Agent ID (generated if empty)")
	dataDir         = flag.String("data", "", "Data directory (overrides config)")
	scanMinutes     = flag.Int("scan-interval", 0, "IOC scan interval in minutes (overrides config)")
	metricsMinutes  = flag.Int("metrics-interval", 0, "Metrics update interval in minutes (overrides config)")
	useTLS          = flag.Bool("tls", false, "Use TLS for server connection (overrides config)")
	connectionTimeout = flag.Int("timeout", 0, "Connection timeout in seconds (overrides config)")
)

// Track if TLS flag was explicitly set
var tlsFlagSet bool

func main() {
	// Check if TLS flag was explicitly set before parsing
	for _, arg := range os.Args[1:] {
		if arg == "-tls" || arg == "--tls" || arg == "-tls=true" || arg == "--tls=true" || arg == "-tls=false" || arg == "--tls=false" {
			tlsFlagSet = true
			break
		}
	}

	// Parse command-line flags
	flag.Parse()

	// Load configuration with precedence: flags > YAML > defaults
	cfg, err := config.LoadConfig(*configFile)
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}
	
	// Ensure agent version is set
	if cfg.AgentVersion == "" {
		cfg.AgentVersion = config.DefaultAgentVersion
	}

	// Apply command-line flag overrides with highest precedence
	flagOverrides := make(map[string]interface{})
	
	// Only override if flag was explicitly set (not default value)
	if *serverAddr != "" {
		flagOverrides["server"] = *serverAddr
	}
	if *agentID != "" {
		flagOverrides["agent_id"] = *agentID
	}
	if *logFile != "" {
		flagOverrides["log_file"] = *logFile
	}
	if *dataDir != "" {
		flagOverrides["data_dir"] = *dataDir
	}
	if *scanMinutes > 0 {
		flagOverrides["scan_interval"] = *scanMinutes
	}
	if *metricsMinutes > 0 {
		flagOverrides["metrics_interval"] = *metricsMinutes
	}
	if tlsFlagSet {
		flagOverrides["use_tls"] = *useTLS
	}
	if *connectionTimeout > 0 {
		flagOverrides["connection_timeout"] = *connectionTimeout
	}

	// Apply flag overrides
	if err := cfg.ApplyFlags(flagOverrides); err != nil {
		log.Fatalf("Failed to apply configuration flags: %v", err)
	}

	// Setup data directory
	if err := os.MkdirAll(cfg.DataDir, 0755); err != nil {
		log.Fatalf("Failed to create data directory: %v", err)
	}

	// Initialize structured logging
	if err := logging.InitLogger(cfg); err != nil {
		log.Fatalf("Failed to initialize logger: %v", err)
	}

	logging.Info().
		Str("version", cfg.AgentVersion).
		Str("server", cfg.ServerAddress).
		Str("data_dir", cfg.DataDir).
		Msg("Starting EDR Agent")

	// Create and start the EDR client
	edrClient, err := client.NewEDRClientWithConfig(cfg)
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
	
	// Always save agent ID if it's empty or different from server response
	log.Printf("DEBUG: cfg.AgentID='%s', agentInfo.AgentID='%s'", cfg.AgentID, agentInfo.AgentID)
	
	if cfg.AgentID == "" || cfg.AgentID != agentInfo.AgentID {
		log.Printf("DEBUG: Condition met, saving config...")
		cfg.AgentID = agentInfo.AgentID
		if err := cfg.SaveConfig(*configFile); err != nil {
			log.Printf("Failed to save updated config: %v", err)
		} else {
			log.Printf("Updated configuration with assigned agent ID: %s", agentInfo.AgentID)
		}
	} else {
		log.Printf("DEBUG: Condition NOT met, skipping config save")
	}

	// Get command handler for IOC Scanner configuration
	commandHandler := edrClient.GetCommandHandler()

	// Use WaitGroup for graceful shutdown
	var wg sync.WaitGroup

	// Start bidirectional command stream - IOC updates will come through this channel
	logging.Info().Msg("Starting bidirectional gRPC streaming - IOC updates will be received through this channel")
	wg.Add(1)
	go func() {
		defer wg.Done()
		edrClient.StartCommandStream(ctx)
	}()

	// Request IOC updates on startup with configured delay
	wg.Add(1)
	go func() {
		defer wg.Done()
		requestIOCUpdatesOnStartup(ctx, edrClient, cfg.GetIOCUpdateDelayDuration())
	}()

	// Configure and start IOC scanner
	scanner := ioc.NewScannerWithConfig(
		commandHandler.GetIOCManager(),
		commandHandler.ReportIOCMatch,
		cfg,
	)

	// Set scanner in command handler
	commandHandler.SetScanner(scanner)

	// Start IOC scanning
	scanner.Start()

	logging.Info().
		Str("agent_id", agentInfo.AgentID).
		Str("server", cfg.ServerAddress).
		Int("scan_interval", cfg.ScanInterval).
		Int("metrics_interval", cfg.MetricsInterval).
		Msg("EDR agent started successfully")

	// Handle graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	sig := <-sigChan

	logging.Info().Str("signal", sig.String()).Msg("Shutdown signal received")

	// Send shutdown signal to server
	shutdownReason := fmt.Sprintf("Graceful shutdown due to signal: %s", sig.String())
	edrClient.SendShutdownSignal(ctx, shutdownReason)

	logging.Info().Msg("Shutting down agent...")

	// Stop the IOC scanner
	scanner.Stop()

	// Cancel context to stop other goroutines
	cancel()

	// Wait for all goroutines to finish
	done := make(chan struct{})
	go func() {
		wg.Wait()
		close(done)
	}()

	// Wait for graceful shutdown or timeout
	select {
	case <-done:
		logging.Info().Msg("All goroutines stopped gracefully")
	case <-time.After(cfg.GetShutdownTimeoutDuration()):
		logging.Warn().
			Dur("timeout", cfg.GetShutdownTimeoutDuration()).
			Msg("Shutdown timeout reached, forcing exit")
	}

	logging.Info().Msg("Agent shutdown complete")
}

// requestIOCUpdatesOnStartup sends a request to the server for IOC updates
func requestIOCUpdatesOnStartup(ctx context.Context, edrClient *client.EDRClient, delay time.Duration) {
	// Give time for the command stream to establish using configured delay
	time.Sleep(delay)

	logging.Info().Msg("Requesting IOC updates from server...")
	edrClient.RequestIOCUpdates(ctx)
} 