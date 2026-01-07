-- =====================================================
-- 匿名访问功能表结构补充脚本
-- =====================================================
-- 创建日期: 2025-09-29
-- 目标: 补充COMPLETE_REBUILD_FOR_ANDROID.sql中缺失的匿名访问相关表结构
-- 说明: 此脚本应在COMPLETE_REBUILD_FOR_ANDROID.sql执行后运行

-- =====================================================
-- 第一步：创建对话和消息相关表
-- =====================================================

-- conversations表 - 对话管理
CREATE TABLE conversations (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT true,
    user_type VARCHAR(20) DEFAULT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- messages表 - 消息管理
CREATE TABLE messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id UUID NOT NULL,
    user_id UUID NOT NULL,
    content TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    user_type VARCHAR(20) DEFAULT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- chat_messages表 - 向后兼容的聊天消息表
CREATE TABLE chat_messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id TEXT NOT NULL,
    content TEXT NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    user_type VARCHAR(20) DEFAULT NULL
);

-- public_shares表 - 公开分享功能
CREATE TABLE public_shares (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id UUID NOT NULL,
    user_id UUID NOT NULL,
    share_token VARCHAR(255) NOT NULL UNIQUE,
    title TEXT,
    description TEXT,
    is_public BOOLEAN DEFAULT true,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    user_type VARCHAR(20) DEFAULT NULL,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- =====================================================
-- 第二步：创建性能索引
-- =====================================================

-- conversations表索引
CREATE INDEX idx_conversations_user_id ON conversations(user_id);
CREATE INDEX idx_conversations_created_at ON conversations(created_at);
CREATE INDEX idx_conversations_user_type ON conversations(user_type) WHERE user_type IS NOT NULL;
CREATE INDEX idx_conversations_user_type_created ON conversations(user_type, created_at) WHERE user_type IS NOT NULL;

-- messages表索引
CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX idx_messages_user_id ON messages(user_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_user_type ON messages(user_type) WHERE user_type IS NOT NULL;
CREATE INDEX idx_messages_user_type_created ON messages(user_type, created_at) WHERE user_type IS NOT NULL;

-- chat_messages表索引
CREATE INDEX idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at);
CREATE INDEX idx_chat_messages_user_type ON chat_messages(user_type) WHERE user_type IS NOT NULL;

-- public_shares表索引
CREATE INDEX idx_public_shares_user_id ON public_shares(user_id);
CREATE INDEX idx_public_shares_conversation_id ON public_shares(conversation_id);
CREATE INDEX idx_public_shares_share_token ON public_shares(share_token);
CREATE INDEX idx_public_shares_created_at ON public_shares(created_at);
CREATE INDEX idx_public_shares_user_type ON public_shares(user_type) WHERE user_type IS NOT NULL;

-- =====================================================
-- 第三步：启用行级安全策略（RLS）
-- =====================================================

-- 启用RLS
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public_shares ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- 第四步：创建匿名用户数据清理函数
-- =====================================================

-- 先删除现有函数（如果存在）
DROP FUNCTION IF EXISTS cleanup_anonymous_user_data(INTEGER);

-- 匿名用户数据清理函数（更新版本，支持新表结构）
CREATE OR REPLACE FUNCTION cleanup_anonymous_user_data(days_old INTEGER DEFAULT 30)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    deleted_conversations INTEGER := 0;
    deleted_messages INTEGER := 0;
    deleted_chat_messages INTEGER := 0;
    deleted_public_shares INTEGER := 0;
    deleted_users INTEGER := 0;
    total_deleted INTEGER := 0;
    cutoff_timestamp TIMESTAMPTZ;
    cutoff_timestamp_ms BIGINT;
BEGIN
    -- 计算截止时间
    cutoff_timestamp := NOW() - INTERVAL '1 day' * days_old;
    cutoff_timestamp_ms := extract(epoch from cutoff_timestamp) * 1000;

    -- 删除过期的匿名用户对话
    DELETE FROM conversations
    WHERE user_type = 'anonymous'
    AND created_at < cutoff_timestamp;
    GET DIAGNOSTICS deleted_conversations = ROW_COUNT;

    -- 删除过期的匿名用户消息
    DELETE FROM messages
    WHERE user_type = 'anonymous'
    AND created_at < cutoff_timestamp;
    GET DIAGNOSTICS deleted_messages = ROW_COUNT;

    -- 删除过期的匿名用户聊天消息（向后兼容）
    DELETE FROM chat_messages
    WHERE user_type = 'anonymous'
    AND created_at < cutoff_timestamp;
    GET DIAGNOSTICS deleted_chat_messages = ROW_COUNT;

    -- 删除过期的匿名用户公开分享
    DELETE FROM public_shares
    WHERE user_type = 'anonymous'
    AND created_at < cutoff_timestamp;
    GET DIAGNOSTICS deleted_public_shares = ROW_COUNT;

    -- 删除过期的匿名用户记录
    WITH deleted_user_records AS (
        DELETE FROM users
        WHERE isAnonymous = 1
        AND createdAt < cutoff_timestamp_ms
        RETURNING user_id
    )
    SELECT COUNT(*) INTO deleted_users FROM deleted_user_records;

    total_deleted := deleted_conversations + deleted_messages + deleted_chat_messages + deleted_public_shares + deleted_users;

    -- 记录清理日志
    RAISE NOTICE 'Anonymous data cleanup completed: conversations=%, messages=%, chat_messages=%, public_shares=%, users=%, total=%',
        deleted_conversations, deleted_messages, deleted_chat_messages, deleted_public_shares, deleted_users, total_deleted;

    RETURN total_deleted;
END;
$$;

-- 授予服务角色执行清理函数的权限
GRANT EXECUTE ON FUNCTION cleanup_anonymous_user_data TO service_role;

-- =====================================================
-- 第五步：权限授予
-- =====================================================

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

-- =====================================================
-- 第六步：验证表结构
-- =====================================================

-- 验证表是否创建成功
SELECT
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_name IN ('conversations', 'messages', 'chat_messages', 'public_shares')
ORDER BY table_name, ordinal_position;

-- 验证索引是否创建成功
SELECT
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN ('conversations', 'messages', 'chat_messages', 'public_shares')
ORDER BY tablename, indexname;

-- =====================================================
-- 使用说明
-- =====================================================

/*
使用步骤：
1. 确保已执行 COMPLETE_REBUILD_FOR_ANDROID.sql
2. 在Supabase Dashboard的SQL Editor中执行此脚本
3. 执行 ANON_RLS_POLICIES.sql 配置RLS策略
4. 验证所有表和索引都已正确创建

注意事项：
- 此脚本补充了匿名访问功能所需的核心表结构
- user_type字段用于审计和数据清理
- 所有表都启用了RLS，需要配合RLS策略使用
- cleanup_anonymous_user_data函数支持自动清理过期匿名用户数据
*/
