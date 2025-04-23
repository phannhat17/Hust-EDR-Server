# Install EDR Agent Script for Windows
# This script downloads and installs the EDR agent as a Windows service
# Must be run with administrator privileges

param(
    [string]$gRPCHost = "localhost:50051"
)

# Set download URL and installation paths
$edrAgentUrl = "https://github.com/phannhat17/Hust-EDR-Server/releases/download/dev-v1.0.2/edr-agent.exe"
$edrDir = "C:\Program Files\Hust-EDR-Agent"
$edrExe = "$edrDir\edr-agent.exe"
$serviceName = "HustEDRAgent"

# NSSM settings
$nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
$nssmZip = "$env:TEMP\nssm.zip"
$nssmDir = "$edrDir\nssm"
$nssmExe = "$nssmDir\nssm-2.24\win64\nssm.exe"

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

# Create logs and data directories
$dataDir = "$env:PROGRAMDATA\HustEDRAgent"
if (!(Test-Path $dataDir)) {
    Write-Host "Creating data directory: $dataDir"
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
}
$logDir = "$dataDir\logs"
if (!(Test-Path $logDir)) {
    Write-Host "Creating logs directory: $logDir"
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
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

# Test the executable first to make sure it works
Write-Host "Testing EDR Agent executable..."
try {
    $processArgs = @("-server=`"$gRPCHost`"")
    $testProcess = Start-Process -FilePath $edrExe -ArgumentList $processArgs -NoNewWindow -PassThru
    Start-Sleep -s 2
    if (!$testProcess.HasExited -or $testProcess.ExitCode -eq 0) {
        if (!$testProcess.HasExited) {
            Stop-Process -Id $testProcess.Id -Force -ErrorAction SilentlyContinue
        }
        Write-Host "EDR Agent executable test successful." -ForegroundColor Green
    }
    else {
        Write-Host "EDR Agent executable test failed with exit code: $($testProcess.ExitCode)" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "Error testing EDR Agent executable: $_" -ForegroundColor Yellow
}

# Download and install NSSM
Write-Host "Downloading NSSM (Non-Sucking Service Manager)..."
if (!(Test-Path $nssmDir)) {
    New-Item -ItemType Directory -Path $nssmDir -Force | Out-Null
}

try {
    # Download NSSM
    Download-File -Url $nssmUrl -OutputFile $nssmZip
    
    # Extract NSSM
    Write-Host "Extracting NSSM..."
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($nssmZip, $nssmDir)
    
    # Verify NSSM exists
    if (!(Test-Path $nssmExe)) {
        throw "NSSM executable not found at expected path: $nssmExe"
    }
} catch {
    Write-Host "Error downloading or extracting NSSM: $_" -ForegroundColor Red
    exit 1
}

# Create log file paths
$stdoutLog = "$logDir\edr-agent-stdout.log"
$stderrLog = "$logDir\edr-agent-stderr.log"

# Install service using NSSM
Write-Host "Installing EDR Agent service using NSSM..."
Write-Host "gRPC Server: $gRPCHost" -ForegroundColor Yellow

# Remove existing service if it exists
& $nssmExe remove $serviceName confirm | Out-Null

# Install the service
& $nssmExe install $serviceName $edrExe "-server $gRPCHost"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to install service using NSSM." -ForegroundColor Red
    exit 1
}

# Configure service details
& $nssmExe set $serviceName DisplayName "EDR Agent Service"
& $nssmExe set $serviceName Description "Endpoint Detection and Response agent service"
& $nssmExe set $serviceName Start SERVICE_AUTO_START

# Configure stdout/stderr redirection
& $nssmExe set $serviceName AppStdout $stdoutLog
& $nssmExe set $serviceName AppStderr $stderrLog
& $nssmExe set $serviceName AppRotateFiles 1
& $nssmExe set $serviceName AppRotateOnline 1
& $nssmExe set $serviceName AppRotateSeconds 86400
& $nssmExe set $serviceName AppRotateBytes 10485760

# Start the service
Write-Host "Starting EDR Agent service..."
Start-Service -Name $serviceName -ErrorAction SilentlyContinue
Start-Sleep -s 3

# Check if service is running
$service = Get-Service $serviceName
if ($service.Status -eq "Running") {
    Write-Host "EDR Agent service started successfully!" -ForegroundColor Green
    Write-Host "Service stdout logs: $stdoutLog" -ForegroundColor Green
    Write-Host "Service stderr logs: $stderrLog" -ForegroundColor Green
} else {
    Write-Host "Failed to start service. Status: $($service.Status)" -ForegroundColor Red
    Write-Host "Check NSSM logs in $logDir" -ForegroundColor Yellow
    
    # Try to get error information
    $nssmStatus = & $nssmExe status $serviceName
    Write-Host "NSSM service status: $nssmStatus" -ForegroundColor Yellow
}

# Create environment variable for EDR path
[System.Environment]::SetEnvironmentVariable("EDR_HOME", $edrDir, [System.EnvironmentVariableTarget]::Machine)
Write-Host "Added EDR_HOME environment variable pointing to $edrDir"

# Clean up NSSM files
Write-Host "Cleaning up NSSM installation files..."
if (Test-Path $nssmDir) {
    Remove-Item -Path $nssmDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "NSSM directory removed."
}
if (Test-Path $nssmZip) {
    Remove-Item -Path $nssmZip -Force -ErrorAction SilentlyContinue
    Write-Host "NSSM zip file removed."
}

Write-Host "EDR Agent installation complete in $edrDir" 