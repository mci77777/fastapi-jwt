# ============================================================
# Git 历史密钥清理脚本
# ============================================================
# 用途: 从 Git 历史中永久删除泄露的 xAI API Key
# 警告: 此操作会重写 Git 历史，需要强制推送
# ============================================================

$ErrorActionPreference = "Stop"

Write-Host "🔥 开始清理 Git 历史中的泄露密钥..." -ForegroundColor Red
Write-Host ""

# 检查是否在 Git 仓库中
if (-not (Test-Path .git)) {
    Write-Host "❌ 错误: 当前目录不是 Git 仓库" -ForegroundColor Red
    exit 1
}

# 确认操作
Write-Host "⚠️  警告: 此操作将重写 Git 历史!" -ForegroundColor Yellow
Write-Host "   - 泄露的文件: storage/ai_router/supabase_endpoints-latest.json" -ForegroundColor Yellow
Write-Host "   - 泄露的 commit: 98ef4ec9397c6627b12acae20e618aa524933073" -ForegroundColor Yellow
Write-Host ""
$confirm = Read-Host "确认执行? (输入 YES 继续)"
if ($confirm -ne "YES") {
    Write-Host "❌ 操作已取消" -ForegroundColor Red
    exit 0
}

Write-Host ""
Write-Host "📦 方案 1: 使用 git filter-repo (推荐)" -ForegroundColor Cyan
Write-Host "   检查是否已安装..."

# 检查 git filter-repo
$hasFilterRepo = $false
try {
    git filter-repo --version 2>$null
    $hasFilterRepo = $true
    Write-Host "   ✅ 已安装 git filter-repo" -ForegroundColor Green
} catch {
    Write-Host "   ⚠️  未安装 git filter-repo" -ForegroundColor Yellow
}

if ($hasFilterRepo) {
    Write-Host ""
    Write-Host "🚀 使用 git filter-repo 清理历史..." -ForegroundColor Cyan
    
    # 删除指定文件的所有历史记录
    git filter-repo --path storage/ai_router/supabase_endpoints-latest.json --invert-paths --force
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Git 历史已清理" -ForegroundColor Green
    } else {
        Write-Host "❌ 清理失败" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host ""
    Write-Host "📦 方案 2: 使用 git filter-branch (备选)" -ForegroundColor Cyan
    Write-Host "   正在清理..."
    
    # 使用 filter-branch 删除文件
    git filter-branch --force --index-filter `
        "git rm --cached --ignore-unmatch storage/ai_router/supabase_endpoints-latest.json" `
        --prune-empty --tag-name-filter cat -- --all
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Git 历史已清理" -ForegroundColor Green
        
        # 清理 refs
        Write-Host "🧹 清理引用..."
        Remove-Item -Path .git/refs/original -Recurse -Force -ErrorAction SilentlyContinue
        
        # 清理 reflog
        git reflog expire --expire=now --all
        
        # 垃圾回收
        git gc --prune=now --aggressive
        
        Write-Host "✅ 清理完成" -ForegroundColor Green
    } else {
        Write-Host "❌ 清理失败" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "📤 下一步: 强制推送到远程仓库" -ForegroundColor Yellow
Write-Host "   运行命令:" -ForegroundColor Yellow
Write-Host "   git push origin --force --all" -ForegroundColor Cyan
Write-Host "   git push origin --force --tags" -ForegroundColor Cyan
Write-Host ""
Write-Host "⚠️  警告: 团队成员需要重新 clone 仓库!" -ForegroundColor Yellow
Write-Host ""
Write-Host "✅ 脚本执行完成" -ForegroundColor Green
