param(
    [string]$gRPCHost = "192.168.133.145:50051",
    [string]$ServerHost = "192.168.133.145:5000"
)

# EDR Agent Installation Script
# This script installs the HUST EDR Agent to C:\Program Files\HUST-EDR-Agent

Write-Host "=== HUST EDR Agent Installation Script ===" -ForegroundColor Green
Write-Host "Installing EDR Agent to C:\Program Files\HUST-EDR-Agent" -ForegroundColor Yellow

# Check if running as Administrator
if (-NOT ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")) {
    Write-Error "This script must be run as Administrator!"
    Write-Host "Please right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Red
    exit 1
}

# Define installation paths
$InstallDir = "C:\Program Files\HUST-EDR-Agent"
$DataDir = "$InstallDir\data"
$LogsDir = "$InstallDir\logs"
$ConfigFile = "$InstallDir\config.yaml"
$AgentBinary = "$InstallDir\edr-agent.exe"
$CACertFile = "$DataDir\ca.crt"

# Create installation directories
Write-Host "Creating installation directories..." -ForegroundColor Yellow
try {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
    Write-Host "Directories created successfully" -ForegroundColor Green
} catch {
    Write-Error "Failed to create directories: $_"
    exit 1
}

# Function for faster downloads using .NET WebClient
function Download-File {
    param (
        [string]$Url,
        [string]$OutputFile
    )
    
    Write-Host "Downloading $Url to $OutputFile..."
    $webClient = New-Object System.Net.WebClient
    $webClient.DownloadFile($Url, $OutputFile)
}

# Set security protocol for downloads
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# Download EDR Agent binary
Write-Host "Downloading EDR Agent binary..." -ForegroundColor Yellow
try {
    $AgentUrl = "http://$ServerHost/api/install/edr-agent-binary"
    # Use faster WebClient instead of Invoke-WebRequest
    Download-File -Url $AgentUrl -OutputFile $AgentBinary
    Write-Host "EDR Agent binary downloaded successfully" -ForegroundColor Green
} catch {
    Write-Host "WebClient download failed, trying alternative method..." -ForegroundColor Yellow
    
    # Fallback to BitsTransfer if available
    if (Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue) {
        Write-Host "Using BITS Transfer..."
        Start-BitsTransfer -Source $AgentUrl -Destination $AgentBinary
    } else {
        # Last resort, use Invoke-WebRequest
        Write-Host "Using Invoke-WebRequest..."
        Invoke-WebRequest -Uri $AgentUrl -OutFile $AgentBinary -UseBasicParsing
    }
    
    if (-not (Test-Path $AgentBinary)) {
        Write-Error "Failed to download EDR Agent binary: $_"
        exit 1
    }
}

# Download CA certificate
Write-Host "Downloading CA certificate..." -ForegroundColor Yellow
try {
    # Try to download from the server's certificate endpoint
    $CertUrl = "http://$ServerHost/api/install/kibana-cert"
    Download-File -Url $CertUrl -OutputFile $CACertFile
    Write-Host "CA certificate downloaded successfully" -ForegroundColor Green
} catch {
    Write-Host "WebClient download failed for certificate, trying alternative method..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -Uri $CertUrl -OutFile $CACertFile -UseBasicParsing
        Write-Host "CA certificate downloaded successfully" -ForegroundColor Green
    } catch {
        Write-Warning "Failed to download CA certificate from server: $_"
        Write-Host "You may need to manually place the CA certificate at: $CACertFile" -ForegroundColor Yellow
    }
}

# Create configuration file with proper Windows path formatting
Write-Host "Creating configuration file..." -ForegroundColor Yellow
$ConfigContent = @"
# EDR Agent Configuration File
# This file contains all configuration options for the EDR Agent
# You can customize these values according to your environment

# Server Configuration
server_address: "$gRPCHost"  # EDR server address (host:port)
use_tls: true                      # Enable TLS encryption for server communication

# TLS/Certificate Configuration (only applies when use_tls is true)
ca_cert_path: "C:\\Program Files\\HUST-EDR-Agent\\data\\ca.crt"               # Path to CA certificate for server verification (leave empty to use system CA)
insecure_skip_verify: false          # Skip certificate verification (not recommended for production)

# Agent Identification
agent_id: ""                       # Agent ID (leave empty for auto-generation)
agent_version: "1.0.0"            # Agent version

# File Paths
log_file: ""                       # Log file path (leave empty for console output)
data_dir: "data"                   # Directory for agent data storage

# Logging Configuration
log_level: "info"                  # Log level: debug, info, warn, error
log_format: "console"              # Log format: console, json

# Timing Configuration (in minutes)
scan_interval: 5                   # IOC scan interval
metrics_interval: 10               # System metrics reporting interval

