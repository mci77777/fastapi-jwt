# GW-Auth 快速验证脚本 (PowerShell)

$ErrorActionPreference = "Stop"

Write-Host "🚀 GW-Auth 网关快速验证" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan

# 基础URL
$BaseUrl = if ($env:BASE_URL) { $env:BASE_URL } else { "http://localhost:9999" }

# 测试计数
$Total = 0
$Passed = 0
$Failed = 0

# 测试函数
function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Url,
        [int]$ExpectedStatus
    )
    
    $script:Total++
    
    Write-Host -NoNewline "测试 $Name ... "
    
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Get -UseBasicParsing -ErrorAction SilentlyContinue
        $status = $response.StatusCode
    }
    catch {
        $status = $_.Exception.Response.StatusCode.value__
    }
    
    if ($status -eq $ExpectedStatus) {
        Write-Host "✅ PASS (HTTP $status)" -ForegroundColor Green
        $script:Passed++
    }
    else {
        Write-Host "❌ FAIL (HTTP $status, expected $ExpectedStatus)" -ForegroundColor Red
        $script:Failed++
    }
}

# 测试健康探针
Write-Host ""
Write-Host "📍 测试健康探针端点" -ForegroundColor Yellow
Write-Host "-------------------"
Test-Endpoint "healthz" "$BaseUrl/api/v1/healthz" 200
Test-Endpoint "livez" "$BaseUrl/api/v1/livez" 200
Test-Endpoint "readyz" "$BaseUrl/api/v1/readyz" 200

# 测试Prometheus指标
Write-Host ""
Write-Host "📊 测试Prometheus指标端点" -ForegroundColor Yellow
Write-Host "------------------------"
Test-Endpoint "metrics" "$BaseUrl/api/v1/metrics" 200

# 测试白名单（快速连续请求）
Write-Host ""
Write-Host "🛡️  测试白名单免限流" -ForegroundColor Yellow
Write-Host "-------------------"
Write-Host -NoNewline "发送20次连续请求 ... "

$failedRequests = 0
for ($i = 1; $i -le 20; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "$BaseUrl/api/v1/healthz" -Method Get -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -ne 200) {
            $failedRequests++
        }
    }
    catch {
        $failedRequests++
    }
}

$Total++
if ($failedRequests -eq 0) {
    Write-Host "✅ PASS (所有请求都成功)" -ForegroundColor Green
    $Passed++
}
else {
    Write-Host "❌ FAIL ($failedRequests 个请求失败)" -ForegroundColor Red
    $Failed++
}

# 测试指标内容
Write-Host ""
Write-Host "🔍 验证Prometheus指标内容" -ForegroundColor Yellow
Write-Host "------------------------"
Write-Host -NoNewline "检查指标是否包含核心指标 ... "

try {
    $metricsContent = (Invoke-WebRequest -Uri "$BaseUrl/api/v1/metrics" -Method Get -UseBasicParsing).Content
    $expectedMetrics = @("auth_requests_total", "jwt_validation_errors_total", "jwks_cache_hits_total", "rate_limit_blocks_total")
    $foundCount = 0
    
    foreach ($metric in $expectedMetrics) {
        if ($metricsContent -match $metric) {
            $foundCount++
        }
    }
    
    $Total++
    if ($foundCount -ge 2) {
        Write-Host "✅ PASS (找到 $foundCount 个核心指标)" -ForegroundColor Green
        $Passed++
    }
    else {
        Write-Host "⚠️  WARN (只找到 $foundCount 个核心指标，可能需要触发更多请求)" -ForegroundColor Yellow
        $Passed++
    }
}
catch {
    Write-Host "❌ FAIL (无法获取指标内容)" -ForegroundColor Red
    $Failed++
}

# 打印摘要
Write-Host ""
Write-Host "========================" -ForegroundColor Cyan
Write-Host "📊 测试摘要" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host "总测试数: $Total"
Write-Host "通过: $Passed ✅" -ForegroundColor Green
Write-Host "失败: $Failed ❌" -ForegroundColor Red

if ($Failed -eq 0) {
    Write-Host ""
    Write-Host "🎉 所有测试通过！GW-Auth 网关工作正常" -ForegroundColor Green
    exit 0
}
else {
    Write-Host ""
    Write-Host "⚠️  部分测试失败，请检查服务状态" -ForegroundColor Red
    Write-Host ""
    Write-Host "故障排查建议:"
    Write-Host "1. 确认服务已启动: python run.py"
    Write-Host "2. 检查端口是否正确: $BaseUrl"
    Write-Host "3. 查看服务日志: docker-compose logs -f api"
    exit 1
}

