package config

import (
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"gopkg.in/yaml.v3"
)

// Default configuration values - centralized constants
const (
	// Server defaults
	DefaultServerAddress = "localhost:50051"
	DefaultUseTLS        = true
	
	// Agent defaults
	DefaultAgentVersion = "1.0.0"
	DefaultDataDir      = "data"
	DefaultConfigFile   = "config.yaml"
	
	// TLS/Certificate defaults
	DefaultCACertPath        = ""    // Path to CA certificate for server verification
	DefaultInsecureSkipVerify = false // Whether to skip certificate verification
	
	// Logging defaults
	DefaultLogLevel  = "info"
	DefaultLogFormat = "console"
	
	// Timing defaults (in minutes)
	DefaultScanInterval    = 5
	DefaultMetricsInterval = 30
	
	// Connection defaults (in seconds)
	DefaultConnectionTimeout    = 30
	DefaultReconnectDelay      = 5
	DefaultMaxReconnectDelay   = 60
	DefaultIOCUpdateDelay      = 3
	DefaultShutdownTimeout     = 500 // milliseconds
	
	// System monitoring defaults
	DefaultCPUSampleDuration = 500 // milliseconds
	
	// Windows-specific defaults
	DefaultSysmonLogPath = "C:\\Windows\\System32\\winevt\\Logs\\Microsoft-Windows-Sysmon%4Operational.evtx"
	DefaultHostsFilePath = "C:\\Windows\\System32\\drivers\\etc\\hosts"
	DefaultBlockedIPRedirect = "127.0.0.1"
	
	// Validation limits
	MinScanInterval    = 1
	MaxScanInterval    = 1440 // 24 hours
	MinMetricsInterval = 1
	MaxMetricsInterval = 1440 // 24 hours
	MinConnectionTimeout = 5
	MaxConnectionTimeout = 300 // 5 minutes
)

// Config represents the complete agent configuration
type Config struct {
	// Server configuration
	ServerAddress string `yaml:"server_address" json:"server_address"`
	UseTLS        bool   `yaml:"use_tls" json:"use_tls"`
	
	// TLS/Certificate configuration
	CACertPath        string `yaml:"ca_cert_path" json:"ca_cert_path"`               // Path to CA certificate for server verification
	InsecureSkipVerify bool   `yaml:"insecure_skip_verify" json:"insecure_skip_verify"` // Skip certificate verification (not recommended for production)
	
	// Agent identification
	AgentID      string `yaml:"agent_id" json:"agent_id"`
	AgentVersion string `yaml:"agent_version" json:"agent_version"`
	
	// File paths
	LogFile   string `yaml:"log_file" json:"log_file"`
	DataDir   string `yaml:"data_dir" json:"data_dir"`
	
	// Logging configuration
	LogLevel  string `yaml:"log_level" json:"log_level"`
	LogFormat string `yaml:"log_format" json:"log_format"` // "json" or "console"
	
	// Timing configuration (in minutes)
	ScanInterval    int `yaml:"scan_interval" json:"scan_interval"`
	MetricsInterval int `yaml:"metrics_interval" json:"metrics_interval"`
	
	// Connection configuration (in seconds)
	ConnectionTimeout   int `yaml:"connection_timeout" json:"connection_timeout"`
	ReconnectDelay     int `yaml:"reconnect_delay" json:"reconnect_delay"`
	MaxReconnectDelay  int `yaml:"max_reconnect_delay" json:"max_reconnect_delay"`
	IOCUpdateDelay     int `yaml:"ioc_update_delay" json:"ioc_update_delay"`
	ShutdownTimeout    int `yaml:"shutdown_timeout" json:"shutdown_timeout"` // milliseconds
	
	// System monitoring configuration
	CPUSampleDuration int `yaml:"cpu_sample_duration" json:"cpu_sample_duration"` // milliseconds
	
	// Windows-specific configuration
	SysmonLogPath     string `yaml:"sysmon_log_path" json:"sysmon_log_path"`
	HostsFilePath     string `yaml:"hosts_file_path" json:"hosts_file_path"`
	BlockedIPRedirect string `yaml:"blocked_ip_redirect" json:"blocked_ip_redirect"`
	
	// Internal flags (not saved to YAML)
	ConfigFile string `yaml:"-" json:"-"`
}

// ValidationError represents a configuration validation error
type ValidationError struct {
	Field   string
	Value   interface{}
	Message string
}

func (e ValidationError) Error() string {
	return fmt.Sprintf("config validation error for field '%s' (value: %v): %s", e.Field, e.Value, e.Message)
}

