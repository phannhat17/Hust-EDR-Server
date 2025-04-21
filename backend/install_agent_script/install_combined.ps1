# Combined Installation Script for Sysmon and Winlogbeat
# This script installs both Sysmon and Winlogbeat in sequence
# Must be run with administrator privileges

param(
    [string]$ServerHost = "localhost:5000"
)

# Check for administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "This script requires administrator privileges. Please run as administrator." -ForegroundColor Red
    exit 1
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

# Function to download and execute script content directly in memory
function Download-And-Execute-Script {
    param (
        [string]$Url,
        [string]$Description
    )
    
    Write-Host "Downloading $Description script from $Url"
    try {
        $webClient = New-Object System.Net.WebClient
        $scriptContent = $webClient.DownloadString($Url)
        
        Write-Host "Executing $Description script in memory..."
        $scriptBlock = [ScriptBlock]::Create($scriptContent)
        & $scriptBlock
        
        if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq $null) {
            Write-Host "$Description installation completed successfully." -ForegroundColor Green
            return $true
        } else {
            Write-Host "$Description installation may have encountered issues. Exit code: $LASTEXITCODE" -ForegroundColor Yellow
            return $false
        }
    } catch {
        Write-Host "Error during $Description installation: $_" -ForegroundColor Red
        return $false
    }
}

# Display banner
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  Starting Installation Process" -ForegroundColor Cyan
Write-Host "  Sysmon + Winlogbeat" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan

# Step 1: Install Sysmon
Write-Host "`n[STEP 1] Installing Sysmon..." -ForegroundColor Green
$sysmonSuccess = Download-And-Execute-Script -Url "http://$ServerHost/api/install/sysmon-script" -Description "Sysmon"

if (-not $sysmonSuccess) {
    Write-Host "Continuing with Winlogbeat installation anyway..." -ForegroundColor Yellow
}

# Step 2: Install Winlogbeat
Write-Host "`n[STEP 2] Installing Winlogbeat..." -ForegroundColor Green
$winlogbeatSuccess = Download-And-Execute-Script -Url "http://$ServerHost/api/install/winlogbeat-script-with-host/$ServerHost" -Description "Winlogbeat"

# Final status
Write-Host "`n=============================================" -ForegroundColor Cyan
Write-Host "  Installation Status" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "Sysmon: $(if ($sysmonSuccess) { "Installed" } else { "Installation failed" })" -ForegroundColor $(if ($sysmonSuccess) { "Green" } else { "Red" })
Write-Host "Winlogbeat: $(if ($winlogbeatSuccess) { "Installed" } else { "Installation failed" })" -ForegroundColor $(if ($winlogbeatSuccess) { "Green" } else { "Red" })
Write-Host "`nFor more information, check the installation logs." -ForegroundColor White

if ($sysmonSuccess -and $winlogbeatSuccess) {
    Write-Host "`nBoth products were successfully installed!" -ForegroundColor Green
} elseif ($sysmonSuccess -or $winlogbeatSuccess) {
    Write-Host "`nPartial success: At least one product was installed successfully." -ForegroundColor Yellow
} else {
    Write-Host "`nInstallation failed for both products. Please check the logs and try again." -ForegroundColor Red
}

exit 0 