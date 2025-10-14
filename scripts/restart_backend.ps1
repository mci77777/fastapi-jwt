# 重启后端服务
Write-Host "正在重启后端服务..." -ForegroundColor Cyan

# 1. 杀死占用 9999 端口的进程
$port = 9999
$process = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique

if ($process) {
    Write-Host "发现占用端口 $port 的进程: PID $process" -ForegroundColor Yellow
    Stop-Process -Id $process -Force
    Write-Host "已杀死进程 PID $process" -ForegroundColor Green
    Start-Sleep -Seconds 2
} else {
    Write-Host "端口 $port 未被占用" -ForegroundColor Yellow
}

# 2. 启动新的后端服务
Write-Host "正在启动后端服务..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd D:\GymBro\vue-fastapi-admin; python run.py"

Write-Host "后端服务已启动！" -ForegroundColor Green
Write-Host "请等待 5-10 秒让服务完全启动..." -ForegroundColor Yellow

