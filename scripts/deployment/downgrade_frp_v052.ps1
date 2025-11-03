# FRP Downgrade to v0.52.3 Script
# Purpose: Downgrade FRP client from v0.61.1 to v0.52.3 (stable version)
# Author: GymBro Team
# Date: 2025-01-13

$ErrorActionPreference = 'Stop'

# Configuration
$FRP_VERSION = "0.52.3"
$FRP_DOWNLOAD_BASE = "https://github.com/fatedier/frp/releases/download"
$FRP_DIR = Join-Path $PSScriptRoot "..\frp"
$FRP_BACKUP_DIR = Join-Path $PSScriptRoot "..\frp_backup_v061"
$ENV_FILE = Join-Path $PSScriptRoot "..\.env"

# Ports
$FRONTEND_PORT = 3101
$BACKEND_PORT = 9999

# Helper Functions
function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

function Read-EnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) {
        Write-ColorOutput "ERROR: .env file not found: $Path" "Red"
        exit 1
    }
    $envVars = @{}
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            if ($line -match '^([^=]+)=(.*)$') {
                $key = $matches[1].Trim()
                $value = $matches[2].Trim()
                $value = $value -replace '^["'']|["'']$', ''
                $envVars[$key] = $value
            }
        }
    }
    return $envVars
}

Write-ColorOutput "`n========================================" "Cyan"
Write-ColorOutput " FRP Downgrade to v0.52.3" "Cyan"
Write-ColorOutput "========================================`n" "Cyan"

# Step 1: Stop existing FRP process
Write-ColorOutput "[1/6] Stopping existing FRP process..." "Cyan"
$existingProcess = Get-Process -Name "frpc" -ErrorAction SilentlyContinue
if ($existingProcess) {
    Write-ColorOutput "  Found FRP process (PID: $($existingProcess.Id))" "Yellow"
    Stop-Process -Name "frpc" -Force
    Start-Sleep -Seconds 2
    Write-ColorOutput "  [OK] FRP process stopped" "Green"
} else {
    Write-ColorOutput "  [OK] No FRP process running" "Green"
}

# Step 2: Backup current version
Write-ColorOutput "`n[2/6] Backing up current version..." "Cyan"
if (Test-Path $FRP_DIR) {
    if (Test-Path $FRP_BACKUP_DIR) {
        Remove-Item $FRP_BACKUP_DIR -Recurse -Force
    }
    Copy-Item $FRP_DIR $FRP_BACKUP_DIR -Recurse
    Write-ColorOutput "  [OK] Backup created: $FRP_BACKUP_DIR" "Green"
} else {
    Write-ColorOutput "  [OK] No existing FRP directory to backup" "Green"
}

# Step 3: Download FRP v0.52.3
Write-ColorOutput "`n[3/6] Downloading FRP v0.52.3..." "Cyan"

$arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "386" }
$fileName = "frp_${FRP_VERSION}_windows_${arch}.zip"
$downloadUrl = "$FRP_DOWNLOAD_BASE/v${FRP_VERSION}/$fileName"
$zipPath = Join-Path $env:TEMP $fileName

Write-ColorOutput "  Version: $FRP_VERSION" "Gray"
Write-ColorOutput "  Architecture: $arch" "Gray"
Write-ColorOutput "  Download URL: $downloadUrl" "Gray"

try {
    Write-ColorOutput "  Downloading..." "Yellow"
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing

    Write-ColorOutput "  Extracting..." "Yellow"
    $extractDir = Join-Path $env:TEMP "frp_extract_v052"
    if (Test-Path $extractDir) {
        Remove-Item $extractDir -Recurse -Force
    }
    Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force

    $extractedFolder = Join-Path $extractDir "frp_${FRP_VERSION}_windows_${arch}"

    # Remove old FRP directory
    if (Test-Path $FRP_DIR) {
        Remove-Item $FRP_DIR -Recurse -Force
    }
    New-Item -ItemType Directory -Path $FRP_DIR -Force | Out-Null

    # Copy new version
    Copy-Item -Path "$extractedFolder\*" -Destination $FRP_DIR -Recurse -Force

    # Cleanup
    Remove-Item $zipPath -Force
    Remove-Item $extractDir -Recurse -Force

    Write-ColorOutput "  [OK] FRP v0.52.3 downloaded and installed" "Green"
} catch {
    Write-ColorOutput "  [ERROR] Download failed: $_" "Red"

    # Restore backup
    if (Test-Path $FRP_BACKUP_DIR) {
        Write-ColorOutput "  Restoring backup..." "Yellow"
        if (Test-Path $FRP_DIR) {
            Remove-Item $FRP_DIR -Recurse -Force
        }
        Copy-Item $FRP_BACKUP_DIR $FRP_DIR -Recurse
        Write-ColorOutput "  [OK] Backup restored" "Green"
    }
    exit 1
}

