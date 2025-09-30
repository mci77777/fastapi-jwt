# 匿名用户后端策略与配置

**版本**: v1.0  
**更新时间**: 2025-09-29  
**任务**: T2 - 后端策略与开关（FastAPI）

## 概述

本文档描述了GymBro FastAPI后端对匿名用户支持的完整实现，包括配置管理、JWT上下文增强、策略门控制、限流降级和日志记录等功能。

## 架构设计

### 中间件执行顺序
```
Request → TraceIDMiddleware → PolicyGateMiddleware → RateLimitMiddleware → Application
```

### 核心组件
1. **配置管理**: `app/settings/config.py` - 匿名用户相关配置
2. **JWT验证器**: `app/auth/jwt_verifier.py` - 提取is_anonymous声明
3. **策略门**: `app/core/policy_gate.py` - 端点访问控制
4. **限流器**: `app/core/rate_limiter.py` - 分级限流策略
5. **SSE守卫**: `app/core/sse_guard.py` - 并发连接控制

## 配置参数

### 主开关
```bash
# 启用/禁用匿名用户支持
ANON_ENABLED=true
```

### 限流配置
```bash
# 匿名用户QPS限制（每秒请求数）
RATE_LIMIT_ANONYMOUS_QPS=5

# 匿名用户日配额限制
RATE_LIMIT_ANONYMOUS_DAILY=1000

# 匿名用户SSE并发连接限制
SSE_MAX_CONCURRENT_PER_ANONYMOUS_USER=2
```

### 对比配置
```bash
# 永久用户配置（参考）
RATE_LIMIT_PER_USER_QPS=10
RATE_LIMIT_PER_USER_DAILY=1000
SSE_MAX_CONCURRENT_PER_USER=2
```

## JWT上下文增强

### AuthenticatedUser类扩展
```python
@dataclass
class AuthenticatedUser:
    uid: str
    claims: Dict[str, Any]
    user_type: str = "permanent"  # "anonymous" or "permanent"
    
    @property
    def is_anonymous(self) -> bool:
        return self.user_type == "anonymous"
```

### JWT验证流程
1. **声明提取**: 从JWT payload中提取`is_anonymous`字段
2. **类型判断**: `is_anonymous=true` → `user_type="anonymous"`
3. **上下文设置**: 将`user_type`附加到`request.state`
4. **日志记录**: 在验证成功日志中包含`user_type`维度

### 代码示例
```python
# JWT验证器中的用户类型提取
is_anonymous = payload.get("is_anonymous", False)
user_type = "anonymous" if is_anonymous else "permanent"

# 创建用户对象
user = AuthenticatedUser(uid=subject, claims=payload, user_type=user_type)

# 设置请求上下文
request.state.user_type = user.user_type
```

## 策略门控制

### 实现原理
- **中间件**: `PolicyGateMiddleware`
- **执行时机**: 在限流中间件之前
- **检查逻辑**: 基于路径模式和HTTP方法判断访问权限

### 限制策略
```python
# 匿名用户禁止访问的端点模式
anonymous_restricted_patterns = [
    r'^/api/v1/admin/.*$',           # 管理后台
    r'^/api/v1/base/.*$',            # 基础信息
    r'^/api/v1/user/.*$',            # 用户管理
    r'^/api/v1/role/.*$',            # 角色管理
    r'^/api/v1/conversations/.+/share$',  # 公开分享
    r'^/api/v1/messages/batch$',     # 批量操作
]

# 匿名用户允许访问的端点模式
anonymous_allowed_patterns = [
    r'^/api/v1/messages$',           # POST 创建消息
    r'^/api/v1/messages/[^/]+/events$',  # GET SSE事件流
    r'^/api/v1/llm/models$',         # GET 获取模型列表
]
```

### 错误响应
```json
{
  "status": 403,
  "code": "ANONYMOUS_ACCESS_DENIED",
  "message": "Anonymous users cannot access this endpoint",
  "trace_id": "abc123def456",
  "hint": "Please upgrade your account to access this feature"
}
```

## 限流降级策略

### 分级限流实现
```python
def _get_user_qps_bucket(self, user_id: str, is_anonymous: bool = False) -> TokenBucket:
    qps_limit = (
        self.settings.rate_limit_anonymous_qps if is_anonymous 
        else self.settings.rate_limit_per_user_qps
    )
    return TokenBucket(capacity=qps_limit, refill_rate=qps_limit)
```

