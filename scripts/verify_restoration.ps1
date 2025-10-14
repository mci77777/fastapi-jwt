# 仓库恢复验证脚本
# 用途: 验证从旧仓库恢复后的功能完整性

param(
    [switch]$Full  # 完整验证（包括启动服务）
)

Write-Host "`n╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          🔍 仓库恢复验证脚本                                  ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

$ErrorActionPreference = "Continue"
$errorsListList = @()
$warningsListList = @()
$successListList = @()

# ============ 1. 检查关键文件是否存在 ============
Write-Host "📁 检查关键文件..." -ForegroundColor Yellow

$criticalFiles = @(
    ".env",
    "app/auth/dependencies.py",
    "app/api/v1/base.py",
    ".pre-commit-config.yaml",
    "web/.env.development",
    "web/.env.production"
)

foreach ($file in $criticalFiles) {
    if (Test-Path $file) {
        Write-Host "   ✅ $file" -ForegroundColor Green
        $successList += "文件存在: $file"
    } else {
        Write-Host "   ❌ $file (缺失)" -ForegroundColor Red
        $errorsList += "文件缺失: $file"
    }
}

# ============ 2. 检查 .env 配置完整性 ============
Write-Host "`n🔧 检查 .env 配置..." -ForegroundColor Yellow

if (Test-Path ".env") {
    $envContent = Get-Content ".env" -Raw

    $requiredEnvVars = @(
        "WEB_URL",
        "API_URL",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_JWKS_URL",
        "FORCE_HTTPS",
        "CORS_ALLOW_ORIGINS"
    )

    foreach ($var in $requiredEnvVars) {
        if ($envContent -match "$var=") {
            Write-Host "   ✅ $var" -ForegroundColor Green
            $successList += "环境变量存在: $var"
        } else {
            Write-Host "   ❌ $var (缺失)" -ForegroundColor Red
            $errorsList += "环境变量缺失: $var"
        }
    }

    # 检查云端 URL
    if ($envContent -match "web\.gymbro\.cloud") {
        Write-Host "   ✅ 云端 URL 已配置 (web.gymbro.cloud)" -ForegroundColor Green
        $successList += "云端 Web URL 已配置"
    } else {
        Write-Host "   ⚠️  未检测到云端 URL" -ForegroundColor Yellow
        $warningsList += "云端 Web URL 未配置"
    }

    if ($envContent -match "api\.gymbro\.cloud") {
        Write-Host "   ✅ 云端 API URL 已配置 (api.gymbro.cloud)" -ForegroundColor Green
        $successList += "云端 API URL 已配置"
    } else {
        Write-Host "   ⚠️  未检测到云端 API URL" -ForegroundColor Yellow
        $warningsList += "云端 API URL 未配置"
    }
} else {
    Write-Host "   ❌ .env 文件不存在" -ForegroundColor Red
    $errorsList += ".env 文件不存在"
}

# ============ 3. 检查认证逻辑恢复 ============
Write-Host "`n🔐 检查认证逻辑..." -ForegroundColor Yellow

if (Test-Path "app/auth/dependencies.py") {
    $authContent = Get-Content "app/auth/dependencies.py" -Raw

    if ($authContent -match "auth_requests_total") {
        Write-Host "   ✅ Prometheus 指标记录已恢复" -ForegroundColor Green
        $successList += "Prometheus 指标记录已恢复"
    } else {
        Write-Host "   ❌ 缺少 Prometheus 指标记录" -ForegroundColor Red
        $errorsList += "认证文件缺少 Prometheus 指标"
    }

    if ($authContent -match "try:.*user = verifier\.verify_token" -and $authContent -match "except HTTPException:") {
        Write-Host "   ✅ Try-catch 错误处理已恢复" -ForegroundColor Green
        $successList += "Try-catch 错误处理已恢复"
    } else {
        Write-Host "   ❌ 缺少 Try-catch 错误处理" -ForegroundColor Red
        $errorsList += "认证文件缺少错误处理"
    }

    if ($authContent -match "_record_user_activity") {
        Write-Host "   ✅ 用户活跃度记录已恢复" -ForegroundColor Green
        $successList += "用户活跃度记录已恢复"
    } else {
        Write-Host "   ❌ 缺少用户活跃度记录" -ForegroundColor Red
        $errorsList += "认证文件缺少活跃度记录"
    }
}

# ============ 4. 检查菜单配置 ============
Write-Host "`n📋 检查菜单配置..." -ForegroundColor Yellow