# Connection Configuration (in seconds)
connection_timeout: 30             # Connection timeout
reconnect_delay: 5                 # Delay between reconnection attempts
max_reconnect_delay: 60            # Maximum reconnection delay
ioc_update_delay: 3                # Delay before requesting IOC updates
shutdown_timeout: 500              # Shutdown timeout (milliseconds)

# System Monitoring Configuration
cpu_sample_duration: 500           # CPU sampling duration (milliseconds)

# Windows-specific Configuration
hosts_file_path: "C:\\Windows\\System32\\drivers\\etc\\hosts"
blocked_ip_redirect: "127.0.0.1"   # IP address to redirect blocked domains to

# Certificate Verification Notes:
# - If ca_cert_path is specified, the agent will use this CA certificate to verify the server
# - If ca_cert_path is empty, the agent will use the system's default CA certificates
# - Setting insecure_skip_verify to true bypasses all certificate verification (not recommended)
# - For production environments, always use proper CA certificates and keep insecure_skip_verify false
"@

try {
    $ConfigContent | Out-File -FilePath $ConfigFile -Encoding UTF8
    Write-Host "Configuration file created successfully" -ForegroundColor Green
} catch {
    Write-Error "Failed to create configuration file: $_"
    exit 1
}

# Check and remove existing service first
$ServiceName = "HUST-EDR-Agent"
Write-Host "Checking for existing service..." -ForegroundColor Yellow
$ExistingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($ExistingService) {
    Write-Host "Found existing service '$ServiceName', removing..." -ForegroundColor Yellow
    try {
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
        
        # Try to remove with sc.exe first
        sc.exe delete $ServiceName | Out-Null
        Start-Sleep -Seconds 2
        
        # Verify removal
        $CheckService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
        if ($CheckService) {
            Write-Warning "Service still exists after sc.exe delete, will handle with NSSM"
        } else {
            Write-Host "Existing service removed successfully" -ForegroundColor Green
        }
    } catch {
        Write-Warning "Could not remove existing service with sc.exe, will handle with NSSM: $_"
    }
}

# Download and install NSSM
Write-Host "Downloading NSSM (Non-Sucking Service Manager)..." -ForegroundColor Yellow
$nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
$nssmZip = "$env:TEMP\nssm.zip"
$nssmDir = "$env:TEMP\nssm"
$nssmExe = "$nssmDir\nssm-2.24\win64\nssm.exe"

try {
    Download-File -Url $nssmUrl -OutputFile $nssmZip
    Expand-Archive -Path $nssmZip -DestinationPath $nssmDir -Force
    Write-Host "NSSM downloaded and extracted successfully" -ForegroundColor Green
} catch {
    Write-Error "Failed to download NSSM: $_"
    exit 1
}

