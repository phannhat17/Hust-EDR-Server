# Install EDR Agent Script for Windows
# This script downloads and installs the HUST-EDR agent as a Windows service
# Must be run with administrator privileges

# Get server host and other parameters
param(
    [string]$ServerHost = "localhost:5000",
    [string]$gRPCHost = "localhost:50051",
    [string]$UseTLS = "true",
    [bool]$InsecureSkipVerify = $false
)

# Format gRPC host - ensure it has proper format
if ($gRPCHost -notlike "*:*") {
    $gRPCHost = "$gRPCHost:50051"
}

# Set download URLs
$edrAgentUrl = "http://$ServerHost/api/install/edr-agent-binary"
$caCertUrl = "http://$ServerHost/api/install/ca-cert"
$nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"

# Set installation paths
$edrDir = "C:\Program Files\HUST-EDR"
$tempDir = "$env:TEMP\HustEDRInstall"
$edrExe = "$edrDir\edr-agent.exe"
$serviceName = "HustEDRAgent"

# All subdirectories within the main EDR directory
$dataDir = "$edrDir\data"
$logDir = "$edrDir\logs"
$certDir = "$edrDir\certs"
$nssmDir = "$edrDir\nssm"
$configFile = "$edrDir\config.yaml"

# Check for administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "This script requires administrator privileges. Please run as administrator." -ForegroundColor Red
    exit 1
}

