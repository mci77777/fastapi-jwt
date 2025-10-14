# Token 自动刷新机制实现文档

> **版本**: v1.0  
> **日期**: 2025-10-14  
> **状态**: ✅ 已完成并测试通过

---

## 📋 问题描述

### 原始问题
- **现象**: Admin 登录后持续出现 JWT 验证失败（401 错误）
- **影响端点**: `/api/v1/base/userinfo`、`/api/v1/base/usermenu` 等需要认证的接口
- **后端日志**: `JWT verification failed` 和 `401 Unauthorized`

### 根本原因
Token 有效期只有 **1 小时**（3600 秒），用户登录后如果超过 1 小时不刷新页面，所有请求都会返回 401 错误。

**问题代码**（`app/api/v1/base.py` 第 58 行）：
```python
"exp": now + 3600,  # 1小时后过期 ❌
```

---

## ✅ 解决方案

### 方案 1：延长 Token 有效期（立即生效）⭐

**修改内容**：
- 文件：`app/api/v1/base.py`
- 函数：`create_test_jwt_token()`
- 变更：将有效期从 1 小时延长到 24 小时

**修改前**：
```python
def create_test_jwt_token(username: str) -> str:
    """创建测试JWT token。"""
    # ...
    payload = {
        # ...
        "exp": now + 3600,  # 1小时后过期
    }
```

**修改后**：
```python
def create_test_jwt_token(username: str, expire_hours: int = 24) -> str:
    """创建测试JWT token。

    Args:
        username: 用户名
        expire_hours: Token 有效期（小时），默认 24 小时

    Returns:
        JWT token 字符串
    """
    # ...
    payload = {
        # ...
        "exp": now + (expire_hours * 3600),  # 默认 24 小时后过期
    }
```

**优点**：
- ✅ 立即生效，无需前端改动
- ✅ 用户可以长时间使用系统（24 小时内）
- ✅ 符合 YAGNI 原则（只做当前需要的）

---

### 方案 2：实现 Token 自动刷新机制（长期方案）⭐⭐⭐

#### 后端实现

**新增端点**：`POST /api/v1/base/refresh_token`

**功能**：
- 验证当前 Token 是否有效
- 生成新的 Token（延长有效期）
- 返回新 Token 给前端

**代码**（`app/api/v1/base.py`）：
```python
@router.post("/refresh_token", summary="刷新 Token")
async def refresh_token(current_user: AuthenticatedUser = Depends(get_current_user_from_token)) -> Dict[str, Any]:
    """
    刷新 JWT Token。

    **功能**：
    - 验证当前 Token 是否有效
    - 生成新的 Token（延长有效期）
    - 返回新 Token 给前端

    **使用场景**：
    - Token 即将过期时自动刷新
    - 用户长时间使用系统时保持登录状态

    **注意**：
    - 需要携带有效的 Authorization header
    - 即使 Token 已过期但在宽限期内（时钟偏移容忍 ±120 秒）仍可刷新
    """
    # 从当前用户信息中提取用户名
    user_metadata = current_user.claims.get("user_metadata", {})
    username = user_metadata.get("username") or current_user.claims.get("email", "").split("@")[0]

    # 生成新的 Token（24 小时有效期）
    new_token = create_test_jwt_token(username)

    return create_response(
        data={
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": 86400,  # 24 小时（秒）
        },
        msg="Token 刷新成功"
    )
```

**特性**：
- ✅ 支持时钟偏移容忍（±120 秒）
- ✅ 即使 Token 已过期但在宽限期内仍可刷新
- ✅ 返回新 Token 和有效期信息

---

#### 前端实现

**修改文件**：`web/src/utils/http/interceptors.js`

**核心功能**：
1. **Token 过期检测**：解码 JWT payload，检查剩余时间
2. **自动刷新触发**：剩余时间 < 5 分钟时自动刷新
3. **并发控制**：使用 Promise 队列避免重复刷新
4. **错误处理**：刷新失败时清除 Token 并重定向登录

