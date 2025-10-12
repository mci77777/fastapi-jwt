# One-Click Dev Environment Startup
# Auto start frontend (3101) and backend (9999)
# Auto-close and restart if ports are occupied
# Clears Python cache before starting backend

$ErrorActionPreference = 'Stop'
$BACKEND_PORT = 9999
$FRONTEND_PORT = 3101
$BACKEND_HEALTH_URL = "http://localhost:$BACKEND_PORT/api/v1/healthz"
$FRONTEND_URL = "http://localhost:$FRONTEND_PORT"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Vue FastAPI Admin - Dev Environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Function to clear Python cache
function Clear-PythonCache {
    Write-Host "[Cache] Clearing Python cache..." -ForegroundColor Yellow

    $cacheCount = 0

    # Remove __pycache__ directories
    Get-ChildItem -Path $PSScriptRoot -Include "__pycache__" -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        $cacheCount++
    }

    # Remove .pyc files
    Get-ChildItem -Path $PSScriptRoot -Include "*.pyc" -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item $_.FullName -Force -ErrorAction SilentlyContinue
        $cacheCount++
    }

    if ($cacheCount -gt 0) {
        Write-Host "[Cache] Cleared $cacheCount cache items" -ForegroundColor Green
    } else {
        Write-Host "[Cache] No cache to clear" -ForegroundColor Green
    }
}

# Function to check and kill port
function Clear-Port {
    param($Port, $Name)

    $connections = netstat -ano | Select-String ":$Port " | Select-String "LISTENING"

    if ($connections) {
        Write-Host "[$Name] Port $Port occupied, closing..." -ForegroundColor Yellow

        $processIds = @()
        foreach ($line in $connections) {
            if ($line -match '\s+(\d+)\s*$') {
                $processId = $matches[1]
                if ($processId -notin $processIds) { $processIds += $processId }
            }
        }

        foreach ($processId in $processIds) {
            try {
                Stop-Process -Id $processId -Force -ErrorAction Stop
                Write-Host "[$Name] Closed PID: $processId" -ForegroundColor Green
            } catch {
                Write-Host "[$Name] Failed to close PID: $processId" -ForegroundColor Red
                return $false
            }
        }
        Start-Sleep -Milliseconds 500
    } else {
        Write-Host "[$Name] Port $Port available" -ForegroundColor Green
    }
    return $true
}

# Function to wait for service health
function Wait-ServiceHealth {
    param($Url, $Name, $MaxRetries = 30)

    Write-Host "[$Name] Waiting for service to be ready..." -ForegroundColor Yellow

    for ($i = 1; $i -le $MaxRetries; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Host "[$Name] Service is ready! (attempt $i/$MaxRetries)" -ForegroundColor Green
                return $true
            }
        } catch {
            # Service not ready yet, continue waiting
            if ($i % 5 -eq 0) {
                Write-Host "[$Name] Still waiting... (attempt $i/$MaxRetries)" -ForegroundColor DarkYellow
            }
        }

        if ($i -eq $MaxRetries) {
            Write-Host "[$Name] Service failed to start (timeout after $MaxRetries seconds)" -ForegroundColor Red
            Write-Host "[$Name] Last error: $($_.Exception.Message)" -ForegroundColor Red
            return $false
        }

        Start-Sleep -Seconds 1
    }

    return $false
}

# Function to check dependencies
function Test-Dependencies {
    # Check Python
    try {
        $pythonVersion = python --version 2>&1
        Write-Host "[Deps] Python: $pythonVersion" -ForegroundColor Green
    } catch {
        Write-Host "[Deps] Python not found! Please install Python 3.11+" -ForegroundColor Red
        return $false
    }

    # Check pnpm
    try {
        $pnpmVersion = pnpm --version 2>&1
        Write-Host "[Deps] pnpm: v$pnpmVersion" -ForegroundColor Green
    } catch {
        Write-Host "[Deps] pnpm not found! Install with: npm install -g pnpm" -ForegroundColor Red
        return $false
    }

    return $true
}