# Create HUST-EDR directory structure
Write-Host "Creating HUST-EDR directory structure..." -ForegroundColor Yellow
foreach ($dir in @($edrDir, $dataDir, $logDir, $certDir, $nssmDir, $tempDir)) {
    if (!(Test-Path $dir)) {
        Write-Host "Creating directory: $dir"
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
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

# Stop and remove existing service if it exists
if (Get-Service $serviceName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping existing HUST-EDR Agent service..."
    Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
    Start-Sleep -s 2
    
    # Force kill any lingering processes
    Get-Process | Where-Object {$_.ProcessName -eq "edr-agent"} | Stop-Process -Force -ErrorAction SilentlyContinue
    
    Write-Host "Removing existing HUST-EDR Agent service..."
    & sc.exe delete $serviceName
    Start-Sleep -s 2
}

# Download EDR Agent binary
Write-Host "Downloading HUST-EDR Agent..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
    # Use faster WebClient instead of Invoke-WebRequest
    Download-File -Url $edrAgentUrl -OutputFile $edrExe
} catch {
    Write-Host "WebClient download failed, trying alternative method..." -ForegroundColor Yellow
    
    # Fallback to BitsTransfer if available
    if (Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue) {
        Write-Host "Using BITS Transfer..."
        Start-BitsTransfer -Source $edrAgentUrl -Destination $edrExe
    } else {
        # Last resort, use Invoke-WebRequest
        Write-Host "Using Invoke-WebRequest..."
        Invoke-WebRequest -Uri $edrAgentUrl -OutFile $edrExe
    }
}

# Download CA Certificate if TLS is enabled
$caCertPath = ""
$useTLSBool = $true
if ($UseTLS -eq "false" -or $UseTLS -eq $false) {
    $useTLSBool = $false
    Write-Host "TLS disabled - skipping CA certificate download" -ForegroundColor Yellow
} else {
    Write-Host "TLS enabled - downloading CA certificate..." -ForegroundColor Yellow
    $caCertFile = "$certDir\ca.crt"
    
    try {
        Download-File -Url $caCertUrl -OutputFile $caCertFile
        
        if (Test-Path $caCertFile) {
            $caCertPath = $caCertFile
            Write-Host "CA certificate downloaded successfully: $caCertFile" -ForegroundColor Green
        } else {
            Write-Host "Failed to download CA certificate - continuing without it" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Warning: Could not download CA certificate. You may need to add it manually." -ForegroundColor Yellow
    }
}

# Create comprehensive configuration file
Write-Host "Creating HUST-EDR Agent configuration..."
$configContent = @"
# HUST-EDR Agent Configuration File
# Server Configuration
server_address: "$gRPCHost"
use_tls: $($useTLSBool.ToString().ToLower())

# TLS/Certificate Configuration
ca_cert_path: "$($caCertPath.Replace("\", "/"))"
insecure_skip_verify: $($InsecureSkipVerify.ToString().ToLower())

# Agent Identification (will be auto-generated if empty)
agent_id: ""
agent_version: "1.0.0"

# File Paths
log_file: "$($logDir.Replace("\", "/"))/edr-agent.log"
data_dir: "$($dataDir.Replace("\", "/"))"

# Logging Configuration
log_level: "info"
log_format: "console"

# Timing Configuration (in minutes)
scan_interval: 5
metrics_interval: 30

# Connection Configuration (in seconds)
connection_timeout: 30
reconnect_delay: 5
max_reconnect_delay: 60
ioc_update_delay: 3
shutdown_timeout: 500

# System Monitoring Configuration
cpu_sample_duration: 500

# Windows-specific Configuration
hosts_file_path: "C:\\Windows\\System32\\drivers\\etc\\hosts"
blocked_ip_redirect: "127.0.0.1"
"@

Set-Content -Path $configFile -Value $configContent -Encoding UTF8

# Download and install NSSM (Non-Sucking Service Manager)
Write-Host "Downloading NSSM (Non-Sucking Service Manager)..."
$nssmZip = "$tempDir\nssm.zip"
$nssmExe = "$nssmDir\nssm-2.24\win64\nssm.exe"

try {
    Download-File -Url $nssmUrl -OutputFile $nssmZip
    
    # Extract NSSM
    Write-Host "Extracting NSSM..."
    Expand-Archive -Path $nssmZip -DestinationPath $nssmDir -Force
    
    # Verify NSSM exists
    if (!(Test-Path $nssmExe)) {
        throw "NSSM executable not found at expected path: $nssmExe"
    }
} catch {
    Write-Host "Error downloading or extracting NSSM: $_" -ForegroundColor Red
    exit 1
}

# Install service using NSSM
Write-Host "Installing HUST-EDR Agent service..."
try {
    # Remove existing service if it exists
    & $nssmExe remove $serviceName confirm 2>$null
    Start-Sleep -s 2
    
    # Install service
    & $nssmExe install $serviceName $edrExe "--config `"$configFile`""
    
    if ($LASTEXITCODE -ne 0) {
        throw "NSSM installation failed with exit code $LASTEXITCODE"
    }
    
    Write-Host "Service installation successful" -ForegroundColor Green
} catch {
    Write-Host "Error during service installation: $_" -ForegroundColor Red
    exit 1
}

# Configure service details
& $nssmExe set $serviceName DisplayName "HUST-EDR Agent Service"
& $nssmExe set $serviceName Description "HUST-EDR Endpoint Detection and Response Agent"
& $nssmExe set $serviceName Start SERVICE_AUTO_START

# Configure log rotation
$stdoutLog = "$logDir\edr-agent-stdout.log"
$stderrLog = "$logDir\edr-agent-stderr.log"

& $nssmExe set $serviceName AppStdout $stdoutLog
& $nssmExe set $serviceName AppStderr $stderrLog
& $nssmExe set $serviceName AppRotateFiles 1
& $nssmExe set $serviceName AppRotateOnline 1
& $nssmExe set $serviceName AppRotateSeconds 86400
& $nssmExe set $serviceName AppRotateBytes 10485760

# Start the service
Write-Host "Starting HUST-EDR Agent service..."
Start-Service -Name $serviceName

# Wait for service to start
$maxWaitTime = 30
$waitInterval = 2
$elapsed = 0

Write-Host "Waiting for service to start..."
while ($elapsed -lt $maxWaitTime) {
    $service = Get-Service $serviceName -ErrorAction SilentlyContinue
    
    if ($service -and $service.Status -eq "Running") {
        Write-Host "HUST-EDR Agent service started successfully!" -ForegroundColor Green
        break
    }
    
    Start-Sleep -s $waitInterval
    $elapsed += $waitInterval
}

# Check if service is running
$service = Get-Service -Name $serviceName -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq "Running") {
    Write-Host "HUST-EDR Agent service is running!" -ForegroundColor Green
    
    # Try to get the agent ID after a moment
    Start-Sleep -s 5
    $finalConfigContent = Get-Content -Path $configFile -Raw -ErrorAction SilentlyContinue
    if ($finalConfigContent -match "agent_id:\s*""?([^""\s]+)""?" -and $matches[1] -ne "" -and $matches[1] -ne "agent_id:") {
        $finalAgentId = $matches[1].Trim('"')
        Write-Host "Agent ID: $finalAgentId" -ForegroundColor Cyan
    }
} else {
    Write-Host "HUST-EDR Agent service is not running. Please check the logs." -ForegroundColor Red
    Write-Host "Check logs at: $logDir" -ForegroundColor Yellow
}

# Create environment variable for EDR path
[System.Environment]::SetEnvironmentVariable("HUST_EDR_HOME", $edrDir, [System.EnvironmentVariableTarget]::Machine)
Write-Host "Added HUST_EDR_HOME environment variable pointing to $edrDir"

# Clean up temporary files
Write-Host "Cleaning up temporary files..."
Remove-Item -Path $tempDir -Recurse -Force

# Final summary
Write-Host "`n" + "="*60 -ForegroundColor Green
Write-Host "HUST-EDR AGENT INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "="*60 -ForegroundColor Green

Write-Host "`nInstallation Summary:" -ForegroundColor Cyan
Write-Host "  Installation Directory: $edrDir" -ForegroundColor White
Write-Host "  Configuration File: $configFile" -ForegroundColor White
Write-Host "  Service Name: $serviceName" -ForegroundColor White
Write-Host "  Service Status: $($service.Status)" -ForegroundColor $(if($service.Status -eq "Running"){"Green"}else{"Red"})
Write-Host "  Server: $gRPCHost" -ForegroundColor White
Write-Host "  TLS Enabled: $useTLSBool" -ForegroundColor White

Write-Host "`nUseful Commands:" -ForegroundColor Yellow
Write-Host "  Check service status: Get-Service $serviceName" -ForegroundColor White
Write-Host "  View logs: Get-Content '$logDir\edr-agent.log' -Tail 20" -ForegroundColor White
Write-Host "  Restart service: Restart-Service $serviceName" -ForegroundColor White

Write-Host "HUST-EDR Agent installation complete in $edrDir" -ForegroundColor Green 