# Install Winlogbeat Script for Windows
# This script downloads and installs Winlogbeat with a specific configuration
# Must be run with administrator privileges

# Get server host from parameter or use default
param(
    [string]$ServerHost = "localhost:5000"
)

#==============================================================================
# HUST Winlogbeat Installation Script
# Description: Downloads and installs Winlogbeat with configuration
# Requirements: Administrator privileges
# Version: 2.0
#==============================================================================

# Script Configuration
$SCRIPT_NAME = "HUST Winlogbeat Installer"
$SCRIPT_VERSION = "2.0"
$SERVICE_NAME = "winlogbeat"

# Installation Paths
$WINLOGBEAT_DIR = "C:\Program Files\Winlogbeat"
$TEMP_DIR = "$env:TEMP\WinlogbeatInstall"

# File Paths
$WINLOGBEAT_ZIP = "$TEMP_DIR\winlogbeat.zip"
$CONFIG_FILE = "$WINLOGBEAT_DIR\winlogbeat.yml"
$TEMP_CONFIG_FILE = "$TEMP_DIR\winlogbeat.yml"
$CERT1_FILE = "$WINLOGBEAT_DIR\kibana.crt"
$CERT2_FILE = "$WINLOGBEAT_DIR\elasticsearch.crt"
$WINLOGBEAT_EXE = "$WINLOGBEAT_DIR\winlogbeat.exe"
$INSTALL_SERVICE_SCRIPT = "$WINLOGBEAT_DIR\install-service-winlogbeat.ps1"

# Download URLs
$WINLOGBEAT_URL = "https://artifacts.elastic.co/downloads/beats/winlogbeat/winlogbeat-9.0.0-windows-x86_64.zip"
$CONFIG_URL = "http://$ServerHost/api/install/winlogbeat-config"
$CERT1_URL = "http://$ServerHost/api/install/kibana-cert"
$CERT2_URL = "http://$ServerHost/api/install/elasticsearch-cert"

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
    $directories = @($WINLOGBEAT_DIR, $TEMP_DIR)
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

