-- 匿名用户（Anonymous）支持 · RLS 策略完整实现
-- 版本: v1.0
-- 更新时间: 2025-09-29
-- 适用范围: T3 数据与RLS（Supabase SQL）

-- =============================================================================
-- 第一部分：确保目标表启用RLS
-- =============================================================================

-- 确保conversations表启用RLS
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;

-- 确保messages表启用RLS
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- 确保chat_messages表启用RLS（向后兼容）
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- 第二部分：Owner-only策略 - user_id = auth.uid() 适用于所有操作
-- =============================================================================

-- conversations表：用户只能访问自己的对话
DROP POLICY IF EXISTS "conversations_owner_select" ON conversations;
DROP POLICY IF EXISTS "conversations_owner_insert" ON conversations;
DROP POLICY IF EXISTS "conversations_owner_update" ON conversations;
DROP POLICY IF EXISTS "conversations_owner_delete" ON conversations;

CREATE POLICY "conversations_owner_select" ON conversations
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "conversations_owner_insert" ON conversations
    FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "conversations_owner_update" ON conversations
    FOR UPDATE TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "conversations_owner_delete" ON conversations
    FOR DELETE TO authenticated
    USING (user_id = auth.uid());

-- messages表：用户只能访问自己的消息
DROP POLICY IF EXISTS "messages_owner_select" ON messages;
DROP POLICY IF EXISTS "messages_owner_insert" ON messages;
DROP POLICY IF EXISTS "messages_owner_update" ON messages;
DROP POLICY IF EXISTS "messages_owner_delete" ON messages;

CREATE POLICY "messages_owner_select" ON messages
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "messages_owner_insert" ON messages
    FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "messages_owner_update" ON messages
    FOR UPDATE TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "messages_owner_delete" ON messages
    FOR DELETE TO authenticated
    USING (user_id = auth.uid());

-- chat_messages表：向后兼容支持
DROP POLICY IF EXISTS "chat_messages_owner_select" ON chat_messages;
DROP POLICY IF EXISTS "chat_messages_owner_insert" ON chat_messages;
DROP POLICY IF EXISTS "chat_messages_owner_update" ON chat_messages;
DROP POLICY IF EXISTS "chat_messages_owner_delete" ON chat_messages;

CREATE POLICY "chat_messages_owner_select" ON chat_messages
    FOR SELECT TO authenticated
    USING (auth.uid()::text = user_id);

CREATE POLICY "chat_messages_owner_insert" ON chat_messages
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "chat_messages_owner_update" ON chat_messages
    FOR UPDATE TO authenticated
    USING (auth.uid()::text = user_id)
    WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "chat_messages_owner_delete" ON chat_messages
    FOR DELETE TO authenticated
    USING (auth.uid()::text = user_id);

-- =============================================================================
-- 第三部分：服务角色完全访问策略
-- =============================================================================

-- conversations表：服务角色完全访问
DROP POLICY IF EXISTS "conversations_service_all" ON conversations;
CREATE POLICY "conversations_service_all" ON conversations
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- messages表：服务角色完全访问
DROP POLICY IF EXISTS "messages_service_all" ON messages;
CREATE POLICY "messages_service_all" ON messages
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- chat_messages表：服务角色完全访问（向后兼容）
DROP POLICY IF EXISTS "chat_messages_service_all" ON chat_messages;
CREATE POLICY "chat_messages_service_all" ON chat_messages
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- =============================================================================
-- 第四部分：匿名用户限制策略（基于 auth.jwt()->>'is_anonymous'）
-- =============================================================================

-- 创建公开分享表（如果不存在）
CREATE TABLE IF NOT EXISTS public_shares (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id UUID NOT NULL,
    user_id UUID NOT NULL,
    share_token VARCHAR(255) NOT NULL UNIQUE,
    title TEXT,
    description TEXT,
    is_public BOOLEAN DEFAULT true,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 启用公开分享表的RLS
ALTER TABLE public_shares ENABLE ROW LEVEL SECURITY;

-- 匿名用户禁止创建公开分享
DROP POLICY IF EXISTS "anonymous_cannot_create_public_shares" ON public_shares;
CREATE POLICY "anonymous_cannot_create_public_shares" ON public_shares
    AS RESTRICTIVE
    FOR INSERT TO authenticated
    WITH CHECK (
        COALESCE((auth.jwt()->>'is_anonymous')::boolean, false) = false
    );

-- 匿名用户禁止更新公开分享
DROP POLICY IF EXISTS "anonymous_cannot_update_public_shares" ON public_shares;
CREATE POLICY "anonymous_cannot_update_public_shares" ON public_shares
    AS RESTRICTIVE
    FOR UPDATE TO authenticated
    WITH CHECK (
        COALESCE((auth.jwt()->>'is_anonymous')::boolean, false) = false
    );

-- 公开分享表的基础owner策略
DROP POLICY IF EXISTS "public_shares_owner_select" ON public_shares;
DROP POLICY IF EXISTS "public_shares_owner_insert" ON public_shares;
DROP POLICY IF EXISTS "public_shares_owner_update" ON public_shares;
DROP POLICY IF EXISTS "public_shares_owner_delete" ON public_shares;

CREATE POLICY "public_shares_owner_select" ON public_shares
    FOR SELECT TO authenticated
    USING (user_id = auth.uid());

CREATE POLICY "public_shares_owner_insert" ON public_shares
    FOR INSERT TO authenticated
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "public_shares_owner_update" ON public_shares
    FOR UPDATE TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

CREATE POLICY "public_shares_owner_delete" ON public_shares
    FOR DELETE TO authenticated
    USING (user_id = auth.uid());

-- 服务角色对公开分享表的完全访问
DROP POLICY IF EXISTS "public_shares_service_all" ON public_shares;
CREATE POLICY "public_shares_service_all" ON public_shares
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- =============================================================================
-- 第五部分：可选审计字段 user_type（由服务器设置，Supabase JWT为准）
-- =============================================================================

-- 为conversations表添加可选的user_type审计字段
ALTER TABLE conversations
ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) DEFAULT NULL;

