# Supabase 配置指南

## 第一步：创建 Supabase 项目

1. 访问 [Supabase Dashboard](https://supabase.com/dashboard)
2. 点击 "New Project" 创建新项目
3. 填写项目信息：
   - **Project Name**: `gymbro-api` (或您喜欢的名称)
   - **Database Password**: 设置一个强密码并记录下来
   - **Region**: 选择离您最近的区域

## 第二步：获取项目配置信息

项目创建完成后，在项目设置中获取以下信息：

### 1. 项目基本信息
- **Project ID**: 在项目设置 → General 中找到
- **Project URL**: 格式为 `https://[project-id].supabase.co`

### 2. API Keys
在项目设置 → API 中获取：
- **anon public key**: 用于客户端（如果需要）
- **service_role key**: 用于后端服务（重要！）

### 3. JWT 配置信息
在项目设置 → Authentication → Settings 中：
- **JWT Secret**: 用于验证 JWT 签名
- **JWKS URL**: `https://[project-id].supabase.co/.well-known/jwks.json`

## 第三步：配置环境变量

将以下配置复制到您的 `.env` 文件中，并替换相应的值：

```bash
# GymBro API 配置
APP_NAME=GymBro API
APP_DESCRIPTION=GymBro 对话与认证服务
APP_VERSION=0.1.0
DEBUG=true

# CORS 配置
CORS_ALLOW_ORIGINS=*
CORS_ALLOW_METHODS=*
CORS_ALLOW_HEADERS=*
CORS_ALLOW_CREDENTIALS=true

# HTTPS 和主机配置
ALLOWED_HOSTS=*
FORCE_HTTPS=false

# Supabase 配置 - 请替换为您的实际值
SUPABASE_PROJECT_ID=your-project-id-here
SUPABASE_JWKS_URL=https://your-project-id-here.supabase.co/.well-known/jwks.json
SUPABASE_ISSUER=https://your-project-id-here.supabase.co
SUPABASE_AUDIENCE=your-project-id-here
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key-here
SUPABASE_CHAT_TABLE=chat_messages

# JWT 配置
JWKS_CACHE_TTL_SECONDS=900
JWT_LEEWAY_SECONDS=30

# HTTP 配置
HTTP_TIMEOUT_SECONDS=10.0
SSE_HEARTBEAT_SECONDS=15.0
TRACE_HEADER_NAME=x-trace-id

# AI 服务配置 - 请替换为您的实际值
AI_PROVIDER=openai
AI_MODEL=gpt-4o-mini
AI_API_KEY=your-openai-api-key-here
```

## 第四步：创建数据库表

在 Supabase SQL Editor 中执行以下 SQL 创建聊天消息表：

```sql
-- 创建聊天消息表
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id VARCHAR(255) NOT NULL,
    message_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_id ON chat_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_message_id ON chat_messages(message_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);

-- 启用 RLS (Row Level Security)
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- 创建 RLS 策略：允许服务角色完全访问
CREATE POLICY "Service role can do everything" ON chat_messages
    FOR ALL USING (auth.role() = 'service_role');

-- 创建 RLS 策略：用户只能访问自己的消息
CREATE POLICY "Users can view own messages" ON chat_messages
    FOR SELECT USING (auth.uid()::text = user_id);

-- 创建 RLS 策略：用户可以插入自己的消息
CREATE POLICY "Users can insert own messages" ON chat_messages
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);
```

## 第五步：验证配置

1. 确保所有环境变量都已正确设置
2. 启动后端服务：`python run.py`
3. 检查服务是否正常启动，没有配置错误

## 安全注意事项

1. **保护 Service Role Key**: 这个密钥拥有完全的数据库访问权限，绝不能暴露给客户端
2. **使用 RLS**: 确保启用了行级安全策略，保护用户数据
3. **环境变量**: 不要将 `.env` 文件提交到版本控制系统
4. **HTTPS**: 生产环境中务必使用 HTTPS

## 故障排除

### 常见问题

1. **JWT 验证失败**
   - 检查 `SUPABASE_PROJECT_ID` 是否正确
   - 确认 `SUPABASE_JWKS_URL` 可以访问
   - 验证 `SUPABASE_ISSUER` 和 `SUPABASE_AUDIENCE` 配置

2. **数据库连接失败**
   - 确认 `SUPABASE_SERVICE_ROLE_KEY` 正确
   - 检查网络连接
   - 验证表是否已创建

3. **权限错误**
   - 确认 RLS 策略已正确设置
   - 检查用户 ID 是否正确传递

## 下一步

配置完成后，您可以：
1. 运行端到端测试验证配置
2. 集成前端应用
3. 部署到生产环境

更多详细信息请参考 [Supabase 官方文档](https://supabase.com/docs)。
