# 匿名用户RLS策略实施指南

**版本**: v1.0  
**更新时间**: 2025-09-29  
**适用范围**: T3 数据与RLS（Supabase SQL）

## 概述

本文档描述了为支持匿名用户功能而实施的Row Level Security (RLS) 策略。这些策略确保匿名用户和永久用户都能安全地访问数据，同时限制匿名用户对敏感功能的访问。

## 核心设计原则

### 1. 基于JWT声明的权限控制
- 使用 `auth.jwt()->>'is_anonymous'` 作为权威数据源
- 匿名用户和永久用户都遵循 `user_id = auth.uid()` 的owner-only原则
- 服务角色 (service_role) 拥有完全访问权限

### 2. 分层安全策略
```
┌─────────────────┐
│   Service Role  │ ← 完全访问权限
├─────────────────┤
│ Permanent Users │ ← 完整功能访问
├─────────────────┤
│ Anonymous Users │ ← 受限功能访问
└─────────────────┘
```

### 3. 零信任架构
- 所有表默认启用RLS
- 明确的权限授予，拒绝默认访问
- 审计字段支持行为分析

## 表结构和策略矩阵

### 核心数据表

| 表名 | 匿名用户 | 永久用户 | 服务角色 | 特殊限制 |
|------|----------|----------|----------|----------|
| `conversations` | ✅ 仅自己数据 | ✅ 仅自己数据 | ✅ 完全访问 | - |
| `messages` | ✅ 仅自己数据 | ✅ 仅自己数据 | ✅ 完全访问 | - |
| `chat_messages` | ✅ 仅自己数据 | ✅ 仅自己数据 | ✅ 完全访问 | 向后兼容 |
| `public_shares` | ❌ 禁止写入 | ✅ 完整访问 | ✅ 完全访问 | 匿名用户只读 |

### RLS策略详解

#### 1. Owner-Only策略
```sql
-- 示例：conversations表的SELECT策略
CREATE POLICY "conversations_owner_select" ON conversations
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());
```

**适用操作**: SELECT, INSERT, UPDATE, DELETE  
**适用表**: 所有核心数据表  
**权限逻辑**: 用户只能访问 `user_id` 等于自己 `auth.uid()` 的记录

#### 2. 服务角色策略
```sql
-- 示例：conversations表的服务角色策略
CREATE POLICY "conversations_service_all" ON conversations
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);
```

**适用操作**: ALL (SELECT, INSERT, UPDATE, DELETE)  
**适用表**: 所有表  
**权限逻辑**: 服务角色绕过所有RLS限制

#### 3. 匿名用户限制策略
```sql
-- 示例：禁止匿名用户创建公开分享
CREATE POLICY "anonymous_cannot_create_public_shares" ON public_shares
    AS RESTRICTIVE
    FOR INSERT TO authenticated
    WITH CHECK (
        COALESCE((auth.jwt()->>'is_anonymous')::boolean, false) = false
    );
```

**策略类型**: RESTRICTIVE（限制性策略）  
**权限逻辑**: 当 `is_anonymous` 为 `true` 时拒绝操作

## 审计字段设计

### user_type字段
- **数据类型**: `VARCHAR(20) DEFAULT NULL`
- **可选值**: `'anonymous'`, `'permanent'`, `NULL`
- **设置时机**: 服务器写入时由后端设置
- **权威来源**: Supabase JWT中的 `is_anonymous` 声明

### 索引策略
```sql
-- 支持按用户类型查询（用于分析）
CREATE INDEX idx_conversations_user_type ON conversations(user_type) 
WHERE user_type IS NOT NULL;

-- 支持用户类型 + 时间范围查询
CREATE INDEX idx_conversations_user_type_created ON conversations(user_type, created_at) 
WHERE user_type IS NOT NULL;
```

## 数据保留策略

### 匿名用户数据清理
- **默认保留期**: 30天
- **清理频率**: 建议每日执行
- **清理函数**: `cleanup_anonymous_user_data(retention_days)`

```sql
-- 手动执行清理（保留30天）
SELECT cleanup_anonymous_user_data(30);

-- 设置定时任务（需要pg_cron扩展）
SELECT cron.schedule('cleanup-anonymous-data', '0 2 * * *', 
    'SELECT cleanup_anonymous_user_data(30);');
```

### 清理日志示例
```
NOTICE: Anonymous data cleanup completed: 
conversations=15, messages=234, chat_messages=0, public_shares=3, total=252
```

## 实施步骤

### 1. 准备阶段
```bash
# 1. 备份现有数据
pg_dump -h your-host -U postgres -d your-db > backup_before_anon.sql

# 2. 验证当前RLS状态
SELECT tablename, rowsecurity FROM pg_tables 
WHERE schemaname = 'public' AND tablename IN ('conversations', 'messages', 'chat_messages');
```

