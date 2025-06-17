param(
    [string]$gRPCHost = "localhost:50051",
    [string]$ServerHost = "localhost:5000"
)

#==============================================================================
# HUST EDR Agent Installation Script
# Description: Installs the HUST EDR Agent as a Windows service
# Requirements: Administrator privileges
# Version: 2.0
#==============================================================================

# Script Configuration
$SCRIPT_NAME = "HUST EDR Agent Installer"
$SCRIPT_VERSION = "2.0"
$SERVICE_NAME = "HUST-EDR-Agent"
$SERVICE_DISPLAY_NAME = "HUST EDR Agent"
$SERVICE_DESCRIPTION = "HUST Endpoint Detection and Response Agent"

# Installation Paths
$INSTALL_DIR = "C:\Program Files\HUST-EDR-Agent"
$DATA_DIR = "C:\ProgramData\HUST-EDR-Agent"
$LOGS_DIR = "$INSTALL_DIR\logs"
$TEMP_DIR = "$env:TEMP\HUST-EDR-Install"

# File Paths
$CONFIG_FILE = "$DATA_DIR\config.yaml"
$AGENT_BINARY = "$INSTALL_DIR\edr-agent.exe"
$CA_CERT_FILE = "$DATA_DIR\ca.crt"
$NSSM_ZIP = "$TEMP_DIR\nssm.zip"
$NSSM_DIR = "$TEMP_DIR\nssm"
$NSSM_EXE = "$NSSM_DIR\nssm-2.24\win64\nssm.exe"

# Download URLs
$AGENT_URL = "http://$ServerHost/api/install/edr-agent-binary"
$CERT_URL = "http://$ServerHost/api/install/ca-cert"
$NSSM_URL = "https://nssm.cc/release/nssm-2.24.zip"

#==============================================================================
# Common Functions
#==============================================================================

function Write-Header {
    param([string]$Title, [string]$Color = "Green")
    Write-Host "`n=== $Title ===" -ForegroundColor $Color
}

function Write-Step {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Yellow
}

function Write-Success {
    param([string]$Message)
    Write-Host $Message -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "WARNING: $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
}

