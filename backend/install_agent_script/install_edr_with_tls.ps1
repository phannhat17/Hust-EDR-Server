# Enhanced HUST-EDR Agent Installation Script with TLS Support
# This script provides advanced installation options with simplified TLS management
# CA certificates are automatically downloaded from the server
# Must be run with administrator privileges

param(
    [string]$ServerHost = "192.168.133.145:5000",
    [string]$gRPCHost = "192.168.133.145",
    [string]$gRPCPort = "50051",
    [string]$UseTLS = "true",
    [bool]$InsecureSkipVerify = $false,
    [string]$LogLevel = "info",
    [string]$LogFormat = "console",
    [int]$ScanInterval = 5,
    [int]$MetricsInterval = 30
)

# Enhanced configuration function
function Install-EDRAgentWithTLS {
    param(
        [hashtable]$Config
    )
    
    Write-Host "Enhanced HUST-EDR Agent Installation with TLS Support" -ForegroundColor Cyan
    Write-Host "======================================================" -ForegroundColor Cyan
    
    # Display configuration
    Write-Host "`nConfiguration:" -ForegroundColor Yellow
    Write-Host "  Server Host: $($Config.ServerHost)" -ForegroundColor Cyan
    Write-Host "  gRPC Address: $($Config.gRPCHost):$($Config.gRPCPort)" -ForegroundColor Cyan
    Write-Host "  Use TLS: $($Config.UseTLS)" -ForegroundColor Cyan
    Write-Host "  Log Level: $($Config.LogLevel)" -ForegroundColor Cyan
    Write-Host "  Log Format: $($Config.LogFormat)" -ForegroundColor Cyan
    Write-Host "  Scan Interval: $($Config.ScanInterval) minutes" -ForegroundColor Cyan
    Write-Host "  Metrics Interval: $($Config.MetricsInterval) minutes" -ForegroundColor Cyan
    
    if ($Config.UseTLS -eq "true") {
        Write-Host "  Insecure Skip Verify: $($Config.InsecureSkipVerify)" -ForegroundColor Cyan
        Write-Host "  CA Certificate: Will be downloaded automatically from server" -ForegroundColor Cyan
    }
    
    # Check for administrator privileges
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Host "This script requires administrator privileges. Please run as administrator." -ForegroundColor Red
        return $false
    }
    
    # Create enhanced configuration script content
    $enhancedScriptPath = "$env:TEMP\install_edr_agent_enhanced.ps1"
    
    # Get the base installation script and modify it
    $baseScriptUrl = "http://$($Config.ServerHost)/api/install/edr-agent-script?host=$($Config.gRPCHost)&port=$($Config.gRPCPort)&use_tls=$($Config.UseTLS)&server_host=" + [Uri]::EscapeDataString($Config.ServerHost)
    if ($Config.InsecureSkipVerify) {
        $baseScriptUrl += "&insecure_skip_verify=true"
    }
    
    try {
        Write-Host "Downloading installation script from server..." -ForegroundColor Yellow
        $webClient = New-Object System.Net.WebClient
        $baseScript = $webClient.DownloadString($baseScriptUrl)
        
        # Modify the script to use our enhanced configuration
        $enhancedScript = $baseScript
        
        # Add our custom parameters to the param block - keeping it simple since CA is auto-downloaded
        $paramBlock = @"
param(
    [string]`$gRPCHost = "$($Config.gRPCHost):$($Config.gRPCPort)",
    [string]`$UseTLS = "$($Config.UseTLS)",
    [bool]`$InsecureSkipVerify = `$$($Config.InsecureSkipVerify.ToString().ToLower()),
    [string]`$ServerHost = "$($Config.ServerHost)"
)
"@
        
        # Replace the param block in the script
        $enhancedScript = $enhancedScript -replace "param\s*\([^}]*\)", $paramBlock
        
        # Save the enhanced script
        Set-Content -Path $enhancedScriptPath -Value $enhancedScript -Encoding UTF8
        
        Write-Host "Executing enhanced HUST-EDR Agent installation..." -ForegroundColor Yellow
        Write-Host "CA certificate will be downloaded automatically from the server..." -ForegroundColor Yellow
        
        # Execute the enhanced script with simplified parameters
        $scriptArgs = @{
            gRPCHost = "$($Config.gRPCHost):$($Config.gRPCPort)"
            UseTLS = $Config.UseTLS
            InsecureSkipVerify = $Config.InsecureSkipVerify
            ServerHost = $Config.ServerHost
        }
        
        & powershell.exe -ExecutionPolicy Bypass -File $enhancedScriptPath @scriptArgs
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "HUST-EDR Agent installation completed successfully!" -ForegroundColor Green
            
            # Verify configuration file - UPDATED PATH
            $configPath = "C:\Program Files\HUST-EDR\config.yaml"
            if (Test-Path $configPath) {
                Write-Host "`nVerifying configuration..." -ForegroundColor Yellow
                $configContent = Get-Content -Path $configPath -Raw
                
                # Check key configuration values
                if ($configContent -match "server_address:\s*""?([^""\n]+)""?") {
                    Write-Host "  Server Address: $($matches[1])" -ForegroundColor Cyan
                }
                if ($configContent -match "use_tls:\s*(\w+)") {
                    Write-Host "  TLS Enabled: $($matches[1])" -ForegroundColor Cyan
                }
                if ($configContent -match "ca_cert_path:\s*""?([^""\n]+)""?" -and $matches[1] -ne "") {
                    Write-Host "  CA Certificate: $($matches[1])" -ForegroundColor Cyan
                } else {
                    Write-Host "  CA Certificate: Not configured (using InsecureSkipVerify or TLS disabled)" -ForegroundColor Yellow
                }
                if ($configContent -match "log_level:\s*""?([^""\n]+)""?") {
                    Write-Host "  Log Level: $($matches[1])" -ForegroundColor Cyan
                }
                if ($configContent -match "agent_id:\s*""?([^""\n]+)""?" -and $matches[1] -ne "") {
                    Write-Host "  Agent ID: $($matches[1])" -ForegroundColor Cyan
                }
            }
            
            # Check service status
            Write-Host "`nService Status:" -ForegroundColor Yellow
            $service = Get-Service "HustEDRAgent" -ErrorAction SilentlyContinue
            if ($service) {
                $color = if ($service.Status -eq "Running") { "Green" } else { "Red" }
                Write-Host "  HUST-EDR Agent Service: $($service.Status)" -ForegroundColor $color
            } else {
                Write-Host "  HUST-EDR Agent Service: Not Found" -ForegroundColor Red
            }
            
            return $true
        } else {
            Write-Host "HUST-EDR Agent installation failed with exit code: $LASTEXITCODE" -ForegroundColor Red
            return $false
        }
        
    } catch {
        Write-Host "Error during enhanced installation: $_" -ForegroundColor Red
        return $false
    } finally {
        # Clean up temporary script
        if (Test-Path $enhancedScriptPath) {
            Remove-Item -Path $enhancedScriptPath -Force -ErrorAction SilentlyContinue
        }
    }
}

