# 匿名用户端点访问限制矩阵

**版本**: v1.0  
**更新时间**: 2025-09-29  
**适用范围**: T2 后端策略与开关（FastAPI）

## 概述

本文档定义了匿名用户（Anonymous Users）在GymBro API中的端点访问权限矩阵。匿名用户通过Supabase匿名登录获得临时访问权限，但受到严格的功能和配额限制。

## 访问权限矩阵

### ✅ 允许访问的端点

| 端点 | 方法 | 描述 | 限制说明 |
|------|------|------|----------|
| `/api/v1/messages` | POST | 创建对话消息 | QPS=5, 日配额=1000 |
| `/api/v1/messages/{message_id}/events` | GET | SSE事件流 | 并发连接≤2 |
| `/api/v1/llm/models` | GET | 获取AI模型列表 | 只读访问 |
| `/health` | GET | 健康检查 | 无限制 |
| `/docs` | GET | API文档 | 无限制 |
| `/openapi.json` | GET | OpenAPI规范 | 无限制 |

### ❌ 禁止访问的端点

#### 管理后台相关
| 端点模式 | 方法 | 描述 | 错误码 |
|----------|------|------|--------|
| `/api/v1/admin/*` | ALL | 管理后台所有功能 | 403 |
| `/api/v1/base/*` | ALL | 基础信息管理 | 403 |
| `/api/v1/user/*` | ALL | 用户管理 | 403 |
| `/api/v1/role/*` | ALL | 角色管理 | 403 |
| `/api/v1/menu/*` | ALL | 菜单管理 | 403 |
| `/api/v1/api/*` | ALL | API管理 | 403 |
| `/api/v1/dept/*` | ALL | 部门管理 | 403 |
| `/api/v1/auditlog/*` | ALL | 审计日志查看 | 403 |

#### 公开分享相关
| 端点模式 | 方法 | 描述 | 错误码 |
|----------|------|------|--------|
| `/api/v1/conversations/{id}/share` | POST | 创建公开分享 | 403 |
| `/api/v1/public_shares/*` | ALL | 公开分享管理 | 403 |

#### 批量操作相关
| 端点模式 | 方法 | 描述 | 错误码 |
|----------|------|------|--------|
| `/api/v1/messages/batch` | POST | 批量消息操作 | 403 |
| `/api/v1/conversations/batch` | POST | 批量对话操作 | 403 |

#### LLM管理相关
| 端点模式 | 方法 | 描述 | 错误码 |
|----------|------|------|--------|
| `/api/v1/llm/models` | POST/PUT/DELETE | 模型管理操作 | 403 |
| `/api/v1/llm/prompts/*` | ALL | 提示词管理 | 403 |

## 限流配置

### 匿名用户专用限制
```bash
# QPS限制（每秒请求数）
RATE_LIMIT_ANONYMOUS_QPS=5

# 日配额限制
RATE_LIMIT_ANONYMOUS_DAILY=1000

# SSE并发连接限制
SSE_MAX_CONCURRENT_PER_ANONYMOUS_USER=2
```

### 对比：永久用户限制
```bash
# QPS限制
RATE_LIMIT_PER_USER_QPS=10

# 日配额限制
RATE_LIMIT_PER_USER_DAILY=1000

# SSE并发连接限制
SSE_MAX_CONCURRENT_PER_USER=2
```

## 错误响应格式

### 403 访问被拒绝
```json
{
  "status": 403,
  "code": "ANONYMOUS_ACCESS_DENIED",
  "message": "Anonymous users cannot access this endpoint",
  "trace_id": "abc123def456",
  "hint": "Please upgrade your account to access this feature"
}
```

### 429 限流触发
```json
{
  "status": 429,
  "code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded: User QPS limit exceeded",
  "trace_id": "abc123def456",
  "hint": "Please upgrade your account to access higher limits"
}
```

## 策略实现

### 策略门中间件
- **文件**: `app/core/policy_gate.py`
- **功能**: 在请求处理前检查匿名用户权限
- **位置**: 在限流中间件之前执行

### 限流增强
- **文件**: `app/core/rate_limiter.py`
- **功能**: 根据用户类型应用不同的限流阈值
- **支持**: QPS、日配额、SSE并发的分级限制

### SSE并发控制
- **文件**: `app/core/sse_guard.py`
- **功能**: 根据用户类型限制SSE连接数
- **策略**: 匿名用户并发连接数更低

## 配置开关

### 全局开关
```bash
# 启用/禁用匿名用户支持
ANON_ENABLED=true
```

### 回滚策略
```bash
# 紧急关闭匿名支持
ANON_ENABLED=false

# 或设置极高阈值"软禁用"
RATE_LIMIT_ANONYMOUS_QPS=999999
SSE_MAX_CONCURRENT_PER_ANONYMOUS_USER=999
```

## 日志记录

### 成功访问日志
```json
{
  "event": "jwt_verification_success",
  "trace_id": "abc123def456",
  "subject": "user_uuid",
  "user_type": "anonymous",
  "audience": "authenticated",
  "issuer": "https://project.supabase.co/auth/v1"
}
```

### 访问被拒绝日志
```json
{
  "level": "WARNING",
  "message": "匿名用户访问受限端点被拒绝",
  "path": "/api/v1/admin/users",
  "method": "GET",
  "trace_id": "abc123def456"
}
```

### 限流触发日志
```json
{
  "level": "INFO",
  "message": "限流命中",
  "ip": "192.168.1.100",
  "user_id": "user_uuid",
  "user_type": "anonymous",
  "reason": "User QPS limit exceeded",
  "retry_after": 60,
  "trace_id": "abc123def456"
}
```

## 升级提示

当匿名用户遇到限制时，系统会在错误响应的`hint`字段中提供升级建议：

- **访问限制**: "Please upgrade your account to access this feature"
- **配额限制**: "Please upgrade your account to access higher limits"
- **并发限制**: "Please upgrade your account for higher concurrency"

## 监控指标

建议在观测系统中添加以下维度：

- `user_type`: "anonymous" | "permanent"
- `endpoint_access_denied_count`: 按端点统计的拒绝次数
- `anonymous_rate_limit_hit_rate`: 匿名用户限流命中率
- `anonymous_sse_rejection_rate`: 匿名用户SSE连接拒绝率

## 测试验证

### 基础功能测试
1. 匿名用户成功发送消息
2. 匿名用户成功建立SSE连接
3. 匿名用户获取模型列表

### 限制测试
1. 匿名用户访问管理端点被拒绝
2. 匿名用户触发QPS限流
3. 匿名用户触发SSE并发限制

### 升级测试
1. 匿名用户升级为永久用户后权限正常
2. 历史对话数据保持连续性