function Test-Administrator {
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Initialize-Environment {
    Write-Step "Initializing environment..."
    
    # Set security protocol
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    
    # Create directories
    $directories = @($INSTALL_DIR, $DATA_DIR, $LOGS_DIR, $TEMP_DIR)
    foreach ($dir in $directories) {
        if (!(Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    
    Write-Success "Environment initialized successfully"
}

function Invoke-FileDownload {
    param(
        [string]$Url,
        [string]$OutputFile,
        [string]$Description = "file"
    )
    
    Write-Step "Downloading $Description from $Url..."
    
    try {
        # Primary method: WebClient (fastest)
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($Url, $OutputFile)
        Write-Success "$Description downloaded successfully"
        return $true
    }
    catch {
        Write-Warning "WebClient download failed, trying alternative methods..."
        
        try {
            # Secondary method: BITS Transfer
            if (Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue) {
                Write-Step "Using BITS Transfer..."
                Start-BitsTransfer -Source $Url -Destination $OutputFile
                Write-Success "$Description downloaded successfully via BITS"
                return $true
            }
        }
        catch {
            Write-Warning "BITS Transfer failed, trying Invoke-WebRequest..."
        }
        
        try {
            # Tertiary method: Invoke-WebRequest
            Invoke-WebRequest -Uri $Url -OutFile $OutputFile -UseBasicParsing
            Write-Success "$Description downloaded successfully via Invoke-WebRequest"
            return $true
        }
        catch {
            Write-Error "All download methods failed for $Description`: $_"
            return $false
        }
    }
}

function Remove-ExistingService {
    Write-Step "Checking for existing service..."
    
    $existingService = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
    if ($existingService) {
        Write-Step "Removing existing service '$SERVICE_NAME'..."
        try {
            Stop-Service -Name $SERVICE_NAME -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            sc.exe delete $SERVICE_NAME | Out-Null
            Start-Sleep -Seconds 2
            Write-Success "Existing service removed successfully"
        }
        catch {
            Write-Warning "Could not remove existing service: $_"
        }
    }
}

function Install-ServiceWithNSSM {
    Write-Step "Creating Windows Service with NSSM..."
    
    try {
        # Remove any existing service with NSSM
        $existingService = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
        if ($existingService) {
            Stop-Service -Name $SERVICE_NAME -Force -ErrorAction SilentlyContinue
            & $NSSM_EXE remove $SERVICE_NAME confirm
            Start-Sleep -Seconds 3
        }
        
        # Install new service
        & $NSSM_EXE install $SERVICE_NAME $AGENT_BINARY
        & $NSSM_EXE set $SERVICE_NAME AppParameters "--config `"$CONFIG_FILE`""
        & $NSSM_EXE set $SERVICE_NAME DisplayName $SERVICE_DISPLAY_NAME
        & $NSSM_EXE set $SERVICE_NAME Description $SERVICE_DESCRIPTION
        & $NSSM_EXE set $SERVICE_NAME Start SERVICE_AUTO_START
        & $NSSM_EXE set $SERVICE_NAME AppDirectory $INSTALL_DIR
        
        # Set logging and recovery options
        & $NSSM_EXE set $SERVICE_NAME AppStdout "$LOGS_DIR\stdout.log"
        & $NSSM_EXE set $SERVICE_NAME AppStderr "$LOGS_DIR\stderr.log"
        & $NSSM_EXE set $SERVICE_NAME AppRotateFiles 1
        & $NSSM_EXE set $SERVICE_NAME AppRotateOnline 1
        & $NSSM_EXE set $SERVICE_NAME AppRotateSeconds 86400
        & $NSSM_EXE set $SERVICE_NAME AppRotateBytes 1048576
        & $NSSM_EXE set $SERVICE_NAME AppExit Default Restart
        & $NSSM_EXE set $SERVICE_NAME AppRestartDelay 5000
        
        Write-Success "Windows Service created successfully with NSSM"
        return $true
    }
    catch {
        Write-Error "Failed to create Windows Service with NSSM: $_"
        return $false
    }
}

function Set-FilePermissions {
    Write-Step "Setting file permissions..."
    
    try {
        icacls $INSTALL_DIR /grant "SYSTEM:(OI)(CI)F" /T | Out-Null
        icacls $INSTALL_DIR /grant "Administrators:(OI)(CI)F" /T | Out-Null
        icacls $INSTALL_DIR /grant "Users:(OI)(CI)RX" /T | Out-Null
        Write-Success "File permissions set successfully"
        return $true
    }
    catch {
        Write-Warning "Failed to set file permissions: $_"
        return $false
    }
}

function Start-ServiceSafely {
    Write-Step "Starting EDR Agent service..."
    
    try {
        Start-Service -Name $SERVICE_NAME
        Start-Sleep -Seconds 5
        
        $serviceStatus = Get-Service -Name $SERVICE_NAME
        if ($serviceStatus.Status -eq "Running") {
            Write-Success "EDR Agent service started successfully"
            return $true
        }
        else {
            Write-Warning "EDR Agent service is not running. Status: $($serviceStatus.Status)"
            
            # Check logs for troubleshooting
            if (Test-Path "$LOGS_DIR\stderr.log") {
                Write-Step "Last 10 lines of stderr log:"
                Get-Content "$LOGS_DIR\stderr.log" -Tail 10 -ErrorAction SilentlyContinue
            }
            
            return $false
        }
    }
    catch {
        Write-Warning "Failed to start EDR Agent service: $_"
        return $false
    }
}

function Invoke-Cleanup {
    Write-Step "Cleaning up temporary files..."
    
    try {
        if (Test-Path $TEMP_DIR) {
            Remove-Item -Path $TEMP_DIR -Recurse -Force -ErrorAction SilentlyContinue
        }
        Write-Success "Temporary files cleaned up"
    }
    catch {
        Write-Warning "Could not clean up some temporary files: $_"
    }
}

function Show-InstallationSummary {
    Write-Header "Installation Summary"
    Write-Host "Installation Directory: $INSTALL_DIR" -ForegroundColor White
    Write-Host "Configuration File: $CONFIG_FILE" -ForegroundColor White
    Write-Host "Data Directory: $DATA_DIR" -ForegroundColor White
    Write-Host "Logs Directory: $LOGS_DIR" -ForegroundColor White
    Write-Host "CA Certificate: $CA_CERT_FILE" -ForegroundColor White
    Write-Host "Service Name: $SERVICE_NAME" -ForegroundColor White
    Write-Host "Server Address: $gRPCHost" -ForegroundColor White
    
    Write-Header "Management Commands" "Cyan"
    Write-Host "Start Service:    Start-Service -Name '$SERVICE_NAME'" -ForegroundColor White
    Write-Host "Stop Service:     Stop-Service -Name '$SERVICE_NAME'" -ForegroundColor White
    Write-Host "Service Status:   Get-Service -Name '$SERVICE_NAME'" -ForegroundColor White
    Write-Host "View Logs:        Get-Content '$LOGS_DIR\stderr.log' -Tail 20" -ForegroundColor White
    Write-Host "Manual Run:       Set-Location '$INSTALL_DIR'; & '.\edr-agent.exe' --config '$CONFIG_FILE'" -ForegroundColor White
}

#==============================================================================
# Main Installation Process
#==============================================================================

Write-Header "$SCRIPT_NAME v$SCRIPT_VERSION"
Write-Host "Installing EDR Agent to $INSTALL_DIR" -ForegroundColor Yellow

# Check administrator privileges
if (-not (Test-Administrator)) {
    Write-Error "This script must be run as Administrator!"
    Write-Host "Please right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Red
    exit 1
}

# Initialize environment
Initialize-Environment

# Download agent binary
if (-not (Invoke-FileDownload -Url $AGENT_URL -OutputFile $AGENT_BINARY -Description "EDR Agent binary")) {
    exit 1
}

# Download CA certificate
Invoke-FileDownload -Url $CERT_URL -OutputFile $CA_CERT_FILE -Description "CA certificate" | Out-Null

# Create configuration file
Write-Step "Creating configuration file..."
$caCertPath = $CA_CERT_FILE.Replace('\', '/')
$hostsFilePath = "C:/Windows/System32/drivers/etc/hosts"
$logFilePath = ($LOGS_DIR + "/edr-agent.log").Replace('\', '/')
$dataDirPath = $DATA_DIR.Replace('\', '/')

$configContent = @"
# EDR Agent Configuration File
server_address: "$gRPCHost"
use_tls: true
ca_cert_path: "$caCertPath"
insecure_skip_verify: false
agent_id: ""
agent_version: "1.0.0"
log_file: "$logFilePath"
data_dir: "$dataDirPath"
log_level: "info"
log_format: "console"
scan_interval: 5
metrics_interval: 10
connection_timeout: 30
reconnect_delay: 5
max_reconnect_delay: 60
ioc_update_delay: 3
shutdown_timeout: 500
cpu_sample_duration: 500
hosts_file_path: "$hostsFilePath"
blocked_ip_redirect: "127.0.0.1"
"@

try {
    $configContent | Out-File -FilePath $CONFIG_FILE -Encoding UTF8
    Write-Success "Configuration file created successfully"
}
catch {
    Write-Error "Failed to create configuration file: $_"
    exit 1
}

# Remove existing service
Remove-ExistingService

# Download and extract NSSM
if (-not (Invoke-FileDownload -Url $NSSM_URL -OutputFile $NSSM_ZIP -Description "NSSM")) {
    exit 1
}

try {
    Expand-Archive -Path $NSSM_ZIP -DestinationPath $NSSM_DIR -Force
    Write-Success "NSSM extracted successfully"
}
catch {
    Write-Error "Failed to extract NSSM: $_"
    exit 1
}

# Install service with NSSM
if (-not (Install-ServiceWithNSSM)) {
    exit 1
}

# Set file permissions
Set-FilePermissions | Out-Null

# Test agent configuration
Write-Step "Testing agent configuration..."
try {
    & $AGENT_BINARY --config $CONFIG_FILE --help 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Agent configuration test passed"
    }
    else {
        Write-Warning "Agent configuration test failed, but installation will continue"
    }
}
catch {
    Write-Warning "Could not test agent configuration: $_"
}

# Start the service
Start-ServiceSafely | Out-Null

# Clean up
Invoke-Cleanup

# Show summary
Show-InstallationSummary

Write-Host "`nHUST EDR Agent installation completed successfully!" -ForegroundColor Green
Write-Host "The agent should now be running and connecting to the server." -ForegroundColor Yellow

Write-Host "`n=== Troubleshooting ===" -ForegroundColor Cyan
Write-Host "If the service fails to start, check the logs:" -ForegroundColor White
Write-Host "1. Service logs: Get-Content '$LOGS_DIR\stderr.log' -Tail 20" -ForegroundColor White
Write-Host "2. Agent logs: Get-Content '$LOGS_DIR\edr-agent.log' -Tail 20" -ForegroundColor White
Write-Host "3. Manual test: Set-Location '$INSTALL_DIR'; & '.\edr-agent.exe' --config '$CONFIG_FILE'" -ForegroundColor White
Write-Host "4. Check config: Get-Content '$CONFIG_FILE'" -ForegroundColor White 