if (Test-Path "app/api/v1/base.py") {
    $baseContent = Get-Content "app/api/v1/base.py" -Raw

    # 检查菜单顺序
    if ($baseContent -match '"name": "Dashboard".*"order": 0' -and
        $baseContent -match '"name": "系统管理".*"order": 5' -and
        $baseContent -match '"name": "AI模型管理".*"order": 10') {
        Write-Host "   ✅ 菜单顺序正确 (Dashboard:0, 系统管理:5, AI模型:10)" -ForegroundColor Green
        $successList += "菜单顺序正确"
    } else {
        Write-Host "   ❌ 菜单顺序不正确" -ForegroundColor Red
        $errorsList += "菜单顺序错误"
    }

    # 检查子菜单
    if ($baseContent -match '"name": "AI 配置"' -and $baseContent -match '"name": "Prompt 管理"') {
        Write-Host "   ✅ 系统管理子菜单完整" -ForegroundColor Green
        $successList += "系统管理子菜单完整"
    } else {
        Write-Host "   ❌ 系统管理子菜单不完整" -ForegroundColor Red
        $errorsList += "系统管理子菜单缺失"
    }
}

# ============ 5. 检查 Pre-commit 配置 ============
Write-Host "`n⚙️  检查 Pre-commit 配置..." -ForegroundColor Yellow

if (Test-Path ".pre-commit-config.yaml") {
    $precommitContent = Get-Content ".pre-commit-config.yaml" -Raw

    if ($precommitContent -match "language_version: python3\.12") {
        Write-Host "   ✅ Python 版本已更新为 3.12" -ForegroundColor Green
        $successList += "Pre-commit Python 版本正确"
    } elseif ($precommitContent -match "language_version: python3\.11") {
        Write-Host "   ❌ 仍在使用 Python 3.11（系统不支持）" -ForegroundColor Red
        $errorsList += "Pre-commit Python 版本错误"
    }
}

# ============ 6. 检查 Git 状态 ============
Write-Host "`n🔄 检查 Git 状态..." -ForegroundColor Yellow

$gitStatus = git status --porcelain
if ($gitStatus) {
    Write-Host "   ⚠️  工作区有未提交的更改" -ForegroundColor Yellow
    Write-Host "      变更文件数: $(($gitStatus | Measure-Object).Count)" -ForegroundColor Gray
    $warningsList += "工作区有未提交的更改"
} else {
    Write-Host "   ✅ 工作区干净" -ForegroundColor Green
    $successList += "工作区干净"
}

# 检查远程仓库
$remotes = git remote -v
if ($remotes -match "old-origin") {
    Write-Host "   ✅ old-origin 远程仓库存在（用于恢复）" -ForegroundColor Green
    $successList += "old-origin 远程仓库已配置"
} else {
    Write-Host "   ⚠️  未找到 old-origin 远程仓库" -ForegroundColor Yellow
    $warningsList += "old-origin 远程仓库未配置"
}

if ($remotes -match "origin.*fastapi-jwt") {
    Write-Host "   ✅ 新仓库 fastapi-jwt 已配置" -ForegroundColor Green
    $successList += "新仓库已配置"
} else {
    Write-Host "   ❌ 未找到新仓库配置" -ForegroundColor Red
    $errorsList += "新仓库未配置"
}

# ============ 7. 完整验证（可选）============
if ($Full) {
    Write-Host "`n🚀 完整验证 - 启动服务..." -ForegroundColor Yellow

    # 检查端口占用
    $port9999 = Get-NetTCPConnection -LocalPort 9999 -ErrorAction SilentlyContinue
    if ($port9999) {
        Write-Host "   ⚠️  端口 9999 已被占用（后端可能正在运行）" -ForegroundColor Yellow
        $warningsList += "端口 9999 已被占用"
    } else {
        Write-Host "   ✅ 端口 9999 空闲" -ForegroundColor Green
    }

    $port3101 = Get-NetTCPConnection -LocalPort 3101 -ErrorAction SilentlyContinue
    if ($port3101) {
        Write-Host "   ⚠️  端口 3101 已被占用（前端可能正在运行）" -ForegroundColor Yellow
        $warningsList += "端口 3101 已被占用"
    } else {
        Write-Host "   ✅ 端口 3101 空闲" -ForegroundColor Green
    }

    # 检查后端健康（如果正在运行）
    try {
        $healthCheck = Invoke-RestMethod -Uri "http://localhost:9999/api/v1/healthz" -Method Get -TimeoutSec 2 -ErrorAction Stop
        Write-Host "   ✅ 后端健康检查通过" -ForegroundColor Green
        Write-Host "      响应: $($healthCheck | ConvertTo-Json -Compress)" -ForegroundColor Gray
        $successList += "后端健康检查通过"
    } catch {
        Write-Host "   ⚠️  后端未运行或健康检查失败" -ForegroundColor Yellow
        $warningsList += "后端未运行"
    }

    # 检查 Prometheus 指标
    try {
        $metrics = Invoke-RestMethod -Uri "http://localhost:9999/api/v1/metrics" -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($metrics -match "auth_requests_total") {
            Write-Host "   ✅ Prometheus 指标端点正常（包含 auth_requests_total）" -ForegroundColor Green
            $successList += "Prometheus 指标端点正常"
        } else {
            Write-Host "   ⚠️  Prometheus 指标中未找到 auth_requests_total" -ForegroundColor Yellow
            $warningsList += "认证指标缺失"
        }
    } catch {
        Write-Host "   ⚠️  无法访问 Prometheus 指标端点" -ForegroundColor Yellow
        $warningsList += "无法访问指标端点"
    }
}