### 限流维度
1. **QPS限流**: 匿名用户5 QPS vs 永久用户10 QPS
2. **日配额**: 匿名用户1000次/天 vs 永久用户1000次/天
3. **SSE并发**: 匿名用户2连接 vs 永久用户2连接

### 限流日志
```json
{
  "level": "INFO",
  "message": "限流命中",
  "user_id": "user_uuid",
  "user_type": "anonymous",
  "reason": "User QPS limit exceeded",
  "retry_after": 60,
  "trace_id": "abc123def456"
}
```

## SSE并发控制

### 动态限制
```python
# 根据用户类型设置不同的并发限制
is_anonymous = user.user_type == "anonymous"
max_concurrent = (
    self.settings.sse_max_concurrent_per_anonymous_user if is_anonymous 
    else self.settings.sse_max_concurrent_per_user
)
```

### 拒绝响应
```json
{
  "status": 429,
  "code": "SSE_CONCURRENCY_LIMIT_EXCEEDED",
  "message": "SSE concurrency limit exceeded: User concurrent SSE limit exceeded (2/2)",
  "trace_id": "abc123def456"
}
```

## 日志记录增强

### 结构化日志维度
所有相关日志都包含`user_type`维度，支持按用户类型进行分析：

```json
{
  "event": "jwt_verification_success",
  "user_type": "anonymous",
  "trace_id": "abc123def456",
  "subject": "user_uuid"
}
```

### 关键日志事件
1. **JWT验证成功**: 包含用户类型
2. **策略门拒绝**: 记录被拒绝的端点和方法
3. **限流触发**: 包含用户类型和限流原因
4. **SSE连接管理**: 记录用户类型和并发状态

## 部署配置

### 环境变量示例
```bash
# .env 文件配置
ANON_ENABLED=true
RATE_LIMIT_ANONYMOUS_QPS=5
RATE_LIMIT_ANONYMOUS_DAILY=1000
SSE_MAX_CONCURRENT_PER_ANONYMOUS_USER=2
```

### 配置验证
```python
# 配置类中的验证
class Settings(BaseSettings):
    anon_enabled: bool = Field(True, env="ANON_ENABLED")
    rate_limit_anonymous_qps: int = Field(5, env="RATE_LIMIT_ANONYMOUS_QPS")
    rate_limit_anonymous_daily: int = Field(1000, env="RATE_LIMIT_ANONYMOUS_DAILY")
    sse_max_concurrent_per_anonymous_user: int = Field(2, env="SSE_MAX_CONCURRENT_PER_ANONYMOUS_USER")
```

## 回滚策略

### 一键关闭
```bash
# 完全禁用匿名支持
ANON_ENABLED=false
```

### 软禁用（保持兼容性）
```bash
# 设置极高阈值，实际禁用功能
RATE_LIMIT_ANONYMOUS_QPS=999999
SSE_MAX_CONCURRENT_PER_ANONYMOUS_USER=999
```

## 监控指标

### 建议监控维度
- `user_type`: "anonymous" | "permanent"
- `endpoint_path`: 请求端点路径
- `rate_limit_reason`: 限流触发原因
- `policy_gate_action`: 策略门动作（allow/deny）

### 关键指标
1. **匿名用户请求成功率**: `anonymous_request_success_rate`
2. **匿名用户限流命中率**: `anonymous_rate_limit_hit_rate`
3. **匿名用户策略拒绝率**: `anonymous_policy_denial_rate`
4. **匿名用户SSE连接拒绝率**: `anonymous_sse_rejection_rate`

## 测试场景

### 功能测试
1. ✅ 匿名用户成功创建消息
2. ✅ 匿名用户成功建立SSE连接
3. ✅ 匿名用户获取模型列表
4. ❌ 匿名用户访问管理端点被拒绝
5. ❌ 匿名用户触发限流保护

### 配置测试
1. `ANON_ENABLED=false` 时策略门不生效
2. 限流阈值配置正确应用
3. SSE并发限制按用户类型生效

### 升级测试
1. 匿名用户升级为永久用户后权限正常
2. 用户类型变更后限流阈值自动调整

## 兼容性保证

### 向后兼容
- 现有永久用户功能不受影响
- 现有API契约保持不变
- 现有限流配置继续有效

### 渐进部署
- 可通过`ANON_ENABLED`开关控制功能启用
- 支持A/B测试和灰度发布
- 出现问题时可快速回滚
