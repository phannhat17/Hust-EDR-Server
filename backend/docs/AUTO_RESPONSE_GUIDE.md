# Auto-Response Guide: Simplified Implementation

This guide explains the new simplified auto-response implementation for the EDR system.

## Overview

The auto-response feature allows automatic execution of commands on agents when security alerts are detected. The new implementation uses fixed fields in the alert data to trigger and configure auto-responses.

## How It Works

1. ElastAlert generates an alert with special `auto_response_*` fields
2. The EDR backend processes the alert and performs the specified action
3. The alert is updated with the result of the action
4. No retries are attempted - one command per alert

## Required Fields

For an alert to trigger an auto-response, it must include the following fields:

| Field | Description | Required |
|-------|-------------|----------|
| `auto_response_type` | Action type (e.g., DELETE_FILE, KILL_PROCESS) | Yes |
| `auto_response_agent_id` | Agent ID to target | If not specified, will attempt to use hostname |

### Action-Specific Fields

Depending on the action type, additional fields are required:

#### DELETE_FILE
- `auto_response_file_path`: Full path to the file to delete

#### KILL_PROCESS or KILL_PROCESS_TREE
- `auto_response_pid`: Process ID to kill

#### BLOCK_IP
- `auto_response_ip`: IP address to block

#### BLOCK_URL
- `auto_response_url`: URL to block

#### NETWORK_ISOLATE
- `auto_response_allowed_ips`: (Optional) Comma-separated list of IPs to allow

### Optional Fields
- `auto_response_priority`: Priority of the command (integer, default: 1)
- `auto_response_timeout`: Timeout in seconds (integer, default: 60)

## Example Alert Data

Here's an example of alert data with auto-response fields for deleting a file:

```json
{
  "rule_name": "Malware Detection",
  "@timestamp": "2023-05-15T12:30:45Z",
  "host": {
    "hostname": "win-desktop-01"
  },
  "file": {
    "path": "C:\\Windows\\Temp\\malware.exe"
  },
  "auto_response_type": "DELETE_FILE",
  "auto_response_file_path": "C:\\Windows\\Temp\\malware.exe"
}
```

## Adding Auto-Response Fields to ElastAlert Rules

You can add auto-response fields to alerts using ElastAlert's `match_enhancements` feature:

```yaml
match_enhancements:
  - "elastalert_modules.enhance_auto_response:add_auto_response_fields"
```

Then create a Python file at `elastalert_modules/enhance_auto_response.py`:

```python
def add_auto_response_fields(match, rule):
    # Add fixed auto-response fields based on alert data
    match['auto_response_type'] = 'DELETE_FILE'
    match['auto_response_file_path'] = match.get('file', {}).get('path')
    return match
```

## Monitoring Auto-Response Results

Auto-response results are logged and stored in the alert status:

- Successful actions: Alert status is set to `processed`
- Failed actions: Alert status is set to `failed` with error details

You can monitor auto-response execution through:

1. ElastAlert UI dashboard
2. Backend logs
3. Elasticsearch queries for alerts with auto-response status 