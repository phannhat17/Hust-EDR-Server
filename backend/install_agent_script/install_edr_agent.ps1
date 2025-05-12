# Install EDR Agent Script for Windows
# This script downloads and installs the EDR agent as a Windows service
# Must be run with administrator privileges

param(
    [string]$gRPCHost = "localhost:50051",
    [string]$caCertUrl = "" # URL to download CA certificate
)

# Format gRPC host - ensure it has protocol and port
if ($gRPCHost -notlike "*:*") {
    $gRPCHost = "$gRPCHost:50051"
}

# Set download URL and installation paths
$edrAgentUrl = "https://github.com/phannhat17/Hust-EDR-Server/releases/download/dev-v1.1.3/edr-agent.exe"
$edrDir = "C:\Program Files\Hust-EDR-Agent"
$edrExe = "$edrDir\edr-agent.exe"
$serviceName = "HustEDRAgent"
$certDir = "$edrDir\cert"
$caCertPath = "$certDir\ca.crt"

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

# Create certificate directory
if (!(Test-Path $certDir)) {
    Write-Host "Creating certificate directory: $certDir"
    New-Item -ItemType Directory -Path $certDir -Force | Out-Null
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
    Stop-Service -Name $serviceName -Force -ErrorAction SilentlyContinue
    Start-Sleep -s 2
    
    # Force kill any lingering processes
    $processName = "edr-agent"
    Get-Process | Where-Object {$_.ProcessName -eq $processName} | Stop-Process -Force -ErrorAction SilentlyContinue
    
    Write-Host "Removing existing EDR Agent service..."
    & sc.exe delete $serviceName
    Start-Sleep -s 2
}

# Make sure registry keys are cleaned up
$registryPaths = @(
    "HKLM:\SYSTEM\CurrentControlSet\Services\$serviceName",
    "HKLM:\SYSTEM\CurrentControlSet\Services\EventLog\Application\$serviceName"
)

