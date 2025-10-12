# 🔐 JWT Token 完整指南

## 📊 Token 类型对比

### 1. 测试 Token（当前使用）

**来源**：Dashboard 后端 `/api/v1/base/access_token`

**特征**：
- **算法**：HS256（对称密钥）
- **签发者**：`https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1`
- **用户ID**：`test-user-{username}`（如 `test-user-admin`）
- **密钥ID**：无（kid = null）
- **签名方式**：使用 `SUPABASE_JWT_SECRET` 对称密钥
- **有效期**：1 小时

**示例 Header**：
```json
{
  "alg": "HS256",
  "typ": "JWT"
}
```

**示例 Payload**：
```json
{
  "iss": "https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1",
  "sub": "test-user-admin",
  "aud": "authenticated",
  "exp": 1760259857,
  "iat": 1760256257,
  "email": "admin@test.local",
  "role": "authenticated",
  "is_anonymous": false,
  "user_metadata": {
    "username": "admin",
    "is_admin": true
  },
  "app_metadata": {
    "provider": "test",
    "providers": ["test"]
  }
}
```

**用途**：
- ✅ 本地开发测试
- ✅ 快速验证功能
- ✅ 不依赖外部 Supabase Auth 服务
- ❌ 不适用于生产环境

---

### 2. 真实 Supabase JWT（生产环境）

**来源**：Supabase Auth 服务

**特征**：
- **算法**：ES256（非对称密钥，椭圆曲线数字签名）
- **签发者**：`https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1`
- **用户ID**：真实的 UUID（如 `0b8bd071-92a0-4e47-b52e-8e819b15f094`）
- **密钥ID**：有（kid = `b96e6ca9-9733-483f-b4bb-7039b3102c92`）
- **签名方式**：使用 JWKS 公钥验证
- **有效期**：可配置（通常 1 小时）

**示例 Header**：
```json
{
  "alg": "ES256",
  "typ": "JWT",
  "kid": "b96e6ca9-9733-483f-b4bb-7039b3102c92"
}
```

**示例 Payload**：
```json
{
  "iss": "https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1",
  "sub": "0b8bd071-92a0-4e47-b52e-8e819b15f094",
  "aud": "authenticated",
  "exp": 1760259857,
  "iat": 1760256257,
  "email": "user@example.com",
  "role": "authenticated",
  "email_confirmed_at": "2025-01-01T00:00:00Z",
  "phone": "",
  "confirmed_at": "2025-01-01T00:00:00Z",
  "user_metadata": {},
  "app_metadata": {
    "provider": "email",
    "providers": ["email"]
  }
}
```

**用途**：
- ✅ 生产环境用户认证
- ✅ 真实用户数据
- ✅ 完整的 Supabase Auth 功能（密码重置、邮箱验证等）
- ❌ 需要配置 Supabase Auth 服务

---

### 3. Supabase 内部密钥

**来源**：ANON_KEY 或 SERVICE_ROLE_KEY

**特征**：
- **算法**：HS256
- **签发者**：`"supabase"`（不是完整 URL）
- **用户ID**：无（用于服务端 API 调用）
- **角色**：`anon` 或 `service_role`

**用途**：
- ✅ 服务端 API 调用
- ✅ 匿名访问
- ❌ 不用于用户认证

---

## 🔧 如何区分 Token 类型

### 方法 1：使用分析脚本

```bash
python -X utf8 scripts/analyze_jwt.py "<your_token>"
```

### 方法 2：手动检查

```javascript
// 在浏览器控制台执行
const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...';
const header = JSON.parse(atob(token.split('.')[0]));
const payload = JSON.parse(atob(token.split('.')[1]));

console.log('算法:', header.alg);
console.log('密钥ID:', header.kid);
console.log('用户ID:', payload.sub);

// 判断逻辑
if (header.alg === 'HS256' && payload.sub.startsWith('test-user-')) {
    console.log('✅ 测试 Token（Dashboard 后端生成）');
} else if (header.alg === 'ES256' && header.kid) {
    console.log('✅ 真实 Supabase JWT');
} else if (header.alg === 'HS256' && payload.iss === 'supabase') {
    console.log('✅ Supabase 内部密钥');
}
```

---

