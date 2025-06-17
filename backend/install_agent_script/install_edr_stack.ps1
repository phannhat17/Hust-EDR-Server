# HUST-EDR Stack Installation Script for Windows
# This script orchestrates the installation of the complete EDR stack:
# 1. HUST-EDR Agent
# 2. Sysmon
# 3. Winlogbeat with EDR ID configuration
# Must be run with administrator privileges

param(
    [string]$ServerHost = "192.168.133.145:5000",
    [string]$gRPCHost = "192.168.133.145:50051",
    [string]$UseTLS = "true",
    [bool]$InsecureSkipVerify = $false
)

#==============================================================================
# HUST EDR Stack Installation Script
# Description: Orchestrates installation of complete EDR stack
#              1. HUST-EDR Agent, 2. Sysmon, 3. Winlogbeat
# Requirements: Administrator privileges
# Version: 2.0
#==============================================================================

# Script Configuration
$SCRIPT_NAME = "HUST EDR Stack Installer"
$SCRIPT_VERSION = "2.0"

# Installation Paths
$TEMP_DIR = "$env:TEMP\EDRStackInstall"
$EDR_CONFIG_PATH = "C:\Program Files\HUST-EDR-Agent\config.yaml"
$EDR_LOG_PATH = "C:\Program Files\HUST-EDR-Agent\logs"
$WINLOGBEAT_CONFIG_PATH = "C:\Program Files\Winlogbeat\winlogbeat.yml"

# File Paths
$EDR_SCRIPT_PATH = "$TEMP_DIR\install_edr_agent.ps1"
$SYSMON_SCRIPT_PATH = "$TEMP_DIR\install_sysmon.ps1"
$WINLOGBEAT_SCRIPT_PATH = "$TEMP_DIR\install_winlogbeat.ps1"
$WINLOGBEAT_CONFIG_FILE = "$TEMP_DIR\winlogbeat.yml"
$EDR_LOG_FILE = "$TEMP_DIR\edr_install.log"

# Build URLs
$EDR_SCRIPT_URL = "http://$ServerHost/api/install/edr-agent-script?grpc_host=$gRPCHost&server_host=$ServerHost" 
$SYSMON_SCRIPT_URL = "http://$ServerHost/api/install/sysmon-script"
$WINLOGBEAT_SCRIPT_URL = "http://$ServerHost/api/install/winlogbeat-script?host=$ServerHost"
$WINLOGBEAT_CONFIG_URL = "http://$ServerHost/api/install/winlogbeat-config"

if ($InsecureSkipVerify) {
    $EDR_SCRIPT_URL += "&insecure_skip_verify=true"
}

# Stack Components
$STACK_COMPONENTS = @(
    @{ Name = "HUST-EDR Agent"; ServiceName = "HUST-EDR-Agent" }
    @{ Name = "Sysmon"; ServiceName = "Sysmon64" }
    @{ Name = "Winlogbeat"; ServiceName = "winlogbeat" }
)

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
    Write-Step "Initializing stack installation environment..."
    
    # Set security protocol
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    
    # Create temp directory
    if (!(Test-Path $TEMP_DIR)) {
        New-Item -ItemType Directory -Path $TEMP_DIR -Force | Out-Null
    }
    
    Write-Success "Environment initialized successfully"
}

function Invoke-ScriptDownload {
    param(
        [string]$Url,
        [string]$OutputFile,
        [string]$Description = "script"
    )
    
    Write-Step "Downloading $Description from $Url..."
    
    try {
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($Url, $OutputFile)
        
        # Validate script content
        if (!(Test-Path $OutputFile) -or (Get-Item $OutputFile).Length -eq 0) {
            throw "Failed to download $Url or file is empty"
        }
        
        Write-Success "$Description downloaded successfully"
        return $true
    }
    catch {
        Write-Error "Download failed for $Description`: $_"
        return $false
    }
}

function Install-EDRAgent {
    Write-Header "Installing HUST-EDR Agent [1/3]" "Cyan"
    
    try {
        # Download EDR agent script
        if (-not (Invoke-ScriptDownload -Url $EDR_SCRIPT_URL -OutputFile $EDR_SCRIPT_PATH -Description "EDR Agent script")) {
            return $null
        }
        
        # Execute EDR agent installation
        Write-Step "Executing HUST-EDR Agent installation..."
        $scriptArgs = @{
            gRPCHost = $gRPCHost
            ServerHost = $ServerHost
        }
        
        $output = & powershell.exe -ExecutionPolicy Bypass -File $EDR_SCRIPT_PATH @scriptArgs *>&1 | Tee-Object -FilePath $EDR_LOG_FILE
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "EDR Agent installation failed with exit code: $LASTEXITCODE"
            return $null
        }
        
        # Extract agent ID from various sources
        $agentId = Get-AgentId -Output $output
        
        if ($agentId) {
            Write-Success "HUST-EDR Agent installed successfully with ID: $agentId"
            return $agentId
        }
        else {
            Write-Warning "Could not extract HUST-EDR Agent ID. Check log: $EDR_LOG_FILE"
            return "PLACEHOLDER_AGENT_ID"
        }
    }
    catch {
        Write-Error "Failed to install HUST-EDR Agent: $_"
        return $null
    }
}

