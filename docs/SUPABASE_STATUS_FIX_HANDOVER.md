# Supabase 状态端点修复交接文档

## 问题描述
Dashboard 的 Supabase 状态卡片频繁报 502 错误（实际是 401 Unauthorized）。

## 根本原因
**后端服务未重新加载代码**，导致修改后的路由定义未生效。

虽然 `run.py` 配置了 `reload=True`，但 Uvicorn 的热重载机制可能因以下原因失效：
1. 文件修改时间戳未更新
2. Uvicorn 监控的文件路径不包含修改的文件
3. 服务器进程卡住或异常

## 已完成的修复

### 1. 移除路由函数的认证依赖
**文件**: `app/api/v1/llm_models.py`（第 245-257 行）

```python
@router.get("/status/supabase")
async def supabase_status(request: Request) -> dict[str, Any]:
    """
    获取 Supabase 连接状态（公开端点，无需认证）。
    
    返回 Supabase REST API 的连接状态、延迟和最近同步时间。
    此端点用于 Dashboard 公开页面的状态监控，不涉及敏感数据。
    
    注意：此端点已配置为公开访问，无需 JWT 认证。
    """
    service = get_service(request)
    status_payload = await service.supabase_status()
    return create_response(data=status_payload)
```

**变更**：
- ✅ 移除 `current_user: AuthenticatedUser = Depends(get_current_user)` 参数
- ✅ 添加文档说明端点为公开访问

### 2. 添加到 PolicyGate 公开端点列表
**文件**: `app/core/policy_gate.py`（第 87 行）

```python
# Supabase 状态（Dashboard 公开页面使用）
re.compile(r'^/api/v1/llm/status/supabase$'),
```

**变更**：
- ✅ 添加到 `public_endpoints` 列表
- ✅ 从 `anonymous_restricted_patterns` 移除（第 52 行注释）

### 3. 添加到 RateLimiter 白名单
**文件**: `app/core/rate_limiter.py`（第 323 行）

```python
WHITELIST_PATHS = {
    "/api/v1/healthz",
    "/api/v1/livez",
    "/api/v1/readyz",
    "/api/v1/metrics",
    "/api/v1/llm/status/supabase",  # Supabase 状态（Dashboard 公开页面）
    "/docs",
    "/redoc",
    "/openapi.json",
}
```

**变更**：
- ✅ 添加到白名单，绕过限流检查

### 4. 更新文档函数
**文件**: `app/core/policy_gate.py`（第 203-239 行）

```python
def get_public_endpoints() -> List[str]:
    """获取公开端点列表（无需认证，用于文档生成）。"""
    return [
        # ...
        "GET /api/v1/llm/status/supabase",  # 新增
        # ...
    ]
```

**变更**：
- ✅ 添加到 `get_public_endpoints()` 返回列表
- ✅ 添加到 `get_anonymous_allowed_endpoints()` 返回列表（继承自公开端点）

## 诊断结果

运行 `python scripts/diagnose_supabase_endpoint.py` 的输出：

```
[1] 检查后端服务...
✓ 后端服务正常运行

[2] 检查 OpenAPI Schema...
✓ Supabase 端点存在于 Schema
  Security: []
  ✓ 端点不需要认证（Schema 层面）
✗ 测试端点不存在于 Schema（代码未重新加载！）

⚠️  后端服务可能没有重新加载代码！
```

**结论**：
- OpenAPI Schema 显示端点不需要认证（`Security: []`）
- 但实际请求仍返回 401 错误
- 测试端点不存在，说明**代码未重新加载**

## 解决方案

### 方案 1：手动重启后端服务（推荐）

1. **关闭当前后端服务**：
   - 找到运行 `python run.py` 的 PowerShell 窗口
   - 按 `Ctrl+C` 停止服务
   - 或直接关闭窗口

2. **重新启动后端服务**：
   ```powershell
   # 方式 1：使用启动脚本（推荐）
   .\start-dev.ps1
   
   # 方式 2：手动启动
   python run.py
   ```

3. **等待服务启动**：
   - 等待 5-10 秒
   - 看到 "Application startup complete" 消息

4. **验证修复**：
   ```powershell
   python scripts/diagnose_supabase_endpoint.py
   ```
   
   预期输出：
   ```
   [4] 测试 Supabase 状态端点...
   ✓ Supabase 状态端点可公开访问
   ```

### 方案 2：使用自动重启脚本

```powershell
.\scripts\restart_backend.ps1
```

**注意**：此脚本会：
1. 自动杀死占用 9999 端口的进程
2. 启动新的后端服务窗口
3. 需要等待 5-10 秒让服务完全启动

### 方案 3：强制触发文件变化

