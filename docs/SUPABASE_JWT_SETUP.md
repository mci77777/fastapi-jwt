# Supabase JWT 验证落地指南

## 概览

本文描述如何在 GymBro FastAPI 项目中正确接入 Supabase JWT 验证链路，并提供验证脚本与排障手册。

---

## 1. 基础配置

首先准备 `.env` 文件并补齐以下关键变量：

```bash
# Supabase 项目信息
SUPABASE_PROJECT_ID=rykglivrwzcykhhnxwoz
SUPABASE_URL=https://rykglivrwzcykhhnxwoz.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# JWT 验证参数
SUPABASE_JWKS_URL=https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_ISSUER=https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1
SUPABASE_AUDIENCE=authenticated

# 数据表
SUPABASE_CHAT_TABLE=ai_chat_messages
```

项目已内置 JWT 验证组件：

- `app/auth/jwt_verifier.py`：核心验证逻辑  
- `app/auth/dependencies.py`：FastAPI 依赖注入  
- `app/auth/provider.py`、`app/auth/supabase_provider.py`：用户信息提供与同步

---

## 2. 初始化数据库

1. 登录 [Supabase Dashboard](https://supabase.com/dashboard)  
2. 选择项目 `rykglivrwzcykhhnxwoz`  
3. 打开 “SQL Editor”  
4. 执行仓库中的 `scripts/create_supabase_tables.sql`

---

## 3. JWT 验证加固参数

项目默认开启安全基线：

```bash
JWT_CLOCK_SKEW_SECONDS=120
JWT_MAX_FUTURE_IAT_SECONDS=120
JWT_REQUIRE_NBF=false      # Supabase 匿名用户未强制提供 nbf
JWT_ALLOWED_ALGORITHMS=ES256,RS256,HS256
```

关键考虑：

1. 确保 Supabase 返回的 token 携带 `is_anonymous` / `providers` 等自定义 Claims  
2. 校准服务端与客户端时间（±2 分钟）  
3. 统一返回格式：`status`、`code`、`message`、`trace_id`  
4. 完整记录验证链路日志，方便排障  
5. 详见 `docs/JWT_HARDENING_GUIDE.md`

---

## 4. 校验脚本与服务启动

### 4.1 运行配置体检

```bash
python scripts/verify_supabase_config.py
python scripts/verify_jwks_cache.py
```

若输出 `PASS` 或成功摘要，说明配置、JWKS、缓存均可用。

### 4.2 启动本地服务

```bash
python run.py
```

---

## 5. 验证 API 工作流

### 5.1 冒烟测试

```bash
python scripts/smoke_test.py
```

该脚本会依次执行：注册测试用户 → 获取 JWT → 调用 `/api/v1/messages` → 监听 SSE → 校验数据库写入。

### 5.2 进一步回归（可选）

```bash
python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py
python scripts/k5_build_and_test.py
```

---

## 6. 获取 JWT Token

### 方案 A：Supabase JS 客户端

```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient('https://rykglivrwzcykhhnxwoz.supabase.co', 'your-anon-key')
const { data: { session } } = await supabase.auth.getSession()
const jwt = session?.access_token
```

### 方案 B：调用 Supabase Auth API

```bash
curl -X POST 'https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1/token?grant_type=password' \
  -H "apikey: YOUR_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}'
```

---

## 7. API 调用示例

### 获取用户信息

```bash
curl -X GET 'http://localhost:9999/api/v1/base/userinfo' \
  -H "token: YOUR_JWT_TOKEN"
```

### 创建消息

```bash
curl -X POST 'http://localhost:9999/api/v1/messages' \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"Hello, AI!","conversation_id":"test-conversation"}'
```

### 订阅 SSE 事件

```bash
curl -N 'http://localhost:9999/api/v1/messages/MESSAGE_ID/events' \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Accept: text/event-stream"
```

---

## 8. 常见问题排障

| 现象 | 可能原因 | 建议 |
|------|----------|------|
| 401 Unauthorized | Token 失效或 Audience/Issuer 不匹配 | 重新生成 Token，确认 `.env` 配置一致 |
| JWKS 拉取失败 | URL 配置错误或网络阻断 | 检查 `SUPABASE_JWKS_URL`，确认代理/防火墙 |
| 数据库查询失败 | Service Role Key 不正确或表不存在 | 重新复制 Key，确认表已建并配置 RLS |
| SSE 无事件 | 消息未写入或队列延迟 | 检查 API 返回的 `message_id`，查看日志 |

---

## 9. 相关脚本速查

- `scripts/verify_supabase_config.py`：环境与权限体检  
- `scripts/verify_jwks_cache.py`：JWKS 缓存 & JWT 验证链路  
- `scripts/smoke_test.py`：端到端冒烟  
- `scripts/verify_gw_auth.py`：网关认证链路  
- `e2e/anon_jwt_sse/scripts/generate_test_token.py`：生成匿名 Token  
- `e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py`：加强版匿名 E2E

---

## 10. 参考资料

- [Supabase Auth](https://supabase.com/docs/guides/auth)  
- [Supabase JWT 指南](https://supabase.com/docs/guides/auth/jwts)  
- [Row Level Security](https://supabase.com/docs/guides/auth/row-level-security)  
- 项目文档：`docs/JWT_HARDENING_GUIDE.md`
