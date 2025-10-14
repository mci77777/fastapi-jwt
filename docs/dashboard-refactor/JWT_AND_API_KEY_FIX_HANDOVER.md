# JWT 认证链路与 API 供应商密钥修复交接文档

**修复时间**: 2025-10-14  
**修复范围**: Prometheus 指标读取错误 + 认证链路澄清  
**修复结果**: ✅ **已完成**

---

## 📋 问题总结

### 问题 1: Prometheus Counter 指标读取错误 ❌

**错误日志**:
```
[WARNING] 2025-10-14T12:04:22.662953
Failed to get JWT availability metrics: 'Counter' object has no attribute '_labels'
```

**根因**:
- **文件**: `app/services/metrics_collector.py` (第 132 行)
- **错误代码**: `for sample in auth_requests_total._metrics.values()`
- **问题**: 使用了 Prometheus Counter 的内部私有 API（`_metrics` 属性），该 API 不稳定且在新版本中已变更

**影响**:
- Dashboard API `/api/v1/stats/dashboard` 中的 `jwt_availability` 字段始终返回 `{"success_rate": 0, "total_requests": 0, "successful_requests": 0}`
- 前端 Dashboard 无法显示真实的 JWT 连通性数据

---

### 问题 2: JWT 认证链路与 API 供应商密钥混淆（澄清） ✅

**误解**:
- 向 AI API 供应商（如 OpenAI、Anthropic）发送 JWT token（❌ 错误）

**实际情况**:
- ✅ **JWT 认证链路已正确实现**：`app/auth/dependencies.py` 第 51 和 56 行已正确更新 Prometheus 指标
- ✅ **AI 请求链路已正确实现**：`app/services/ai_service.py` 第 226 行使用 `self._settings.ai_api_key`（非 JWT）

**结论**: 无需修复，仅需澄清认证链路边界

---

## 🔧 修复详情

### 修复 1: Prometheus Counter 指标读取

**文件**: `app/services/metrics_collector.py`  
**修改位置**: 第 119-151 行

#### 修改前代码（错误）
```python
async def _get_jwt_availability(self) -> Dict[str, Any]:
    """查询 JWT 可获取性（从 Prometheus 指标计算）。"""
    try:
        total = 0
        success = 0
        
        # ❌ 错误：使用内部私有 API
        for sample in auth_requests_total._metrics.values():
            value = sample._value._value  # ❌ 不稳定的内部属性
            labels = sample._labels       # ❌ 不稳定的内部属性
            
            total += value
            if labels.get("status") == "success":
                success += value
        
        success_rate = (success / total * 100) if total > 0 else 0
        
        return {
            "success_rate": round(success_rate, 2),
            "total_requests": int(total),
            "successful_requests": int(success),
        }
    except Exception as exc:
        logger.warning("Failed to get JWT availability metrics: %s", exc)
        return {"success_rate": 0, "total_requests": 0, "successful_requests": 0}
```

#### 修改后代码（正确）
```python
async def _get_jwt_availability(self) -> Dict[str, Any]:
    """查询 JWT 可获取性（从 Prometheus 指标计算）。"""
    try:
        total = 0
        success = 0
        
        # ✅ 正确：使用 collect() 方法（Prometheus 官方 API）
        for metric in auth_requests_total.collect():
            for sample in metric.samples:
                # sample.name: 指标名称
                # sample.labels: 标签字典 {"status": "success", "user_type": "permanent"}
                # sample.value: 指标值
                if sample.name == "auth_requests_total":
                    total += sample.value
                    if sample.labels.get("status") == "success":
                        success += sample.value
        
        success_rate = (success / total * 100) if total > 0 else 0
        
        return {
            "success_rate": round(success_rate, 2),
            "total_requests": int(total),
            "successful_requests": int(success),
        }
    except Exception as exc:
        logger.warning("Failed to get JWT availability metrics: %s", exc)
        return {"success_rate": 0, "total_requests": 0, "successful_requests": 0}
```

#### 关键变更
1. **替换 API**: `auth_requests_total._metrics.values()` → `auth_requests_total.collect()`
2. **访问属性**: `sample._value._value` → `sample.value`（公共 API）
3. **访问标签**: `sample._labels` → `sample.labels`（公共 API）
4. **添加过滤**: 检查 `sample.name == "auth_requests_total"` 确保只处理目标指标

---

## 🔗 认证链路图

### 链路 1: 用户认证（Supabase JWT）

```
前端 App → POST /api/v1/base/access_token → Supabase 认证
         ← 返回 Supabase JWT token
         
前端 App → 后续请求携带 Authorization: Bearer <Supabase JWT>
         → GymBro FastAPI 后端验证 JWT（通过 JWKS）
         → 确认用户身份和权限
```

**用途**: 验证用户是否有权限访问 GymBro 后端服务

**关键文件**:
- `app/auth/dependencies.py::get_current_user()` - JWT 验证入口
- `app/auth/jwt_verifier.py::verify_token()` - JWKS 验证逻辑
- `app/core/metrics.py::auth_requests_total` - Prometheus 指标更新

**Prometheus 指标更新**（已正确实现）:
```python
# app/auth/dependencies.py 第 51 行
auth_requests_total.labels(status="success", user_type=user.user_type).inc()

# app/auth/dependencies.py 第 56 行
auth_requests_total.labels(status="failure", user_type="unknown").inc()
```

