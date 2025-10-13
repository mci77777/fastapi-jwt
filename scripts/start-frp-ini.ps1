# FRP Client Start Script (INI Format - Workaround for v0.61.1 TOML bug)
# Purpose: Start FRP client using INI configuration format
# Author: GymBro Team
# Date: 2025-01-13

$ErrorActionPreference = 'Stop'

# Configuration
$FRP_DIR = Join-Path $PSScriptRoot "..\frp"
$FRP_EXECUTABLE = Join-Path $FRP_DIR "frpc.exe"
$FRP_CONFIG_FILE = Join-Path $FRP_DIR "frpc.ini"
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
Write-ColorOutput " FRP Client Start Script (INI Format)" "Cyan"
Write-ColorOutput "========================================`n" "Cyan"

# Read environment variables
Write-ColorOutput "[1/4] Reading configuration..." "Cyan"
$envVars = Read-EnvFile -Path $ENV_FILE
$serverAddr = $envVars["FRP_BASE_IP"]
$token = $envVars["FRP_TOKEN"]

if (-not $serverAddr -or -not $token) {
    Write-ColorOutput "  [ERROR] Missing FRP_BASE_IP or FRP_TOKEN in .env" "Red"
    exit 1
}

Write-ColorOutput "  Server: $serverAddr" "Gray"
Write-ColorOutput "  Token: $($token.Substring(0, 8))..." "Gray"
Write-ColorOutput "  [OK] Configuration loaded" "Green"

# Check FRP client
Write-ColorOutput "`n[2/4] Checking FRP client..." "Cyan"
if (-not (Test-Path $FRP_EXECUTABLE)) {
    Write-ColorOutput "  [ERROR] FRP client not found: $FRP_EXECUTABLE" "Red"
    Write-ColorOutput "  Run .\scripts\start-frp-client.ps1 first to download FRP" "Yellow"
    exit 1
}
Write-ColorOutput "  [OK] FRP client found" "Green"

# Generate INI configuration
Write-ColorOutput "`n[3/4] Generating INI configuration..." "Cyan"

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

Set-Content -Path $FRP_CONFIG_FILE -Value $config -Encoding ASCII
Write-ColorOutput "  [OK] Configuration file generated: $FRP_CONFIG_FILE" "Green"

# Stop existing process
$existingProcess = Get-Process -Name "frpc" -ErrorAction SilentlyContinue
if ($existingProcess) {
    Write-ColorOutput "`n  [WARN] Existing FRP client process detected (PID: $($existingProcess.Id))" "Yellow"
    $kill = Read-Host "  Kill existing process and restart? (y/N)"
    if ($kill -eq "y" -or $kill -eq "Y") {
        Stop-Process -Name "frpc" -Force
        Start-Sleep -Seconds 2
        Write-ColorOutput "  [OK] Existing process terminated" "Green"
    } else {
        Write-ColorOutput "  Cancelled" "Yellow"
        exit 0
    }
}

# Start FRP client
Write-ColorOutput "`n[4/4] Starting FRP client..." "Cyan"
Write-ColorOutput "  Starting..." "Yellow"

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$FRP_DIR'; Write-Host 'FRP Client Running (INI Format)...' -ForegroundColor Cyan; .\frpc.exe -c frpc.ini"

Start-Sleep -Seconds 3

$process = Get-Process -Name "frpc" -ErrorAction SilentlyContinue
if ($process) {
    Write-ColorOutput "  [OK] FRP client started (PID: $($process.Id))" "Green"
    
    Write-ColorOutput "`n========================================" "Cyan"
    Write-ColorOutput " FRP Tunnel Information" "Cyan"
    Write-ColorOutput "========================================" "Cyan"
    
    Write-ColorOutput "`nLocal Service -> Remote Access:" "White"
    Write-ColorOutput "  Frontend: http://localhost:$FRONTEND_PORT -> http://${serverAddr}:$FRONTEND_PORT" "Gray"
    Write-ColorOutput "  Backend:  http://localhost:$BACKEND_PORT -> http://${serverAddr}:$BACKEND_PORT" "Gray"
    
    Write-ColorOutput "`nDomain Access (requires Nginx):" "White"
    Write-ColorOutput "  Frontend: http://web.gymbro.cloud" "Gray"
    Write-ColorOutput "  Backend:  http://api.gymbro.cloud" "Gray"
    
    Write-ColorOutput "`nManagement Commands:" "White"
    Write-ColorOutput "  View logs: Check FRP client window" "Gray"
    Write-ColorOutput "  Stop service: Close FRP client window or run Stop-Process -Name frpc" "Gray"
    Write-ColorOutput "  Restart: Run this script again" "Gray"
    
    Write-ColorOutput "`n========================================`n" "Cyan"
    Write-ColorOutput "FRP client started successfully!" "Green"
    Write-ColorOutput "`nNote: Using INI format as workaround for FRP v0.61.1 TOML bug" "Yellow"
    Write-ColorOutput "See docs/FRP_TROUBLESHOOTING.md for details`n" "Yellow"
} else {
    Write-ColorOutput "  [ERROR] FRP client failed to start" "Red"
    Write-ColorOutput "  Check FRP client window for error messages" "Yellow"
    exit 1
}