// NewDefaultConfig creates a new configuration with default values
func NewDefaultConfig() *Config {
	return &Config{
		ServerAddress:       DefaultServerAddress,
		UseTLS:             DefaultUseTLS,
		CACertPath:         DefaultCACertPath,
		InsecureSkipVerify: DefaultInsecureSkipVerify,
		AgentVersion:       DefaultAgentVersion,
		DataDir:            DefaultDataDir,
		LogLevel:           DefaultLogLevel,
		LogFormat:          DefaultLogFormat,
		ScanInterval:       DefaultScanInterval,
		MetricsInterval:    DefaultMetricsInterval,
		ConnectionTimeout:  DefaultConnectionTimeout,
		ReconnectDelay:     DefaultReconnectDelay,
		MaxReconnectDelay:  DefaultMaxReconnectDelay,
		IOCUpdateDelay:     DefaultIOCUpdateDelay,
		ShutdownTimeout:    DefaultShutdownTimeout,
		CPUSampleDuration:  DefaultCPUSampleDuration,
		SysmonLogPath:      DefaultSysmonLogPath,
		HostsFilePath:      DefaultHostsFilePath,
		BlockedIPRedirect:  DefaultBlockedIPRedirect,
		ConfigFile:         DefaultConfigFile,
	}
}

// LoadConfig loads configuration with precedence: flags > YAML > defaults
func LoadConfig(configFile string) (*Config, error) {
	// Start with defaults
	cfg := NewDefaultConfig()
	cfg.ConfigFile = configFile
	
	// Check if config file exists
	if _, err := os.Stat(configFile); os.IsNotExist(err) {
		// File doesn't exist, create it with default values
		fmt.Printf("Configuration file %s not found, creating with default values...\n", configFile)
		
		if err := cfg.SaveConfig(configFile); err != nil {
			return nil, fmt.Errorf("failed to create default config file %s: %v", configFile, err)
		}
		
		fmt.Printf("Default configuration file created at %s\n", configFile)
		fmt.Printf("You can edit this file to customize your agent settings.\n")
	} else {
		// Load from existing YAML file
		if err := cfg.loadFromYAML(configFile); err != nil {
			return nil, fmt.Errorf("failed to load config from %s: %v", configFile, err)
		}
	}
	
	// Validate configuration
	if err := cfg.Validate(); err != nil {
		return nil, fmt.Errorf("configuration validation failed: %v", err)
	}
	
	return cfg, nil
}

// loadFromYAML loads configuration from a YAML file
func (c *Config) loadFromYAML(filename string) error {
	data, err := os.ReadFile(filename)
	if err != nil {
		return err
	}
	
	return yaml.Unmarshal(data, c)
}

// ApplyFlags applies command-line flag values with highest precedence
func (c *Config) ApplyFlags(flags map[string]interface{}) error {
	for key, value := range flags {
		if value == nil {
			continue
		}
		
		switch key {
		case "server":
			if v, ok := value.(string); ok && v != "" {
				c.ServerAddress = v
			}
		case "agent_id":
			if v, ok := value.(string); ok && v != "" {
				c.AgentID = v
			}
		case "log_file":
			if v, ok := value.(string); ok && v != "" {
				c.LogFile = v
			}
		case "data_dir":
			if v, ok := value.(string); ok && v != "" {
				c.DataDir = v
			}
		case "scan_interval":
			if v, ok := value.(int); ok && v > 0 {
				c.ScanInterval = v
			}
		case "metrics_interval":
			if v, ok := value.(int); ok && v > 0 {
				c.MetricsInterval = v
			}
		case "use_tls":
			if v, ok := value.(bool); ok {
				c.UseTLS = v
			}
		case "connection_timeout":
			if v, ok := value.(int); ok && v > 0 {
				c.ConnectionTimeout = v
			}
		}
	}
	
	// Validate after applying flags
	return c.Validate()
}

