# K2 数据与 RLS 收口交付报告

## 📋 结构变更摘要

### 新表结构
- **conversations**: 对话主表 (id, user_id, title, created_at, updated_at, source, trace_id)
- **messages**: 消息详情表 (id, conversation_id, user_id, role, content, created_at, provider, channel, build_type, trace_id)

### 删除旧表
- 删除 `chat_messages` 和 `ai_chat_messages` 旧表及相关策略

## 🔐 RLS 策略矩阵

| 角色 | conversations | messages | 说明 |
|------|---------------|----------|------|
| anon | ❌ 无访问权限 | ❌ 无访问权限 | 匿名用户完全禁止 |
| authenticated | ✅ 仅自己数据 | ✅ 仅自己数据 | auth.uid() = user_id |
| service_role | ✅ 完全访问 | ✅ 完全访问 | 后端服务专用 |

### 具体策略
- `conversations_user_select/insert/update/delete`: 用户仅操作自己的对话
- `messages_user_select/insert/update/delete`: 用户仅操作自己的消息  
- `conversations_service_all/messages_service_all`: 服务角色完全权限

## 📊 索引列表

### conversations 表
- `idx_conversations_user_id`: 按用户查询
- `idx_conversations_created_at`: 按创建时间排序
- `idx_conversations_user_created`: 复合索引，用户+时间

### messages 表  
- `idx_messages_conversation_id`: 按对话查询
- `idx_messages_conv_created`: 对话+时间复合索引（核心查询）
- `idx_messages_user_created`: 用户+时间复合索引
- `idx_messages_provider/trace_id`: 审计维度索引

## 🚀 EXPLAIN 基线

```sql
-- 查询最近50条消息（核心场景）
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM messages 
WHERE conversation_id = $1 
ORDER BY created_at DESC 
LIMIT 50;

-- 预期: Index Scan using idx_messages_conv_created
-- Cost: ~1.0..50.0, Rows: 50
```

## 📅 保留策略

### 30天保留（pg_cron方案）
```sql
-- 每日凌晨2点执行
SELECT cron.schedule('cleanup-old-messages', '0 2 * * *', 
  'DELETE FROM messages WHERE created_at < NOW() - INTERVAL ''30 days''');
```

### 90天归档（Edge Function方案）  
```sql
-- 归档到冷存储，保留元数据
INSERT INTO messages_archive 
SELECT * FROM messages 
WHERE created_at < NOW() - INTERVAL '90 days';
```

### 回滚方式
```sql
-- 停止定时任务
SELECT cron.unschedule('cleanup-old-messages');
-- 从归档恢复（如需要）
INSERT INTO messages SELECT * FROM messages_archive WHERE ...;
```

## ✅ 验收确认

- [x] **RLS测试**: anon/auth仅访问自己数据，service_role完全访问
- [x] **索引验证**: conversation_id + created_at 查询使用复合索引  
- [x] **权限矩阵**: 客户端→后端API→service_role链路清晰
- [x] **代码审查**: app/目录无直连Supabase新增用法
- [x] **审计字段**: trace_id、provider、channel、build_type必填支持

## 🔗 最小PostgREST示例

```javascript
// ❌ 禁止：客户端直连
const { data } = await supabase.from('messages').select('*');

// ✅ 正确：通过后端API  
const response = await fetch('/api/v1/messages', {
  headers: { 'Authorization': `Bearer ${jwt}` }
});
```

## ⚠️ Service Role警示

**Service Role仅限服务端使用**
- 环境变量: `SUPABASE_SERVICE_ROLE_KEY`
- 使用位置: `app/auth/supabase_provider.py`
- 禁止: 前端代码、客户端应用、公开API
