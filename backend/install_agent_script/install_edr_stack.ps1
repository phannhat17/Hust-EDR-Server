# HUST-EDR Stack Installation Script for Windows
# This script orchestrates the installation of the complete EDR stack:
# 1. HUST-EDR Agent
# 2. Sysmon
# 3. Winlogbeat with EDR ID configuration
# Must be run with administrator privileges

function Install-EDRStack {
    param(
        [string]$ServerHost = "192.168.133.145:5000",
        [string]$gRPCHost = "192.168.133.145",
        [string]$gRPCPort = "50051",
        [string]$UseTLS = "true",
        [bool]$InsecureSkipVerify = $false
    )

    Write-Host "Starting HUST-EDR Stack Installation..." -ForegroundColor Cyan
    Write-Host "=======================================" -ForegroundColor Cyan
    Write-Host "Server Host: $ServerHost" -ForegroundColor Cyan
    Write-Host "gRPC Host: $gRPCHost" -ForegroundColor Cyan
    Write-Host "gRPC Port: $gRPCPort" -ForegroundColor Cyan
    Write-Host "Use TLS: $UseTLS" -ForegroundColor Cyan

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

    # Step 1: Install HUST-EDR Agent and capture the Agent ID
    Write-Host "`n[1/3] Installing HUST-EDR Agent..." -ForegroundColor Cyan

    # Download the EDR agent script - SIMPLIFIED URL WITHOUT CA CERT PATH
    $edrScriptPath = "$tempDir\install_edr_agent.ps1"
    $edrScriptUrl = "http://$ServerHost/api/install/edr-agent-script?host=$gRPCHost&port=$gRPCPort&use_tls=$UseTLS&server_host=" + [Uri]::EscapeDataString($ServerHost)
    if ($InsecureSkipVerify) {
        $edrScriptUrl += "&insecure_skip_verify=true"
    }

    try {
        Download-Script -Url $edrScriptUrl -OutputFile $edrScriptPath
        
        # Create a log file to capture output
        $edrLogFile = "$tempDir\edr_install.log"
        
        # Execute the EDR agent script with simplified parameters
        Write-Host "Executing HUST-EDR Agent installation script with TLS configuration..."
        $scriptArgs = @{
            gRPCHost = "$gRPCHost`:$gRPCPort"
            UseTLS = $UseTLS
            InsecureSkipVerify = $InsecureSkipVerify
            ServerHost = $ServerHost
        }
        
        $output = & powershell.exe -ExecutionPolicy Bypass -File $edrScriptPath @scriptArgs *>&1 | Tee-Object -FilePath $edrLogFile
        
        # Extract agent ID from various sources with updated paths
        $edrAgentId = $null
        
        # First try to extract from test output
        $testIdMatch = $output | Select-String -Pattern "Retrieved agent ID from test: ([0-9a-f\-]+)" | Select-Object -First 1
        if ($testIdMatch) {
            $edrAgentId = $testIdMatch.Matches.Groups[1].Value
            Write-Host "Found agent ID from test output: $edrAgentId" -ForegroundColor Green
        }
        
        # If not found, check the config file with new consolidated path
        if (-not $edrAgentId) {
            $configFilePath = "C:\Program Files\HUST-EDR\config.yaml"
            if (Test-Path $configFilePath) {
                Write-Host "Checking agent config file for ID: $configFilePath" -ForegroundColor Yellow
                
                # Wait longer for the new agent to register
                Write-Host "Waiting for agent service to register with server..." -ForegroundColor Yellow
                Start-Sleep -s 15
                
                # Read the config file with updated YAML format
                $configContent = Get-Content -Path $configFilePath -Raw -ErrorAction SilentlyContinue
                if ($configContent -match 'agent_id:\s*"?([^"\s\n]+)"?' -and $matches[1] -ne "" -and $matches[1] -ne "agent_id:") {
                    $edrAgentId = $matches[1].Trim('"')
                    Write-Host "Found agent ID in config file: $edrAgentId" -ForegroundColor Green
                } else {
                    # Check service logs for registration messages in consolidated directory
                    $stdoutLogPath = "C:\Program Files\HUST-EDR\logs\edr-agent-stdout.log"
                    $mainLogPath = "C:\Program Files\HUST-EDR\logs\edr-agent.log"
                    
                    foreach ($logPath in @($stdoutLogPath, $mainLogPath)) {
                        if (Test-Path $logPath) {
                            Write-Host "Checking service log file: $logPath" -ForegroundColor Yellow
                            $logContent = Get-Content -Path $logPath -ErrorAction SilentlyContinue
                            $idMatch = $logContent | Select-String -Pattern "Registered with server as agent ID: ([0-9a-f\-]+)" | Select-Object -First 1
                            if ($idMatch) {
                                $edrAgentId = $idMatch.Matches.Groups[1].Value
                                Write-Host "Found agent ID in service log: $edrAgentId" -ForegroundColor Green
                                break
                            }
                        }
                    }
                }
            }
        }
        
        # If still not found, check final output patterns
        if (-not $edrAgentId) {
            $finalIdMatch = $output | Select-String -Pattern "Final Agent ID: ([0-9a-f\-]+)" | Select-Object -First 1
            if ($finalIdMatch) {
                $edrAgentId = $finalIdMatch.Matches.Groups[1].Value
                Write-Host "Found agent ID from final output: $edrAgentId" -ForegroundColor Green
            }
        }
        
        if (-not $edrAgentId) {
            Write-Host "Could not extract HUST-EDR Agent ID from any source. Please check $edrLogFile" -ForegroundColor Yellow
            Write-Host "Installation will continue, but Winlogbeat may not have the correct agent ID." -ForegroundColor Yellow
            # Continue with a placeholder ID that can be updated later
            $edrAgentId = "PLACEHOLDER_AGENT_ID"
        }
        
        Write-Host "HUST-EDR Agent installed successfully with ID: $edrAgentId" -ForegroundColor Green
        
    } catch {
        Write-Host "Failed to install HUST-EDR Agent: $_" -ForegroundColor Red
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
        
        Write-Host "Updated Winlogbeat configuration with HUST-EDR Agent ID: $edrAgentId" -ForegroundColor Green
        
        # Create a modified Winlogbeat script that uses our config
        $winlogbeatScriptPath = "$tempDir\install_winlogbeat.ps1"
        $winlogbeatScriptUrl = "http://$ServerHost/api/install/winlogbeat-script?host=$ServerHost"
        
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

    # Final status report
    Write-Host "`n" + "="*70 -ForegroundColor Green
    Write-Host "HUST-EDR STACK INSTALLATION COMPLETE!" -ForegroundColor Green
    Write-Host "="*70 -ForegroundColor Green

    Write-Host "`nInstallation Summary:" -ForegroundColor Cyan
    Write-Host "  HUST-EDR Agent ID: $edrAgentId" -ForegroundColor White
    Write-Host "  TLS Enabled: $UseTLS" -ForegroundColor White
    Write-Host "  Server Host: $ServerHost" -ForegroundColor White
    Write-Host "  All components have been installed and configured successfully." -ForegroundColor White
    
    # Configuration verification
    Write-Host "`nConfiguration Files:" -ForegroundColor Yellow
    $configFilePath = "C:\Program Files\HUST-EDR\config.yaml"
    if (Test-Path $configFilePath) {
        Write-Host "  ✓ HUST-EDR Agent Config: $configFilePath" -ForegroundColor Green
    } else {
        Write-Host "  ✗ HUST-EDR Agent Config: Not Found" -ForegroundColor Red
    }
    
    $winlogbeatConfigPath = "C:\Program Files\Winlogbeat\winlogbeat.yml"
    if (Test-Path $winlogbeatConfigPath) {
        Write-Host "  ✓ Winlogbeat Config: $winlogbeatConfigPath" -ForegroundColor Green
    } else {
        Write-Host "  ✗ Winlogbeat Config: Not Found" -ForegroundColor Red
    }
    
    # Service status check
    Write-Host "`nService Status:" -ForegroundColor Yellow
    $services = @("HustEDRAgent", "Sysmon", "Winlogbeat")
    foreach ($serviceName in $services) {
        $service = Get-Service $serviceName -ErrorAction SilentlyContinue
        if ($service) {
            $status = $service.Status
            if ($status -eq "Running") {
                Write-Host "  ✓ $serviceName`: $status" -ForegroundColor Green
            } else {
                Write-Host "  ⚠ $serviceName`: $status" -ForegroundColor Yellow
            }
        } else {
            Write-Host "  ✗ $serviceName`: Not Found" -ForegroundColor Red
        }
    }

    # Final instructions
    Write-Host "`nNext Steps:" -ForegroundColor Cyan
    Write-Host "  1. Verify all services are running properly" -ForegroundColor White
    Write-Host "  2. Check HUST-EDR logs: Get-Content 'C:\Program Files\HUST-EDR\logs\edr-agent.log' -Tail 20" -ForegroundColor White
    Write-Host "  3. Monitor the HUST-EDR dashboard for agent connectivity" -ForegroundColor White
    Write-Host "  4. Review Elasticsearch for incoming log data" -ForegroundColor White

    Write-Host "`n" + "="*70 -ForegroundColor Green
}

# Auto-execute if not dot-sourced
if ($MyInvocation.InvocationName -ne ".") {
    # Parse parameters for the simplified TLS options
    param(
        [string]$ServerHost = "192.168.133.145:5000",
        [string]$gRPCHost = "192.168.133.145",
        [string]$gRPCPort = "50051",
        [string]$UseTLS = "true",
        [bool]$InsecureSkipVerify = $false
    )
    
    # Build script arguments
    $scriptArgs = @{
        ServerHost = $ServerHost
        gRPCHost = $gRPCHost
        gRPCPort = $gRPCPort
        UseTLS = $UseTLS
        InsecureSkipVerify = $InsecureSkipVerify
    }
    
    Install-EDRStack @scriptArgs
} 