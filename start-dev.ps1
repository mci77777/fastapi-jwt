# One-Click Dev Environment Startup
# Auto start frontend (3101) and backend (9999)
# Auto-close and restart if ports are occupied
# Clears Python cache before starting backend

$ErrorActionPreference = 'Stop'
$BACKEND_PORT = 9999
$FRONTEND_PORT = 3101

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

# Function to wait for port to be listening
function Wait-PortListening {
    param($Port, $Name, $MaxRetries = 30)

    Write-Host "[$Name] Waiting for port $Port to be ready..." -ForegroundColor Yellow

    for ($i = 1; $i -le $MaxRetries; $i++) {
        $connections = netstat -ano | Select-String ":$Port " | Select-String "LISTENING"

        if ($connections) {
            Write-Host "[$Name] Service is ready on port $Port! (attempt $i/$MaxRetries)" -ForegroundColor Green
            return $true
        }

        if ($i % 5 -eq 0) {
            Write-Host "[$Name] Still waiting... (attempt $i/$MaxRetries)" -ForegroundColor DarkYellow
        }

        if ($i -eq $MaxRetries) {
            Write-Host "[$Name] Service failed to start (timeout after $MaxRetries seconds)" -ForegroundColor Red
            Write-Host "[$Name] Check the service terminal window for error messages" -ForegroundColor Yellow
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

# Build backend startup command
$backendCommand = "Write-Host 'Starting backend server...' -ForegroundColor Cyan; python run.py"
Write-Host "[Backend] Command: $backendCommand" -ForegroundColor DarkGray

try {
    # Start backend in new PowerShell window with proper working directory
    $backendProcess = Start-Process powershell `
        -ArgumentList "-NoExit -Command `"$backendCommand`"" `
        -WorkingDirectory $PSScriptRoot `
        -PassThru `
        -ErrorAction Stop

    Write-Host "[Backend] Process started (PID: $($backendProcess.Id))" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "[Backend] Failed to start process!" -ForegroundColor Red
    Write-Host "  Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Ensure Python is installed and in PATH" -ForegroundColor Yellow
    Write-Host "  2. Try running manually: python run.py" -ForegroundColor Yellow
    Write-Host "  3. Check if run.py exists in: $PSScriptRoot" -ForegroundColor Yellow
    exit 1
}

# Wait for backend to be ready (check port instead of HTTP)
if (-not (Wait-PortListening -Port $BACKEND_PORT -Name "Backend" -MaxRetries 30)) {
    Write-Host ""
    Write-Host "Backend failed to start within 30 seconds." -ForegroundColor Red
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

# Build frontend startup command
$frontendCommand = "Write-Host 'Starting frontend server...' -ForegroundColor Cyan; pnpm dev"
$frontendWorkDir = Join-Path $PSScriptRoot "web"
Write-Host "[Frontend] Command: $frontendCommand" -ForegroundColor DarkGray
Write-Host "[Frontend] Working Directory: $frontendWorkDir" -ForegroundColor DarkGray

# Verify frontend directory exists
if (-not (Test-Path $frontendWorkDir)) {
    Write-Host ""
    Write-Host "[Frontend] Directory not found: $frontendWorkDir" -ForegroundColor Red
    Write-Host "  Please ensure the 'web' directory exists in the project root" -ForegroundColor Yellow
    exit 1
}

try {
    # Start frontend in new PowerShell window with proper working directory
    $frontendProcess = Start-Process powershell `
        -ArgumentList "-NoExit -Command `"$frontendCommand`"" `
        -WorkingDirectory $frontendWorkDir `
        -PassThru `
        -ErrorAction Stop

    Write-Host "[Frontend] Process started (PID: $($frontendProcess.Id))" -ForegroundColor Green
} catch {
    Write-Host ""
    Write-Host "[Frontend] Failed to start process!" -ForegroundColor Red
    Write-Host "  Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Ensure pnpm is installed: npm install -g pnpm" -ForegroundColor Yellow
    Write-Host "  2. Install dependencies: cd web && pnpm install" -ForegroundColor Yellow
    Write-Host "  3. Try running manually: cd web && pnpm dev" -ForegroundColor Yellow
    exit 1
}

# Wait for frontend to be ready (check port instead of HTTP)
if (-not (Wait-PortListening -Port $FRONTEND_PORT -Name "Frontend" -MaxRetries 30)) {
    Write-Host ""
    Write-Host "Frontend failed to start within 30 seconds." -ForegroundColor Red
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
