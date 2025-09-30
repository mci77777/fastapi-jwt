# Supabase JWT 认证配置指南

## 概述

本文档说明如何在 GymBro FastAPI 项目中正确配置 Supabase JWT 认证。

## ✅ 已完成的配置

### 1. 环境变量配置

您的 `.env` 文件已正确配置：

```bash
# Supabase 项目配置
SUPABASE_PROJECT_ID=rykglivrwzcykhhnxwoz
SUPABASE_URL=https://rykglivrwzcykhhnxwoz.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# JWT 验证配置
SUPABASE_JWKS_URL=https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1/.well-known/jwks.json
SUPABASE_ISSUER=https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1
SUPABASE_AUDIENCE=authenticated

# 数据库表配置
SUPABASE_CHAT_TABLE=ai_chat_messages
```

### 2. JWT 验证器

项目已包含完整的 JWT 验证系统：
- `app/auth/jwt_verifier.py` - JWT 验证核心逻辑
- `app/auth/dependencies.py` - FastAPI 依赖注入
- `app/auth/provider.py` - 认证提供者抽象
- `app/auth/supabase_provider.py` - Supabase 集成

## 🔧 需要完成的步骤

### 第一步：创建数据库表

1. 登录 [Supabase Dashboard](https://supabase.com/dashboard)
2. 选择您的项目 `rykglivrwzcykhhnxwoz`
3. 进入 "SQL Editor"
4. 运行 `scripts/create_supabase_tables.sql` 中的 SQL 脚本

## 🔒 JWT 验证器硬化功能

### 新增硬化配置

项目现已支持 JWT 验证器硬化功能，提供更好的安全性和 Supabase 兼容性：

```bash
# JWT 验证硬化配置
JWT_CLOCK_SKEW_SECONDS=120      # 时钟偏移容忍度
JWT_MAX_FUTURE_IAT_SECONDS=120  # iat 最大未来时间
JWT_REQUIRE_NBF=false           # Supabase 兼容：nbf 可选
JWT_ALLOWED_ALGORITHMS=ES256,RS256,HS256  # 允许的算法
```

### 主要改进

1. **Supabase 兼容性**: 支持无 `nbf` 声明的 JWT
2. **时钟偏移容忍**: ±120 秒时钟偏移窗口
3. **算法安全**: 限制允许的签名算法
4. **统一错误格式**: 包含 status、code、message、trace_id
5. **增强日志**: 结构化日志记录，包含详细上下文

详细信息请参考 [JWT 硬化指南](./JWT_HARDENING_GUIDE.md)。

### 第二步：验证配置

运行配置验证脚本：

```bash
python scripts/simple_jwt_test.py
```

应该看到：
```
🎉 所有测试通过！JWT 配置正确。
```

### 第三步：启动服务器

```bash
python run.py
```

### 第四步：测试 API 端点

```bash
python scripts/test_jwt_api.py
```

## 🔑 JWT Token 获取方式

### 方法一：使用 Supabase 客户端库

在前端应用中：

```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  'https://rykglivrwzcykhhnxwoz.supabase.co',
  'your-anon-key'
)

// 用户登录后获取 JWT
const { data: { session } } = await supabase.auth.getSession()
const jwt = session?.access_token
```

### 方法二：直接从 Supabase Auth API

```bash
# 用户登录
curl -X POST 'https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1/token?grant_type=password' \
-H "apikey: YOUR_ANON_KEY" \
-H "Content-Type: application/json" \
-d '{
  "email": "user@example.com",
  "password": "password"
}'
```

## 📋 API 端点测试

### 获取用户信息

```bash
curl -X GET 'http://localhost:8000/api/v1/me' \
-H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### 创建消息

```bash
curl -X POST 'http://localhost:8000/api/v1/messages' \
-H "Authorization: Bearer YOUR_JWT_TOKEN" \
-H "Content-Type: application/json" \
-d '{
  "content": "Hello, AI!",
  "conversation_id": "test-conversation"
}'
```

### SSE 事件流

```bash
curl -X GET 'http://localhost:8000/api/v1/messages/MESSAGE_ID/events' \
-H "Authorization: Bearer YOUR_JWT_TOKEN" \
-H "Accept: text/event-stream"
```

## 🔍 故障排除

### 常见错误

1. **401 Unauthorized**
   - 检查 JWT token 是否有效
   - 确认 issuer 和 audience 配置正确

2. **JWKS 获取失败**
   - 检查网络连接
   - 确认 SUPABASE_JWKS_URL 正确

3. **数据库连接失败**
   - 确认 SUPABASE_SERVICE_ROLE_KEY 正确
   - 检查数据库表是否已创建

### 调试工具

- `scripts/simple_jwt_test.py` - 验证 JWT 配置
- `scripts/test_jwt_api.py` - 测试 API 端点
- FastAPI 自动文档：http://localhost:8000/docs

## 📚 相关文档

- [Supabase Auth 文档](https://supabase.com/docs/guides/auth)
- [JWT 验证指南](https://supabase.com/docs/guides/auth/jwts)
- [Row Level Security](https://supabase.com/docs/guides/auth/row-level-security)