# Create Windows Service using NSSM
Write-Host "Creating Windows Service using NSSM..." -ForegroundColor Yellow
try {
    $ServiceDisplayName = "HUST EDR Agent"
    $ServiceDescription = "HUST Endpoint Detection and Response Agent"
    
    # Check if service still exists and remove with NSSM
    $ExistingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($ExistingService) {
        Write-Host "Service still exists, removing with NSSM..." -ForegroundColor Yellow
        Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
        & $nssmExe remove $ServiceName confirm
        Start-Sleep -Seconds 3
    }
    
    # Install service with NSSM
    Write-Host "Installing service with NSSM..." -ForegroundColor Yellow
    & $nssmExe install $ServiceName $AgentBinary
    
    # Set parameters with proper escaping for paths with spaces
    $ConfigParam = "--config `"$ConfigFile`""
    & $nssmExe set $ServiceName AppParameters $ConfigParam
    
    & $nssmExe set $ServiceName DisplayName $ServiceDisplayName
    & $nssmExe set $ServiceName Description $ServiceDescription
    & $nssmExe set $ServiceName Start SERVICE_AUTO_START
    & $nssmExe set $ServiceName AppDirectory $InstallDir
    
    Write-Host "NSSM Configuration:" -ForegroundColor Cyan
    Write-Host "  Binary: $AgentBinary" -ForegroundColor White
    Write-Host "  Parameters: $ConfigParam" -ForegroundColor White
    Write-Host "  Directory: $InstallDir" -ForegroundColor White
    
    # Verify NSSM configuration
    Write-Host "Verifying NSSM configuration..." -ForegroundColor Yellow
    $nssmAppPath = & $nssmExe get $ServiceName Application
    $nssmAppParams = & $nssmExe get $ServiceName AppParameters
    $nssmAppDir = & $nssmExe get $ServiceName AppDirectory
    Write-Host "  Verified Binary: $nssmAppPath" -ForegroundColor Gray
    Write-Host "  Verified Parameters: $nssmAppParams" -ForegroundColor Gray
    Write-Host "  Verified Directory: $nssmAppDir" -ForegroundColor Gray
    
    # Set service recovery options
    & $nssmExe set $ServiceName AppStdout "$LogsDir\stdout.log"
    & $nssmExe set $ServiceName AppStderr "$LogsDir\stderr.log"
    & $nssmExe set $ServiceName AppRotateFiles 1
    & $nssmExe set $ServiceName AppRotateOnline 1
    & $nssmExe set $ServiceName AppRotateSeconds 86400
    & $nssmExe set $ServiceName AppRotateBytes 1048576
    
    Write-Host "Windows Service created successfully with NSSM" -ForegroundColor Green
} catch {
    Write-Error "Failed to create Windows Service with NSSM: $_"
    exit 1
}

# Set appropriate permissions
Write-Host "Setting file permissions..." -ForegroundColor Yellow
try {
    # Give SYSTEM and Administrators full control
    icacls $InstallDir /grant "SYSTEM:(OI)(CI)F" /T | Out-Null
    icacls $InstallDir /grant "Administrators:(OI)(CI)F" /T | Out-Null
    
    # Give Users read and execute permissions
    icacls $InstallDir /grant "Users:(OI)(CI)RX" /T | Out-Null
    
    Write-Host "File permissions set successfully" -ForegroundColor Green
} catch {
    Write-Warning "Failed to set file permissions: $_"
}

# Test agent configuration
Write-Host "Testing agent configuration..." -ForegroundColor Yellow
try {
    $TestOutput = & $AgentBinary --config $ConfigFile --help 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Agent configuration test passed" -ForegroundColor Green
    } else {
        Write-Warning "Agent configuration test failed, but installation will continue"
    }
} catch {
    Write-Warning "Could not test agent configuration: $_"
}

# Start the service
Write-Host "Starting EDR Agent service..." -ForegroundColor Yellow
try {
    Start-Service -Name $ServiceName
    Start-Sleep -Seconds 3
    
    $ServiceStatus = Get-Service -Name $ServiceName
    if ($ServiceStatus.Status -eq "Running") {
        Write-Host "EDR Agent service started successfully" -ForegroundColor Green
    } else {
        Write-Warning "EDR Agent service is not running. Status: $($ServiceStatus.Status)"
        Write-Host "You can start it manually with: Start-Service -Name '$ServiceName'" -ForegroundColor Yellow
    }
} catch {
    Write-Warning "Failed to start EDR Agent service: $_"
    Write-Host "You can start it manually with: Start-Service -Name '$ServiceName'" -ForegroundColor Yellow
}

# Clean up temporary files
Write-Host "Cleaning up temporary files..." -ForegroundColor Yellow
try {
    Remove-Item -Path $nssmZip -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $nssmDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Temporary files cleaned up" -ForegroundColor Green
} catch {
    Write-Warning "Could not clean up some temporary files: $_"
}

# Installation summary
Write-Host "`n=== Installation Summary ===" -ForegroundColor Green
Write-Host "Installation Directory: $InstallDir" -ForegroundColor White
Write-Host "Configuration File: $ConfigFile" -ForegroundColor White
Write-Host "Data Directory: $DataDir" -ForegroundColor White
Write-Host "Logs Directory: $LogsDir" -ForegroundColor White
Write-Host "CA Certificate: $CACertFile" -ForegroundColor White
Write-Host "Service Name: $ServiceName" -ForegroundColor White
Write-Host "Server Address: $gRPCHost" -ForegroundColor White

Write-Host "`n=== Management Commands ===" -ForegroundColor Cyan
Write-Host "Start Service:    Start-Service -Name '$ServiceName'" -ForegroundColor White
Write-Host "Stop Service:     Stop-Service -Name '$ServiceName'" -ForegroundColor White
Write-Host "Service Status:   Get-Service -Name '$ServiceName'" -ForegroundColor White
Write-Host "View Stdout Log:  Get-Content '$LogsDir\stdout.log' -Tail 20" -ForegroundColor White
Write-Host "View Stderr Log:  Get-Content '$LogsDir\stderr.log' -Tail 20" -ForegroundColor White
Write-Host "Manual Run:       & '$AgentBinary' --config '$ConfigFile'" -ForegroundColor White
Write-Host "Manual Run (CD):  cd '$InstallDir'; .\edr-agent.exe --config '$ConfigFile'" -ForegroundColor White
Write-Host "Remove Service:   nssm remove '$ServiceName' confirm" -ForegroundColor White

Write-Host "`nHUST EDR Agent installation completed successfully!" -ForegroundColor Green
Write-Host "The agent should now be running and connecting to the server." -ForegroundColor Yellow 