# ============ 8. 生成报告 ============
Write-Host "`n" -NoNewline
Write-Host "╔════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          📊 验证结果总览                                      ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════════════════════════════╝`n" -ForegroundColor Cyan

Write-Host "✅ 成功项: " -ForegroundColor Green -NoNewline
Write-Host "$($successList.Count)" -ForegroundColor White
Write-Host "⚠️  警告项: " -ForegroundColor Yellow -NoNewline
Write-Host "$($warningsList.Count)" -ForegroundColor White
Write-Host "❌ 错误项: " -ForegroundColor Red -NoNewline
Write-Host "$($errorsList.Count)" -ForegroundColor White

if ($errorsList.Count -gt 0) {
    Write-Host "`n❌ 发现严重问题:" -ForegroundColor Red
    foreach ($error in $errorsList) {
        Write-Host "   • $error" -ForegroundColor Red
    }
}

if ($warningsList.Count -gt 0) {
    Write-Host "`n⚠️  需要注意:" -ForegroundColor Yellow
    foreach ($warning in $warningsList) {
        Write-Host "   • $warning" -ForegroundColor Yellow
    }
}

# ============ 9. 下一步建议 ============
Write-Host "`n📋 下一步建议:" -ForegroundColor Cyan

if ($errorsList.Count -eq 0) {
    Write-Host "   1. ✅ 基础验证通过，可以继续开发" -ForegroundColor Green

    if (-not $Full) {
        Write-Host "   2. 运行完整验证: .\scripts\verify_restoration.ps1 -Full" -ForegroundColor White
    } else {
        Write-Host "   2. ✅ 完整验证已完成" -ForegroundColor Green
    }

    Write-Host "   3. 测试登录功能:" -ForegroundColor White
    Write-Host "      • 启动: .\start-dev.ps1" -ForegroundColor Gray
    Write-Host "      • 访问: http://localhost:3101" -ForegroundColor Gray

    Write-Host "   4. 修复 detect-secrets 兼容性:" -ForegroundColor White
    Write-Host "      • pre-commit autoupdate --repo https://github.com/Yelp/detect-secrets" -ForegroundColor Gray

} else {
    Write-Host "   1. ❌ 请先修复上述错误" -ForegroundColor Red
    Write-Host "   2. 查看详细报告: docs/REPO_RESTORATION_REPORT.md" -ForegroundColor White
    Write-Host "   3. 从旧仓库恢复缺失文件:" -ForegroundColor White
    Write-Host "      • git show old-origin/feature/dashboard-phase2:<file> > <file>" -ForegroundColor Gray
}

Write-Host "`n📚 相关文档:" -ForegroundColor Cyan
Write-Host "   • 恢复报告: docs/REPO_RESTORATION_REPORT.md" -ForegroundColor White
Write-Host "   • 云端部署: docs/deployment/CLOUD_DEPLOYMENT_GUIDE.md" -ForegroundColor White
Write-Host "   • 快速开始: DEV_START.md" -ForegroundColor White

# 返回退出代码
if ($errorsList.Count -gt 0) {
    Write-Host "`n⚠️  验证失败，发现 $($errorsList.Count) 个错误" -ForegroundColor Red
    exit 1
} elseif ($warningsList.Count -gt 0) {
    Write-Host "`n✅ 验证通过（有 $($warningsList.Count) 个警告）" -ForegroundColor Yellow
    exit 0
} else {
    Write-Host "`n🎉 验证完全通过！" -ForegroundColor Green
    exit 0
}