## 🚀 端到端测试方案

### 方案 A：使用 Token 注入工具（推荐）

**工具地址**：`file:///d:/GymBro/vue-fastapi-admin/scripts/inject_token_to_browser.html`

**步骤**：

1. **打开工具**（已自动打开）

2. **自动登录**：
   - 点击 "🚀 自动登录并获取 Token" 按钮
   - 系统自动调用 `POST /api/v1/base/access_token`
   - 使用默认凭证：`admin` / `123456`

3. **注入 Token**：
   - 点击 "💉 注入 Token" 按钮
   - Token 自动保存到 `localStorage.ACCESS_TOKEN`

4. **验证 Token**：
   - 点击 "✅ 验证 Token" 按钮
   - 检查 token 是否有效、是否过期

5. **测试 WebSocket**：
   - 点击 "🔌 测试 WebSocket 连接" 按钮
   - 观察连接状态和消息

**预期结果**：
```
✅ 登录成功！
算法: HS256 | 用户: test-user-admin | 有效期: 2025-10-12 17:04:17

✅ Token 已注入到 localStorage
现在可以刷新前端应用 (http://localhost:3101) 或测试 WebSocket 连接

✅ WebSocket 连接成功！
URL: ws://localhost:9999/api/v1/ws/dashboard
JWT 验证通过
```

---

### 方案 B：前端应用登录

**步骤**：

1. **打开前端**：http://localhost:3101

2. **输入凭证**：
   - 用户名：`admin`
   - 密码：`123456`

3. **点击登录**

4. **验证成功**：
   - 页面跳转到 Dashboard
   - localStorage 中有 ACCESS_TOKEN

**验证方法**：
```javascript
// 在前端应用的浏览器控制台执行
const token = JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value;
console.log('Token:', token?.slice(0, 50) + '...');
console.log('Length:', token?.length);
```

---

### 方案 C：命令行自动化

**步骤**：

1. **自动登录并获取 Token**：
```bash
python -X utf8 scripts/auto_login.py
```

2. **分析 Token**：
```bash
# Token 已保存到 scripts/.last_token.txt
python -X utf8 scripts/analyze_jwt.py "$(cat scripts/.last_token.txt)"
```

3. **验证 Token**：
```bash
python -X utf8 scripts/tmp_verify_es256_jwt.py "$(cat scripts/.last_token.txt)"
```

---

## 🔍 localStorage 问题解答

### 问题：为什么浏览器测试工具无法读取 ACCESS_TOKEN？

**原因**：
1. **跨域限制**：`file://` 协议的页面无法访问 `http://localhost:3101` 的 localStorage
2. **不同源**：每个源（协议 + 域名 + 端口）有独立的 localStorage

**解决方案**：

#### 方案 1：使用 Token 注入工具
- 打开 `inject_token_to_browser.html`
- 点击 "自动登录并获取 Token"
- 点击 "注入 Token"
- Token 会保存到**当前页面**的 localStorage

#### 方案 2：在前端应用中登录
- 打开 http://localhost:3101
- 登录后，Token 会保存到 `http://localhost:3101` 的 localStorage
- 然后在**同一个浏览器标签页**中测试 WebSocket

#### 方案 3：手动注入
```javascript
// 在前端应用（http://localhost:3101）的浏览器控制台执行
const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'; // 从 auto_login.py 获取
localStorage.setItem('ACCESS_TOKEN', JSON.stringify({value: token}));
location.reload(); // 刷新页面
```

---

## 📋 完整测试流程

### 流程 1：使用注入工具（最简单）

```
1. 打开 inject_token_to_browser.html
   ↓
2. 点击 "自动登录并获取 Token"
   ↓
3. 点击 "注入 Token"
   ↓
4. 点击 "测试 WebSocket 连接"
   ↓
5. 观察连接状态和后端日志
```

### 流程 2：使用前端应用

```
1. 打开 http://localhost:3101
   ↓
2. 输入 admin / 123456
   ↓
3. 点击登录
   ↓
4. 在浏览器控制台测试 WebSocket:
   const token = JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value;
   const ws = new WebSocket(`ws://localhost:9999/api/v1/ws/dashboard?token=${token}`);
   ws.onopen = () => console.log('✅ Connected!');
   ↓