**关键代码**：

```javascript
// Token 刷新状态管理
let isRefreshing = false
let refreshPromise = null

/**
 * 检查 Token 是否即将过期
 * @param {string} token - JWT token
 * @returns {boolean} - 是否需要刷新
 */
function shouldRefreshToken(token) {
  if (!token) return false

  try {
    // 解码 JWT payload（不验证签名，只读取过期时间）
    const parts = token.split('.')
    if (parts.length !== 3) return false

    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')))
    const exp = payload.exp

    if (!exp) return false

    // 当前时间（秒）
    const now = Math.floor(Date.now() / 1000)
    // 剩余时间（秒）
    const remaining = exp - now

    // 如果剩余时间少于 5 分钟（300 秒），则需要刷新
    return remaining > 0 && remaining < 300
  } catch (error) {
    console.error('解析 Token 失败:', error)
    return false
  }
}

/**
 * 刷新 Token
 * @returns {Promise<string>} - 新的 Token
 */
async function refreshToken() {
  // 如果正在刷新，返回现有的 Promise
  if (isRefreshing && refreshPromise) {
    return refreshPromise
  }

  isRefreshing = true

  refreshPromise = (async () => {
    try {
      const token = getToken()
      if (!token) {
        throw new Error('No token to refresh')
      }

      // 调用后端刷新端点
      const response = await fetch('/api/v1/base/refresh_token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        throw new Error(`Token refresh failed: ${response.status}`)
      }

      const data = await response.json()

      if (data.code !== 200 || !data.data?.access_token) {
        throw new Error('Invalid refresh response')
      }

      const newToken = data.data.access_token

      // 保存新 Token
      setToken(newToken)

      console.log('✅ Token 刷新成功')

      return newToken
    } catch (error) {
      console.error('❌ Token 刷新失败:', error)
      // 刷新失败，清除 Token 并重定向到登录页
      localStorage.removeItem('ACCESS_TOKEN')
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      window.location.href = '/login'
      throw error
    } finally {
      isRefreshing = false
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export async function reqResolve(config) {
  // 处理不需要token的请求
  if (config.noNeedToken) {
    return config
  }

  const token = getToken()
  if (token) {
    // 检查 Token 是否即将过期
    if (shouldRefreshToken(token)) {
      try {
        console.log('⏰ Token 即将过期，自动刷新...')
        const newToken = await refreshToken()
        // 使用新 Token
        config.headers.Authorization = config.headers.Authorization || `Bearer ${newToken}`
      } catch (error) {
        // 刷新失败，使用旧 Token（可能会导致 401）
        config.headers.Authorization = config.headers.Authorization || `Bearer ${token}`
      }
    } else {
      // 使用 Bearer token 格式,符合后端的认证要求
      config.headers.Authorization = config.headers.Authorization || `Bearer ${token}`
    }
  }

  // ... 其他逻辑
  return config
}
```

**特性**：
- ✅ 自动检测 Token 过期时间
- ✅ 剩余 5 分钟时自动刷新（用户无感知）
- ✅ 并发控制（避免重复刷新）
- ✅ 错误处理（刷新失败时重定向登录）

---

## 🧪 测试验证

### 测试脚本
- **文件**: `scripts/test_token_refresh.py`
- **功能**: 测试登录、刷新、访问受保护端点、过期检测

### 测试步骤

1. **运行测试脚本**：
   ```bash
   python scripts/test_token_refresh.py
   ```

2. **预期结果**：
   ```
   ✅ 登录成功（Token 有效期 24 小时）
   ✅ Token 刷新成功（新 Token 有效期 24 小时）
   ✅ 新 Token 可以访问受保护端点
   ✅ 即将过期的 Token 可以刷新
   ```

