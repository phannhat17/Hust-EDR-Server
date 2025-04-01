package config

import (
	"time"
)

// Config holds the agent configuration parameters
type Config struct {
	// ServerAddress is the gRPC server address (host:port)
	ServerAddress string

	// UpdateInterval is the interval between status updates
	UpdateInterval time.Duration

	// TLSEnabled indicates whether to use TLS for gRPC connections
	TLSEnabled bool

	// InsecureSkipVerify allows skipping TLS certificate verification
	InsecureSkipVerify bool

	// AgentVersion is the current agent software version
	AgentVersion string

	// LogFile is the path to the log file
	LogFile string

	// Debug enables debug logging
	Debug bool
}

// DefaultConfig returns a Config with default values
func DefaultConfig() *Config {
	return &Config{
		ServerAddress:      "localhost:50051",
		UpdateInterval:     60 * time.Second,
		TLSEnabled:         false,
		InsecureSkipVerify: false,
		AgentVersion:       "1.0.0",
		LogFile:            "",
		Debug:              false,
	}
} 