// Validate validates all configuration values
func (c *Config) Validate() error {
	var errors []ValidationError
	
	// Validate server address
	if c.ServerAddress == "" {
		errors = append(errors, ValidationError{
			Field:   "server_address",
			Value:   c.ServerAddress,
			Message: "server address cannot be empty",
		})
	} else {
		if err := c.validateServerAddress(); err != nil {
			errors = append(errors, ValidationError{
				Field:   "server_address",
				Value:   c.ServerAddress,
				Message: err.Error(),
			})
		}
	}
	
	// Validate intervals
	if c.ScanInterval < MinScanInterval || c.ScanInterval > MaxScanInterval {
		errors = append(errors, ValidationError{
			Field:   "scan_interval",
			Value:   c.ScanInterval,
			Message: fmt.Sprintf("must be between %d and %d minutes", MinScanInterval, MaxScanInterval),
		})
	}
	
	if c.MetricsInterval < MinMetricsInterval || c.MetricsInterval > MaxMetricsInterval {
		errors = append(errors, ValidationError{
			Field:   "metrics_interval",
			Value:   c.MetricsInterval,
			Message: fmt.Sprintf("must be between %d and %d minutes", MinMetricsInterval, MaxMetricsInterval),
		})
	}
	
	// Validate connection timeout
	if c.ConnectionTimeout < MinConnectionTimeout || c.ConnectionTimeout > MaxConnectionTimeout {
		errors = append(errors, ValidationError{
			Field:   "connection_timeout",
			Value:   c.ConnectionTimeout,
			Message: fmt.Sprintf("must be between %d and %d seconds", MinConnectionTimeout, MaxConnectionTimeout),
		})
	}
	
	// Validate reconnect delays
	if c.ReconnectDelay <= 0 {
		errors = append(errors, ValidationError{
			Field:   "reconnect_delay",
			Value:   c.ReconnectDelay,
			Message: "must be greater than 0",
		})
	}
	
	if c.MaxReconnectDelay < c.ReconnectDelay {
		errors = append(errors, ValidationError{
			Field:   "max_reconnect_delay",
			Value:   c.MaxReconnectDelay,
			Message: "must be greater than or equal to reconnect_delay",
		})
	}
	
	// Validate data directory
	if c.DataDir == "" {
		errors = append(errors, ValidationError{
			Field:   "data_dir",
			Value:   c.DataDir,
			Message: "data directory cannot be empty",
		})
	}
	
	// Validate file paths
	if c.SysmonLogPath == "" {
		errors = append(errors, ValidationError{
			Field:   "sysmon_log_path",
			Value:   c.SysmonLogPath,
			Message: "sysmon log path cannot be empty",
		})
	}
	
	if c.HostsFilePath == "" {
		errors = append(errors, ValidationError{
			Field:   "hosts_file_path",
			Value:   c.HostsFilePath,
			Message: "hosts file path cannot be empty",
		})
	}
	
	// Validate IP redirect address
	if net.ParseIP(c.BlockedIPRedirect) == nil {
		errors = append(errors, ValidationError{
			Field:   "blocked_ip_redirect",
			Value:   c.BlockedIPRedirect,
			Message: "must be a valid IP address",
		})
	}
	
	// Validate CA certificate path if TLS is enabled and path is specified
	if c.UseTLS && c.CACertPath != "" {
		if _, err := os.Stat(c.CACertPath); os.IsNotExist(err) {
			errors = append(errors, ValidationError{
				Field:   "ca_cert_path",
				Value:   c.CACertPath,
				Message: "CA certificate file does not exist",
			})
		}
	}
	
	// Return first error if any
	if len(errors) > 0 {
		return errors[0]
	}
	
	return nil
}

// validateServerAddress validates the server address format
func (c *Config) validateServerAddress() error {
	// Check if it contains a port
	host, port, err := net.SplitHostPort(c.ServerAddress)
	if err != nil {
		return fmt.Errorf("invalid server address format (expected host:port): %v", err)
	}
	
	// Validate host
	if host == "" {
		return fmt.Errorf("host cannot be empty")
	}
	
	// Validate port
	portNum, err := strconv.Atoi(port)
	if err != nil {
		return fmt.Errorf("invalid port number: %v", err)
	}
	
	if portNum < 1 || portNum > 65535 {
		return fmt.Errorf("port number must be between 1 and 65535")
	}
	
	return nil
}

// SaveConfig saves configuration to a YAML file with helpful comments
func (c *Config) SaveConfig(filename string) error {
	// Create directory if it doesn't exist
	dir := filepath.Dir(filename)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("failed to create config directory: %v", err)
	}
	
	// Create YAML content with comments
	yamlContent := c.generateYAMLWithComments()
	
	// Write to file
	if err := os.WriteFile(filename, []byte(yamlContent), 0644); err != nil {
		return fmt.Errorf("failed to write config file: %v", err)
	}
	
	return nil
}