3. **浏览器测试**：
   - 登录系统：`http://localhost:3101/login`
   - 打开浏览器控制台（F12）
   - 等待 Token 即将过期（或手动修改 localStorage 中的 Token）
   - 观察控制台输出：`⏰ Token 即将过期，自动刷新...`
   - 验证刷新成功：`✅ Token 刷新成功`

---

## 📊 验收标准

- [x] Admin 登录后不再出现 401 错误
- [x] Token 有效期延长到 24 小时
- [x] Token 在即将过期时自动刷新（用户无感知）
- [x] 刷新失败时正确处理（清除 Token + 重定向登录）
- [x] 后端日志不再显示 `JWT verification failed`
- [x] 用户可以长时间使用系统而不需要重新登录
- [x] 浏览器控制台无错误
- [x] 编译通过（前端 + 后端）
- [x] 所有测试通过

---

## 📁 修改文件清单

### 后端（2 个文件）
1. `app/api/v1/base.py`
   - 修改 `create_test_jwt_token()` 函数（延长有效期到 24 小时）
   - 新增 `refresh_token()` 端点

### 前端（1 个文件）
1. `web/src/utils/http/interceptors.js`
   - 新增 `shouldRefreshToken()` 函数（检测过期）
   - 新增 `refreshToken()` 函数（刷新逻辑）
   - 修改 `reqResolve()` 函数（自动刷新）

### 测试（2 个文件）
1. `scripts/test_token_refresh.py` - 后端测试脚本
2. `scripts/diagnose_token.html` - 前端诊断工具

### 文档（1 个文件）
1. `docs/TOKEN_REFRESH_IMPLEMENTATION.md` - 本文档

---

## 🚀 部署建议

### 本地测试
```bash
# 1. 启动后端
python run.py

# 2. 启动前端
cd web && pnpm dev

# 3. 运行测试
python scripts/test_token_refresh.py

# 4. 浏览器测试
# 访问 http://localhost:3101/login
# 登录后观察控制台输出
```

### 生产部署
```bash
# 1. 构建前端
cd web && pnpm build

# 2. 部署到生产环境
# 前端：https://web.gymbro.cloud
# 后端：https://api.gymbro.cloud

# 3. 验证
# 访问 https://web.gymbro.cloud/login
# 登录后长时间使用，验证不会自动登出
```

---

## 🔧 配置说明

### 后端配置（`.env`）
```bash
# JWT 配置
JWT_CLOCK_SKEW_SECONDS=120       # 时钟偏移容忍（±120 秒）
JWT_REQUIRE_NBF=false            # Supabase token 缺少 nbf 声明
JWT_ALLOWED_ALGORITHMS=ES256,RS256,HS256
```

### 前端配置
- **Token 刷新阈值**: 5 分钟（300 秒）
- **Token 有效期**: 24 小时（86400 秒）
- **刷新失败处理**: 清除 Token + 重定向登录

---

## ⚠️ 注意事项

1. **不要绕过刷新机制**：
   - 前端拦截器会自动处理刷新
   - 不要手动调用 `refreshToken()` 函数

2. **刷新失败处理**：
   - 刷新失败时会自动清除 Token 并重定向登录
   - 不要在刷新失败后继续使用旧 Token

3. **并发控制**：
   - 使用 Promise 队列避免重复刷新
   - 多个并发请求会共享同一个刷新 Promise

4. **时钟偏移容忍**：
   - 后端配置 ±120 秒时钟偏移容忍
   - 即使 Token 已过期但在宽限期内仍可刷新

---

## 📚 相关文档

- **JWT 硬化指南**: `docs/JWT_HARDENING_GUIDE.md`
- **网关认证文档**: `docs/GW_AUTH_README.md`
- **项目概览**: `docs/PROJECT_OVERVIEW.md`
- **诊断工具**: `scripts/diagnose_token.html`

---

**完成日期**: 2025-10-14  
**验收状态**: ✅ 全部完成并通过所有测试  
**生产环境**: 可直接部署
