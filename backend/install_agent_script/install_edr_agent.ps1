# Install EDR Agent Script for Windows
# This script downloads and installs the EDR agent as a Windows service
# Must be run with administrator privileges

param(
    [string]$gRPCHost = "192.168.133.145:50051"
)

# Set download URL and installation paths
$edrAgentUrl = "https://github.com/phannhat17/Hust-EDR-Server/releases/download/dev-v1.0.2/edr-agent.exe"
$edrDir = "C:\Program Files\Hust-EDR-Agent"
$edrExe = "$edrDir\edr-agent.exe"
$serviceName = "HustEDRAgent"

# Check for administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "This script requires administrator privileges. Please run as administrator." -ForegroundColor Red
    exit 1
}

# Create EDR directory if it doesn't exist
if (!(Test-Path $edrDir)) {
    Write-Host "Creating EDR directory: $edrDir"
    New-Item -ItemType Directory -Path $edrDir -Force | Out-Null
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

# Delete and stop the service if it already exists
if (Get-Service $serviceName -ErrorAction SilentlyContinue) {
    Write-Host "Stopping existing EDR Agent service..."
    Stop-Service -Name $serviceName
    (Get-Service $serviceName).WaitForStatus('Stopped')
    Start-Sleep -s 1
    sc.exe delete $serviceName
}

# Download EDR Agent
Write-Host "Downloading EDR Agent..."
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

# Create the new service using New-Service
Write-Host "Creating EDR Agent service..."
Write-Host "gRPC Server: $gRPCHost" -ForegroundColor Yellow
# Fix the binary path to ensure proper parameter passing
$binaryPathName = "`"$edrExe`" -server $gRPCHost"
New-Service -name $serviceName `
    -displayName "EDR Agent Service" `
    -description "Endpoint Detection and Response agent service" `
    -binaryPathName $binaryPathName 


# # Attempt to set the service to delayed start using sc config
# Try {
#     Write-Host "Setting service to delayed start..."
#     Start-Process -FilePath sc.exe -ArgumentList "config $serviceName start= delayed-auto"
# } Catch { 
#     Write-Host -f red "An error occurred setting the service to delayed start."
# }

# # Start the service
# Write-Host "Starting EDR Agent service..."
# Try {
#     Start-Service -Name $serviceName -ErrorAction Stop
#     Write-Host "EDR Agent service started successfully!" -ForegroundColor Green
# } Catch {
#     Write-Host "Failed to start EDR Agent service: $_" -ForegroundColor Red
    
#     # Get detailed error information
#     Write-Host "Checking service status and configuration..." -ForegroundColor Yellow
#     $serviceDetails = Get-CimInstance -ClassName Win32_Service -Filter "Name='$serviceName'"
#     Write-Host "Service Path: $($serviceDetails.PathName)" -ForegroundColor Yellow
#     Write-Host "Service Start Mode: $($serviceDetails.StartMode)" -ForegroundColor Yellow
#     Write-Host "Service State: $($serviceDetails.State)" -ForegroundColor Yellow
    
#     # Try running the executable directly to see if there are any errors
#     # Write-Host "Attempting to run the executable directly for troubleshooting..." -ForegroundColor Yellow
#     # & $edrExe -server="$gRPCHost"
# }

# # Create environment variable for EDR path
# [System.Environment]::SetEnvironmentVariable("EDR_HOME", $edrDir, [System.EnvironmentVariableTarget]::Machine)
# Write-Host "Added EDR_HOME environment variable pointing to $edrDir"

# Write-Host "EDR Agent installation complete in $edrDir" 