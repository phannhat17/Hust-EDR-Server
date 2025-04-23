# Install Sysmon Script for Windows
# This script downloads and installs Sysmon with a specific configuration
# Must be run with administrator privileges

# Set download URLs
$sysmonUrl = "https://download.sysinternals.com/files/Sysmon.zip"
$configUrl = "https://raw.githubusercontent.com/olafhartong/sysmon-modular/refs/heads/master/sysmonconfig.xml"

# Set installation paths
$sysmonDir = "C:\Program Files\Sysmon"
$tempDir = "$env:TEMP\SysmonInstall"
$sysmonZip = "$tempDir\Sysmon.zip"
$configFile = "$sysmonDir\sysmonconfig.xml"

# Check for administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "This script requires administrator privileges. Please run as administrator." -ForegroundColor Red
    exit 1
}

# Create Sysmon directory if it doesn't exist
if (!(Test-Path $sysmonDir)) {
    Write-Host "Creating Sysmon directory: $sysmonDir"
    New-Item -ItemType Directory -Path $sysmonDir -Force | Out-Null
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

# Download Sysmon
Write-Host "Downloading Sysmon..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
try {
    # Use faster WebClient instead of Invoke-WebRequest
    Download-File -Url $sysmonUrl -OutputFile $sysmonZip
} catch {
    Write-Host "WebClient download failed, trying alternative method..." -ForegroundColor Yellow
    
    # Fallback to BitsTransfer if available
    if (Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue) {
        Write-Host "Using BITS Transfer..."
        Start-BitsTransfer -Source $sysmonUrl -Destination $sysmonZip
    } else {
        # Last resort, use Invoke-WebRequest
        Write-Host "Using Invoke-WebRequest..."
        Invoke-WebRequest -Uri $sysmonUrl -OutFile $sysmonZip
    }
}

# Download configuration file
Write-Host "Downloading Sysmon configuration..."
try {
    Download-File -Url $configUrl -OutputFile $configFile
} catch {
    Write-Host "WebClient download failed for config, using Invoke-WebRequest..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $configUrl -OutFile $configFile
}

# Extract Sysmon to Program Files directory
Write-Host "Extracting Sysmon to $sysmonDir..."
Expand-Archive -Path $sysmonZip -DestinationPath $sysmonDir -Force

# Install Sysmon
Write-Host "Installing Sysmon..."
& "$sysmonDir\Sysmon64.exe" -accepteula -h md5,sha256,imphash -l -n -i $configFile

# Check if installation was successful
if ($LASTEXITCODE -eq 0) {
    Write-Host "Sysmon installed successfully!" -ForegroundColor Green
} else {
    Write-Host "Sysmon installation failed with exit code: $LASTEXITCODE" -ForegroundColor Red
}

# Create environment variable for Sysmon path
[System.Environment]::SetEnvironmentVariable("SYSMON_HOME", $sysmonDir, [System.EnvironmentVariableTarget]::Machine)
Write-Host "Added SYSMON_HOME environment variable pointing to $sysmonDir"

# Clean up
Write-Host "Cleaning up temporary files..."
Remove-Item -Path $tempDir -Recurse -Force

Write-Host "Sysmon installation complete in $sysmonDir" 