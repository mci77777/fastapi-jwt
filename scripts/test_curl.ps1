# 测试 Supabase 状态端点（PowerShell）
$url = "http://localhost:9999/api/v1/llm/status/supabase"

Write-Host "测试 URL: $url" -ForegroundColor Cyan
Write-Host "不携带认证 Token（测试公开访问）" -ForegroundColor Yellow
Write-Host ""

try {
    $response = Invoke-WebRequest -Uri $url -Method GET -UseBasicParsing
    Write-Host "状态码: $($response.StatusCode)" -ForegroundColor Green
    Write-Host "响应体:" -ForegroundColor Green
    Write-Host $response.Content
} catch {
    Write-Host "状态码: $($_.Exception.Response.StatusCode.value__)" -ForegroundColor Red
    Write-Host "响应体:" -ForegroundColor Red
    $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
    $responseBody = $reader.ReadToEnd()
    Write-Host $responseBody
}

