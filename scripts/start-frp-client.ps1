# FRP Client Auto-Start Script
# Purpose: Map local dev environment (frontend 3101, backend 9999) to remote server via FRP tunnel
# Author: GymBro Team
# Date: 2025-01-13

$ErrorActionPreference = 'Stop'

# Configuration
$FRP_VERSION = "0.61.1"
$FRP_DOWNLOAD_BASE = "https://github.com/fatedier/frp/releases/download"
$FRP_DIR = Join-Path $PSScriptRoot "..\frp"
$FRP_CONFIG_FILE = Join-Path $FRP_DIR "frpc.toml"
$FRP_EXECUTABLE = Join-Path $FRP_DIR "frpc.exe"
$ENV_FILE = Join-Path $PSScriptRoot "..\.env"

$FRONTEND_PORT = 3101
$BACKEND_PORT = 9999
$REMOTE_FRONTEND_PORT = 3101
$REMOTE_BACKEND_PORT = 9999

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

function Test-PortListening {
    param([int]$Port)
    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect("127.0.0.1", $Port)
        $connection.Close()
        return $true
    } catch {
        return $false
    }
}

function Get-FRPClient {
    param([string]$Version, [string]$DestDir)
    Write-ColorOutput "`n[1/5] Downloading FRP client..." "Cyan"
    $arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "386" }
    $fileName = "frp_${Version}_windows_${arch}.zip"
    $downloadUrl = "$FRP_DOWNLOAD_BASE/v${Version}/$fileName"
    $zipPath = Join-Path $env:TEMP $fileName
    Write-ColorOutput "  Version: $Version" "Gray"
    Write-ColorOutput "  Architecture: $arch" "Gray"
    Write-ColorOutput "  Download URL: $downloadUrl" "Gray"
    try {
        Write-ColorOutput "  Downloading..." "Yellow"
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing
        Write-ColorOutput "  Extracting..." "Yellow"
        $extractDir = Join-Path $env:TEMP "frp_extract"
        if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force }
        Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force
        $extractedFolder = Join-Path $extractDir "frp_${Version}_windows_${arch}"
        if (-not (Test-Path $DestDir)) { New-Item -ItemType Directory -Path $DestDir -Force | Out-Null }
        Copy-Item -Path "$extractedFolder\*" -Destination $DestDir -Recurse -Force
        Remove-Item $zipPath -Force
        Remove-Item $extractDir -Recurse -Force
        Write-ColorOutput "  [OK] FRP client downloaded successfully" "Green"
    } catch {
        Write-ColorOutput "  [ERROR] Download failed: $_" "Red"
        exit 1
    }
}

function New-FRPConfig {
    param([string]$ConfigPath, [hashtable]$EnvVars)
    Write-ColorOutput "`n[2/5] Generating FRP configuration..." "Cyan"
    $serverAddr = $EnvVars["FRP_BASE_IP"]
    $token = $EnvVars["FRP_TOKEN"]
    if (-not $serverAddr -or -not $token) {
        Write-ColorOutput "  [ERROR] Missing FRP_BASE_IP or FRP_TOKEN in .env" "Red"
        exit 1
    }
    Write-ColorOutput "  Server address: $serverAddr" "Gray"
    Write-ColorOutput "  Auth token: $($token.Substring(0, 8))..." "Gray"
    $config = @"
# FRP Client Configuration
# Auto-generated at $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

serverAddr = "$serverAddr"
serverPort = 7000

auth.method = "token"
auth.token = "$token"

log.level = "info"
log.maxDays = 3

[[proxies]]
name = "gymbro-frontend"
type = "tcp"
localIP = "127.0.0.1"
localPort = $FRONTEND_PORT
remotePort = $REMOTE_FRONTEND_PORT

[[proxies]]
name = "gymbro-backend"
type = "tcp"
localIP = "127.0.0.1"
localPort = $BACKEND_PORT
remotePort = $REMOTE_BACKEND_PORT

[[proxies]]
name = "gymbro-api-http"
type = "http"
localIP = "127.0.0.1"
localPort = $BACKEND_PORT
customDomains = ["api.gymbro.cloud"]

[[proxies]]
name = "gymbro-web-http"
type = "http"
localIP = "127.0.0.1"
localPort = $FRONTEND_PORT
customDomains = ["web.gymbro.cloud"]
"@
    Set-Content -Path $ConfigPath -Value $config -Encoding UTF8
    Write-ColorOutput "  [OK] Configuration file generated: $ConfigPath" "Green"
}

