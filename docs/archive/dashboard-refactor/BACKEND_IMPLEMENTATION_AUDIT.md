# Dashboard 后端实现审查报告

**审查时间**: 2025-10-14  
**审查范围**: 后端数据采集逻辑（用户活跃度、AI 请求统计、JWT 认证统计）  
**审查结果**: ⚠️ **发现 1 个关键问题**

---

## 📋 审查总结

### ✅ 已正确实现的功能

1. **用户活跃度记录** - 正常工作
2. **AI 请求统计记录** - 正常工作
3. **数据库查询逻辑** - 正常工作

### ❌ 发现的问题

1. **Prometheus `auth_requests_total` 指标从未被更新** - **关键问题**
   - **影响**: JWT 连通性显示为 0%（前端无法获取真实数据）
   - **根因**: 缺少 `auth_requests_total.labels(status=..., user_type=...).inc()` 调用
   - **位置**: `app/auth/dependencies.py::get_current_user()` 或 `app/auth/jwt_verifier.py::verify_token()`

---

## 1. 用户活跃度记录 ✅

### 1.1 数据写入逻辑

**文件**: `app/auth/dependencies.py` (第 50-76 行)

**触发时机**: 每次 JWT 认证成功后自动调用

**写入逻辑**:
```python
async def _record_user_activity(request: Request, user: AuthenticatedUser) -> None:
    """记录用户活跃度到 user_activity_stats 表。"""
    try:
        from app.db.sqlite_manager import get_sqlite_manager
        
        db = get_sqlite_manager(request.app)
        today = datetime.now().date().isoformat()
        
        await db.execute(
            """
            INSERT INTO user_activity_stats (user_id, user_type, activity_date, request_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, activity_date)
            DO UPDATE SET
                request_count = request_count + 1,
                last_request_at = CURRENT_TIMESTAMP
        """,
            [user.uid, user.user_type, today],
        )
    except Exception as exc:
        # 不阻塞主流程，仅记录日志
        logger.warning("Failed to record user activity: %s", exc)
```

**调用链**:
```
用户请求 → get_current_user() → JWT 验证成功 → _record_user_activity() → 写入 user_activity_stats 表
```

**数据库验证**:
```bash
sqlite3 db.sqlite3 "SELECT COUNT(*), MAX(last_request_at) FROM user_activity_stats;"
# 输出: 5|2025-10-14 03:27:01

sqlite3 db.sqlite3 "SELECT * FROM user_activity_stats ORDER BY last_request_at DESC LIMIT 3;"
# 输出:
# 5554|test-user-admin|permanent|2025-10-14|707|2025-10-14 00:59:50|2025-10-14 03:27:01|...
# 4884|test-user-admin|permanent|2025-10-13|670|2025-10-13 08:11:31|2025-10-13 11:26:45|...
# 10|test-user-admin|permanent|2025-10-12|4851|2025-10-12 00:47:06|2025-10-12 14:03:22|...
```

**结论**: ✅ **数据写入逻辑正确，数据库有真实数据**

---

## 2. AI 请求统计记录 ✅

### 2.1 数据写入逻辑

**文件**: `app/services/ai_service.py` (第 248-302 行)

**触发时机**: 每次 AI 请求完成后（成功或失败）

**写入逻辑**:
```python
async def _record_ai_request(
    self,
    user_id: str,
    endpoint_id: Optional[int],
    model: Optional[str],
    latency_ms: float,
    success: bool,
) -> None:
    """记录 AI 请求统计到 ai_request_stats 表。"""
    if not self._db:
        # 未注入 SQLiteManager，跳过记录
        return
    
    try:
        today = datetime.now().date().isoformat()
        
        await self._db.execute(
            """
            INSERT INTO ai_request_stats (
                user_id, endpoint_id, model, request_date,
                count, total_latency_ms, success_count, error_count
            )
            VALUES (?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(user_id, endpoint_id, model, request_date)
            DO UPDATE SET
                count = count + 1,
                total_latency_ms = total_latency_ms + ?,
                success_count = success_count + ?,
                error_count = error_count + ?,
                updated_at = CURRENT_TIMESTAMP
        """,
            [
                user_id,
                endpoint_id,
                model or "unknown",
                today,
                latency_ms,
                1 if success else 0,
                0 if success else 1,
                latency_ms,
                1 if success else 0,
                0 if success else 1,
            ],
        )
    except Exception as exc:
        # 不阻塞主流程，仅记录日志
        logger.warning("Failed to record AI request stats: %s", exc)
```

