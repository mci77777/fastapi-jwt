<#
.SYNOPSIS
快速配置 .env 文件的交互式脚本

.DESCRIPTION
帮助用户快速配置必需的环境变量，包括 Supabase 和 xAI API 密钥

.EXAMPLE
.\scripts\configure-env.ps1
#>

$ErrorActionPreference = "Stop"

Write-Host @"

╔═══════════════════════════════════════════════════════════════╗
║          🔧 GymBro .env 配置向导                             ║
╚═══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

# 检查 .env 文件是否存在
if (-not (Test-Path .env)) {
    Write-Host "❌ .env 文件不存在，正在从模板创建..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "✅ .env 文件已创建" -ForegroundColor Green
}

Write-Host "`n📋 请提供以下配置信息（按 Enter 跳过可选项）`n" -ForegroundColor Yellow

# ============ Supabase 配置 ============
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host "1️⃣  Supabase 配置" -ForegroundColor Cyan
Write-Host "   访问: https://supabase.com/dashboard → 你的项目 → Settings" -ForegroundColor Gray
Write-Host ""

$supabaseProjectId = Read-Host "   Supabase Project ID (必填)"
if ([string]::IsNullOrWhiteSpace($supabaseProjectId)) {
    Write-Host "⚠️  跳过 Supabase 配置（服务可能无法正常工作）" -ForegroundColor Yellow
} else {
    Write-Host ""
    $supabaseServiceKey = Read-Host "   Supabase Service Role Key (必填，从 Settings → API 获取)"

    if (-not [string]::IsNullOrWhiteSpace($supabaseServiceKey)) {
        # 更新 .env 文件
        $envContent = Get-Content .env -Raw

        $envContent = $envContent -replace 'SUPABASE_PROJECT_ID=.*', "SUPABASE_PROJECT_ID=$supabaseProjectId"
        $envContent = $envContent -replace 'SUPABASE_JWKS_URL=.*', "SUPABASE_JWKS_URL=https://$supabaseProjectId.supabase.co/.well-known/jwks.json"
        $envContent = $envContent -replace 'SUPABASE_ISSUER=.*', "SUPABASE_ISSUER=https://$supabaseProjectId.supabase.co"
        $envContent = $envContent -replace 'SUPABASE_AUDIENCE=.*', "SUPABASE_AUDIENCE=$supabaseProjectId"
        $envContent = $envContent -replace 'SUPABASE_SERVICE_ROLE_KEY=.*', "SUPABASE_SERVICE_ROLE_KEY=$supabaseServiceKey"

        $envContent | Set-Content .env -NoNewline
        Write-Host "   ✅ Supabase 配置已更新" -ForegroundColor Green
    }
}

# ============ xAI API 配置 ============
Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host "2️⃣  xAI API 配置" -ForegroundColor Cyan
Write-Host "   访问: https://console.x.ai/api-keys → Create API Key" -ForegroundColor Gray
Write-Host ""

$xaiApiKey = Read-Host "   xAI API Key (必填，格式: xai-xxxxxxxxxx)"
if ([string]::IsNullOrWhiteSpace($xaiApiKey)) {
    Write-Host "⚠️  跳过 xAI 配置（AI 功能将无法使用）" -ForegroundColor Yellow
} else {
    $envContent = Get-Content .env -Raw
    $envContent = $envContent -replace 'AI_API_KEY=.*', "AI_API_KEY=$xaiApiKey"
    $envContent | Set-Content .env -NoNewline
    Write-Host "   ✅ xAI API 配置已更新" -ForegroundColor Green
}

# ============ 环境类型 ============
Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host "3️⃣  环境类型" -ForegroundColor Cyan
Write-Host ""

$environment = Read-Host "   选择环境 (dev/prod) [默认: dev]"
if ([string]::IsNullOrWhiteSpace($environment)) {
    $environment = "dev"
}

$envContent = Get-Content .env -Raw
if ($environment -eq "prod") {
    $envContent = $envContent -replace 'DEBUG=.*', "DEBUG=false"
    $envContent = $envContent -replace 'FORCE_HTTPS=.*', "FORCE_HTTPS=true"
    Write-Host "   ✅ 生产环境配置已应用" -ForegroundColor Green
} else {
    $envContent = $envContent -replace 'DEBUG=.*', "DEBUG=true"
    Write-Host "   ✅ 开发环境配置已应用" -ForegroundColor Green
}
$envContent | Set-Content .env -NoNewline

# ============ 验证配置 ============
Write-Host "`n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray
Write-Host "🔍 验证配置..." -ForegroundColor Cyan

$errors = @()

# 检查必填项
$envContent = Get-Content .env
if ($envContent -match 'SUPABASE_PROJECT_ID=your-project-id|SUPABASE_PROJECT_ID=$') {
    $errors += "Supabase Project ID 未配置"
}
if ($envContent -match 'AI_API_KEY=your-openai-api-key|AI_API_KEY=$') {
    $errors += "xAI API Key 未配置"
}

if ($errors.Count -gt 0) {
    Write-Host "`n⚠️  警告: 以下配置项缺失" -ForegroundColor Yellow
    $errors | ForEach-Object { Write-Host "   • $_" -ForegroundColor Yellow }
    Write-Host "`n   服务可能无法正常启动，请手动编辑 .env 文件" -ForegroundColor Yellow
} else {
    Write-Host "`n✅ 所有必填项已配置" -ForegroundColor Green
}

# ============ 完成 ============
Write-Host @"

╔═══════════════════════════════════════════════════════════════╗
║          ✅ 配置完成！                                       ║
╚═══════════════════════════════════════════════════════════════╝

📋 后续步骤:

1. 查看配置文件:
   code .env

2. 验证 Supabase 连接:
   python scripts/verify_supabase_config.py

3. 测试 xAI API:
   python scripts/verify_jwks_cache.py

4. 启动服务:
   python run.py

📚 详细文档: docs/ENV_CONFIGURATION_GUIDE.md

"@ -ForegroundColor Cyan

# 询问是否立即打开 .env 文件
$openFile = Read-Host "是否现在编辑 .env 文件? (Y/n)"
if ($openFile -ne 'n' -and $openFile -ne 'N') {
    code .env
}