function Test-LocalServices {
    Write-ColorOutput "`n[3/5] Checking local services..." "Cyan"
    $frontendRunning = Test-PortListening -Port $FRONTEND_PORT
    $backendRunning = Test-PortListening -Port $BACKEND_PORT
    if ($frontendRunning) {
        Write-ColorOutput "  [OK] Frontend service running (port $FRONTEND_PORT)" "Green"
    } else {
        Write-ColorOutput "  [WARN] Frontend service not running (port $FRONTEND_PORT)" "Yellow"
    }
    if ($backendRunning) {
        Write-ColorOutput "  [OK] Backend service running (port $BACKEND_PORT)" "Green"
    } else {
        Write-ColorOutput "  [WARN] Backend service not running (port $BACKEND_PORT)" "Yellow"
    }
    if (-not $frontendRunning -and -not $backendRunning) {
        Write-ColorOutput "`n  [WARN] No local services running" "Yellow"
        Write-ColorOutput "  Suggestion: Run .\start-dev.ps1 first" "Yellow"
        $continue = Read-Host "`n  Continue? (y/N)"
        if ($continue -ne "y" -and $continue -ne "Y") {
            Write-ColorOutput "`n  Cancelled" "Yellow"
            exit 0
        }
    }
}

function Start-FRPClient {
    param([string]$ExePath, [string]$ConfigPath)
    Write-ColorOutput "`n[4/5] Starting FRP client..." "Cyan"
    $existingProcess = Get-Process -Name "frpc" -ErrorAction SilentlyContinue
    if ($existingProcess) {
        Write-ColorOutput "  [WARN] Existing FRP client process detected" "Yellow"
        $kill = Read-Host "  Kill and restart? (y/N)"
        if ($kill -eq "y" -or $kill -eq "Y") {
            Stop-Process -Name "frpc" -Force
            Start-Sleep -Seconds 2
            Write-ColorOutput "  [OK] Existing process terminated" "Green"
        } else {
            Write-ColorOutput "  Cancelled" "Yellow"
            exit 0
        }
    }
    Write-ColorOutput "  Starting..." "Yellow"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FRP_DIR'; Write-Host 'FRP Client Running...' -ForegroundColor Cyan; .\frpc.exe -c '$ConfigPath'"
    Start-Sleep -Seconds 3
    $process = Get-Process -Name "frpc" -ErrorAction SilentlyContinue
    if ($process) {
        Write-ColorOutput "  [OK] FRP client started (PID: $($process.Id))" "Green"
    } else {
        Write-ColorOutput "  [ERROR] FRP client failed to start" "Red"
        exit 1
    }
}

function Show-Summary {
    param([hashtable]$EnvVars)
    Write-ColorOutput "`n[5/5] Startup complete" "Cyan"
    Write-ColorOutput "`n========================================" "Cyan"
    Write-ColorOutput " FRP Tunnel Mapping Information" "Cyan"
    Write-ColorOutput "========================================" "Cyan"
    $serverAddr = $EnvVars["FRP_BASE_IP"]
    Write-ColorOutput "`nLocal -> Remote:" "White"
    Write-ColorOutput "  Frontend: http://localhost:$FRONTEND_PORT -> http://${serverAddr}:$REMOTE_FRONTEND_PORT" "Gray"
    Write-ColorOutput "  Backend:  http://localhost:$BACKEND_PORT -> http://${serverAddr}:$REMOTE_BACKEND_PORT" "Gray"
    Write-ColorOutput "`nDomain Access:" "White"
    Write-ColorOutput "  Frontend: http://web.gymbro.cloud" "Gray"
    Write-ColorOutput "  Backend:  http://api.gymbro.cloud" "Gray"
    Write-ColorOutput "`n========================================`n" "Cyan"
}

# Main Process
Write-ColorOutput "`n========================================" "Cyan"
Write-ColorOutput " FRP Client Auto-Start Script" "Cyan"
Write-ColorOutput "========================================`n" "Cyan"

$envVars = Read-EnvFile -Path $ENV_FILE

if (-not (Test-Path $FRP_EXECUTABLE)) {
    Write-ColorOutput "FRP client not detected, downloading..." "Yellow"
    Get-FRPClient -Version $FRP_VERSION -DestDir $FRP_DIR
} else {
    Write-ColorOutput "[OK] FRP client already installed" "Green"
}

New-FRPConfig -ConfigPath $FRP_CONFIG_FILE -EnvVars $envVars
Test-LocalServices
Start-FRPClient -ExePath $FRP_EXECUTABLE -ConfigPath $FRP_CONFIG_FILE
Show-Summary -EnvVars $envVars

Write-ColorOutput "FRP client started successfully!" "Green"
