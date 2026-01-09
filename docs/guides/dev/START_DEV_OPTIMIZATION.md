# start-dev.ps1 优化说明

## 📋 概述

本次优化解决了 `start-dev.ps1` 脚本在某些环境下的参数传递问题和错误处理不足的问题。

## 🔧 主要改进

### 1. **改进的参数传递方式**

**之前的问题：**
```powershell
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot'; python run.py"
```
- 使用数组形式的 ArgumentList 在某些 PowerShell 版本中可能导致参数解析错误
- 在命令中使用 `cd` 改变工作目录不够可靠

**优化后：**
```powershell
$backendCommand = "Write-Host 'Starting backend server...' -ForegroundColor Cyan; python run.py"
$backendProcess = Start-Process powershell `
    -ArgumentList "-NoExit -Command `"$backendCommand`"" `
    -WorkingDirectory $PSScriptRoot `
    -PassThru `
    -ErrorAction Stop
```

**改进点：**
- ✅ 使用单个字符串而不是数组，避免参数解析问题
- ✅ 使用 `-WorkingDirectory` 参数明确设置工作目录
- ✅ 使用 `-PassThru` 返回进程对象，便于跟踪
- ✅ 使用 `-ErrorAction Stop` 确保错误被捕获

### 2. **增强的错误处理**

**新增功能：**
- ✅ try-catch 块包裹所有 `Start-Process` 调用
- ✅ 详细的错误消息和故障排除提示
- ✅ 进程 ID (PID) 显示，便于调试
- ✅ 前端目录存在性验证

**后端启动错误处理：**
```powershell
try {
    $backendProcess = Start-Process powershell ...
    Write-Host "[Backend] Process started (PID: $($backendProcess.Id))" -ForegroundColor Green
} catch {
    Write-Host "[Backend] Failed to start process!" -ForegroundColor Red
    Write-Host "  Error: $_" -ForegroundColor Red
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Ensure Python is installed and in PATH" -ForegroundColor Yellow
    Write-Host "  2. Try running manually: python run.py" -ForegroundColor Yellow
    Write-Host "  3. Check if run.py exists in: $PSScriptRoot" -ForegroundColor Yellow
    exit 1
}
```

**前端启动错误处理：**
```powershell
# 验证目录存在
if (-not (Test-Path $frontendWorkDir)) {
    Write-Host "[Frontend] Directory not found: $frontendWorkDir" -ForegroundColor Red
    exit 1
}

try {
    $frontendProcess = Start-Process powershell ...
    Write-Host "[Frontend] Process started (PID: $($frontendProcess.Id))" -ForegroundColor Green
} catch {
    Write-Host "[Frontend] Failed to start process!" -ForegroundColor Red
    Write-Host "  Error: $_" -ForegroundColor Red
    Write-Host "Troubleshooting:" -ForegroundColor Yellow
    Write-Host "  1. Ensure pnpm is installed: npm install -g pnpm" -ForegroundColor Yellow
    Write-Host "  2. Install dependencies: cd web && pnpm install" -ForegroundColor Yellow
    Write-Host "  3. Try running manually: cd web && pnpm dev" -ForegroundColor Yellow
    exit 1
}
```

### 3. **增强的日志输出**

**新增调试信息：**
```powershell
Write-Host "[Backend] Command: $backendCommand" -ForegroundColor DarkGray
Write-Host "[Backend] Process started (PID: 12345)" -ForegroundColor Green

Write-Host "[Frontend] Command: $frontendCommand" -ForegroundColor DarkGray
Write-Host "[Frontend] Working Directory: $frontendWorkDir" -ForegroundColor DarkGray
Write-Host "[Frontend] Process started (PID: 67890)" -ForegroundColor Green
```

**好处：**
- ✅ 显示实际执行的命令，便于调试
- ✅ 显示进程 ID，便于手动管理进程
- ✅ 显示工作目录，确认路径正确

### 4. **保留的现有功能**

所有原有功能均保持不变：
- ✅ 自动端口检测和清理（Clear-Port）
- ✅ Python 缓存清理（Clear-PythonCache）
- ✅ 依赖检查（Test-Dependencies）
- ✅ 端口监听等待（Wait-PortListening）
- ✅ 详细的步骤提示和进度显示
- ✅ 成功后的访问 URL 显示

## 🧪 测试验证

### 运行测试脚本

```powershell
.\test-start-dev.ps1
```

**测试内容：**
1. ✅ 检查 start-dev.ps1 文件存在
2. ✅ 检查 run.py 文件存在
3. ✅ 检查 web 目录存在
4. ✅ 检查 Python 安装
5. ✅ 检查 pnpm 安装
6. ✅ 验证 PowerShell 语法

### 实际启动测试

```powershell
.\start-dev.ps1
```

**预期输出：**
```
========================================
 Vue FastAPI Admin - Dev Environment