# Step 4: Verify version
Write-ColorOutput "`n[4/6] Verifying FRP version..." "Cyan"
$frpcExe = Join-Path $FRP_DIR "frpc.exe"
if (Test-Path $frpcExe) {
    $versionOutput = & $frpcExe --version 2>&1 | Select-Object -First 1
    Write-ColorOutput "  Installed version: $versionOutput" "Gray"
    Write-ColorOutput "  [OK] FRP v0.52.3 verified" "Green"
} else {
    Write-ColorOutput "  [ERROR] frpc.exe not found" "Red"
    exit 1
}

# Step 5: Generate INI configuration
Write-ColorOutput "`n[5/6] Generating INI configuration..." "Cyan"

$envVars = Read-EnvFile -Path $ENV_FILE
$serverAddr = $envVars["FRP_BASE_IP"]
$token = $envVars["FRP_TOKEN"]

if (-not $serverAddr -or -not $token) {
    Write-ColorOutput "  [ERROR] Missing FRP_BASE_IP or FRP_TOKEN in .env" "Red"
    exit 1
}

Write-ColorOutput "  Server: $serverAddr" "Gray"
Write-ColorOutput "  Token: $($token.Substring(0, 8))..." "Gray"

$configFile = Join-Path $FRP_DIR "frpc.ini"
$config = @"
[common]
server_addr = $serverAddr
server_port = 7000
auth_token = $token
log_level = info
log_max_days = 3

[gymbro-backend]
type = tcp
local_ip = 127.0.0.1
local_port = $BACKEND_PORT
remote_port = $BACKEND_PORT

[gymbro-frontend]
type = tcp
local_ip = 127.0.0.1
local_port = $FRONTEND_PORT
remote_port = $FRONTEND_PORT

[gymbro-api-http]
type = http
local_ip = 127.0.0.1
local_port = $BACKEND_PORT
custom_domains = api.gymbro.cloud

[gymbro-web-http]
type = http
local_ip = 127.0.0.1
local_port = $FRONTEND_PORT
custom_domains = web.gymbro.cloud
"@

Set-Content -Path $configFile -Value $config -Encoding ASCII
Write-ColorOutput "  [OK] Configuration file generated: $configFile" "Green"

# Step 6: Start FRP client
Write-ColorOutput "`n[6/6] Starting FRP client..." "Cyan"
Write-ColorOutput "  Starting..." "Yellow"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FRP_DIR'; Write-Host 'FRP Client v0.52.3 Running...' -ForegroundColor Cyan; Write-Host 'Configuration: frpc.ini' -ForegroundColor Gray; Write-Host ''; .\frpc.exe -c frpc.ini"

Start-Sleep -Seconds 5

$process = Get-Process -Name "frpc" -ErrorAction SilentlyContinue
if ($process) {
    Write-ColorOutput "  [OK] FRP client started (PID: $($process.Id))" "Green"

    Write-ColorOutput "`n========================================" "Cyan"
    Write-ColorOutput " FRP v0.52.3 Installation Complete" "Cyan"
    Write-ColorOutput "========================================" "Cyan"

    Write-ColorOutput "`nVersion Information:" "White"
    Write-ColorOutput "  Previous: v0.61.1 (buggy TOML parser)" "Gray"
    Write-ColorOutput "  Current:  v0.52.3 (stable)" "Green"
    Write-ColorOutput "  Config:   INI format (frpc.ini)" "Gray"

    Write-ColorOutput "`nTunnel Mapping:" "White"
    Write-ColorOutput "  Frontend: http://localhost:$FRONTEND_PORT -> http://${serverAddr}:$FRONTEND_PORT" "Gray"
    Write-ColorOutput "  Backend:  http://localhost:$BACKEND_PORT -> http://${serverAddr}:$BACKEND_PORT" "Gray"

    Write-ColorOutput "`nDomain Access:" "White"
    Write-ColorOutput "  Frontend: http://web.gymbro.cloud" "Gray"
    Write-ColorOutput "  Backend:  http://api.gymbro.cloud" "Gray"

    Write-ColorOutput "`nManagement:" "White"
    Write-ColorOutput "  View logs: Check FRP client window" "Gray"
    Write-ColorOutput "  Stop: Close FRP window or run Stop-Process -Name frpc" "Gray"
    Write-ColorOutput "  Restart: .\scripts\start-frp-ini.ps1" "Gray"

    Write-ColorOutput "`nBackup Location:" "White"
    Write-ColorOutput "  Old version backed up to: $FRP_BACKUP_DIR" "Gray"

    Write-ColorOutput "`n========================================`n" "Cyan"
    Write-ColorOutput "FRP v0.52.3 downgrade completed successfully!" "Green"
    Write-ColorOutput "`nWait 10 seconds for connection to establish, then check the FRP window for:" "Yellow"
    Write-ColorOutput "  - 'login to server success'" "Gray"
    Write-ColorOutput "  - 'proxy added: [gymbro-backend]'" "Gray"
    Write-ColorOutput "  - 'proxy added: [gymbro-frontend]'" "Gray"
    Write-ColorOutput "  - 'start proxy success'" "Gray"
    Write-ColorOutput "`nIf you see these messages, the tunnel is working!`n" "Green"
} else {
    Write-ColorOutput "  [ERROR] FRP client failed to start" "Red"
    Write-ColorOutput "  Check FRP client window for error messages" "Yellow"
    exit 1
}