### 2. 执行RLS策略
```sql
-- 在Supabase Dashboard的SQL Editor中执行
\i docs/jwt改造/ANON/ANON_RLS_POLICIES.sql
```

### 3. 验证实施结果
```sql
-- 验证策略创建
SELECT tablename, policyname, cmd FROM pg_policies 
WHERE tablename IN ('conversations', 'messages', 'chat_messages', 'public_shares')
ORDER BY tablename, policyname;

-- 验证审计字段
SELECT table_name, column_name FROM information_schema.columns 
WHERE table_name IN ('conversations', 'messages', 'chat_messages', 'public_shares')
AND column_name = 'user_type';
```

### 4. 功能测试
```javascript
// 测试匿名用户访问
const { data: conversations } = await supabase
  .from('conversations')
  .select('*')
  .eq('user_id', anonymousUserId);

// 测试匿名用户创建公开分享（应该失败）
const { error } = await supabase
  .from('public_shares')
  .insert({
    conversation_id: 'test-conv-id',
    user_id: anonymousUserId,
    share_token: 'test-token'
  });
// 预期: error.code === '42501' (权限不足)
```

## 监控和告警

### 关键指标
1. **匿名用户活跃度**
   ```sql
   SELECT COUNT(*) as anonymous_users_today
   FROM conversations 
   WHERE user_type = 'anonymous' 
   AND created_at >= CURRENT_DATE;
   ```

2. **权限违规尝试**
   ```sql
   -- 监控Supabase日志中的42501错误（权限不足）
   -- 特别关注public_shares表的INSERT/UPDATE操作
   ```

3. **数据增长趋势**
   ```sql
   SELECT 
       user_type,
       DATE(created_at) as date,
       COUNT(*) as daily_conversations
   FROM conversations 
   WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
   GROUP BY user_type, DATE(created_at)
   ORDER BY date DESC, user_type;
   ```

### 告警规则建议
- 匿名用户权限违规尝试 > 100次/小时
- 匿名用户数据增长 > 1000条/小时
- 数据清理函数执行失败

## 故障排除

### 常见问题

#### 1. 匿名用户无法访问数据
**症状**: 查询返回空结果或权限错误  
**排查步骤**:
```sql
-- 检查JWT中的is_anonymous声明
SELECT auth.jwt()->>'is_anonymous' as is_anonymous;

-- 检查user_id匹配
SELECT auth.uid() as current_user_id;

-- 检查RLS策略
SELECT * FROM pg_policies WHERE tablename = 'conversations';
```

#### 2. 服务角色权限不足
**症状**: 后端服务无法写入数据  
**解决方案**:
```sql
-- 确认服务角色策略存在
SELECT * FROM pg_policies 
WHERE tablename = 'conversations' 
AND policyname LIKE '%service%';

-- 重新授予权限
GRANT ALL ON conversations TO service_role;
```

#### 3. 数据清理函数执行失败
**症状**: 匿名用户数据未按期清理  
**排查步骤**:
```sql
-- 检查函数是否存在
SELECT proname FROM pg_proc WHERE proname = 'cleanup_anonymous_user_data';

-- 手动执行测试
SELECT cleanup_anonymous_user_data(1); -- 测试清理1天前的数据
```

## 回滚方案

如需回滚匿名用户功能：

```sql
-- 执行回滚脚本
\i docs/jwt改造/ANON_RLS_ROLLBACK.sql
```

**回滚影响**:
- 删除所有匿名用户相关的RLS策略
- 删除 `user_type` 审计字段
- 删除数据清理函数
- 恢复原始的owner-only策略

## 最佳实践

### 1. 开发环境测试
- 使用测试数据验证所有策略
- 模拟匿名用户和永久用户的各种操作场景
- 验证服务角色的完全访问权限

### 2. 生产环境部署
- 在低峰期执行RLS策略更新
- 逐步启用匿名用户功能
- 密切监控系统性能和错误日志

### 3. 数据治理
- 定期审查匿名用户数据保留策略
- 监控数据增长趋势
- 确保合规性要求得到满足

### 4. 安全审计
- 定期检查RLS策略的有效性
- 监控权限违规尝试
- 验证JWT声明的完整性

## 相关文档

- [T2 后端策略与开关实施报告](./T2_BACKEND_DELIVERY_REPORT.md)
- [匿名用户端点访问矩阵](./ANON_ENDPOINT_MATRIX.md)
- [匿名用户后端策略配置](./ANON_BACKEND_POLICY.md)
- [Supabase RLS官方文档](https://supabase.com/docs/guides/auth/row-level-security)
