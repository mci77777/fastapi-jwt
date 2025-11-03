# Supabase 保活机制

## 📋 概述

Supabase 免费层项目在 **7 天无活动**后会自动暂停。本文档说明如何使用内置的保活机制防止项目暂停。

## 🎯 工作原理

### 核心机制
- **定期 Ping**：每 10 分钟（可配置）向 Supabase REST API 发送轻量级 HEAD 请求
- **自动启动**：应用启动时自动初始化保活服务
- **优雅关闭**：应用关闭时自动停止保活任务
- **指标监控**：通过 Prometheus 指标暴露保活状态

### 技术实现
- **服务类**：`app/services/supabase_keepalive.py::SupabaseKeepaliveService`
- **集成点**：`app/core/application.py::lifespan()` 生命周期钩子
- **请求目标**：`https://{project_id}.supabase.co/rest/v1/ai_model?limit=1` (HEAD 请求)
- **认证方式**：使用 `SUPABASE_SERVICE_ROLE_KEY` 进行认证
- **请求方式**：与 `supabase_status()` 一致，使用 `/ai_model` 表进行轻量级查询

## ⚙️ 配置

### 环境变量

在 `.env` 文件中添加以下配置：

```bash
# Supabase 保活配置（防止免费层 7 天无活动后暂停）
SUPABASE_KEEPALIVE_ENABLED=true                # 启用保活功能（默认: true）
SUPABASE_KEEPALIVE_INTERVAL_MINUTES=10         # 保活间隔（分钟，默认: 10）
```

### 配置说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `SUPABASE_KEEPALIVE_ENABLED` | bool | `true` | 是否启用保活功能 |
| `SUPABASE_KEEPALIVE_INTERVAL_MINUTES` | int | `10` | 保活请求间隔（分钟） |

### 推荐设置

- **生产环境**：`INTERVAL_MINUTES=10`（每 10 分钟一次，安全余量充足）
- **开发环境**：`INTERVAL_MINUTES=5`（更频繁的测试）
- **禁用保活**：`ENABLED=false`（仅在不需要时禁用）

## 📊 监控与观测

### Prometheus 指标

保活服务暴露以下 Prometheus 指标（通过 `/api/v1/metrics` 端点）：

```prometheus
# 保活请求总数（按状态分类）
supabase_keepalive_requests_total{status="success"} 42
supabase_keepalive_requests_total{status="failure"} 0

# 最后成功 ping 的时间戳
supabase_keepalive_last_success_timestamp 1704067200
```

### 日志输出

保活服务会记录以下日志：

```
INFO: Supabase keepalive started (interval=600 seconds, project_id=abc123)
DEBUG: Supabase keepalive ping successful (total_success=1)
WARNING: Supabase keepalive ping failed (total_failures=1): Connection timeout
INFO: Supabase keepalive stopped
```

### 状态查询

通过服务快照 API 查询保活状态：

```python
from app.core.application import app

keepalive = app.state.supabase_keepalive
snapshot = keepalive.snapshot()

# 返回示例:
{
    "enabled": true,
    "is_running": true,
    "interval_seconds": 600,
    "last_ping_at": "2025-01-01T12:00:00+00:00",
    "success_count": 42,
    "failure_count": 0,
    "last_error": null
}
```

## 🧪 测试

### 手动测试

运行测试脚本验证保活服务：

```bash
python scripts/test_supabase_keepalive.py
```

**预期输出**：
```
============================================================
Supabase 保活服务测试
============================================================

1. 配置检查:
   - 启用状态: True
   - 间隔时间: 600 秒 (10 分钟)
   - Project ID: your-project-id

2. 启动保活服务...
   ✅ 服务已启动: True

3. 等待第一次保活 ping（最多 15 秒）...
   ✅ 第一次 ping 成功!
   - 时间: 2025-01-01T12:00:00+00:00
   - 成功次数: 1
   - 失败次数: 0

4. 服务状态快照:
   - enabled: True
   - is_running: True
   - interval_seconds: 600
   - last_ping_at: 2025-01-01T12:00:00+00:00
   - success_count: 1
   - failure_count: 0
   - last_error: None

5. Prometheus 指标检查:
   - supabase_keepalive_requests_total{'status': 'success'}: 1.0

6. 停止保活服务...
   ✅ 服务已停止: True

============================================================
测试完成!
============================================================
```

### 集成测试

保活服务在应用启动时自动运行，可通过以下方式验证：

1. **启动应用**：
   ```bash
   python run.py
   ```

2. **检查日志**：
   ```
   INFO: Supabase keepalive started (interval=600 seconds, project_id=abc123)
   ```

3. **查询指标**：
   ```bash
   curl http://localhost:9999/api/v1/metrics | grep supabase_keepalive
   ```

## 🔧 故障排查

### 问题 1：保活服务未启动

**症状**：日志中没有 "Supabase keepalive started" 消息

**原因**：
- `SUPABASE_KEEPALIVE_ENABLED=false`
- 缺少 `SUPABASE_PROJECT_ID` 或 `SUPABASE_SERVICE_ROLE_KEY`

**解决方案**：
1. 检查 `.env` 配置
2. 确保 Supabase 凭证正确

### 问题 2：保活请求失败

**症状**：`failure_count` 持续增加

**原因**：
- Supabase 服务不可用
- 网络连接问题
- 认证凭证错误

**解决方案**：
1. 检查 Supabase 项目状态
2. 验证 `SUPABASE_SERVICE_ROLE_KEY` 是否正确
3. 检查网络连接

### 问题 3：保活间隔过短

**症状**：请求频率过高，可能触发 Supabase 限流

**解决方案**：
- 增加 `SUPABASE_KEEPALIVE_INTERVAL_MINUTES` 到 10 或更高
- 推荐值：10-30 分钟

## 📚 相关资源

- **Supabase 官方文档**：[Production Checklist](https://supabase.com/docs/guides/deployment/going-into-prod)
- **社区方案**：
  - [Supabase Inactive Fix (Python)](https://github.com/travisvn/supabase-inactive-fix)
  - [Supabase Pause Prevention (Next.js)](https://github.com/travisvn/supabase-pause-prevention)
- **本项目实现**：
  - 服务类：`app/services/supabase_keepalive.py`
  - 配置：`app/settings/config.py`
  - 指标：`app/core/metrics.py`

## 🎯 最佳实践

1. **保持默认配置**：10 分钟间隔足以防止暂停，且不会过度消耗资源
2. **监控指标**：定期检查 `failure_count`，及时发现问题
3. **日志审计**：保留保活日志用于故障排查
4. **升级计划**：如果项目流量增长，考虑升级到 Supabase Pro 计划

## ⚠️ 注意事项

- **免费层限制**：保活机制仅适用于免费层项目，Pro 计划不会自动暂停
- **资源消耗**：HEAD 请求非常轻量，对 Supabase 配额影响极小
- **不影响限流**：保活请求不会触发应用的 RateLimiter 中间件
- **优雅降级**：如果 Supabase 不可用，保活失败不会影响应用主功能