// generateYAMLWithComments creates a YAML string with helpful comments
func (c *Config) generateYAMLWithComments() string {
	return fmt.Sprintf(`# EDR Agent Configuration File
# This file contains all configuration options for the EDR Agent
# You can customize these values according to your environment

# Server Configuration
server_address: "%s"  # EDR server address (host:port)
use_tls: %t                      # Enable TLS encryption for server communication

# TLS/Certificate Configuration (only applies when use_tls is true)
ca_cert_path: "%s"               # Path to CA certificate for server verification (leave empty to use system CA)
insecure_skip_verify: %t          # Skip certificate verification (not recommended for production)

# Agent Identification
agent_id: "%s"                       # Agent ID (leave empty for auto-generation)
agent_version: "%s"            # Agent version

# File Paths
log_file: "%s"                       # Log file path (leave empty for console output)
data_dir: "%s"                   # Directory for agent data storage

# Logging Configuration
log_level: "%s"                  # Log level: debug, info, warn, error
log_format: "%s"              # Log format: console, json

# Timing Configuration (in minutes)
scan_interval: %d                   # IOC scan interval
metrics_interval: %d               # System metrics reporting interval

# Connection Configuration (in seconds)
connection_timeout: %d             # Connection timeout
reconnect_delay: %d                 # Delay between reconnection attempts
max_reconnect_delay: %d            # Maximum reconnection delay
ioc_update_delay: %d                # Delay before requesting IOC updates
shutdown_timeout: %d              # Shutdown timeout (milliseconds)

# System Monitoring Configuration
cpu_sample_duration: %d           # CPU sampling duration (milliseconds)

# Windows-specific Configuration
sysmon_log_path: "%s"
hosts_file_path: "%s"
blocked_ip_redirect: "%s"   # IP address to redirect blocked domains to

# Certificate Verification Notes:
# - If ca_cert_path is specified, the agent will use this CA certificate to verify the server
# - If ca_cert_path is empty, the agent will use the system's default CA certificates
# - Setting insecure_skip_verify to true bypasses all certificate verification (not recommended)
# - For production environments, always use proper CA certificates and keep insecure_skip_verify false
`,
		c.ServerAddress,
		c.UseTLS,
		c.CACertPath,
		c.InsecureSkipVerify,
		c.AgentID,
		c.AgentVersion,
		c.LogFile,
		c.DataDir,
		c.LogLevel,
		c.LogFormat,
		c.ScanInterval,
		c.MetricsInterval,
		c.ConnectionTimeout,
		c.ReconnectDelay,
		c.MaxReconnectDelay,
		c.IOCUpdateDelay,
		c.ShutdownTimeout,
		c.CPUSampleDuration,
		c.SysmonLogPath,
		c.HostsFilePath,
		c.BlockedIPRedirect,
	)
}

// GetConnectionTimeoutDuration returns connection timeout as time.Duration
func (c *Config) GetConnectionTimeoutDuration() time.Duration {
	return time.Duration(c.ConnectionTimeout) * time.Second
}

// GetReconnectDelayDuration returns reconnect delay as time.Duration
func (c *Config) GetReconnectDelayDuration() time.Duration {
	return time.Duration(c.ReconnectDelay) * time.Second
}

// GetMaxReconnectDelayDuration returns max reconnect delay as time.Duration
func (c *Config) GetMaxReconnectDelayDuration() time.Duration {
	return time.Duration(c.MaxReconnectDelay) * time.Second
}

// GetIOCUpdateDelayDuration returns IOC update delay as time.Duration
func (c *Config) GetIOCUpdateDelayDuration() time.Duration {
	return time.Duration(c.IOCUpdateDelay) * time.Second
}

// GetShutdownTimeoutDuration returns shutdown timeout as time.Duration
func (c *Config) GetShutdownTimeoutDuration() time.Duration {
	return time.Duration(c.ShutdownTimeout) * time.Millisecond
}

// GetCPUSampleDuration returns CPU sample duration as time.Duration
func (c *Config) GetCPUSampleDuration() time.Duration {
	return time.Duration(c.CPUSampleDuration) * time.Millisecond
}

// GetScanIntervalDuration returns scan interval as time.Duration
func (c *Config) GetScanIntervalDuration() time.Duration {
	return time.Duration(c.ScanInterval) * time.Minute
}

// GetMetricsIntervalDuration returns metrics interval as time.Duration
func (c *Config) GetMetricsIntervalDuration() time.Duration {
	return time.Duration(c.MetricsInterval) * time.Minute
}

// String returns a string representation of the configuration
func (c *Config) String() string {
	return fmt.Sprintf("Config{Server: %s, TLS: %v, DataDir: %s, ScanInterval: %dm, MetricsInterval: %dm}",
		c.ServerAddress, c.UseTLS, c.DataDir, c.ScanInterval, c.MetricsInterval)
}

// Legacy functions for backward compatibility
func LoadConfigLegacy(filename string) (*Config, error) {
	return LoadConfig(filename)
}

func SaveConfigLegacy(filename string, cfg *Config) error {
	return cfg.SaveConfig(filename)
} 