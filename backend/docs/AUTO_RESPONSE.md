# ElastAlert Auto-Response Feature

The EDR system now supports automatic response actions triggered by ElastAlert rules. This feature allows you to automatically execute commands on agents when specific security events are detected.

## How It Works

1. ElastAlert rules include an `auto_response` section defining:
   - Target agents (by agent ID, hostname, or IP)
   - Actions to take (commands to send)
   - Dynamic parameters extracted from alert data

2. When ElastAlert generates an alert, the EDR system:
   - Identifies the affected agents
   - Executes the specified commands (like killing processes or blocking IPs)
   - Updates the alert with information about actions taken

## Setting Up Auto-Response Rules

### Rule Configuration

Add an `auto_response` section to your ElastAlert rule YAML file:

```yaml
# Auto-response configuration
auto_response:
  enabled: true                # Enable/disable auto-response for this rule
  
  targets:                     # How to identify target agents
    field: host.hostname       # Field in alert containing target identifier
    field_type: hostname       # Type of identifier: agent_id, hostname, or ip_address
    filter:
      status: online           # Only target online agents
  
  actions:                     # Commands to execute
    - type: KILL_PROCESS       # Command type
      params:
        pid: "$process.pid"    # Parameter with $ references alert fields
      priority: 2              # Priority (higher is more urgent)
      timeout: 30              # Timeout in seconds
```

### Target Specification

You can specify targets in multiple ways:

1. **By Field**: Extract target from a field in the alert
   ```yaml
   targets:
     field: host.hostname      # Field containing hostname
     field_type: hostname      # Convert to agent ID
   ```

2. **By Regular Expression**: Extract targets using regex
   ```yaml
   targets:
     from_field: message       # Field to extract from
     regex: "host=([\\w-]+)"   # Regex pattern with capture group
     field_type: hostname      # Type of captured value
   ```

3. **Explicit List**: Specify agent IDs directly
   ```yaml
   targets:
     agent_ids:
       - "agent-123"
       - "agent-456"
   ```

### Action Types

The following action types are supported:

| Action Type | Description | Required Parameters |
|-------------|-------------|---------------------|
| `DELETE_FILE` | Delete a file | `path` |
| `KILL_PROCESS` | Kill a process | `pid` |
| `KILL_PROCESS_TREE` | Kill a process and its children | `pid` |
| `BLOCK_IP` | Block an IP address | `ip` |
| `BLOCK_URL` | Block a URL/domain | `url` |
| `NETWORK_ISOLATE` | Isolate host from network | `allowed_ips` (optional) |
| `NETWORK_RESTORE` | Restore network connectivity | None |

### Dynamic Parameters

You can extract parameters from the alert data using the `$` prefix:

```yaml
params:
  pid: "$process.pid"        # Use the process.pid field from the alert
  path: "$process.executable" # Use the process.executable field from the alert
```

## Example Rules

### Suspicious Process Detection

```yaml
name: Suspicious Process with Auto Response
type: any
index: filebeat-*
filter:
- query:
    query_string:
      query: "process.name:mimikatz.exe OR process.name:pwdump.exe"

# Alert configuration
alert: ["email"]
email: ["security@example.com"]

# Auto-response configuration
auto_response:
  enabled: true
  targets:
    field: host.hostname
    field_type: hostname
  
  actions:
    - type: KILL_PROCESS
      params:
        pid: "$process.pid"
      priority: 2
      timeout: 30
```

### Malicious Connection

```yaml
name: Malicious Connection with Auto Response
type: any
index: filebeat-*
filter:
- query:
    query_string:
      query: "destination.ip:\"185.176.27.132\""

# Auto-response configuration
auto_response:
  enabled: true
  targets:
    field: host.hostname
    field_type: hostname
  
  actions:
    - type: BLOCK_IP
      params:
        ip: "$destination.ip"
    - type: KILL_PROCESS
      params:
        pid: "$process.pid"
```

## Processing Alerts Manually

A command-line tool is available to process alerts with auto-response:

```bash
python process_alerts.py --limit 20
```

Options:
- `--limit`: Maximum number of alerts to process (default: 20)
- `--dry-run`: Do not execute actions, just report what would happen
- `--output`: Save results to a JSON file

## Setting Up Scheduled Processing

You can set up a cron job to regularly process new alerts:

1. Create a crontab entry:
   ```
   */5 * * * * cd /path/to/backend && python process_alerts.py --limit 50 >> /var/log/edr_auto_response.log 2>&1
   ```

2. This will process new alerts every 5 minutes.

## Alert Status Management

When auto-response actions are executed, the alert status is updated to "in_progress" with details about the actions taken. This information is visible in the alerts dashboard.

## Security Considerations

- Auto-response actions have the potential to impact system availability
- Test rules thoroughly in a controlled environment before enabling in production
- Consider using the `--dry-run` option initially to validate rule behavior
- Use selective targeting to limit the scope of actions
- Set appropriate timeouts for commands 