**调用链**:
```
POST /api/v1/messages → AIService.run_conversation() → AI 请求完成 → _record_ai_request() → 写入 ai_request_stats 表
```

**调用位置**:
1. **成功路径**: `app/services/ai_service.py` 第 180 行（`finally` 块）
2. **失败路径**: `app/services/ai_service.py` 第 121 行（用户信息获取失败）

**数据库验证**:
```bash
sqlite3 db.sqlite3 "SELECT COUNT(*), SUM(count) FROM ai_request_stats;"
# 输出: 1|1
```

**结论**: ✅ **数据写入逻辑正确，数据库有真实数据**

---

## 3. JWT 认证统计 ❌ **关键问题**

### 3.1 Prometheus 指标定义

**文件**: `app/core/metrics.py` (第 21-25 行)

```python
# Prometheus指标定义
# 1. 认证请求总数（按状态和用户类型分类）
auth_requests_total = Counter(
    'auth_requests_total',
    'Total number of authentication requests',
    ['status', 'user_type']
)
```

### 3.2 指标读取逻辑

**文件**: `app/services/metrics_collector.py` (第 119-149 行)

```python
async def _get_jwt_availability(self) -> Dict[str, Any]:
    """查询 JWT 可获取性（从 Prometheus 指标计算）。"""
    # 从 Prometheus Counter 获取数据
    try:
        # 获取所有 auth_requests_total 指标
        total = 0
        success = 0
        
        # 遍历所有标签组合
        for sample in auth_requests_total._metrics.values():
            value = sample._value._value
            labels = sample._labels
            
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

### 3.3 ❌ **问题：指标从未被更新**

**搜索结果**:
```bash
# 搜索 auth_requests_total.labels 调用
findstr /S /N "auth_requests_total.labels" *.py
# 输出: （无结果）
```

**结论**: ❌ **`auth_requests_total` 指标从未被更新，导致 JWT 连通性始终显示为 0%**

### 3.4 预期的更新位置

**应该在以下位置更新指标**:

#### 位置 1: JWT 验证成功时
**文件**: `app/auth/dependencies.py::get_current_user()` (第 31-47 行)

**当前代码**:
```python
async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> AuthenticatedUser:
    """解析并验证当前请求的 Bearer Token。"""
    
    token = _extract_bearer_token(authorization)
    verifier = get_jwt_verifier()
    user = verifier.verify_token(token)  # ← JWT 验证成功
    request.state.user = user
    request.state.token = token
    request.state.user_type = user.user_type
    
    # 记录用户活跃度（Phase 1）
    await _record_user_activity(request, user)
    
    return user
```

**缺少的代码**:
```python
# ❌ 缺少 Prometheus 指标更新
from app.core.metrics import auth_requests_total

# 应该在 JWT 验证成功后添加：
auth_requests_total.labels(status="success", user_type=user.user_type).inc()
```

#### 位置 2: JWT 验证失败时
**文件**: `app/auth/jwt_verifier.py::verify_token()` (第 200-294 行)

**当前代码**:
```python
def verify_token(self, token: str) -> AuthenticatedUser:
    """验证 JWT token 并返回用户信息。"""
    try:
        # ... JWT 验证逻辑 ...
        return AuthenticatedUser(uid=subject, claims=payload, user_type=user_type)
    except jwt.ExpiredSignatureError:
        # ❌ 缺少 Prometheus 指标更新
        raise self._create_unauthorized_error("token_expired", "Token has expired")
    except jwt.InvalidTokenError as exc:
        # ❌ 缺少 Prometheus 指标更新
        raise self._create_unauthorized_error("invalid_token", f"Invalid token: {exc}")
```

**缺少的代码**:
```python
# ❌ 缺少 Prometheus 指标更新
from app.core.metrics import auth_requests_total