function Get-AgentId {
    param([array]$Output)
    
    Write-Step "Extracting agent ID from installation output..."
    
    # Try multiple extraction methods
    $extractionMethods = @(
        { param($output) $output | Select-String -Pattern "Retrieved agent ID from test: ([0-9a-f\-]+)" | Select-Object -First 1 },
        { param($output) $output | Select-String -Pattern "Final Agent ID: ([0-9a-f\-]+)" | Select-Object -First 1 }
    )
    
    foreach ($method in $extractionMethods) {
        $match = & $method $Output
        if ($match) {
            $agentId = $match.Matches.Groups[1].Value
            Write-Success "Found agent ID from output: $agentId"
            return $agentId
        }
    }
    
    # Check config file
    if (Test-Path $EDR_CONFIG_PATH) {
        Write-Step "Checking agent config file for ID..."
        Start-Sleep -Seconds 15  # Wait for agent registration
        
        $configContent = Get-Content -Path $EDR_CONFIG_PATH -Raw -ErrorAction SilentlyContinue
        if ($configContent -match 'agent_id:\s*"?([^"\s\n]+)"?' -and $matches[1] -ne "" -and $matches[1] -ne "agent_id:") {
            $agentId = $matches[1].Trim('"')
            Write-Success "Found agent ID in config file: $agentId"
            return $agentId
        }
    }
    
    # Check service logs
    $logPaths = @(
        "$EDR_LOG_PATH\stdout.log",
        "$EDR_LOG_PATH\edr-agent.log"
    )
    
    foreach ($logPath in $logPaths) {
        if (Test-Path $logPath) {
            Write-Step "Checking service log: $logPath"
            $logContent = Get-Content -Path $logPath -ErrorAction SilentlyContinue
            $idMatch = $logContent | Select-String -Pattern "Registered with server as agent ID: ([0-9a-f\-]+)" | Select-Object -First 1
            if ($idMatch) {
                $agentId = $idMatch.Matches.Groups[1].Value
                Write-Success "Found agent ID in service log: $agentId"
                return $agentId
            }
        }
    }
    
    return $null
}

function Install-Sysmon {
    Write-Header "Installing Sysmon [2/3]" "Cyan"
    
    try {
        # Download Sysmon script
        if (-not (Invoke-ScriptDownload -Url $SYSMON_SCRIPT_URL -OutputFile $SYSMON_SCRIPT_PATH -Description "Sysmon script")) {
            return $false
        }
        
        # Execute Sysmon installation
        Write-Step "Executing Sysmon installation..."
        & powershell.exe -ExecutionPolicy Bypass -File $SYSMON_SCRIPT_PATH
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Sysmon installation failed with exit code: $LASTEXITCODE"
            return $false
        }
        
        Write-Success "Sysmon installed successfully!"
        return $true
    }
    catch {
        Write-Error "Failed to install Sysmon: $_"
        return $false
    }
}