# Main execution
$installConfig = @{
    ServerHost = $ServerHost
    gRPCHost = $gRPCHost
    gRPCPort = $gRPCPort
    UseTLS = $UseTLS
    InsecureSkipVerify = $InsecureSkipVerify
    LogLevel = $LogLevel
    LogFormat = $LogFormat
    ScanInterval = $ScanInterval
    MetricsInterval = $MetricsInterval
}

$success = Install-EDRAgentWithTLS -Config $installConfig

if ($success) {
    Write-Host "`n" + "="*60 -ForegroundColor Green
    Write-Host "INSTALLATION SUMMARY" -ForegroundColor Green
    Write-Host "="*60 -ForegroundColor Green
    Write-Host "HUST-EDR Agent has been successfully installed and configured." -ForegroundColor Green
    Write-Host "`nInstallation Directory: C:\Program Files\HUST-EDR" -ForegroundColor Cyan
    Write-Host "Configuration file: C:\Program Files\HUST-EDR\config.yaml" -ForegroundColor Cyan
    Write-Host "Log directory: C:\Program Files\HUST-EDR\logs" -ForegroundColor Cyan
    Write-Host "Data directory: C:\Program Files\HUST-EDR\data" -ForegroundColor Cyan
    Write-Host "Certificate directory: C:\Program Files\HUST-EDR\certs" -ForegroundColor Cyan
    if ($UseTLS -eq "true") {
        Write-Host "CA Certificate: Downloaded automatically from server" -ForegroundColor Cyan
    }
    Write-Host "`nThe agent should now be connected to the HUST-EDR server." -ForegroundColor Green
    Write-Host "="*60 -ForegroundColor Green
} else {
    Write-Host "`nInstallation failed. Please check the error messages above." -ForegroundColor Red
    exit 1
} 