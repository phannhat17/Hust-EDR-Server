# EDR Agent

The EDR Agent is a Windows-based endpoint detection and response agent that combines three components:
1. Sysmon - For detailed system monitoring
2. Winlogbeat - For log collection and forwarding
3. Custom Agent - For real-time monitoring and response

## Installation

The agent is installed using a PowerShell script that sets up all components. The installation requires administrator privileges.

### Prerequisites

- Windows 10/11 or Windows Server 2016/2019/2022
- Administrator privileges
- PowerShell 5.1 or later
- .NET Framework 4.7.2 or later

### Installation Process

1. Download the agent package
2. Extract the files to a temporary location
3. Run the installation script as administrator:

```powershell
.\install.ps1 -ElkServer "your-elk-server" -ElkPort "9200" -ElkUsername "elastic" -ElkPassword "your-password"
```

Optional parameters:
- `-AgentId`: Custom agent ID (default: auto-generated GUID)
- `-InstallPath`: Installation directory (default: "C:\Program Files\EDR Agent")

### Components

#### Sysmon
- Installed with predefined security-focused configuration
- Monitors system activity and process creation
- Logs to Windows Event Log

#### Winlogbeat
- Collects and forwards Windows Event Logs
- Configured to send logs to Elasticsearch
- Uses SSL/TLS for secure communication
- Includes custom fields for agent identification

#### Custom Agent
- Installed as a Windows service
- Communicates with the EDR server
- Performs real-time monitoring and response
- Handles auto-response actions

## Directory Structure

```
agent/
├── install/                    # Installation scripts and resources
│   ├── sysmon/                # Sysmon installation files
│   │   ├── sysmon.exe         # Sysmon executable
│   │   └── sysmon-config.xml  # Predefined Sysmon configuration
│   ├── winlogbeat/            # Winlogbeat installation files
│   │   ├── winlogbeat.exe     # Winlogbeat executable
│   │   ├── winlogbeat.yml     # Template configuration
│   │   └── elk-ca.pem         # ELK server certificate
│   └── install.ps1            # Main PowerShell installation script
└── src/                       # Agent source code
    ├── main.go
    ├── go.mod
    ├── client/
    ├── proto/
    ├── collector/
    └── config/
```

## Configuration

### Winlogbeat Configuration
The Winlogbeat configuration is generated during installation with the following parameters:
- ELK server address and port
- Authentication credentials
- Agent ID
- SSL/TLS settings

### Agent Configuration
The agent configuration is stored in the installation directory and includes:
- Server connection details
- Monitoring settings
- Auto-response rules

## Troubleshooting

### Common Issues

1. **Installation Fails**
   - Ensure running as administrator
   - Check PowerShell execution policy
   - Verify network connectivity to ELK server

2. **Winlogbeat Service Not Starting**
   - Check configuration file syntax
   - Verify ELK server connectivity
   - Check Windows Event Log for errors

3. **Agent Service Issues**
   - Check agent logs in installation directory
   - Verify server connectivity
   - Check Windows Event Log for service errors

### Logs

- Sysmon logs: Windows Event Log -> Applications and Services Logs -> Microsoft -> Windows -> Sysmon
- Winlogbeat logs: Windows Event Log -> Applications and Services Logs -> Winlogbeat
- Agent logs: Installation directory -> logs folder

## Security

- All components use secure communication (TLS)
- Sensitive credentials are stored securely
- Services run with least privilege
- Regular security updates recommended

## Development

For development and building the agent, see the `src` directory README. 