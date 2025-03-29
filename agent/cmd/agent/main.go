package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/hustonpi/edr-agent/internal/client"
)

var (
	serverAddr   = flag.String("server", "localhost:50051", "Server address (host:port)")
	sendInterval = flag.Duration("interval", 5*time.Minute, "Interval between machine info updates")
	checkMode    = flag.Bool("check", false, "Check connection to server and exit")
)

func main() {
	// Parse command line flags
	flag.Parse()

	// Create a new client
	grpcClient, err := client.NewClient(*serverAddr)
	if err != nil {
		log.Fatalf("Failed to create client: %v", err)
	}
	defer grpcClient.Close()

	// Check mode - just verify connection and exit
	if *checkMode {
		fmt.Printf("Checking connection to server at %s...\n", *serverAddr)
		connected, err := grpcClient.CheckConnection()
		if err != nil {
			fmt.Printf("❌ Failed to connect to server: %v\n", err)
			os.Exit(1)
		}
		if connected {
			fmt.Printf("✅ Successfully connected to EDR server at %s\n", *serverAddr)
			os.Exit(0)
		} else {
			fmt.Printf("❌ Connection test failed: Server returned error\n")
			os.Exit(1)
		}
	}

	log.Println("Starting EDR agent...")
	log.Printf("Server address: %s", *serverAddr)
	log.Printf("Update interval: %s", *sendInterval)

	// Set up signal handling for graceful shutdown
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)

	// Create a ticker for periodic updates
	ticker := time.NewTicker(*sendInterval)
	defer ticker.Stop()

	// Send the initial machine info
	if err := sendMachineInfo(grpcClient); err != nil {
		log.Printf("Failed to send initial machine info: %v", err)
	}

	// Main loop
	for {
		select {
		case <-ticker.C:
			if err := sendMachineInfo(grpcClient); err != nil {
				log.Printf("Failed to send machine info: %v", err)
			}
		case sig := <-sigChan:
			log.Printf("Received signal: %v", sig)
			log.Println("Shutting down agent...")
			return
		}
	}
}

// sendMachineInfo sends the machine info to the server
func sendMachineInfo(c *client.Client) error {
	log.Println("Sending machine information to server...")
	
	// Try to send the machine info
	err := c.SendMachineInfo()
	if err != nil {
		return fmt.Errorf("failed to send machine info: %v", err)
	}
	
	log.Println("Machine information sent successfully")
	return nil
} 