========================================

[Step 1/5] Checking dependencies...
[Deps] Python: Python 3.11.x
[Deps] pnpm: v8.x.x

[Step 2/5] Clearing Python cache...
[Cache] Cleared X cache items

[Step 3/5] Checking ports...
[Backend] Port 9999 available
[Frontend] Port 3101 available

[Step 4/5] Starting backend...
  URL: http://localhost:9999
  API Docs: http://localhost:9999/docs
[Backend] Command: Write-Host 'Starting backend server...' -ForegroundColor Cyan; python run.py
[Backend] Process started (PID: 12345)
[Backend] Service is ready on port 9999! (attempt 5/30)

[Step 5/5] Starting frontend...
  URL: http://localhost:3101
[Frontend] Command: Write-Host 'Starting frontend server...' -ForegroundColor Cyan; pnpm dev
[Frontend] Working Directory: <repo-root>/web
[Frontend] Process started (PID: 67890)
[Frontend] Service is ready on port 3101! (attempt 10/30)

========================================
 Development Environment Ready!
========================================

Access URLs:
  Frontend:  http://localhost:3101
  Backend:   http://localhost:9999
  API Docs:  http://localhost:9999/docs

To stop: Close the PowerShell windows or press Ctrl+C
```

## 🔍 故障排除

### 问题 1: "Failed to start process"

**可能原因：**
- Python 或 pnpm 未安装或不在 PATH 中
- run.py 或 web 目录不存在

**解决方案：**
1. 检查 Python 安装：`python --version`
2. 检查 pnpm 安装：`pnpm --version`
3. 验证文件存在：`Test-Path run.py`
4. 验证目录存在：`Test-Path web`

### 问题 2: "Port already in use"

**可能原因：**
- 端口 9999 或 3101 被其他进程占用
- 之前的服务未正确关闭

**解决方案：**
脚本会自动检测并关闭占用端口的进程。如果自动清理失败：

```powershell
# 手动查找占用端口的进程
netstat -ano | findstr :9999
netstat -ano | findstr :3101

# 手动关闭进程（替换 PID）
Stop-Process -Id <PID> -Force
```

### 问题 3: "Service failed to start (timeout)"

**可能原因：**
- 首次运行需要安装依赖，耗时较长
- 数据库初始化耗时
- 服务启动时遇到错误

**解决方案：**
1. 检查新打开的 PowerShell 窗口中的错误消息
2. 手动运行服务查看详细错误：
   ```powershell
   # 后端
   python run.py

   # 前端
   cd web
   pnpm dev
   ```

## 📊 性能影响

- **启动时间：** 无变化（~10-30 秒，取决于首次运行）
- **内存占用：** 无变化
- **可靠性：** 显著提升（更好的错误处理和参数传递）

## 🔄 兼容性

**测试环境：**
- ✅ Windows 10/11
- ✅ PowerShell 5.1
- ✅ PowerShell 7.x
- ✅ Python 3.11+
- ✅ pnpm 8.x

## 📝 变更摘要

| 变更项 | 之前 | 之后 |
|--------|------|------|
| 参数传递 | 数组形式 | 单字符串 + WorkingDirectory |
| 错误处理 | 无 | try-catch + 详细提示 |
| 日志输出 | 基本 | 增强（命令、PID、路径） |
| 目录验证 | 无 | 前端目录存在性检查 |
| 进程跟踪 | 无 | PassThru 返回进程对象 |

## 🎯 验收标准

- [x] 脚本在 PowerShell 5.1 和 7.x 中均可正常运行
- [x] 参数传递不再出现错误
- [x] 错误时提供清晰的故障排除提示
- [x] 显示进程 ID 便于调试
- [x] 保留所有原有功能
- [x] 通过测试脚本验证

## 🚀 使用建议

1. **首次使用：** 运行 `.\test-start-dev.ps1` 验证环境
2. **日常开发：** 直接运行 `.\start-dev.ps1`
3. **遇到问题：** 查看新打开的 PowerShell 窗口中的错误消息
4. **手动调试：** 使用显示的命令和 PID 进行手动调试

## 📚 相关文档

- [DEV_START.md](../DEV_START.md) - 快速启动指南
- [README.md](../README.md) - 项目总览
- [CLAUDE.md](../CLAUDE.md) - 开发工作流