-- 为messages表添加可选的user_type审计字段
ALTER TABLE messages
ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) DEFAULT NULL;

-- 为chat_messages表添加可选的user_type审计字段（向后兼容）
ALTER TABLE chat_messages
ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) DEFAULT NULL;

-- 为public_shares表添加可选的user_type审计字段
ALTER TABLE public_shares
ADD COLUMN IF NOT EXISTS user_type VARCHAR(20) DEFAULT NULL;

-- 创建索引以支持按用户类型查询（用于分析和监控）
CREATE INDEX IF NOT EXISTS idx_conversations_user_type ON conversations(user_type) WHERE user_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_user_type ON messages(user_type) WHERE user_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_type ON chat_messages(user_type) WHERE user_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_public_shares_user_type ON public_shares(user_type) WHERE user_type IS NOT NULL;

-- 创建复合索引：用户类型 + 创建时间（用于分析匿名用户行为）
CREATE INDEX IF NOT EXISTS idx_conversations_user_type_created ON conversations(user_type, created_at) WHERE user_type IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_messages_user_type_created ON messages(user_type, created_at) WHERE user_type IS NOT NULL;

-- =============================================================================
-- 第六部分：匿名用户数据清理策略
-- =============================================================================

-- 创建清理匿名用户数据的函数（30天保留期）
CREATE OR REPLACE FUNCTION cleanup_anonymous_user_data(retention_days INTEGER DEFAULT 30)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    deleted_conversations INTEGER := 0;
    deleted_messages INTEGER := 0;
    deleted_chat_messages INTEGER := 0;
    deleted_public_shares INTEGER := 0;
    total_deleted INTEGER := 0;
BEGIN
    -- 删除过期的匿名用户对话
    DELETE FROM conversations
    WHERE user_type = 'anonymous'
    AND created_at < NOW() - INTERVAL '1 day' * retention_days;
    GET DIAGNOSTICS deleted_conversations = ROW_COUNT;

    -- 删除过期的匿名用户消息
    DELETE FROM messages
    WHERE user_type = 'anonymous'
    AND created_at < NOW() - INTERVAL '1 day' * retention_days;
    GET DIAGNOSTICS deleted_messages = ROW_COUNT;

    -- 删除过期的匿名用户聊天消息（向后兼容）
    DELETE FROM chat_messages
    WHERE user_type = 'anonymous'
    AND created_at < NOW() - INTERVAL '1 day' * retention_days;
    GET DIAGNOSTICS deleted_chat_messages = ROW_COUNT;

    -- 删除过期的匿名用户公开分享
    DELETE FROM public_shares
    WHERE user_type = 'anonymous'
    AND created_at < NOW() - INTERVAL '1 day' * retention_days;
    GET DIAGNOSTICS deleted_public_shares = ROW_COUNT;

    total_deleted := deleted_conversations + deleted_messages + deleted_chat_messages + deleted_public_shares;

    -- 记录清理日志
    RAISE NOTICE 'Anonymous data cleanup completed: conversations=%, messages=%, chat_messages=%, public_shares=%, total=%',
        deleted_conversations, deleted_messages, deleted_chat_messages, deleted_public_shares, total_deleted;

    RETURN total_deleted;
END;
$$;

-- 授予服务角色执行清理函数的权限
GRANT EXECUTE ON FUNCTION cleanup_anonymous_user_data TO service_role;

-- =============================================================================
-- 第七部分：权限授予
-- =============================================================================

-- 授予authenticated角色对表的基本权限
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON conversations TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON messages TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON chat_messages TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public_shares TO authenticated;

-- 授予service_role完全权限
GRANT ALL ON conversations TO service_role;
GRANT ALL ON messages TO service_role;
GRANT ALL ON chat_messages TO service_role;
GRANT ALL ON public_shares TO service_role;

-- =============================================================================
-- 第八部分：验证查询
-- =============================================================================

-- 验证RLS策略是否正确应用
SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual,
    with_check
FROM pg_policies
WHERE tablename IN ('conversations', 'messages', 'chat_messages', 'public_shares')
ORDER BY tablename, policyname;

-- 验证表结构和审计字段
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name IN ('conversations', 'messages', 'chat_messages', 'public_shares')
AND column_name IN ('user_type', 'user_id', 'created_at')
ORDER BY table_name, column_name;

-- 验证索引
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN ('conversations', 'messages', 'chat_messages', 'public_shares')
AND indexname LIKE '%user_type%'
ORDER BY tablename, indexname;

-- =============================================================================
-- 实施说明
-- =============================================================================

/*
实施步骤：
1. 在Supabase Dashboard的SQL Editor中执行此脚本
2. 确认所有策略都已正确创建
3. 验证表结构包含user_type审计字段
4. 测试匿名用户和永久用户的访问权限
5. 配置定时任务执行cleanup_anonymous_user_data函数

注意事项：
- user_type字段由服务器在写入时设置，客户端不应直接修改
- Supabase JWT中的is_anonymous声明是权威数据源
- 匿名用户数据默认30天保留期，可通过参数调整
- 所有策略都支持向后兼容，不会影响现有功能
*/
