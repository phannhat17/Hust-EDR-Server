package config

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

// Config represents the agent configuration
type Config struct {
	ServerAddress string `yaml:"server_address"`
	AgentID       string `yaml:"agent_id"`
	LogFile       string `yaml:"log_file"`
	DataDir       string `yaml:"data_dir"`
	ScanInterval  int    `yaml:"scan_interval"`
	Version       string `yaml:"version"`
	UseTLS        bool   `yaml:"use_tls"`
}

// LoadConfig loads configuration from a YAML file
func LoadConfig(filename string) (*Config, error) {
	// Read file contents
	data, err := os.ReadFile(filename)
	if err != nil {
		return nil, err
	}

	// Unmarshal YAML
	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("failed to parse config file: %v", err)
	}

	// Set defaults for empty values
	if cfg.ServerAddress == "" {
		cfg.ServerAddress = "localhost:50051"
	}
	if cfg.DataDir == "" {
		cfg.DataDir = "data"
	}
	if cfg.ScanInterval <= 0 {
		cfg.ScanInterval = 5
	}
	if cfg.Version == "" {
		cfg.Version = "1.0.0"
	}

	return &cfg, nil
}

// SaveConfig saves configuration to a YAML file
func SaveConfig(filename string, cfg *Config) error {
	// Marshal to YAML
	data, err := yaml.Marshal(cfg)
	if err != nil {
		return fmt.Errorf("failed to marshal config: %v", err)
	}

	// Write to file
	return os.WriteFile(filename, data, 0644)
} 