foreach ($path in $registryPaths) {
    if (Test-Path $path) {
        Write-Host "Removing registry key: $path"
        Remove-Item -Path $path -Recurse -Force -ErrorAction SilentlyContinue
    }
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

# Download CA certificate if URL is provided
$useTLS = $false
if ($caCertUrl -ne "") {
    Write-Host "Downloading CA certificate..."
    try {
        Download-File -Url $caCertUrl -OutputFile $caCertPath
        $useTLS = $true
        Write-Host "CA certificate downloaded successfully to: $caCertPath" -ForegroundColor Green
    } catch {
        Write-Host "Failed to download CA certificate: $_" -ForegroundColor Yellow
        Write-Host "Will continue without TLS certificate verification" -ForegroundColor Yellow
    }
}

# Test the executable first to make sure it works
Write-Host "Testing EDR Agent executable..."
$agentIdFromTest = $null
try {
    $configDir = "$env:PROGRAMDATA\HustEDRAgent"
    if (!(Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    }
    
    # Create an initial config file for the test with empty agent ID
    $configFilePath = "$configDir\config.yaml"
    $logFileEscaped = $logDir.Replace("\", "/") + "/edr-agent.log"
    $dataFileEscaped = $configDir.Replace("\", "/") + "/data"
    
    # Build config based on whether we have a CA certificate
    $configContent = @"
server_address: $gRPCHost
agent_id: ""
log_file: "$logFileEscaped"
data_dir: "$dataFileEscaped"
version: "1.0.1"
use_tls: $($useTLS.ToString().ToLower())
"@

    # Add CA certificate path if available
    if ($useTLS) {
        $caCertPathEscaped = $caCertPath.Replace("\", "/")
        $configContent += "`nca_cert_path: `"$caCertPathEscaped`""
    }

    $configContent | Set-Content -Path $configFilePath
    Write-Host "Created initial config file at $configFilePath" -ForegroundColor Green
    
    # Testing connection to gRPC server
    Write-Host "Testing connection to gRPC server: $gRPCHost" -ForegroundColor Yellow
    $processArgs = @("-config=`"$configFilePath`"")
    $testProcess = Start-Process -FilePath $edrExe -ArgumentList $processArgs -NoNewWindow -PassThru
    
    # Wait a bit for registration to happen, but don't wait too long for test
    $testTimeout = 15 # seconds
    $testInterval = 1 # seconds
    $elapsed = 0
    
    # Log the test output in real-time to see connection issues
    $testLogFile = "$logDir\edr-agent-test.log"
    while (-not $testProcess.HasExited -and $elapsed -lt $testTimeout) {
        Write-Host "Waiting for test process... ($elapsed/$testTimeout seconds)" -ForegroundColor Yellow
        if (Test-Path $configFilePath) {
            $configContent = Get-Content -Path $configFilePath -Raw -ErrorAction SilentlyContinue
            if ($configContent -match "agent_id:\s*""([^""]+)""" -and $matches[1] -ne "") {
                $agentIdFromTest = $matches[1]
                Write-Host "Retrieved agent ID from test: $agentIdFromTest" -ForegroundColor Green
                break
            }
        }
        Start-Sleep -s $testInterval
        $elapsed += $testInterval
    }
    
    # If still running after timeout, kill the process
    if (-not $testProcess.HasExited) {
        Write-Host "Test registration timeout, terminating test process" -ForegroundColor Yellow
        Stop-Process -Id $testProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    # Check if test was successful
    if ($agentIdFromTest) {
        # Now we have the agent ID, let's make sure our config file has it
        $logFileEscaped = $logDir.Replace("\", "/") + "/edr-agent.log"
        $dataFileEscaped = $configDir.Replace("\", "/") + "/data"
        
        # Build updated config with agent ID
        $configContent = @"
server_address: $gRPCHost
agent_id: "$agentIdFromTest"
log_file: "$logFileEscaped"
data_dir: "$dataFileEscaped"
version: "1.0.1"
use_tls: $($useTLS.ToString().ToLower())
"@

        # Add CA certificate path if available
        if ($useTLS) {
            $caCertPathEscaped = $caCertPath.Replace("\", "/")
            $configContent += "`nca_cert_path: `"$caCertPathEscaped`""
        }

        $configContent | Set-Content -Path $configFilePath
        Write-Host "Updated config file with agent ID" -ForegroundColor Green
        Write-Host "EDR Agent executable test successful." -ForegroundColor Green
    } else {
        # Test failed, but we'll try running the service directly
        Write-Host "Could not obtain agent ID during test, will try during service installation" -ForegroundColor Yellow
        if ($testProcess.ExitCode -ne $null) {
            Write-Host "Test process exit code: $($testProcess.ExitCode)" -ForegroundColor Yellow
        }
    }
} catch {
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

# Create a new service
try {
    # Remove existing service if it exists (with confirmation suppressed)
    & $nssmExe remove $serviceName confirm 2>$null
    
    # Allow a moment for any removal to complete
    Start-Sleep -s 1
    
    # Make sure we have a valid config file
    $configFilePath = "$env:PROGRAMDATA\HustEDRAgent\config.yaml"
    if (-not (Test-Path $configFilePath)) {
        # If config file doesn't exist, create it now
        $logFileEscaped = $logDir.Replace("\", "/") + "/edr-agent.log"
        $dataFileEscaped = "$env:PROGRAMDATA\HustEDRAgent".Replace("\", "/") + "/data"
        @"
server_address: $gRPCHost
agent_id: ""
log_file: "$logFileEscaped"
data_dir: "$dataFileEscaped"
version: "1.0.1"
"@ | Set-Content -Path $configFilePath
        Write-Host "Created config file for service at $configFilePath" -ForegroundColor Green
    }
    
    # Always install the service with config file
    Write-Host "Installing service using config file: $configFilePath" -ForegroundColor Green
    & $nssmExe install $serviceName $edrExe "-config `"$configFilePath`""
    
    if ($LASTEXITCODE -ne 0) {
        throw "NSSM returned exit code $LASTEXITCODE"
    }
    
    Write-Host "Service installation successful" -ForegroundColor Green
} catch {
    Write-Host "Error during service installation: $_" -ForegroundColor Red
    
    # Try alternative approach if the first one fails
    Write-Host "Trying alternative installation method..." -ForegroundColor Yellow
    try {
        # Always use config file for alternative method too
        & sc.exe create $serviceName binPath= "$edrExe -config $configFilePath" DisplayName= "EDR Agent Service" start= auto
        
        if ($LASTEXITCODE -ne 0) {
            throw "sc.exe create returned exit code $LASTEXITCODE"
        }
        Write-Host "Alternative service installation successful" -ForegroundColor Green
    } catch {
        Write-Host "Alternative service installation also failed: $_" -ForegroundColor Red
        exit 1
    }
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
try {
    Start-Service -Name $serviceName -ErrorAction Stop
    Write-Host "Service start command issued successfully" -ForegroundColor Green
} catch {
    Write-Host "Error starting service: $_" -ForegroundColor Red
    Write-Host "Will attempt to continue anyway..." -ForegroundColor Yellow
}

# Wait for service to start with proper feedback
$maxWaitTime = 30  # seconds
$waitInterval = 3  # seconds
$elapsed = 0

while ($elapsed -lt $maxWaitTime) {
    Write-Host "Waiting for service to start... ($elapsed/$maxWaitTime seconds)" -ForegroundColor Yellow
    $service = Get-Service $serviceName -ErrorAction SilentlyContinue
    
    if ($service -and $service.Status -eq "Running") {
        Write-Host "EDR Agent service started successfully!" -ForegroundColor Green
        Write-Host "Service stdout logs: $stdoutLog" -ForegroundColor Green
        Write-Host "Service stderr logs: $stderrLog" -ForegroundColor Green
        break
    }
    
    Start-Sleep -s $waitInterval
    $elapsed += $waitInterval
}

# Final check
$service = Get-Service $serviceName -ErrorAction SilentlyContinue
if (-not $service -or $service.Status -ne "Running") {
    Write-Host "WARNING: Service did not start within the expected time." -ForegroundColor Red
    Write-Host "Current status: $($service.Status)" -ForegroundColor Red
    Write-Host "Check logs for more information:" -ForegroundColor Yellow
    Write-Host "  - Stdout: $stdoutLog" -ForegroundColor Yellow
    Write-Host "  - Stderr: $stderrLog" -ForegroundColor Yellow
    
    # Show log content if available
    if (Test-Path $stderrLog) {
        Write-Host "Last 10 lines of stderr log:" -ForegroundColor Yellow
        Get-Content -Path $stderrLog -Tail 10
    }
    
    # Don't exit here, as we want to complete the rest of the installation
    Write-Host "Continuing with installation despite service start issues..." -ForegroundColor Yellow
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