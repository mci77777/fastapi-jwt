# 🔐 登录指南

## 快速登录

### 默认测试账号

```
用户名: admin
密码: 123456
```

### 登录步骤

1. **打开前端应用**：http://localhost:3101
   - 浏览器会自动跳转到登录页面

2. **输入凭证**：
   - 用户名：`admin`
   - 密码：`123456`

3. **点击登录按钮**

4. **验证登录成功**：
   - 页面跳转到 Dashboard
   - localStorage 中有 ACCESS_TOKEN

---

## 验证登录状态

### 方法 1：浏览器控制台

```javascript
// 检查 token 是否存在
const token = JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value;
console.log('Token exists:', !!token);
console.log('Token length:', token?.length);
console.log('Token preview:', token?.slice(0, 50) + '...');
```

### 方法 2：解码 Token

```javascript
// 解码 token header 和 payload
const token = JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value;
const [h, p] = token.split('.');
const decode = s => JSON.parse(atob(s.replace(/-/g, '+').replace(/_/g, '/')));

console.log('Header:', decode(h));
console.log('Payload:', decode(p));
```

**预期输出**：
```javascript
Header: {
  "alg": "HS256",
  "typ": "JWT"
}

Payload: {
  "iss": "https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1",
  "sub": "test-user-admin",
  "aud": "authenticated",
  "email": "admin@test.local",
  "role": "authenticated",
  "is_anonymous": false,
  "user_metadata": {
    "username": "admin",
    "is_admin": true
  }
}
```

---

## 关于测试 Token

### Token 类型

当前登录端点 (`POST /api/v1/base/access_token`) 返回的是**测试 JWT token**：

- **算法**: HS256（对称密钥）
- **Issuer**: `https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1`
- **签名密钥**: `SUPABASE_JWT_SECRET`
- **有效期**: 1 小时

### 与真实 Supabase JWT 的区别

| 特性 | 测试 Token | 真实 Supabase JWT |
|------|-----------|------------------|
| 算法 | HS256 | ES256 |
| 签名方式 | 对称密钥 | 非对称密钥（JWKS） |
| 签发者 | 后端 `/base/access_token` | Supabase Auth |
| 用途 | 开发测试 | 生产环境 |

### 为什么使用测试 Token？

根据代码注释（`app/api/v1/base.py` 第 140-145 行）：

```python
"""
用户名密码登录接口。

**注意**: 当前版本使用Supabase JWT认证，此端点为兼容性端点。
实际生产环境应该通过Supabase Auth进行认证。
"""
```

这是一个**兼容性端点**，用于：
1. 本地开发测试
2. 不依赖外部 Supabase Auth 服务
3. 快速验证功能

---

## 测试 WebSocket JWT 验证

### 前提条件

- ✅ 已登录（用户名 `admin`，密码 `123456`）
- ✅ localStorage 中有 ACCESS_TOKEN

### 方法 1：使用浏览器测试工具

1. **打开测试工具**：
   ```
   file:///d:/GymBro/vue-fastapi-admin/scripts/browser_test_ws.html
   ```

2. **点击 "从 localStorage 获取 Token"**

3. **点击 "连接 WebSocket"**

4. **观察日志**：
   - ✅ 成功：`[WS] ✅ Connected!`
   - ❌ 失败：查看错误信息

### 方法 2：浏览器控制台

```javascript
// 在前端应用的浏览器控制台执行
const token = JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value;
const ws = new WebSocket(`ws://localhost:9999/api/v1/ws/dashboard?token=${token}`);

ws.onopen = () => console.log('[WS] ✅ Connected!');
ws.onmessage = (e) => console.log('[WS] 📨 Message:', e.data);
ws.onerror = (e) => console.error('[WS] ❌ Error:', e);
ws.onclose = (e) => console.log('[WS] 🔌 Closed:', e.code, e.reason);
```

### 方法 3：命令行验证

```powershell
# 1. 在浏览器控制台复制 token
# const token = JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value;
# console.log(token);

# 2. 运行验证脚本（注意：不要使用 <token>，而是粘贴实际的 token）
python scripts/tmp_verify_es256_jwt.py eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**注意**：`<token>` 是占位符，需要替换为实际的 token 字符串！

---

## 预期结果

### 成功场景

**浏览器控制台**：
```
[WS] ✅ Connected!
[WS] 📨 Message: {"type":"connection","data":"Connected to dashboard"}
```

**后端日志**（Terminal ID 33）：
```
[WS_DEBUG_ENTRY] WebSocket endpoint called, token length: 505
[WS_DEBUG] WebSocket connection accepted
[WS_DEBUG_AUTH] get_current_user_ws called
2025-10-12 15:xx:xx | INFO | JWT verification successful
[WS_DEBUG_AUTH] WebSocket JWT verification success: uid=test-user-admin user_type=permanent
[WS_DEBUG] WebSocket connection fully accepted
```

### 失败场景

**如果看到 JWT 验证失败**：

1. **检查 token 是否过期**：
   ```javascript
   const token = JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value;
   const payload = JSON.parse(atob(token.split('.')[1]));
   const exp = new Date(payload.exp * 1000);
   console.log('Token expires at:', exp);
   console.log('Is expired:', exp < new Date());
   ```

2. **重新登录**：
   - 退出登录
   - 重新输入 `admin` / `123456`
   - 获取新 token

3. **检查后端日志**：
   - 查看详细的错误信息
   - 确认 JWT 验证器配置正确

---

## 故障排除

### 问题 1：登录按钮无响应

**检查**：
- 浏览器控制台是否有错误
- 网络请求是否成功（F12 → Network）
- 后端服务是否运行

**解决**：
```bash
# 检查后端服务
python -X utf8 scripts/check_services.py
```

### 问题 2：登录失败（401 错误）

**原因**：
- 用户名或密码错误
- 后端服务未运行

**解决**：
- 确认用户名：`admin`
- 确认密码：`123456`
- 检查后端日志

### 问题 3：Token 验证失败

**原因**：
- Token 已过期（1 小时有效期）
- JWT 密钥配置错误

**解决**：
```bash
# 1. 重新登录获取新 token
# 2. 检查 .env 配置
cat .env | grep SUPABASE_JWT_SECRET

# 3. 验证 JWT 配置
python -X utf8 scripts/test_jwks_keys.py
```

---

## 快速参考

### 登录凭证
```
用户名: admin
密码: 123456
```

### 访问地址
- 前端: http://localhost:3101
- 后端: http://localhost:9999
- API 文档: http://localhost:9999/docs
- WebSocket 测试: file:///d:/GymBro/vue-fastapi-admin/scripts/browser_test_ws.html

### 常用命令
```bash
# 检查服务状态
python -X utf8 scripts/check_services.py

# 验证 JWT token
python scripts/tmp_verify_es256_jwt.py <实际的token>

# 测试 JWKS
python -X utf8 scripts/test_jwks_keys.py
```

---

## 下一步

1. ✅ 登录成功
2. ✅ 获取 ACCESS_TOKEN
3. ✅ 测试 WebSocket 连接
4. ✅ 验证 JWT 端到端功能

**完成后，您就可以开始使用完整的 WebSocket JWT 验证功能了！**

