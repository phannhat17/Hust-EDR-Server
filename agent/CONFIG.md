# EDR Agent Configuration System

## Overview

The EDR Agent uses a centralized configuration system that supports multiple sources with clear precedence rules. All configuration values are managed through the `config.go` file and can be set via YAML files, command-line flags, or defaults.

## Configuration Precedence

The configuration system follows a strict precedence order:

1. **Command-line flags** (highest priority)
2. **YAML configuration file**
3. **Default values** (lowest priority)

This means command-line flags will always override YAML file settings, and YAML file settings will override default values.

## Configuration Sources

### 1. Default Values

All configuration options have sensible default values defined as constants in `config/config.go`:

```go
const (
    DefaultServerAddress = "localhost:50051"
    DefaultUseTLS        = true
    DefaultScanInterval  = 5
    // ... etc
)
```

### 2. YAML Configuration File

Create a `config.yaml` file to customize settings:

```yaml
server_address: "production-server:50051"
use_tls: true
scan_interval: 10
metrics_interval: 60
data_dir: "/opt/edr/data"
log_file: "/var/log/edr-agent.log"
```

### 3. Command-line Flags

Override any setting using command-line flags:

```bash
./edr-agent \
  --server "custom-server:50051" \
  --scan-interval 15 \
  --data "/custom/data/dir" \
  --tls=false
```

## Configuration Options

### Server Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `server_address` | string | `localhost:50051` | Server address and port |
| `use_tls` | bool | `true` | Enable TLS encryption |

### Agent Identification

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `agent_id` | string | `""` | Agent ID (auto-generated if empty) |
| `agent_version` | string | `1.0.0` | Agent version |

### File Paths

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `log_file` | string | `""` | Log file path (stdout if empty) |
| `data_dir` | string | `data` | Data directory for IOCs and storage |

### Timing Configuration (minutes)

| Option | Type | Default | Range | Description |
|--------|------|---------|-------|-------------|
| `scan_interval` | int | `5` | 1-1440 | IOC scan interval |
| `metrics_interval` | int | `5` | 1-1440 | System metrics reporting interval (must be < 10 minutes for agent to stay online) |

### Connection Configuration (seconds)

| Option | Type | Default | Range | Description |
|--------|------|---------|-------|-------------|
| `connection_timeout` | int | `30` | 5-300 | Connection timeout |
| `reconnect_delay` | int | `5` | >0 | Initial reconnect delay |
| `max_reconnect_delay` | int | `60` | >=reconnect_delay | Maximum reconnect delay |
| `ioc_update_delay` | int | `3` | >0 | Startup IOC update delay |
| `shutdown_timeout` | int | `500` | >0 | Shutdown timeout (milliseconds) |

### System Monitoring

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `cpu_sample_duration` | int | `500` | CPU usage sample duration (milliseconds) |

### Windows-specific Configuration

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `hosts_file_path` | string | `C:\Windows\System32\drivers\etc\hosts` | Windows hosts file path |
| `blocked_ip_redirect` | string | `127.0.0.1` | IP address for blocked domains |

## Configuration Validation

The configuration system includes comprehensive validation:

### Automatic Validation

- **Server address**: Must be in `host:port` format with valid port (1-65535)
- **IP addresses**: Must be valid IPv4/IPv6 addresses
- **File paths**: Must not be empty for required paths
- **Ranges**: All numeric values are validated against their allowed ranges

### Validation Errors

If validation fails, the agent will exit with a descriptive error message:

```
config validation error for field 'scan_interval' (value: 0): must be between 1 and 1440 minutes
```

## Usage Examples

### Basic Usage with Defaults

```bash
./edr-agent
```

Uses all default values.

### Using Configuration File

```bash
./edr-agent --config /etc/edr/config.yaml
```

### Override Specific Settings

```bash
./edr-agent \
  --config /etc/edr/config.yaml \
  --server "production:50051" \
  --scan-interval 30
```

### Development Mode

```bash
./edr-agent \
  --server "localhost:50051" \
  --tls=false \
  --scan-interval 1 \
  --log /tmp/edr-debug.log
```

## Configuration Management

### Loading Configuration

```go
// Load with defaults and YAML
cfg, err := config.LoadConfig("config.yaml")
if err != nil {
    log.Fatalf("Failed to load config: %v", err)
}

// Apply command-line overrides
flagOverrides := map[string]interface{}{
    "server": "custom-server:50051",
    "scan_interval": 15,
}
err = cfg.ApplyFlags(flagOverrides)
```

### Saving Configuration

```go
// Save current configuration
err := cfg.SaveConfig("config.yaml")
if err != nil {
    log.Printf("Failed to save config: %v", err)
}
```

### Accessing Configuration Values

```go
// Direct access
serverAddr := cfg.ServerAddress
scanInterval := cfg.ScanInterval

// Duration helpers
scanDuration := cfg.GetScanIntervalDuration()
timeout := cfg.GetConnectionTimeoutDuration()
```

## Migration from Hardcoded Values

All previously hardcoded values have been moved to the configuration system:

- **Timeouts**: `3*time.Second`, `5*time.Second`, `60*time.Second` → configurable
- **File paths**: `C:\Windows\...` → configurable with defaults
- **IP addresses**: `127.0.0.1`, `localhost:50051` → configurable
- **Intervals**: Fixed scan/metrics intervals → configurable

## Best Practices

1. **Use YAML files** for environment-specific settings
2. **Use command-line flags** for temporary overrides
3. **Validate configuration** early in application startup
4. **Document custom settings** in your deployment
5. **Use duration helpers** instead of manual time calculations
6. **Keep metrics_interval < 10 minutes** to ensure agents stay online (server timeout is 10 minutes)
6. **Keep sensitive data** out of configuration files when possible

## Troubleshooting

### Common Issues

1. **Invalid server address**: Ensure format is `host:port`
2. **Permission errors**: Check file permissions for config/log files
3. **Validation failures**: Review error messages for specific field issues
4. **Path issues**: Use absolute paths for production deployments

### Debug Configuration

Enable debug logging to see configuration loading:

```bash
./edr-agent --log /tmp/debug.log
```

Check the log for configuration loading messages and validation results. 