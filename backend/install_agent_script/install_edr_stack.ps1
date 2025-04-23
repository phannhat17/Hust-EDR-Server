# EDR Stack Installation Script for Windows
# This script orchestrates the installation of the complete EDR stack:
# 1. EDR Agent
# 2. Sysmon
# 3. Winlogbeat with EDR ID configuration
# Must be run with administrator privileges

function Install-EDRStack {
    param(
        [string]$ServerHost = "192.168.133.145:5000",
        [string]$gRPCHost = "192.168.133.145:50051"
    )

    Write-Host "Starting EDR Stack Installation..." -ForegroundColor Cyan
    Write-Host "Server Host: $ServerHost" -ForegroundColor Cyan
    Write-Host "gRPC Host: $gRPCHost" -ForegroundColor Cyan

    # Check for administrator privileges
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host "This script requires administrator privileges. Please run as administrator." -ForegroundColor Red
        return
    }

    # Create temp directory for downloads
    $tempDir = "$env:TEMP\EDRStackInstall"
    if (!(Test-Path $tempDir)) {
        New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
        Write-Host "Created temporary directory: $tempDir"
    }

    # Function for downloading scripts
    function Download-Script {
        param (
            [string]$Url,
            [string]$OutputFile
        )
        
        Write-Host "Downloading $Url to $OutputFile..."
        try {
            $webClient = New-Object System.Net.WebClient
            $webClient.DownloadFile($Url, $OutputFile)
            
            # Validate script content
            if (!(Test-Path $OutputFile) -or (Get-Item $OutputFile).Length -eq 0) {
                throw "Failed to download $Url or file is empty"
            }
        }
        catch {
            throw "Download error: $_"
        }
    }

    # Step 1: Install EDR Agent and capture the Agent ID
    Write-Host "`n[1/3] Installing EDR Agent..." -ForegroundColor Cyan

    # Download the EDR agent script
    $edrScriptPath = "$tempDir\install_edr_agent.ps1"
    $edrScriptUrl = "http://$ServerHost/api/install/edr-agent-script-with-host/$gRPCHost"

    try {
        Download-Script -Url $edrScriptUrl -OutputFile $edrScriptPath
        
        # Create a log file to capture output
        $edrLogFile = "$tempDir\edr_install.log"
        
        # Execute the EDR agent script and capture output
        Write-Host "Executing EDR Agent installation script..."
        $output = & powershell.exe -ExecutionPolicy Bypass -File $edrScriptPath *>&1 | Tee-Object -FilePath $edrLogFile
        
        # Extract the EDR Agent ID from the log
        $edrAgentId = $output | Select-String -Pattern "Registering agent ([0-9a-f\-]+) with server" | ForEach-Object { $_.Matches.Groups[1].Value }
        
        if (-not $edrAgentId) {
            Write-Host "Could not extract EDR Agent ID from installation logs. Please check $edrLogFile" -ForegroundColor Yellow
            return
        }
        
        Write-Host "EDR Agent installed successfully with ID: $edrAgentId" -ForegroundColor Green
        
    } catch {
        Write-Host "Failed to install EDR Agent: $_" -ForegroundColor Red
        return
    }

    # Step 2: Install Sysmon
    Write-Host "`n[2/3] Installing Sysmon..." -ForegroundColor Cyan

    # Download the Sysmon script
    $sysmonScriptPath = "$tempDir\install_sysmon.ps1"
    $sysmonScriptUrl = "http://$ServerHost/api/install/sysmon-script"

    try {
        Download-Script -Url $sysmonScriptUrl -OutputFile $sysmonScriptPath
        
        # Execute the Sysmon script
        Write-Host "Executing Sysmon installation script..."
        & powershell.exe -ExecutionPolicy Bypass -File $sysmonScriptPath
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Sysmon installation failed with exit code: $LASTEXITCODE" -ForegroundColor Red
            return
        }
        
        Write-Host "Sysmon installed successfully!" -ForegroundColor Green
        
    } catch {
        Write-Host "Failed to install Sysmon: $_" -ForegroundColor Red
        return
    }

    # Step 3: Install Winlogbeat with EDR Agent ID
    Write-Host "`n[3/3] Installing Winlogbeat..." -ForegroundColor Cyan

    # Download the Winlogbeat configuration
    $winlogbeatConfigPath = "$tempDir\winlogbeat.yml"
    $winlogbeatConfigUrl = "http://$ServerHost/api/install/winlogbeat-config"

    try {
        Download-Script -Url $winlogbeatConfigUrl -OutputFile $winlogbeatConfigPath
        
        # Replace the EDR ID placeholder with the actual EDR Agent ID
        $configContent = Get-Content -Path $winlogbeatConfigPath -Raw
        $configContent = $configContent -replace "<edr agent id go there>", $edrAgentId
        Set-Content -Path $winlogbeatConfigPath -Value $configContent
        
        Write-Host "Updated Winlogbeat configuration with EDR Agent ID: $edrAgentId" -ForegroundColor Green
        
        # Create a modified Winlogbeat script that uses our config
        $winlogbeatScriptPath = "$tempDir\install_winlogbeat.ps1"
        $winlogbeatScriptUrl = "http://$ServerHost/api/install/winlogbeat-script-with-host/$ServerHost"
        
        Download-Script -Url $winlogbeatScriptUrl -OutputFile $winlogbeatScriptPath
        
        # Modify the script to use our pre-configured winlogbeat.yml
        $winlogbeatScript = Get-Content -Path $winlogbeatScriptPath -Raw
        $winlogbeatScript = $winlogbeatScript -replace "Download-File -Url \`$configUrl -OutputFile \`$tempConfigFile", "Copy-Item -Path `"$winlogbeatConfigPath`" -Destination `"`$tempConfigFile`" -Force"
        Set-Content -Path $winlogbeatScriptPath -Value $winlogbeatScript
        
        # Execute the Winlogbeat script
        Write-Host "Executing Winlogbeat installation script..."
        & powershell.exe -ExecutionPolicy Bypass -File $winlogbeatScriptPath -ServerHost $ServerHost
        
        Write-Host "Winlogbeat installed successfully!" -ForegroundColor Green
        
    } catch {
        Write-Host "Failed to install Winlogbeat: $_" -ForegroundColor Red
        return
    }

    # Clean up
    Write-Host "`nCleaning up temporary files..."
    Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue

    Write-Host "`nEDR Stack Installation Complete!" -ForegroundColor Green
    Write-Host "EDR Agent ID: $edrAgentId" -ForegroundColor Cyan
    Write-Host "All components have been installed and configured successfully." -ForegroundColor Green
}

# Auto-execute if not dot-sourced
if ($MyInvocation.InvocationName -ne ".") {
    # Only auto-run if script was executed directly (not using & or dot-sourcing)
    $scriptArgs = @{}
    if ($PSBoundParameters.ContainsKey('ServerHost')) { $scriptArgs['ServerHost'] = $ServerHost }
    if ($PSBoundParameters.ContainsKey('gRPCHost')) { $scriptArgs['gRPCHost'] = $gRPCHost }
    
    Install-EDRStack @scriptArgs
} 