# 自动切换 UTF-8 并启动 Headless Chrome DevTools
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
$env:LANG = 'zh_CN.UTF-8'
$env:LC_ALL = 'zh_CN.UTF-8'
$arguments = @('--headless=new', '--remote-debugging-port=9222', 'about:blank')
$proc = Start-Process -FilePath 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ArgumentList $arguments -PassThru
$uri = 'http://127.0.0.1:9222/json/version'
Write-Host 'Chrome DevTools 启动中，端口 9222...'
Start-Sleep -Seconds 3
try {
    $resp = Invoke-WebRequest -Uri $uri
    Write-Host 'DevTools 元信息：'
    $resp.Content
    Write-Host 'WebSocket 调试地址：'
    ($resp.Content | ConvertFrom-Json).webSocketDebuggerUrl
    Write-Host '按 Ctrl+C 停止并回收浏览器进程。'
    Wait-Process -Id $proc.Id
} finally {
    if ($proc -and -not $proc.HasExited) {
        Stop-Process -Id $proc.Id -Force
    }
}
