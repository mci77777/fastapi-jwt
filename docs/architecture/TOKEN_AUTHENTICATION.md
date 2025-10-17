# Token 认证架构文档

> GymBro API 的 JWT 认证系统完整指南  
> 包含：JWT 硬化、Token 刷新、Supabase 集成

**文档来源**：合并自以下文档
- `JWT_HARDENING_GUIDE.md` - JWT 验证器硬化指南（238 行）
- `TOKEN_REFRESH_HANDOVER.md` - Token 自动刷新机制（378 行）
- `TOKEN_REFRESH_IMPLEMENTATION.md` - Token 刷新实现细节

---

## 📋 目录

1. [系统概述](#1-系统概述)
2. [JWT 硬化功能](#2-jwt-硬化功能)
3. [Token 刷新机制](#3-token-刷新机制)
4. [Supabase 集成](#4-supabase-集成)
5. [配置参考](#5-配置参考)
6. [故障排查](#6-故障排查)
7. [最佳实践](#7-最佳实践)

---

## 1. 系统概述

### 1.1 认证流程

```
用户登录 → 后端签发 JWT → 前端存储 Token → 携带 Token 访问 API
                ↓
         Token 即将过期（剩余 5 分钟）
                ↓
         自动刷新 Token → 更新存储 → 继续访问
```

### 1.2 核心组件

| 组件 | 文件 | 功能 |
|------|------|------|
| **JWT 验证器** | `app/auth/jwt_verifier.py` | 验证 JWT token，支持 JWKS 和硬化功能 |
| **认证依赖** | `app/auth/dependencies.py` | FastAPI 依赖注入，提供 `get_current_user()` |
| **Token 端点** | `app/api/v1/base.py` | 登录、刷新 Token 端点 |
| **前端拦截器** | `web/src/utils/http/index.js` | Axios 拦截器，自动刷新 Token |
| **用户 Store** | `web/src/store/modules/user.js` | Pinia store，管理用户状态和 Token |

### 1.3 Token 生命周期

| 阶段 | 时间 | 操作 |
|------|------|------|
| **签发** | T+0 | 用户登录，后端签发 24 小时有效期的 JWT |
| **使用** | T+0 ~ T+23h55m | 前端携带 Token 访问 API |
| **预刷新** | T+23h55m | 前端检测到 Token 剩余 5 分钟，自动刷新 |
| **刷新** | T+23h55m | 后端签发新 Token，前端更新存储 |
| **过期** | T+24h | 如果未刷新，Token 过期，用户需重新登录 |

---

## 2. JWT 硬化功能

### 2.1 Supabase JWT 兼容性

**问题**: Supabase 签发的 JWT 通常不包含 `nbf` (not before) 声明，但标准 JWT 验证器可能要求此字段。

**解决方案**: 
- `nbf` 声明现在是可选的（默认 `JWT_REQUIRE_NBF=false`）
- 如果 `nbf` 存在，仍会进行验证
- 完全兼容 Supabase 认证流程

**配置**:
```bash
JWT_REQUIRE_NBF=false  # Supabase 兼容性
```

**代码实现**:
```python
# app/auth/jwt_verifier.py
def verify_token(self, token: str) -> dict:
    options = {
        "verify_signature": True,
        "verify_exp": True,
        "verify_nbf": self.settings.JWT_REQUIRE_NBF,  # 可选
        "verify_iat": True,
        "verify_aud": True,
    }
    return jwt.decode(token, key, algorithms=algorithms, options=options)
```

### 2.2 时钟偏移容忍

**问题**: 分布式系统中服务器时钟可能存在偏差，导致合法 JWT 被错误拒绝。

**解决方案**:
- 支持 ±120 秒的时钟偏移窗口
- 对 `iat` 未来时间进行特殊检查
- 防止时间攻击

**配置**:
```bash
JWT_CLOCK_SKEW_SECONDS=120      # 时钟偏移容忍度
JWT_MAX_FUTURE_IAT_SECONDS=120  # iat 最大未来时间
```

**代码实现**:
```python
# app/auth/jwt_verifier.py
def verify_token(self, token: str) -> dict:
    # 时钟偏移容忍
    leeway = self.settings.JWT_CLOCK_SKEW_SECONDS
    
    # iat 未来时间检查
    if payload.get("iat"):
        now = datetime.now(timezone.utc).timestamp()
        if payload["iat"] > now + self.settings.JWT_MAX_FUTURE_IAT_SECONDS:
            raise JWTError("Token issued too far in the future")
    
    return jwt.decode(token, key, algorithms=algorithms, options=options, leeway=leeway)
```

### 2.3 算法安全限制

**问题**: 某些 JWT 算法存在安全风险或不适合生产环境。

**解决方案**:
- 默认只允许 `ES256`, `RS256`, `HS256`
- 优先推荐 `ES256` (椭圆曲线数字签名)
- 可配置允许的算法列表

**配置**:
```bash
JWT_ALLOWED_ALGORITHMS=ES256,RS256,HS256
```

**代码实现**:
```python
# app/auth/jwt_verifier.py
def verify_token(self, token: str) -> dict:
    # 算法限制
    allowed_algorithms = self.settings.JWT_ALLOWED_ALGORITHMS.split(",")
    
    # 检查 token header 中的算法
    header = jwt.get_unverified_header(token)
    if header.get("alg") not in allowed_algorithms:
        raise JWTError(f"Algorithm {header.get('alg')} not allowed")
    
    return jwt.decode(token, key, algorithms=allowed_algorithms, options=options)
```

### 2.4 统一错误响应

**问题**: JWT 验证失败时，错误信息不一致，难以调试。

**解决方案**:
- 统一错误响应格式
- 包含 Trace ID、错误代码、提示信息
- 区分不同的验证失败原因

**错误响应格式**:
```json
{
  "status": 401,
  "code": "token_expired",
  "message": "JWT token has expired",
  "trace_id": "abc123",
  "hint": "Please refresh your token or login again"
}
```

**错误代码**:
| 代码 | 含义 | 提示 |
|------|------|------|
| `token_missing` | Token 缺失 | 请提供 Authorization header |
| `token_invalid` | Token 格式错误 | 请检查 Token 格式 |
| `token_expired` | Token 过期 | 请刷新 Token 或重新登录 |
| `token_not_yet_valid` | Token 尚未生效 | 请检查服务器时间 |
| `signature_invalid` | 签名验证失败 | Token 可能被篡改 |
| `algorithm_not_allowed` | 算法不允许 | 请使用允许的算法 |

---

## 3. Token 刷新机制

### 3.1 问题背景

**现象**: Admin 登录后持续出现 JWT 验证失败（401 错误）

**根本原因**: Token 有效期只有 1 小时，用户登录后超过 1 小时会自动过期

### 3.2 解决方案

1. **延长 Token 有效期**：从 1 小时延长到 24 小时 ✅
2. **实现自动刷新机制**：Token 即将过期时（剩余 5 分钟）自动刷新 ✅

### 3.3 后端实现

#### 延长 Token 有效期

**文件**: `app/api/v1/base.py`  
**函数**: `create_test_jwt_token()`

```python
def create_test_jwt_token(username: str, expire_hours: int = 24) -> str:
    """创建测试JWT token。

    Args:
        username: 用户名
        expire_hours: Token 有效期（小时），默认 24 小时
    """
    now = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": username,
        "email": f"{username}@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "iss": settings.SUPABASE_ISSUER,
        "iat": now,
        "exp": now + (expire_hours * 3600),  # 默认 24 小时后过期
    }
    return jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
```

#### 新增刷新端点

**文件**: `app/api/v1/base.py`  
**端点**: `POST /api/v1/base/refresh_token`

```python
@router.post("/refresh_token", summary="刷新 Token")
async def refresh_token(
    request: Request,
    user: AuthenticatedUser = Depends(get_current_user)
) -> dict:
    """刷新 JWT token。
    
    - 验证当前 token 有效性
    - 签发新的 24 小时有效期 token
    - 返回新 token 和过期时间
    """
    # 生成新 token
    new_token = create_test_jwt_token(user.username, expire_hours=24)
    
    # 计算过期时间
    expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    
    return {
        "code": 200,
        "message": "Token refreshed successfully",
        "data": {
            "access_token": new_token,
            "token_type": "Bearer",
            "expires_at": expires_at.isoformat(),
            "expires_in": 24 * 3600,  # 秒
        }
    }
```

### 3.4 前端实现

#### Axios 响应拦截器

**文件**: `web/src/utils/http/index.js`

```javascript
// 响应拦截器
service.interceptors.response.use(
  async (response) => {
    // 检查 token 是否即将过期（剩余 5 分钟）
    const token = storage.get(ACCESS_TOKEN_KEY)
    if (token?.value) {
      const payload = JSON.parse(atob(token.value.split('.')[1]))
      const expiresIn = payload.exp - Math.floor(Date.now() / 1000)
      
      // 如果剩余时间少于 5 分钟，自动刷新
      if (expiresIn > 0 && expiresIn < 300) {
        try {
          const { data } = await axios.post('/api/v1/base/refresh_token', {}, {
            headers: { Authorization: `Bearer ${token.value}` }
          })
          
          // 更新 token
          storage.set(ACCESS_TOKEN_KEY, {
            value: data.data.access_token,
            expires: new Date(data.data.expires_at).getTime()
          })
        } catch (error) {
          console.error('Token refresh failed:', error)
        }
      }
    }
    
    return response
  },
  (error) => {
    // 401 错误处理
    if (error.response?.status === 401) {
      const userStore = useUserStore()
      userStore.logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
```

#### 用户 Store

**文件**: `web/src/store/modules/user.js`

```javascript
export const useUserStore = defineStore('user', {
  actions: {
    async refreshToken() {
      try {
        const { data } = await http.post('/api/v1/base/refresh_token')
        
        // 更新 token
        storage.set(ACCESS_TOKEN_KEY, {
          value: data.data.access_token,
          expires: new Date(data.data.expires_at).getTime()
        })
        
        return true
      } catch (error) {
        console.error('Token refresh failed:', error)
        this.logout()
        return false
      }
    }
  }
})
```

---

## 4. Supabase 集成

### 4.1 JWKS 端点

**端点**: `https://<project-id>.supabase.co/auth/v1/.well-known/jwks.json`

**用途**: 获取 Supabase 的公钥，用于验证 JWT 签名

**配置**:
```bash
SUPABASE_URL=https://rykglivrwzcykhhnxwoz.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_JWT_SECRET=<jwt-secret>
SUPABASE_ISSUER=https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1
```

### 4.2 JWT 验证流程

```
1. 前端发送请求 → 携带 Authorization: Bearer <token>
2. 后端拦截请求 → 提取 token
3. JWT 验证器 → 从 JWKS 端点获取公钥
4. JWT 验证器 → 验证签名、过期时间、issuer 等
5. JWT 验证器 → 返回用户信息
6. 后端处理请求 → 返回响应
```

---

## 5. 配置参考

### 5.1 环境变量

```bash
# JWT 硬化配置
JWT_REQUIRE_NBF=false                    # Supabase 兼容性
JWT_CLOCK_SKEW_SECONDS=120               # 时钟偏移容忍度
JWT_MAX_FUTURE_IAT_SECONDS=120           # iat 最大未来时间
JWT_ALLOWED_ALGORITHMS=ES256,RS256,HS256 # 允许的算法

# Supabase 配置
SUPABASE_URL=https://rykglivrwzcykhhnxwoz.supabase.co
SUPABASE_ANON_KEY=<anon-key>
SUPABASE_JWT_SECRET=<jwt-secret>
SUPABASE_ISSUER=https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1

# Token 配置
TOKEN_EXPIRE_HOURS=24                    # Token 有效期（小时）
TOKEN_REFRESH_THRESHOLD=300              # 刷新阈值（秒，5 分钟）
```

### 5.2 代码配置

**文件**: `app/settings/config.py`

```python
class Settings(BaseSettings):
    # JWT 硬化
    JWT_REQUIRE_NBF: bool = False
    JWT_CLOCK_SKEW_SECONDS: int = 120
    JWT_MAX_FUTURE_IAT_SECONDS: int = 120
    JWT_ALLOWED_ALGORITHMS: str = "ES256,RS256,HS256"
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_JWT_SECRET: str
    SUPABASE_ISSUER: str
    
    # Token
    TOKEN_EXPIRE_HOURS: int = 24
    TOKEN_REFRESH_THRESHOLD: int = 300
```

---

## 6. 故障排查

### 6.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| Token 验证失败（401） | Token 过期 | 刷新 Token 或重新登录 |
| Token 验证失败（401） | 签名验证失败 | 检查 JWT_SECRET 配置 |
| Token 验证失败（401） | 算法不允许 | 检查 JWT_ALLOWED_ALGORITHMS 配置 |
| Token 刷新失败 | 刷新端点不可用 | 检查后端服务状态 |
| Token 刷新失败 | 当前 Token 已过期 | 重新登录 |

### 6.2 调试命令

```bash
# 1. 检查 JWT 配置
python scripts/verify_jwks_cache.py

# 2. 解码 JWT token
python scripts/decode_jwt.py <token>

# 3. 测试 JWT 验证
python scripts/test_jwt_complete.py

# 4. 测试 Token 刷新
curl -X POST http://localhost:9999/api/v1/base/refresh_token \
  -H "Authorization: Bearer <token>"
```

---

## 7. 最佳实践

### 7.1 安全建议

1. **使用 HTTPS**：生产环境必须使用 HTTPS 传输 Token
2. **定期轮换密钥**：定期更新 JWT_SECRET
3. **限制 Token 有效期**：不要设置过长的有效期（推荐 24 小时）
4. **实现 Token 黑名单**：用户登出后将 Token 加入黑名单
5. **监控异常登录**：记录和监控 JWT 验证失败的请求

### 7.2 性能优化

1. **缓存 JWKS**：缓存 Supabase 的公钥，减少网络请求
2. **异步刷新**：在后台异步刷新 Token，不阻塞用户操作
3. **批量验证**：对于高并发场景，考虑批量验证 Token

### 7.3 监控指标

| 指标 | 含义 | 告警阈值 |
|------|------|----------|
| `auth_requests_total` | 认证请求总数 | - |
| `jwt_validation_errors_total` | JWT 验证失败总数 | > 100/min |
| `token_refresh_total` | Token 刷新总数 | - |
| `token_refresh_errors_total` | Token 刷新失败总数 | > 10/min |

---

## 📚 相关文档

- **项目概览**: [docs/PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)
- **网关认证**: [docs/GW_AUTH_README.md](../GW_AUTH_README.md)
- **调试指南**: [docs/guides/debugging/DEBUGGING_GUIDE.md](../guides/debugging/DEBUGGING_GUIDE.md)

---

**最后更新**: 2025-10-17  
**维护者**: GymBro Team