function Install-Winlogbeat {
    param([string]$AgentId)
    
    Write-Header "Installing Winlogbeat [3/3]" "Cyan"
    
    try {
        # Download Winlogbeat configuration
        if (-not (Invoke-ScriptDownload -Url $WINLOGBEAT_CONFIG_URL -OutputFile $WINLOGBEAT_CONFIG_FILE -Description "Winlogbeat configuration")) {
            return $false
        }
        
        # Update configuration with agent ID
        Write-Step "Updating Winlogbeat configuration with agent ID: $AgentId"
        $configContent = Get-Content -Path $WINLOGBEAT_CONFIG_FILE -Raw
        $configContent = $configContent -replace "<edr agent id go there>", $AgentId
        Set-Content -Path $WINLOGBEAT_CONFIG_FILE -Value $configContent
        
        # Download and modify Winlogbeat script
        if (-not (Invoke-ScriptDownload -Url $WINLOGBEAT_SCRIPT_URL -OutputFile $WINLOGBEAT_SCRIPT_PATH -Description "Winlogbeat script")) {
            return $false
        }
        
        # Modify script to use our pre-configured config
        $scriptContent = Get-Content -Path $WINLOGBEAT_SCRIPT_PATH -Raw
        $scriptContent = $scriptContent -replace "Invoke-FileDownload -Url \`$CONFIG_URL -OutputFile \`$TEMP_CONFIG_FILE -Description `"Winlogbeat configuration`"", "Copy-Item -Path `"$WINLOGBEAT_CONFIG_FILE`" -Destination `"`$TEMP_CONFIG_FILE`" -Force"
        Set-Content -Path $WINLOGBEAT_SCRIPT_PATH -Value $scriptContent
        
        # Execute Winlogbeat installation
        Write-Step "Executing Winlogbeat installation..."
        & powershell.exe -ExecutionPolicy Bypass -File $WINLOGBEAT_SCRIPT_PATH -ServerHost $ServerHost
        
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Winlogbeat installation failed with exit code: $LASTEXITCODE"
            return $false
        }
        
        Write-Success "Winlogbeat installed successfully!"
        return $true
    }
    catch {
        Write-Error "Failed to install Winlogbeat: $_"
        return $false
    }
}

function Test-ServiceStatus {
    param([string]$ServiceName)
    
    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($service) {
        return @{
            Exists = $true
            Status = $service.Status
            IsRunning = ($service.Status -eq "Running")
        }
    }
    else {
        return @{
            Exists = $false
            Status = "Not Found"
            IsRunning = $false
        }
    }
}

function Show-ServiceStatus {
    Write-Header "Service Status Check" "Yellow"
    
    $allRunning = $true
    foreach ($component in $STACK_COMPONENTS) {
        $status = Test-ServiceStatus -ServiceName $component.ServiceName
        
        if ($status.Exists) {
            if ($status.IsRunning) {
                Write-Host "  ✓ $($component.Name): $($status.Status)" -ForegroundColor Green
            }
            else {
                Write-Host "  ⚠ $($component.Name): $($status.Status)" -ForegroundColor Yellow
                $allRunning = $false
            }
        }
        else {
            Write-Host "  ✗ $($component.Name): $($status.Status)" -ForegroundColor Red
            $allRunning = $false
        }
    }
    
    return $allRunning
}

function Show-ConfigurationStatus {
    Write-Header "Configuration Files Check" "Yellow"
    
    $configFiles = @(
        @{ Name = "HUST-EDR Agent Config"; Path = $EDR_CONFIG_PATH },
        @{ Name = "Winlogbeat Config"; Path = $WINLOGBEAT_CONFIG_PATH }
    )
    
    foreach ($config in $configFiles) {
        if (Test-Path $config.Path) {
            Write-Host "  ✓ $($config.Name): $($config.Path)" -ForegroundColor Green
        }
        else {
            Write-Host "  ✗ $($config.Name): Not Found" -ForegroundColor Red
        }
    }
}

function Show-InstallationSummary {
    param([string]$AgentId, [bool]$AllServicesRunning)
    
    Write-Header "HUST-EDR STACK INSTALLATION COMPLETE!" "Green"
    
    Write-Host "Installation Summary:" -ForegroundColor Cyan
    Write-Host "  HUST-EDR Agent ID: $AgentId" -ForegroundColor White
    Write-Host "  TLS Enabled: $UseTLS" -ForegroundColor White
    Write-Host "  Server Host: $ServerHost" -ForegroundColor White
    
    if ($AllServicesRunning) {
        Write-Host "  Status: All components installed and running successfully" -ForegroundColor Green
    }
    else {
        Write-Host "  Status: Installation completed with some service issues" -ForegroundColor Yellow
    }
    
    Write-Header "Next Steps" "Cyan"
    Write-Host "  1. Verify all services are running properly" -ForegroundColor White
    Write-Host "  2. Check HUST-EDR logs: Get-Content '$EDR_LOG_PATH\edr-agent.log' -Tail 20" -ForegroundColor White
    Write-Host "  3. Monitor the HUST-EDR dashboard for agent connectivity" -ForegroundColor White
    Write-Host "  4. Review Elasticsearch for incoming log data" -ForegroundColor White
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

#==============================================================================
# Main Installation Process
#==============================================================================

function Install-EDRStack {
    Write-Header "$SCRIPT_NAME v$SCRIPT_VERSION"
    Write-Host "Installing complete EDR stack to system" -ForegroundColor Yellow
    
    Write-Host "Configuration:" -ForegroundColor Cyan
    Write-Host "  Server Host: $ServerHost" -ForegroundColor White
    Write-Host "  gRPC Host: $gRPCHost" -ForegroundColor White
    Write-Host "  Use TLS: $UseTLS" -ForegroundColor White
    Write-Host "  Insecure Skip Verify: $InsecureSkipVerify" -ForegroundColor White
    
    # Check administrator privileges
    if (-not (Test-Administrator)) {
        Write-Error "This script requires administrator privileges. Please run as administrator."
        return $false
    }
    
    # Initialize environment
    Initialize-Environment
    
    # Install components in sequence
    $agentId = Install-EDRAgent
    if (-not $agentId) {
        Write-Error "EDR Agent installation failed. Aborting stack installation."
        return $false
    }
    
    if (-not (Install-Sysmon)) {
        Write-Error "Sysmon installation failed. Aborting stack installation."
        return $false
    }
    
    if (-not (Install-Winlogbeat -AgentId $agentId)) {
        Write-Error "Winlogbeat installation failed. Aborting stack installation."
        return $false
    }
    
    # Verify installation
    Show-ConfigurationStatus
    $allServicesRunning = Show-ServiceStatus
    
    # Clean up
    Invoke-Cleanup
    
    # Show summary
    Show-InstallationSummary -AgentId $agentId -AllServicesRunning $allServicesRunning
    
    return $true
}

# Execute installation
$installResult = Install-EDRStack
if ($installResult) {
    Write-Host "`nEDR Stack installation completed successfully!" -ForegroundColor Green
    exit 0
}
else {
    Write-Host "`nEDR Stack installation failed!" -ForegroundColor Red
    exit 1
} 