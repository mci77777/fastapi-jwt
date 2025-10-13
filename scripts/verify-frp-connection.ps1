# FRP Connection Verification Script
# Purpose: Verify FRP tunnel is working properly
# Author: GymBro Team
# Date: 2025-01-13

$ErrorActionPreference = 'Stop'

$ENV_FILE = Join-Path $PSScriptRoot "..\.env"
$FRONTEND_PORT = 3101
$BACKEND_PORT = 9999

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

function Test-HttpEndpoint {
    param([string]$Url, [string]$Name, [int]$TimeoutSeconds = 5)
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -UseBasicParsing -TimeoutSec $TimeoutSeconds -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-ColorOutput "  [OK] $Name - Connected (HTTP $($response.StatusCode))" "Green"
            return $true
        } else {
            Write-ColorOutput "  [WARN] $Name - Unexpected response (HTTP $($response.StatusCode))" "Yellow"
            return $false
        }
    } catch {
        Write-ColorOutput "  [ERROR] $Name - Connection failed: $($_.Exception.Message)" "Red"
        return $false
    }
}

function Test-TcpPort {
    param([string]$Host, [int]$Port, [string]$Name)
    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect($Host, $Port)
        $connection.Close()
        Write-ColorOutput "  [OK] $Name - Port reachable (${Host}:${Port})" "Green"
        return $true
    } catch {
        Write-ColorOutput "  [ERROR] $Name - Port unreachable (${Host}:${Port})" "Red"
        return $false
    }
}

function Test-FRPProcess {
    $process = Get-Process -Name "frpc" -ErrorAction SilentlyContinue
    if ($process) {
        Write-ColorOutput "  [OK] FRP client process running (PID: $($process.Id))" "Green"
        return $true
    } else {
        Write-ColorOutput "  [ERROR] FRP client process not running" "Red"
        return $false
    }
}

# Main Process
Write-ColorOutput "`n========================================" "Cyan"
Write-ColorOutput " FRP Connection Verification Script" "Cyan"
Write-ColorOutput "========================================`n" "Cyan"

$envVars = Read-EnvFile -Path $ENV_FILE
$serverAddr = $envVars["FRP_BASE_IP"]

if (-not $serverAddr) {
    Write-ColorOutput "ERROR: Missing FRP_BASE_IP in .env" "Red"
    exit 1
}

Write-ColorOutput "Server address: $serverAddr`n" "Gray"

$totalTests = 0
$passedTests = 0

# Test 1: FRP Process Check
Write-ColorOutput "[Test 1/6] Checking FRP client process" "Cyan"
$totalTests++
if (Test-FRPProcess) { $passedTests++ } else {
    Write-ColorOutput "`n  Hint: Run .\scripts\start-frp-client.ps1 first`n" "Yellow"
}

# Test 2: Local Services Check
Write-ColorOutput "`n[Test 2/6] Checking local services" "Cyan"
$totalTests++
if (Test-HttpEndpoint -Url "http://localhost:$BACKEND_PORT/api/v1/healthz" -Name "Local backend service") { $passedTests++ }
$totalTests++
if (Test-TcpPort -Host "127.0.0.1" -Port $FRONTEND_PORT -Name "Local frontend service") { $passedTests++ }

# Test 3: Remote TCP Ports Check
Write-ColorOutput "`n[Test 3/6] Checking remote TCP port mapping" "Cyan"
$totalTests++
if (Test-TcpPort -Host $serverAddr -Port $BACKEND_PORT -Name "Remote backend port") { $passedTests++ }
$totalTests++
if (Test-TcpPort -Host $serverAddr -Port $FRONTEND_PORT -Name "Remote frontend port") { $passedTests++ }

# Test 4: Remote HTTP Access Check
Write-ColorOutput "`n[Test 4/6] Checking remote HTTP access" "Cyan"
$totalTests++
if (Test-HttpEndpoint -Url "http://${serverAddr}:$BACKEND_PORT/api/v1/healthz" -Name "Remote backend API") { $passedTests++ }

# Test 5: Domain Access Check (Optional)
Write-ColorOutput "`n[Test 5/6] Checking domain access (requires Nginx)" "Cyan"
$totalTests++
$domainTest = Test-HttpEndpoint -Url "http://api.gymbro.cloud/api/v1/healthz" -Name "Domain access (api.gymbro.cloud)" -TimeoutSeconds 10
if ($domainTest) { $passedTests++ } else {
    Write-ColorOutput "  Hint: Domain access may fail if Nginx is not configured or DNS not resolved" "Yellow"
}

# Test 6: FRP Server Connection Check
Write-ColorOutput "`n[Test 6/6] Checking FRP server connection" "Cyan"
$totalTests++
if (Test-TcpPort -Host $serverAddr -Port 7000 -Name "FRP server") { $passedTests++ }

# Test Summary
Write-ColorOutput "`n========================================" "Cyan"
Write-ColorOutput " Test Summary" "Cyan"
Write-ColorOutput "========================================" "Cyan"

$failedTests = $totalTests - $passedTests
$successRate = [math]::Round(($passedTests / $totalTests) * 100, 2)

Write-ColorOutput "`nTotal tests: $totalTests" "White"
Write-ColorOutput "Passed: $passedTests [OK]" "Green"
Write-ColorOutput "Failed: $failedTests [ERROR]" "Red"
Write-ColorOutput "Success rate: $successRate%`n" "White"

if ($failedTests -eq 0) {
    Write-ColorOutput "All tests passed! FRP tunnel is working properly" "Green"
    Write-ColorOutput "`nRemote access addresses:" "White"
    Write-ColorOutput "  Frontend: http://${serverAddr}:$FRONTEND_PORT" "Gray"
    Write-ColorOutput "  Backend:  http://${serverAddr}:$BACKEND_PORT" "Gray"
    Write-ColorOutput "  Domain:   http://api.gymbro.cloud (requires Nginx)`n" "Gray"
    exit 0
} else {
    Write-ColorOutput "Some tests failed, please check:" "Yellow"
    Write-ColorOutput "`nTroubleshooting suggestions:" "White"
    Write-ColorOutput "  1. Ensure local services are running: .\start-dev.ps1" "Gray"
    Write-ColorOutput "  2. Ensure FRP client is running: .\scripts\start-frp-client.ps1" "Gray"
    Write-ColorOutput "  3. Check FRP_BASE_IP and FRP_TOKEN in .env" "Gray"
    Write-ColorOutput "  4. Check remote server firewall (ports 3101, 9999, 7000)" "Gray"
    Write-ColorOutput "  5. Check FRP client window for log output" "Gray"
    Write-ColorOutput "`nDocumentation: docs/FRP_CLIENT_GUIDE.md`n" "Cyan"
    exit 1
}
