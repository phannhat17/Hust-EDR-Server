# Install Winlogbeat Script for Windows
# This script downloads and installs Winlogbeat with a specific configuration
# Must be run with administrator privileges

# Get server host from parameter or use default
param(
    [string]$ServerHost = "localhost:5000"
)

# Set download URLs
$winlogbeatUrl = "https://artifacts.elastic.co/downloads/beats/winlogbeat/winlogbeat-9.0.0-windows-x86_64.zip"
$configUrl = "http://$ServerHost/api/install/winlogbeat-config"
$cert1Url = "http://$ServerHost/api/install/kibana-cert"
$cert2Url = "http://$ServerHost/api/install/elasticsearch-cert"

# Set installation paths
$winlogbeatDir = "C:\Program Files\Winlogbeat"
$tempDir = "$env:TEMP\WinlogbeatInstall"
$winlogbeatZip = "$tempDir\winlogbeat.zip"
$configFile = "$winlogbeatDir\winlogbeat.yml"
$cert1File = "$winlogbeatDir\kibana.crt"
$cert2File = "$winlogbeatDir\elasticsearch.crt"

# Check for administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "This script requires administrator privileges. Please run as administrator." -ForegroundColor Red
    exit 1
}

# Create Winlogbeat directory if it doesn't exist
if (!(Test-Path $winlogbeatDir)) {
    Write-Host "Creating Winlogbeat directory: $winlogbeatDir"
    New-Item -ItemType Directory -Path $winlogbeatDir -Force | Out-Null
}

# Create temp directory if it doesn't exist
if (!(Test-Path $tempDir)) {
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    Write-Host "Created temporary directory: $tempDir"
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

# Download Winlogbeat
Write-Host "Downloading Winlogbeat..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
    # Use faster WebClient instead of Invoke-WebRequest
    Download-File -Url $winlogbeatUrl -OutputFile $winlogbeatZip
} catch {
    Write-Host "WebClient download failed, trying alternative method..." -ForegroundColor Yellow
    
    # Fallback to BitsTransfer if available
    if (Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue) {
        Write-Host "Using BITS Transfer..."
        Start-BitsTransfer -Source $winlogbeatUrl -Destination $winlogbeatZip
    } else {
        # Last resort, use Invoke-WebRequest
        Write-Host "Using Invoke-WebRequest..."
        Invoke-WebRequest -Uri $winlogbeatUrl -OutFile $winlogbeatZip
    }
}

# Download configuration file
Write-Host "Downloading Winlogbeat configuration from $configUrl..."
Download-File -Url $configUrl -OutputFile $configFile

# Download certificates
Write-Host "Downloading certificates..."
try {
    Download-File -Url $cert1Url -OutputFile $cert1File
    Download-File -Url $cert2Url -OutputFile $cert2File
    Write-Host "Certificates downloaded successfully."
} catch {
    Write-Host "Warning: Could not download certificates. You may need to add them manually." -ForegroundColor Yellow
}

# Extract Winlogbeat to Program Files directory
Write-Host "Extracting Winlogbeat to $winlogbeatDir..."
Expand-Archive -Path $winlogbeatZip -DestinationPath $tempDir -Force

# Get the extracted directory name (might contain version number)
$extractedDir = Get-ChildItem -Path $tempDir -Directory | Select-Object -First 1
$extractedPath = $extractedDir.FullName

# Copy all files from the extracted directory to the installation directory
Write-Host "Copying files to $winlogbeatDir..."
Copy-Item -Path "$extractedPath\*" -Destination $winlogbeatDir -Recurse -Force

# Install Winlogbeat service
Write-Host "Installing Winlogbeat service..."
Start-Process -FilePath "powershell.exe" -ArgumentList "-ExecutionPolicy Unrestricted -File `"$winlogbeatDir\install-service-winlogbeat.ps1`"" -WorkingDirectory $winlogbeatDir -Wait

# Set up Winlogbeat
Write-Host "Setting up Winlogbeat..."
Start-Process -FilePath "$winlogbeatDir\winlogbeat.exe" -ArgumentList "setup -e" -WorkingDirectory $winlogbeatDir -Wait

# Start Winlogbeat service
Write-Host "Starting Winlogbeat service..."
Start-Service winlogbeat

# Check if service is running
$service = Get-Service -Name "winlogbeat" -ErrorAction SilentlyContinue
if ($service -and $service.Status -eq "Running") {
    Write-Host "Winlogbeat service is running!" -ForegroundColor Green
} else {
    Write-Host "Winlogbeat service is not running. Please check the logs." -ForegroundColor Yellow
}

# Create environment variable for Winlogbeat path
[System.Environment]::SetEnvironmentVariable("WINLOGBEAT_HOME", $winlogbeatDir, [System.EnvironmentVariableTarget]::Machine)
Write-Host "Added WINLOGBEAT_HOME environment variable pointing to $winlogbeatDir"

# Clean up
Write-Host "Cleaning up temporary files..."
Remove-Item -Path $tempDir -Recurse -Force

Write-Host "Winlogbeat installation complete in $winlogbeatDir" 