function Install-WinlogbeatService {
    Write-Step "Installing Winlogbeat service..."
    
    try {
        # Run the install service script
        Start-Process -FilePath "powershell.exe" -ArgumentList "-ExecutionPolicy Unrestricted -File `"$INSTALL_SERVICE_SCRIPT`"" -WorkingDirectory $WINLOGBEAT_DIR -Wait
        Write-Success "Winlogbeat service installed successfully"
        return $true
    }
    catch {
        Write-Error "Failed to install Winlogbeat service: $_"
        return $false
    }
}

function Initialize-Winlogbeat {
    Write-Step "Setting up Winlogbeat..."
    
    try {
        Start-Process -FilePath $WINLOGBEAT_EXE -ArgumentList "setup -e" -WorkingDirectory $WINLOGBEAT_DIR -Wait
        Write-Success "Winlogbeat setup completed successfully"
        return $true
    }
    catch {
        Write-Error "Failed to setup Winlogbeat: $_"
        return $false
    }
}

function Start-ServiceSafely {
    Write-Step "Starting Winlogbeat service..."
    
    try {
        Start-Service $SERVICE_NAME
        Start-Sleep -Seconds 5
        
        $service = Get-Service -Name $SERVICE_NAME -ErrorAction SilentlyContinue
        if ($service -and $service.Status -eq "Running") {
            Write-Success "Winlogbeat service is running!"
            return $true
        }
        else {
            Write-Warning "Winlogbeat service is not running. Please check the logs."
            return $false
        }
    }
    catch {
        Write-Warning "Failed to start Winlogbeat service: $_"
        return $false
    }
}

function Set-EnvironmentVariable {
    Write-Step "Setting environment variables..."
    
    try {
        [System.Environment]::SetEnvironmentVariable("WINLOGBEAT_HOME", $WINLOGBEAT_DIR, [System.EnvironmentVariableTarget]::Machine)
        Write-Success "Added WINLOGBEAT_HOME environment variable pointing to $WINLOGBEAT_DIR"
        return $true
    }
    catch {
        Write-Warning "Failed to set environment variable: $_"
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
    Write-Host "Installation Directory: $WINLOGBEAT_DIR" -ForegroundColor White
    Write-Host "Configuration File: $CONFIG_FILE" -ForegroundColor White
    Write-Host "Winlogbeat Executable: $WINLOGBEAT_EXE" -ForegroundColor White
    Write-Host "Service Name: $SERVICE_NAME" -ForegroundColor White
    Write-Host "Kibana Certificate: $CERT1_FILE" -ForegroundColor White
    Write-Host "Elasticsearch Certificate: $CERT2_FILE" -ForegroundColor White
    Write-Host "Environment Variable: WINLOGBEAT_HOME = $WINLOGBEAT_DIR" -ForegroundColor White
    
    Write-Header "Management Commands" "Cyan"
    Write-Host "Start Service:    Start-Service -Name '$SERVICE_NAME'" -ForegroundColor White
    Write-Host "Stop Service:     Stop-Service -Name '$SERVICE_NAME'" -ForegroundColor White
    Write-Host "Service Status:   Get-Service -Name '$SERVICE_NAME'" -ForegroundColor White
    Write-Host "View Config:      Get-Content '$CONFIG_FILE'" -ForegroundColor White
    Write-Host "Test Connection:  & '$WINLOGBEAT_EXE' test config" -ForegroundColor White
    Write-Host "View Logs:        Get-EventLog -LogName Application -Source winlogbeat -Newest 10" -ForegroundColor White
}

#==============================================================================
# Main Installation Process
#==============================================================================

Write-Header "$SCRIPT_NAME v$SCRIPT_VERSION"
Write-Host "Installing Winlogbeat to $WINLOGBEAT_DIR" -ForegroundColor Yellow

# Check administrator privileges
if (-not (Test-Administrator)) {
    Write-Error "This script requires administrator privileges. Please run as administrator."
    exit 1
}

# Initialize environment
Initialize-Environment

# Download Winlogbeat
if (-not (Invoke-FileDownload -Url $WINLOGBEAT_URL -OutputFile $WINLOGBEAT_ZIP -Description "Winlogbeat")) {
    exit 1
}

# Download configuration file to temp location first
if (-not (Invoke-FileDownload -Url $CONFIG_URL -OutputFile $TEMP_CONFIG_FILE -Description "Winlogbeat configuration")) {
    exit 1
}

# Download certificates
Write-Step "Downloading certificates..."
$cert1Success = Invoke-FileDownload -Url $CERT1_URL -OutputFile $CERT1_FILE -Description "Kibana certificate"
$cert2Success = Invoke-FileDownload -Url $CERT2_URL -OutputFile $CERT2_FILE -Description "Elasticsearch certificate"

if (-not ($cert1Success -and $cert2Success)) {
    Write-Warning "Could not download all certificates. You may need to add them manually."
}

# Extract Winlogbeat to installation directory
Write-Step "Extracting Winlogbeat to $WINLOGBEAT_DIR..."
try {
    Expand-Archive -Path $WINLOGBEAT_ZIP -DestinationPath $TEMP_DIR -Force
    
    # Get the extracted directory name (might contain version number)
    $extractedDir = Get-ChildItem -Path $TEMP_DIR -Directory | Select-Object -First 1
    $extractedPath = $extractedDir.FullName
    
    # Copy all files from the extracted directory to the installation directory
    Copy-Item -Path "$extractedPath\*" -Destination $WINLOGBEAT_DIR -Recurse -Force
    Write-Success "Winlogbeat extracted successfully"
}
catch {
    Write-Error "Failed to extract Winlogbeat: $_"
    exit 1
}

# Apply custom configuration file
Write-Step "Applying custom Winlogbeat configuration..."
try {
    Copy-Item -Path $TEMP_CONFIG_FILE -Destination $CONFIG_FILE -Force
    Write-Success "Custom configuration applied successfully"
}
catch {
    Write-Error "Failed to apply custom configuration: $_"
    exit 1
}

# Install Winlogbeat service
if (-not (Install-WinlogbeatService)) {
    exit 1
}

# Set up Winlogbeat
if (-not (Initialize-Winlogbeat)) {
    exit 1
}

# Start Winlogbeat service
Start-ServiceSafely | Out-Null

# Set environment variable
Set-EnvironmentVariable | Out-Null

# Clean up
Invoke-Cleanup

# Show summary
Show-InstallationSummary

Write-Host "`nWinlogbeat installation completed successfully!" -ForegroundColor Green
Write-Host "Winlogbeat is now forwarding Windows event logs." -ForegroundColor Yellow 