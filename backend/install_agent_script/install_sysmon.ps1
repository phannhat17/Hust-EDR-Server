#==============================================================================
# HUST Sysmon Installation Script
# Description: Downloads and installs Sysmon with configuration
# Requirements: Administrator privileges
# Version: 2.0
#==============================================================================

# Script Configuration
$SCRIPT_NAME = "HUST Sysmon Installer"
$SCRIPT_VERSION = "2.0"

# Installation Paths
$SYSMON_DIR = "C:\Program Files\Sysmon"
$TEMP_DIR = "$env:TEMP\SysmonInstall"

# File Paths
$SYSMON_ZIP = "$TEMP_DIR\Sysmon.zip"
$CONFIG_FILE = "$SYSMON_DIR\sysmonconfig.xml"
$SYSMON_EXE = "$SYSMON_DIR\Sysmon64.exe"

# Download URLs
$SYSMON_URL = "https://download.sysinternals.com/files/Sysmon.zip"
$CONFIG_URL = "https://raw.githubusercontent.com/olafhartong/sysmon-modular/refs/heads/master/sysmonconfig.xml"

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
    $directories = @($SYSMON_DIR, $TEMP_DIR)
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

function Install-Sysmon {
    Write-Step "Installing Sysmon with configuration..."
    
    try {
        & $SYSMON_EXE -accepteula -h md5,sha256,imphash -l -n -i $CONFIG_FILE
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Sysmon installed successfully!"
            return $true
        }
        else {
            Write-Error "Sysmon installation failed with exit code: $LASTEXITCODE"
            return $false
        }
    }
    catch {
        Write-Error "Failed to install Sysmon: $_"
        return $false
    }
}

function Set-EnvironmentVariable {
    Write-Step "Setting environment variables..."
    
    try {
        [System.Environment]::SetEnvironmentVariable("SYSMON_HOME", $SYSMON_DIR, [System.EnvironmentVariableTarget]::Machine)
        Write-Success "Added SYSMON_HOME environment variable pointing to $SYSMON_DIR"
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
    Write-Host "Installation Directory: $SYSMON_DIR" -ForegroundColor White
    Write-Host "Configuration File: $CONFIG_FILE" -ForegroundColor White
    Write-Host "Sysmon Executable: $SYSMON_EXE" -ForegroundColor White
    Write-Host "Environment Variable: SYSMON_HOME = $SYSMON_DIR" -ForegroundColor White
}

#==============================================================================
# Main Installation Process
#==============================================================================

Write-Header "$SCRIPT_NAME v$SCRIPT_VERSION"
Write-Host "Installing Sysmon to $SYSMON_DIR" -ForegroundColor Yellow

# Check administrator privileges
if (-not (Test-Administrator)) {
    Write-Error "This script requires administrator privileges. Please run as administrator."
    exit 1
}

# Initialize environment
Initialize-Environment

# Download Sysmon
if (-not (Invoke-FileDownload -Url $SYSMON_URL -OutputFile $SYSMON_ZIP -Description "Sysmon")) {
    exit 1
}

# Download configuration file
if (-not (Invoke-FileDownload -Url $CONFIG_URL -OutputFile $CONFIG_FILE -Description "Sysmon configuration")) {
    exit 1
}

# Extract Sysmon to installation directory
Write-Step "Extracting Sysmon to $SYSMON_DIR..."
try {
    Expand-Archive -Path $SYSMON_ZIP -DestinationPath $SYSMON_DIR -Force
    Write-Success "Sysmon extracted successfully"
}
catch {
    Write-Error "Failed to extract Sysmon: $_"
    exit 1
}

# Install Sysmon
if (-not (Install-Sysmon)) {
    exit 1
}

# Set environment variable
Set-EnvironmentVariable | Out-Null

# Clean up
Invoke-Cleanup

# Show summary
Show-InstallationSummary

Write-Host "`nSysmon installation completed successfully!" -ForegroundColor Green
Write-Host "Sysmon is now monitoring system events." -ForegroundColor Yellow 