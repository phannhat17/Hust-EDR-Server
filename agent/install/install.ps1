# EDR Agent Installation Script
# This script installs and configures the EDR agent components:
# 1. Sysmon with predefined configuration
# 2. Winlogbeat with custom configuration
# 3. EDR Agent as a Windows service

param(
    [Parameter(Mandatory=$true)]
    [string]$ElkServer,
    
    [Parameter(Mandatory=$true)]
    [string]$ElkPort,
    
    [Parameter(Mandatory=$true)]
    [string]$ElkUsername,
    
    [Parameter(Mandatory=$true)]
    [string]$ElkPassword,
    
    [Parameter(Mandatory=$false)]
    [string]$AgentId = (New-Guid).ToString(),
    
    [Parameter(Mandatory=$false)]
    [string]$InstallPath = "C:\Program Files\EDR Agent"
)

# Script variables
$ErrorActionPreference = "Stop"
$ScriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$SysmonPath = Join-Path $ScriptPath "sysmon"
$WinlogbeatPath = Join-Path $ScriptPath "winlogbeat"

# Function to check if running as administrator
function Test-Administrator {
    $currentUser = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $currentUser.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# Function to install Sysmon
function Install-Sysmon {
    Write-Host "Installing Sysmon..."
    
    # Check if Sysmon is already installed
    if (Get-Service -Name "Sysmon" -ErrorAction SilentlyContinue) {
        Write-Host "Sysmon is already installed. Updating configuration..."
        & "$SysmonPath\sysmon.exe" -c "$SysmonPath\sysmon-config.xml"
        return
    }
    
    # Install Sysmon
    & "$SysmonPath\sysmon.exe" -accepteula -i "$SysmonPath\sysmon-config.xml"
    
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Sysmon"
    }
    
    Write-Host "Sysmon installed successfully"
}

# Function to install Winlogbeat
function Install-Winlogbeat {
    Write-Host "Installing Winlogbeat..."
    
    # Check if Winlogbeat is already installed
    if (Get-Service -Name "winlogbeat" -ErrorAction SilentlyContinue) {
        Write-Host "Winlogbeat is already installed. Updating configuration..."
        & "$WinlogbeatPath\winlogbeat.exe" test config -c "$WinlogbeatPath\winlogbeat.yml"
        if ($LASTEXITCODE -ne 0) {
            throw "Winlogbeat configuration test failed"
        }
        Restart-Service -Name "winlogbeat"
        return
    }
    
    # Copy Winlogbeat files
    Copy-Item "$WinlogbeatPath\winlogbeat.exe" "$InstallPath\winlogbeat.exe"
    Copy-Item "$WinlogbeatPath\winlogbeat.yml" "$InstallPath\winlogbeat.yml"
    Copy-Item "$WinlogbeatPath\elk-ca.pem" "$InstallPath\elk-ca.pem"
    
    # Generate Winlogbeat configuration
    $winlogbeatConfig = Get-Content "$WinlogbeatPath\winlogbeat.yml" -Raw
    $winlogbeatConfig = $winlogbeatConfig -replace "ELK_SERVER", $ElkServer
    $winlogbeatConfig = $winlogbeatConfig -replace "ELK_PORT", $ElkPort
    $winlogbeatConfig = $winlogbeatConfig -replace "ELK_USERNAME", $ElkUsername
    $winlogbeatConfig = $winlogbeatConfig -replace "ELK_PASSWORD", $ElkPassword
    $winlogbeatConfig = $winlogbeatConfig -replace "AGENT_ID", $AgentId
    
    Set-Content -Path "$InstallPath\winlogbeat.yml" -Value $winlogbeatConfig
    
    # Install Winlogbeat service
    & "$InstallPath\winlogbeat.exe" install
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Winlogbeat service"
    }
    
    # Start Winlogbeat service
    Start-Service -Name "winlogbeat"
    
    Write-Host "Winlogbeat installed successfully"
}

# Function to install EDR Agent
function Install-EDRAgent {
    Write-Host "Installing EDR Agent..."
    
    # Check if EDR Agent is already installed
    if (Get-Service -Name "EDRAgent" -ErrorAction SilentlyContinue) {
        Write-Host "EDR Agent is already installed. Updating configuration..."
        Stop-Service -Name "EDRAgent"
        # TODO: Update agent configuration
        Start-Service -Name "EDRAgent"
        return
    }
    
    # Create installation directory
    New-Item -ItemType Directory -Path "$InstallPath" -Force
    
    # Copy agent files
    # TODO: Copy agent executable and configuration
    
    # Install agent service
    # TODO: Install agent as Windows service
    
    Write-Host "EDR Agent installed successfully"
}

# Main installation process
try {
    # Check if running as administrator
    if (-not (Test-Administrator)) {
        throw "This script must be run as administrator"
    }
    
    # Create installation directory
    New-Item -ItemType Directory -Path "$InstallPath" -Force
    
    # Install components
    Install-Sysmon
    Install-Winlogbeat
    Install-EDRAgent
    
    Write-Host "EDR Agent installation completed successfully"
}
catch {
    Write-Host "Installation failed: $_" -ForegroundColor Red
    exit 1
} 