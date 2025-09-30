# Supabase 部署检查清单

## 概述

本文档提供了完整的 Supabase 配置和部署检查清单，确保 GymBro API 能够正确集成 Supabase 认证和数据库功能。

## ✅ 已完成的配置

### 1. 后端架构 ✅
- **JWT 验证中间件**: 完整实现，支持 JWKS 和静态 JWK
- **Provider 抽象层**: 支持 Supabase 和内存 Provider
- **AI 对话接口**: 完整的 SSE 流式响应
- **错误处理**: 统一的异常处理和追踪
- **配置管理**: 环境变量驱动的配置系统

### 2. API 端点 ✅
- `POST /api/v1/messages` - 创建对话消息
- `GET /api/v1/messages/{message_id}/events` - SSE 事件流
- 完整的 JWT 认证保护
- 统一的错误响应格式

### 3. 开发工具 ✅
- **配置检查脚本**: `scripts/check_config.py`
- **API 测试脚本**: `scripts/test_api.py`
- **Supabase 验证脚本**: `scripts/verify_supabase_config.py`
- **Postman 测试集合**: `docs/jwt改造/GymBro_API_Tests.postman_collection.json`

## 🔧 需要管理员完成的配置步骤

### 第一步：创建 Supabase 项目

1. 访问 [Supabase Dashboard](https://supabase.com/dashboard)
2. 创建新项目，记录以下信息：
   - **Project ID**: `your-project-id`
   - **Project URL**: `https://your-project-id.supabase.co`
   - **Service Role Key**: 从 API 设置页面获取
   - **JWKS URL**: `https://your-project-id.supabase.co/.well-known/jwks.json`

### 第二步：配置环境变量

编辑 `.env` 文件，替换以下占位符：

```bash
# 替换这些值为您的实际 Supabase 配置
SUPABASE_PROJECT_ID=your-actual-project-id
SUPABASE_JWKS_URL=https://your-actual-project-id.supabase.co/.well-known/jwks.json
SUPABASE_ISSUER=https://your-actual-project-id.supabase.co
SUPABASE_AUDIENCE=your-actual-project-id
SUPABASE_SERVICE_ROLE_KEY=your-actual-service-role-key

# 替换为您的 AI 服务配置
AI_API_KEY=your-actual-openai-api-key
```

### 第三步：创建数据库表

在 Supabase SQL Editor 中执行：`docs/jwt改造/supabase_schema.sql`

### 第四步：验证配置

运行配置检查脚本：
```bash
python scripts/check_config.py
```

## 🧪 测试验证步骤

### 1. 基础服务测试

```bash
# 启动服务
python run.py

# 运行 API 测试
python scripts/test_api.py
```

### 2. Supabase 集成测试

```bash
# 验证 Supabase 配置
python scripts/verify_supabase_config.py
```

### 3. 端到端测试

使用 Postman 导入测试集合：`docs/jwt改造/GymBro_API_Tests.postman_collection.json`

测试流程：
1. 在 Supabase 中注册测试用户
2. 获取有效的 JWT token
3. 测试 API 端点
4. 验证数据同步

## 📋 部署前检查清单

- [ ] Supabase 项目已创建
- [ ] 环境变量已正确配置
- [ ] 数据库表已创建
- [ ] RLS 策略已设置
- [ ] 配置检查脚本通过
- [ ] API 测试通过
- [ ] Supabase 连接测试通过
- [ ] 端到端测试通过

## 🚀 生产部署建议

### 安全配置
1. **HTTPS**: 生产环境必须使用 HTTPS
2. **CORS**: 限制允许的源域名
3. **密钥管理**: 使用环境变量或密钥管理服务
4. **日志**: 配置结构化日志和监控

### 性能优化
1. **缓存**: 启用 JWKS 缓存
2. **连接池**: 配置数据库连接池
3. **限流**: 添加 API 限流中间件
4. **监控**: 集成 APM 工具

### 示例生产配置

```bash
# 生产环境配置示例
DEBUG=false
FORCE_HTTPS=true
CORS_ALLOW_ORIGINS=["https://yourdomain.com"]
ALLOWED_HOSTS=["yourdomain.com"]

# 使用实际的生产值
SUPABASE_PROJECT_ID=prod-project-id
SUPABASE_SERVICE_ROLE_KEY=prod-service-key
AI_API_KEY=prod-openai-key
```

## 🔍 故障排除

### 常见问题

1. **JWT 验证失败**
   - 检查 SUPABASE_PROJECT_ID 是否正确
   - 验证 JWKS_URL 可访问性
   - 确认 token 格式正确

2. **数据库连接失败**
   - 验证 SERVICE_ROLE_KEY 权限
   - 检查网络连接
   - 确认表和 RLS 策略正确

3. **API 响应错误**
   - 查看服务日志
   - 检查 trace_id 追踪请求
   - 验证请求格式

### 日志分析

服务提供详细的结构化日志：
- 请求追踪 (X-Trace-Id)
- JWT 验证过程
- 数据库操作
- AI 服务调用

## 📞 支持

如需技术支持，请提供：
1. 错误日志和 trace_id
2. 配置检查脚本输出
3. 具体的错误重现步骤

---

**注意**: 请确保在生产环境中保护好所有敏感信息，包括 Service Role Key 和 API Keys。