# Step 1: Check dependencies
Write-Host ""
Write-Host "[Step 1/5] Checking dependencies..." -ForegroundColor Cyan
if (-not (Test-Dependencies)) {
    Write-Host ""
    Write-Host "Dependency check failed. Please install missing dependencies." -ForegroundColor Red
    exit 1
}

# Step 2: Clear Python cache
Write-Host ""
Write-Host "[Step 2/5] Clearing Python cache..." -ForegroundColor Cyan
Clear-PythonCache

# Step 3: Check and clear ports
Write-Host ""
Write-Host "[Step 3/5] Checking ports..." -ForegroundColor Cyan
$backendPortCleared = Clear-Port -Port $BACKEND_PORT -Name "Backend"
$frontendPortCleared = Clear-Port -Port $FRONTEND_PORT -Name "Frontend"

if (-not $backendPortCleared -or -not $frontendPortCleared) {
    Write-Host ""
    Write-Host "Failed to clear ports. Please manually close processes using ports $BACKEND_PORT and $FRONTEND_PORT" -ForegroundColor Red
    exit 1
}

# Step 4: Start backend
Write-Host ""
Write-Host "[Step 4/5] Starting backend..." -ForegroundColor Cyan
Write-Host "  URL: http://localhost:$BACKEND_PORT" -ForegroundColor White
Write-Host "  API Docs: http://localhost:$BACKEND_PORT/docs" -ForegroundColor White

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; Write-Host 'Starting backend server...' -ForegroundColor Cyan; python run.py"

# Wait for backend to be ready (increased timeout for first start)
if (-not (Wait-ServiceHealth -Url $BACKEND_HEALTH_URL -Name "Backend" -MaxRetries 60)) {
    Write-Host ""
    Write-Host "Backend failed to start within 60 seconds." -ForegroundColor Red
    Write-Host "Possible reasons:" -ForegroundColor Yellow
    Write-Host "  1. Check the backend PowerShell window for error messages" -ForegroundColor Yellow
    Write-Host "  2. Database initialization may be taking longer than expected" -ForegroundColor Yellow
    Write-Host "  3. Port 9999 may still be in use by another process" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Try manually starting backend with: python run.py" -ForegroundColor Cyan
    exit 1
}

# Step 5: Start frontend
Write-Host ""
Write-Host "[Step 5/5] Starting frontend..." -ForegroundColor Cyan
Write-Host "  URL: http://localhost:$FRONTEND_PORT" -ForegroundColor White

Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\web'; Write-Host 'Starting frontend server...' -ForegroundColor Cyan; pnpm dev"

# Wait for frontend to be ready (increased timeout for dependency installation)
if (-not (Wait-ServiceHealth -Url $FRONTEND_URL -Name "Frontend" -MaxRetries 60)) {
    Write-Host ""
    Write-Host "Frontend failed to start within 60 seconds." -ForegroundColor Red
    Write-Host "Possible reasons:" -ForegroundColor Yellow
    Write-Host "  1. Check the frontend PowerShell window for error messages" -ForegroundColor Yellow
    Write-Host "  2. First run may take longer (installing node_modules)" -ForegroundColor Yellow
    Write-Host "  3. Port 3101 may still be in use by another process" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Try manually starting frontend with: cd web && pnpm dev" -ForegroundColor Cyan
    exit 1
}

# Success!
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Development Environment Ready!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Access URLs:" -ForegroundColor Cyan
Write-Host "  Frontend:  http://localhost:$FRONTEND_PORT" -ForegroundColor Green
Write-Host "  Backend:   http://localhost:$BACKEND_PORT" -ForegroundColor Green
Write-Host "  API Docs:  http://localhost:$BACKEND_PORT/docs" -ForegroundColor Green
Write-Host ""
Write-Host "To stop: Close the PowerShell windows or press Ctrl+C" -ForegroundColor Yellow
Write-Host ""
