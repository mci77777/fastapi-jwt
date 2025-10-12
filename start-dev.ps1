# One-Click Dev Environment Startup
# Auto start frontend (3101) and backend (9999)
# Auto-close and restart if ports are occupied

$ErrorActionPreference = 'Stop'
$BACKEND_PORT = 9999
$FRONTEND_PORT = 3101

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Vue FastAPI Admin - Dev Environment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Function to check and kill port
function Clear-Port {
    param($Port, $Name)
    
    $connections = netstat -ano | Select-String ":$Port " | Select-String "LISTENING"
    
    if ($connections) {
        Write-Host "[$Name] Port $Port occupied, closing..." -ForegroundColor Yellow
        
        $processIds = @()
        foreach ($line in $connections) {
            if ($line -match '\s+(\d+)\s*$') {
                $pid = $matches[1]
                if ($pid -notin $processIds) { $processIds += $pid }
            }
        }
        
        foreach ($pid in $processIds) {
            try {
                Stop-Process -Id $pid -Force -ErrorAction Stop
                Write-Host "[$Name] Closed PID: $pid" -ForegroundColor Green
            } catch {
                Write-Host "[$Name] Failed to close PID: $pid" -ForegroundColor Red
            }
        }
        Start-Sleep -Milliseconds 500
    } else {
        Write-Host "[$Name] Port $Port available" -ForegroundColor Green
    }
}

# Check ports
Clear-Port -Port $BACKEND_PORT -Name "Backend"
Clear-Port -Port $FRONTEND_PORT -Name "Frontend"

Write-Host ""
Write-Host "Starting services..." -ForegroundColor Cyan
Write-Host "  Backend:  http://localhost:$BACKEND_PORT" -ForegroundColor White
Write-Host "  Frontend: http://localhost:$FRONTEND_PORT" -ForegroundColor White
Write-Host ""

# Start backend
Write-Host "Starting backend..." -ForegroundColor Blue
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; python run.py"
Start-Sleep -Seconds 2

# Start frontend  
Write-Host "Starting frontend..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\web'; npm run dev"

Write-Host ""
Write-Host "Done! Wait 10 seconds then visit:" -ForegroundColor Cyan
Write-Host "  http://localhost:$FRONTEND_PORT" -ForegroundColor Green
Write-Host ""
