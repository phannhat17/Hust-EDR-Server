#!/usr/bin/env pwsh
# Install EDR Agent with mTLS certificate setup
# This script downloads all necessary certificates and configures the agent for mTLS

param(
    [string]$serverAddress = "localhost:50051",
    [string]$caCertUrl = "",              # URL to download CA certificate
    [string]$clientCertUrl = "",          # URL to download client certificate
    [string]$clientKeyUrl = "",           # URL to download client key
    [string]$agentName = "agent1"         # Name of the agent for cert generation
)

# Define paths
$edrDir = "C:\Program Files\Hust-EDR-Agent"
$certDir = "$edrDir\cert"
$caCertPath = "$certDir\ca.crt"
$clientCertPath = "$certDir\$agentName.crt"
$clientKeyPath = "$certDir\$agentName.key"
$configDir = "$env:PROGRAMDATA\HustEDRAgent"
$configPath = "$configDir\config.yaml"

# Create directories if they don't exist
foreach ($dir in @($edrDir, $certDir, $configDir)) {
    if (!(Test-Path $dir)) {
        Write-Host "Creating directory: $dir"
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}

# Function to download a file
function Download-File {
    param (
        [string]$Url,
        [string]$OutputFile
    )
    
    if ([string]::IsNullOrEmpty($Url)) {
        Write-Host "No URL provided for $OutputFile" -ForegroundColor Yellow
        return $false
    }
    
    try {
        Write-Host "Downloading $Url to $OutputFile..."
        $webClient = New-Object System.Net.WebClient
        $webClient.DownloadFile($Url, $OutputFile)
        return $true
    }
    catch {
        Write-Host "Failed to download from $Url: $_" -ForegroundColor Red
        return $false
    }
}

# Check if we need to generate certificates locally
$needLocalGeneration = $true

# Try downloading certificates first if URLs are provided
$caSuccess = Download-File -Url $caCertUrl -OutputFile $caCertPath
$clientCertSuccess = Download-File -Url $clientCertUrl -OutputFile $clientCertPath
$clientKeySuccess = Download-File -Url $clientKeyUrl -OutputFile $clientKeyPath

# Complete mTLS setup requires all three files
$mtlsReady = $caSuccess -and $clientCertSuccess -and $clientKeySuccess

if ($mtlsReady) {
    Write-Host "Successfully downloaded all certificates for mTLS" -ForegroundColor Green
    $needLocalGeneration = $false
} else {
    Write-Host "Not all certificate files could be downloaded." -ForegroundColor Yellow
    
    # Check if we got at least the CA certificate
    if ($caSuccess) {
        Write-Host "CA certificate downloaded, will use it for server verification only." -ForegroundColor Yellow
    } else {
        Write-Host "Failed to download CA certificate. TLS will not be enabled." -ForegroundColor Yellow
    }
}

# Create or update the config.yaml
Write-Host "Configuring EDR agent..."

# Start with base configuration
$configContent = @"
server_address: $serverAddress
agent_id: ""
data_dir: "$($configDir.Replace('\', '/'))/data"
version: "1.0.1"
"@

# Add certificate configuration
if ($caSuccess) {
    $configContent += @"

# TLS Configuration
use_tls: true
ca_cert_path: "$($caCertPath.Replace('\', '/'))"
"@
    
    if ($mtlsReady) {
        $configContent += @"

# mTLS Configuration
client_cert_path: "$($clientCertPath.Replace('\', '/'))"
client_key_path: "$($clientKeyPath.Replace('\', '/'))"
"@
    }
} else {
    $configContent += @"

# TLS Configuration
use_tls: false
"@
}

# Write the configuration
$configContent | Set-Content -Path $configPath

Write-Host "Configuration written to $configPath" -ForegroundColor Green

# Print configuration summary
Write-Host "`nEDR Agent Configuration Summary:" -ForegroundColor Cyan
Write-Host "--------------------------------"
Write-Host "Server Address: $serverAddress"

if ($caSuccess) {
    Write-Host "TLS Enabled: Yes"
    Write-Host "CA Certificate: $caCertPath"
    
    if ($mtlsReady) {
        Write-Host "mTLS Enabled: Yes"
        Write-Host "Client Certificate: $clientCertPath"
        Write-Host "Client Key: $clientKeyPath"
    } else {
        Write-Host "mTLS Enabled: No (only server verification)"
    }
} else {
    Write-Host "TLS Enabled: No"
}

Write-Host "`nInstallation preparation completed. You can now run the main installation script:" -ForegroundColor Cyan
Write-Host "Install-EDRAgent.ps1 -gRPCHost $serverAddress" -ForegroundColor Yellow 