# 应该在异常处理中添加：
auth_requests_total.labels(status="failure", user_type="unknown").inc()
```

---

## 4. 修复建议

### 4.1 修复 `auth_requests_total` 指标更新

#### 修复方案 1: 在 `get_current_user()` 中更新（推荐）

**文件**: `app/auth/dependencies.py`

**修改位置**: 第 31-47 行

**修改内容**:
```python
async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> AuthenticatedUser:
    """解析并验证当前请求的 Bearer Token。"""
    
    from app.core.metrics import auth_requests_total  # 新增导入
    
    token = _extract_bearer_token(authorization)
    verifier = get_jwt_verifier()
    
    try:
        user = verifier.verify_token(token)
        request.state.user = user
        request.state.token = token
        request.state.user_type = user.user_type
        
        # 记录用户活跃度（Phase 1）
        await _record_user_activity(request, user)
        
        # 记录 JWT 验证成功（新增）
        auth_requests_total.labels(status="success", user_type=user.user_type).inc()
        
        return user
    except HTTPException:
        # 记录 JWT 验证失败（新增）
        auth_requests_total.labels(status="failure", user_type="unknown").inc()
        raise
```

#### 修复方案 2: 在 `jwt_verifier.py` 中更新（备选）

**文件**: `app/auth/jwt_verifier.py`

**修改位置**: 第 200-294 行

**修改内容**:
```python
def verify_token(self, token: str) -> AuthenticatedUser:
    """验证 JWT token 并返回用户信息。"""
    from app.core.metrics import auth_requests_total  # 新增导入
    
    try:
        # ... JWT 验证逻辑 ...
        
        # 记录成功验证（新增）
        auth_requests_total.labels(status="success", user_type=user_type).inc()
        
        return AuthenticatedUser(uid=subject, claims=payload, user_type=user_type)
    except jwt.ExpiredSignatureError:
        # 记录失败验证（新增）
        auth_requests_total.labels(status="failure", user_type="unknown").inc()
        raise self._create_unauthorized_error("token_expired", "Token has expired")
    except jwt.InvalidTokenError as exc:
        # 记录失败验证（新增）
        auth_requests_total.labels(status="failure", user_type="unknown").inc()
        raise self._create_unauthorized_error("invalid_token", f"Invalid token: {exc}")
```

### 4.2 推荐方案对比

| 方案 | 优点 | 缺点 | 推荐度 |
|------|------|------|--------|
| 方案 1（`get_current_user()`） | 集中管理，易于维护 | 仅覆盖 `get_current_user()` 路径 | ⭐⭐⭐⭐⭐ |
| 方案 2（`jwt_verifier.py`） | 覆盖所有 JWT 验证路径 | 增加 `jwt_verifier.py` 复杂度 | ⭐⭐⭐ |

**推荐**: 使用**方案 1**（在 `get_current_user()` 中更新），因为：
1. 所有需要认证的端点都通过 `get_current_user()` 依赖注入
2. 集中管理，易于维护
3. 与用户活跃度记录逻辑保持一致

---

## 5. 验证步骤

### 5.1 修复后验证

1. **重启后端服务**:
   ```bash
   python run.py
   ```

2. **触发 JWT 认证**:
   ```bash
   # 登录获取 token
   curl -X POST http://localhost:9999/api/v1/base/access_token \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "123456"}'
   
   # 使用 token 访问受保护端点
   curl -X GET http://localhost:9999/api/v1/stats/dashboard \
     -H "Authorization: Bearer <token>"
   ```

3. **检查 Prometheus 指标**:
   ```bash
   curl http://localhost:9999/api/v1/metrics | grep auth_requests_total
   # 预期输出:
   # auth_requests_total{status="success",user_type="permanent"} 1.0
   ```

4. **检查 Dashboard 显示**:
   ```bash
   # 访问前端 Dashboard
   open http://localhost:3101/dashboard
   
   # 检查 JWT 连通性卡片
   # 预期显示: 100%（而非 0%）
   ```

---

## 6. 总结

### 6.1 审查结果

| 功能模块 | 状态 | 问题描述 | 优先级 |
|---------|------|---------|--------|
| 用户活跃度记录 | ✅ 正常 | 无 | - |
| AI 请求统计记录 | ✅ 正常 | 无 | - |
| JWT 认证统计 | ❌ **异常** | `auth_requests_total` 指标从未被更新 | **P0** |

### 6.2 影响范围

- **前端 Dashboard**: JWT 连通性显示为 0%（数据失真）
- **监控系统**: 无法追踪 JWT 认证成功率和失败率
- **告警系统**: 无法基于 JWT 认证失败率触发告警

### 6.3 修复优先级

**P0 - 立即修复**: 添加 `auth_requests_total` 指标更新逻辑

---

**审查完成时间**: 2025-10-14  
**下一步**: 实施修复方案 1（在 `get_current_user()` 中更新 Prometheus 指标）