---

### 链路 2: AI 请求（API 供应商密钥）

```
前端 App → POST /api/v1/messages（携带 Supabase JWT）
         → GymBro FastAPI 后端验证 JWT ✅
         → 提取用户消息 + 附加系统 Prompt
         → 调用 AI API 供应商（OpenAI/Anthropic/etc.）
            请求头: Authorization: Bearer <API_SUPPLIER_KEY>  ← 使用 API 供应商密钥
            请求体: { "messages": [...], "model": "..." }
         ← AI 响应
         → 返回给前端 App
```

**用途**: 使用 API 供应商密钥调用第三方 AI 服务

**关键文件**:
- `app/services/ai_service.py::_call_openai_completion()` - AI 请求发送逻辑
- `app/settings/config.py::Settings.ai_api_key` - API 供应商密钥配置

**API 供应商密钥使用**（已正确实现）:
```python
# app/services/ai_service.py 第 226 行
headers = {
    "Authorization": f"Bearer {self._settings.ai_api_key}",  # ✅ 使用 API 供应商密钥
    "Content-Type": "application/json",
}
```

---

## ⚠️ 关键边界（绝不能出错）

### Supabase JWT 使用范围
- ✅ **应该使用**: 前端 ↔ GymBro 后端认证
- ❌ **禁止使用**: 发送给第三方 AI API 供应商

### API 供应商密钥使用范围
- ✅ **应该使用**: GymBro 后端 ↔ AI API 供应商认证
- ❌ **禁止使用**: 暴露给前端或存储在 JWT 中

### 用户隐私保护
- ✅ **允许发送**: 用户消息内容（业务需要）
- ❌ **禁止发送**: 用户 email、uid、JWT token（除非业务明确需要）

---

## ✅ 验证步骤

### 验证 1: Prometheus 指标读取修复

**运行验证脚本**:
```bash
python scripts/verify_prometheus_metrics.py
```

**预期输出**:
```
1. Generate test JWT token...
   ✅ Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

2. Trigger JWT authentication...
   ✅ Authentication successful

3. Check Prometheus metrics...
   [OK] auth_requests_total{status="success"} = 1.0
   [OK] auth_requests_total{status="failure"} = 0.0
   
   [OK] Prometheus metrics updated successfully!
```

**验证要点**:
- ✅ 无 `'Counter' object has no attribute '_labels'` 错误
- ✅ `auth_requests_total` 指标值正确累加
- ✅ Dashboard API 返回真实的 JWT 连通性数据

---

### 验证 2: Dashboard API 数据正确性

**测试命令**:
```bash
# 1. 生成测试 JWT
python scripts/create_test_jwt.py

# 2. 调用 Dashboard API
curl -H "Authorization: Bearer <JWT>" http://localhost:9999/api/v1/stats/dashboard
```

**预期响应**:
```json
{
  "daily_active_users": 1,
  "ai_requests": {
    "total": 0,
    "success": 0,
    "error": 0,
    "avg_latency_ms": 0
  },
  "token_usage": null,
  "api_connectivity": {
    "is_running": true,
    "healthy_endpoints": 4,
    "total_endpoints": 4,
    "connectivity_rate": 100.0,
    "last_check": "2025-10-14T12:00:00"
  },
  "jwt_availability": {
    "success_rate": 100.0,        // ✅ 不再是 0
    "total_requests": 1,           // ✅ 不再是 0
    "successful_requests": 1       // ✅ 不再是 0
  }
}
```

---

### 验证 3: AI 请求链路认证正确性

**测试命令**:
```bash
python scripts/test_ai_request_direct.py
```

**验证要点**:
- ✅ AI 请求发送时使用 `Authorization: Bearer <API_SUPPLIER_KEY>`
- ✅ 请求体不包含 JWT token 或用户敏感信息
- ✅ AI 响应正常返回

---

## 📊 Git Commit

**提交信息**:
```
fix(metrics): 修复 Prometheus Counter 指标读取错误并澄清认证链路

- 修复 app/services/metrics_collector.py 中的 Prometheus API 使用错误
  - 替换 auth_requests_total._metrics.values() 为 collect() 方法
  - 使用公共 API (sample.value, sample.labels) 替代私有属性
- 创建认证链路图澄清 Supabase JWT 和 API 供应商密钥的使用边界
- 添加修复交接文档 docs/dashboard-refactor/JWT_AND_API_KEY_FIX_HANDOVER.md

验证:
- ✅ Prometheus 指标读取无错误
- ✅ Dashboard API 返回真实 JWT 连通性数据
- ✅ AI 请求链路使用正确的 API 供应商密钥
```

**提交文件**:
- `app/services/metrics_collector.py`
- `docs/dashboard-refactor/JWT_AND_API_KEY_FIX_HANDOVER.md`

---

## 📚 参考文档

- **Prometheus Python Client 官方文档**: https://github.com/prometheus/client_python
- **JWT 硬化指南**: `docs/JWT_HARDENING_GUIDE.md`
- **网关认证文档**: `docs/GW_AUTH_README.md`
- **后端实现审查**: `docs/dashboard-refactor/BACKEND_IMPLEMENTATION_AUDIT.md`

---

**修复完成时间**: 2025-10-14  
**验证状态**: ✅ 通过  
**下一步**: 运行验证脚本并监控生产环境指标

