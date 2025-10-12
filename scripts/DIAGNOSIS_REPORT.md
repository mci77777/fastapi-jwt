# 服务状态诊断报告

生成时间: 2025-10-12 15:35

## 📊 诊断总结

### ✅ 服务状态（全部正常）

| 服务 | 状态 | 地址 | 说明 |
|------|------|------|------|
| 后端 API | ✅ 运行中 | http://localhost:9999 | 健康检查通过 |
| 前端应用 | ✅ 运行中 | http://localhost:3101 | 页面可访问 |
| API 文档 | ✅ 可访问 | http://localhost:9999/docs | Swagger UI |
| 数据库 | ✅ 正常 | db.sqlite3 (544 KB) | 20 个表，数据完整 |

### ✅ 数据库状态

**表统计**：
- 总表数: 20 个
- 用户表: 1 个用户（本地测试用户）
- AI 配置: 3 个端点，2 个提示词
- 权限配置: 2 个角色，43 个 API，9 个菜单

**认证系统**：
- 类型: Supabase Auth
- URL: https://rykglivrwzcykhhnxwoz.supabase.co
- Issuer: https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1
- JWT 算法: ES256（椭圆曲线数字签名）

---

## 🔍 问题分析

### 问题 1: localStorage 中没有 ACCESS_TOKEN

**根因**：
- ✅ 服务正常运行
- ✅ 数据库正常
- ❌ **用户尚未登录**

**解释**：
- ACCESS_TOKEN 是在用户成功登录后由 Supabase Auth 签发的 JWT token
- 该 token 会自动保存到浏览器的 localStorage 中
- 如果没有登录，localStorage 中不会有 ACCESS_TOKEN

**验证方法**：
```javascript
// 在浏览器控制台执行
localStorage.getItem('ACCESS_TOKEN')
// 如果返回 null，说明未登录
```

---

## ✅ 解决方案

### 方案 1: 完成登录流程（推荐）

#### 步骤 1: 访问登录页面
```
打开浏览器访问: http://localhost:3101
```

由于路由配置 `redirect: '/login'`，未登录用户会自动跳转到登录页面。

#### 步骤 2: 使用 Supabase 账号登录

**如果您已有 Supabase 账号**：
1. 在登录页面输入邮箱和密码
2. 点击登录按钮
3. 登录成功后会自动跳转到主页

**如果您没有 Supabase 账号**：
1. 访问 Supabase Dashboard: https://supabase.com/dashboard/project/rykglivrwzcykhhnxwoz
2. 进入 Authentication → Users
3. 点击 "Add user" 创建测试用户
4. 或使用邮箱注册功能（如果前端有注册页面）

#### 步骤 3: 验证登录成功

在浏览器控制台执行：
```javascript
const token = JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value;
console.log('Token length:', token?.length);
console.log('Token preview:', token?.slice(0, 50) + '...');
```

如果输出类似：
```
Token length: 505
Token preview: eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6...
```

说明登录成功！

---

### 方案 2: 使用测试 Token（仅用于开发测试）

如果无法登录，可以使用后端生成的测试 token：

```bash
# 生成测试 token
python scripts/tmp_verify_hs256.py
```

**注意**：测试 token 使用 HS256 算法，issuer 为 "supabase"，与真实用户 JWT（ES256）不同。

---

## 🧪 验证 WebSocket JWT 功能

### 前提条件
- ✅ 已完成登录
- ✅ localStorage 中有 ACCESS_TOKEN

### 方法 1: 使用浏览器测试工具

1. **打开测试工具**：
   ```
   file:///d:/GymBro/vue-fastapi-admin/scripts/browser_test_ws.html
   ```

2. **点击 "从 localStorage 获取 Token"**

3. **点击 "连接 WebSocket"**

4. **观察日志输出**：
   - ✅ 连接成功: `[WS] ✅ Connected!`
   - ❌ 连接失败: 检查后端日志

### 方法 2: 使用命令行测试

```bash
# 1. 在浏览器控制台复制 token
const token = JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value;
console.log(token);

# 2. 运行验证脚本
python scripts/tmp_verify_es256_jwt.py <粘贴token>
```

### 方法 3: 浏览器控制台直接测试

```javascript
// 在前端应用的浏览器控制台执行
const token = JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value;
const ws = new WebSocket(`ws://localhost:9999/api/v1/ws/dashboard?token=${token}`);
ws.onopen = () => console.log('[WS] ✅ Connected!');
ws.onmessage = (e) => console.log('[WS] 📨', e.data);
ws.onerror = (e) => console.error('[WS] ❌', e);
ws.onclose = (e) => console.log('[WS] 🔌 Closed:', e.code, e.reason);
```

### 预期结果

**成功场景**：
- 浏览器控制台: `[WS] ✅ Connected!`
- 后端日志（Terminal ID 33）:
  ```
  [WS_DEBUG_AUTH] WebSocket JWT verification success: uid=<user-id> user_type=permanent
  WebSocket connection fully accepted
  ```

**失败场景**：
- 如果看到 `JWT verification failed`，检查：
  1. Token 是否过期（重新登录）
  2. Token 格式是否正确（应为 ES256）
  3. 后端日志中的详细错误信息

---

## 📋 快速参考

### 常用命令

```bash
# 检查服务状态
python -X utf8 scripts/check_services.py

# 检查数据库
python -X utf8 scripts/check_database.py

# 验证 JWT token
python scripts/tmp_verify_es256_jwt.py <token>

# 测试 JWKS 密钥加载
python -X utf8 scripts/test_jwks_keys.py
```

### 访问地址

- 前端: http://localhost:3101
- 后端: http://localhost:9999
- API 文档: http://localhost:9999/docs
- 健康检查: http://localhost:9999/api/v1/healthz
- WebSocket 测试工具: file:///d:/GymBro/vue-fastapi-admin/scripts/browser_test_ws.html

### 重要文件

- 配置文件: `.env`
- 数据库: `db.sqlite3`
- 后端日志: Terminal ID 33（运行 `python run.py` 的终端）
- 前端日志: Terminal ID 34（运行 `pnpm dev` 的终端）

---

## 🔧 故障排除

### 问题: 无法访问前端
```bash
# 检查端口占用
netstat -ano | findstr :3101

# 重启前端
cd web && pnpm dev
```

### 问题: 无法访问后端
```bash
# 检查端口占用
netstat -ano | findstr :9999

# 重启后端
python run.py
```

### 问题: 数据库错误
```bash
# 重新初始化数据库
make clean-db
make migrate
make upgrade
```

### 问题: JWT 验证失败
1. 检查 `.env` 中的 `SUPABASE_JWKS_URL` 是否配置
2. 检查 `cryptography` 库是否安装: `pip install cryptography`
3. 重新登录获取新 token
4. 查看后端日志中的详细错误信息

---

## ✅ 结论

**当前状态**: 所有服务运行正常，数据库配置正确

**下一步**: 完成登录流程以获取 ACCESS_TOKEN，然后进行 WebSocket JWT 验证测试

**预计时间**: 5-10 分钟（登录 + 测试）