5. 观察连接状态和后端日志
```

### 流程 3：命令行 + 浏览器

```
1. 运行: python -X utf8 scripts/auto_login.py
   ↓
2. 复制输出的 token
   ↓
3. 在浏览器控制台执行:
   localStorage.setItem('ACCESS_TOKEN', JSON.stringify({value: '<token>'}));
   ↓
4. 测试 WebSocket 连接
```

---

## ✅ 验证步骤和预期结果

### 验证点 1：Token 获取成功

**检查**：
```bash
python -X utf8 scripts/auto_login.py
```

**预期输出**：
```
✅ 登录成功！
Token 长度: 505
算法: HS256
用户ID: test-user-admin
过期时间: 2025-10-12 17:04:17 (剩余 60 分钟)
```

### 验证点 2：Token 已注入 localStorage

**检查**：
```javascript
// 在浏览器控制台执行
const stored = localStorage.getItem('ACCESS_TOKEN');
console.log('Stored:', !!stored);
console.log('Value:', JSON.parse(stored||'{}').value?.slice(0, 50) + '...');
```

**预期输出**：
```
Stored: true
Value: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJod...
```

### 验证点 3：WebSocket 连接成功

**检查**：浏览器控制台和后端日志

**预期输出（浏览器）**：
```
[WS] ✅ Connected!
[WS] 📨 Message: {"type":"connection","data":"Connected to dashboard"}
```

**预期输出（后端日志）**：
```
[WS_DEBUG_ENTRY] WebSocket endpoint called, token length: 505
[WS_DEBUG] WebSocket connection accepted
[WS_DEBUG_AUTH] get_current_user_ws called
2025-10-12 16:xx:xx | INFO | JWT verification successful
[WS_DEBUG_AUTH] WebSocket JWT verification success: uid=test-user-admin user_type=permanent
[WS_DEBUG] WebSocket connection fully accepted
```

---

## 🛠️ 故障排除

### 问题 1：自动登录失败

**症状**：`❌ 登录失败: HTTP 500`

**原因**：后端服务未运行

**解决**：
```bash
python -X utf8 scripts/check_services.py
# 如果后端未运行，启动它
python run.py
```

### 问题 2：Token 验证失败

**症状**：`❌ Token 验证失败: invalid_token`

**原因**：
- Token 已过期
- JWT 密钥配置错误

**解决**：
```bash
# 1. 重新登录获取新 token
python -X utf8 scripts/auto_login.py

# 2. 检查 JWT 配置
cat .env | grep SUPABASE_JWT_SECRET
```

### 问题 3：WebSocket 连接失败

**症状**：`WebSocket connection failed`

**原因**：
- Token 未注入到 localStorage
- Token 格式错误
- 后端服务未运行

**解决**：
```bash
# 1. 验证 token
python -X utf8 scripts/tmp_verify_es256_jwt.py "<token>"

# 2. 检查后端服务
python -X utf8 scripts/check_services.py

# 3. 查看后端日志
# 在运行 python run.py 的终端中查看错误信息
```

---

## 📚 相关文档

- **登录指南**：`scripts/LOGIN_GUIDE.md`
- **诊断报告**：`scripts/DIAGNOSIS_REPORT.md`
- **JWT 分析工具**：`scripts/analyze_jwt.py`
- **自动登录脚本**：`scripts/auto_login.py`
- **Token 注入工具**：`scripts/inject_token_to_browser.html`
- **WebSocket 测试工具**：`scripts/browser_test_ws.html`

---

## 🎯 总结

### Token 类型
- ✅ **测试 Token**：HS256，由 Dashboard 后端生成，用于本地开发
- ✅ **真实 Supabase JWT**：ES256，由 Supabase Auth 签发，用于生产环境

### localStorage 问题
- ✅ **原因**：跨域限制，不同源有独立的 localStorage
- ✅ **解决**：使用 Token 注入工具或在前端应用中登录

### 端到端测试
- ✅ **最简单**：使用 `inject_token_to_browser.html` 工具
- ✅ **最真实**：在前端应用中登录
- ✅ **最灵活**：命令行 + 浏览器手动注入

**所有工具已准备就绪，选择您喜欢的方式开始测试！** 🚀