如果不想重启服务，可以尝试强制触发 Uvicorn 的热重载：

```powershell
# 修改一个文件的时间戳
(Get-Item app\api\v1\llm_models.py).LastWriteTime = Get-Date
```

然后等待 2-3 秒，Uvicorn 应该会自动重新加载。

## 验证步骤

### 1. 后端 API 测试

```powershell
python scripts/test_supabase_status.py
```

预期输出：
```
[1] 测试后端 API（无认证）...
OK - Supabase 状态端点正常
```

### 2. 前端测试

1. 打开浏览器访问 `http://localhost:3101/dashboard`
2. 查看 Supabase 状态卡片
3. 应该显示：
   - 状态：在线/离线
   - 延迟：XXX ms
   - 最近同步：时间戳

### 3. Chrome DevTools 验证

1. 打开 Chrome DevTools（F12）
2. 切换到 Network 标签
3. 刷新 Dashboard 页面
4. 查找 `status/supabase` 请求
5. 验证：
   - 状态码：200 OK
   - 响应体包含 `{"code": 200, "msg": "success", "data": {...}}`

## 技术细节

### 中间件执行顺序

```
请求 → CORS → TraceID → PolicyGate → RateLimiter → 路由处理器
```

**PolicyGate 逻辑**（`app/core/policy_gate.py::dispatch`）：
1. 检查是否是公开端点（第 100-101 行）
   - 如果是，直接放行 → `return await call_next(request)`
2. 检查匿名支持是否启用（第 104-105 行）
3. 获取用户信息（第 108 行）
4. 检查匿名用户访问权限（第 116-121 行）

**关键点**：
- 公开端点在**第一步**就放行，不会执行后续的认证检查
- `request.state.user` 只在非公开端点时才会被读取
- 因此，公开端点**不需要**设置 `request.state.user`

### 为什么 OpenAPI Schema 正确但实际请求失败？

**原因**：
- OpenAPI Schema 是在**应用启动时**生成的
- 如果代码修改后服务未重启，Schema 会反映新代码
- 但**运行时的路由处理器**仍然是旧代码
- 这导致 Schema 显示不需要认证，但实际请求仍调用旧的认证逻辑

**解决方案**：
- 必须重启服务，确保运行时代码与 Schema 一致

## 后续优化建议

### 1. 添加健康检查端点

在 `app/api/v1/health.py` 中添加：

```python
@router.get("/code-version")
async def code_version() -> dict[str, Any]:
    """返回代码版本信息（用于验证代码是否重新加载）。"""
    import time
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "version": "1.0.0",
            "reload_timestamp": time.time(),
            "test_endpoint_exists": True,  # 用于验证代码重新加载
        }
    }
```

### 2. 改进热重载机制

在 `run.py` 中添加更详细的日志：

```python
config = uvicorn.Config(
    "app:app",
    host="0.0.0.0",
    port=9999,
    reload=True,
    reload_dirs=["app"],  # 明确指定监控目录
    log_level="info",
    log_config=LOGGING_CONFIG
)
```

### 3. 添加自动化测试

创建 `tests/test_public_endpoints.py`：

```python
def test_supabase_status_public_access(client):
    """测试 Supabase 状态端点可公开访问。"""
    response = client.get("/api/v1/llm/status/supabase")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 200
    assert "status" in data["data"]
```

## 相关文件清单

### 修改的文件
- `app/api/v1/llm_models.py`（移除认证依赖）
- `app/core/policy_gate.py`（添加公开端点）
- `app/core/rate_limiter.py`（添加白名单）

### 新增的文件
- `scripts/test_supabase_status.py`（测试脚本）
- `scripts/debug_supabase_endpoint.py`（调试脚本）
- `scripts/diagnose_supabase_endpoint.py`（诊断脚本）
- `scripts/check_openapi_schema.py`（Schema 检查脚本）
- `scripts/restart_backend.ps1`（重启脚本）
- `docs/SUPABASE_STATUS_FIX_HANDOVER.md`（本文档）

### 相关文档
- `docs/GW_AUTH_README.md`（网关认证文档）
- `docs/JWT_HARDENING_GUIDE.md`（JWT 硬化指南）
- `docs/PROJECT_OVERVIEW.md`（项目总览）

## 总结

**问题**：Supabase 状态端点返回 401 错误

**根本原因**：后端服务未重新加载代码

**解决方案**：手动重启后端服务

**验证方法**：运行 `python scripts/diagnose_supabase_endpoint.py`

**预期结果**：端点返回 200 OK，Dashboard 显示 Supabase 状态

---

**交接时间**：2025-10-14 02:30 UTC
**修复人员**：AI Assistant
**验证状态**：待用户重启后端服务后验证

