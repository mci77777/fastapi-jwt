-- 匿名用户（Anonymous）支持 · RLS 策略回滚脚本
-- 版本: v1.0
-- 更新时间: 2025-09-29
-- 用途: 完全回滚T3匿名用户RLS策略和相关修改

-- =============================================================================
-- 警告：此脚本将完全回滚匿名用户支持功能
-- 执行前请确保：
-- 1. 已备份重要数据
-- 2. 已通知相关用户功能变更
-- 3. 已停止相关应用服务
-- =============================================================================

-- =============================================================================
-- 第一部分：删除匿名用户相关的RLS策略
-- =============================================================================

-- 删除conversations表的匿名用户策略
DROP POLICY IF EXISTS "conversations_owner_select" ON conversations;
DROP POLICY IF EXISTS "conversations_owner_insert" ON conversations;
DROP POLICY IF EXISTS "conversations_owner_update" ON conversations;
DROP POLICY IF EXISTS "conversations_owner_delete" ON conversations;
DROP POLICY IF EXISTS "conversations_service_all" ON conversations;

-- 删除messages表的匿名用户策略
DROP POLICY IF EXISTS "messages_owner_select" ON messages;
DROP POLICY IF EXISTS "messages_owner_insert" ON messages;
DROP POLICY IF EXISTS "messages_owner_update" ON messages;
DROP POLICY IF EXISTS "messages_owner_delete" ON messages;
DROP POLICY IF EXISTS "messages_service_all" ON messages;

-- 删除chat_messages表的匿名用户策略
DROP POLICY IF EXISTS "chat_messages_owner_select" ON chat_messages;
DROP POLICY IF EXISTS "chat_messages_owner_insert" ON chat_messages;
DROP POLICY IF EXISTS "chat_messages_owner_update" ON chat_messages;
DROP POLICY IF EXISTS "chat_messages_owner_delete" ON chat_messages;
DROP POLICY IF EXISTS "chat_messages_service_all" ON chat_messages;

-- 删除public_shares表的所有策略
DROP POLICY IF EXISTS "anonymous_cannot_create_public_shares" ON public_shares;
DROP POLICY IF EXISTS "anonymous_cannot_update_public_shares" ON public_shares;
DROP POLICY IF EXISTS "public_shares_owner_select" ON public_shares;
DROP POLICY IF EXISTS "public_shares_owner_insert" ON public_shares;
DROP POLICY IF EXISTS "public_shares_owner_update" ON public_shares;
DROP POLICY IF EXISTS "public_shares_owner_delete" ON public_shares;
DROP POLICY IF EXISTS "public_shares_service_all" ON public_shares;

-- =============================================================================
-- 第二部分：恢复原始RLS策略（基于K2之前的设计）
-- =============================================================================

-- 恢复chat_messages表的原始策略
CREATE POLICY "Service role can do everything" ON chat_messages
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Users can view own messages" ON chat_messages
    FOR SELECT USING (auth.uid()::text = user_id);

CREATE POLICY "Users can insert own messages" ON chat_messages
    FOR INSERT WITH CHECK (auth.uid()::text = user_id);

-- 如果conversations和messages表存在，恢复基础策略
DO $$
BEGIN
    -- 检查conversations表是否存在
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'conversations') THEN
        -- 恢复conversations表的基础策略
        EXECUTE 'CREATE POLICY "conversations_user_select" ON conversations
            FOR SELECT TO authenticated
            USING (user_id = auth.uid())';
            
        EXECUTE 'CREATE POLICY "conversations_user_insert" ON conversations
            FOR INSERT TO authenticated
            WITH CHECK (user_id = auth.uid())';
            
        EXECUTE 'CREATE POLICY "conversations_user_update" ON conversations
            FOR UPDATE TO authenticated
            USING (user_id = auth.uid())
            WITH CHECK (user_id = auth.uid())';
            
        EXECUTE 'CREATE POLICY "conversations_user_delete" ON conversations
            FOR DELETE TO authenticated
            USING (user_id = auth.uid())';
            
        EXECUTE 'CREATE POLICY "conversations_service_all" ON conversations
            FOR ALL TO service_role
            USING (true)
            WITH CHECK (true)';
    END IF;
    
    -- 检查messages表是否存在
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'messages') THEN
        -- 恢复messages表的基础策略
        EXECUTE 'CREATE POLICY "messages_user_select" ON messages
            FOR SELECT TO authenticated
            USING (user_id = auth.uid())';
            
        EXECUTE 'CREATE POLICY "messages_user_insert" ON messages
            FOR INSERT TO authenticated
            WITH CHECK (user_id = auth.uid())';
            
        EXECUTE 'CREATE POLICY "messages_user_update" ON messages
            FOR UPDATE TO authenticated
            USING (user_id = auth.uid())
            WITH CHECK (user_id = auth.uid())';
            
        EXECUTE 'CREATE POLICY "messages_user_delete" ON messages
            FOR DELETE TO authenticated
            USING (user_id = auth.uid())';
            
        EXECUTE 'CREATE POLICY "messages_service_all" ON messages
            FOR ALL TO service_role
            USING (true)
            WITH CHECK (true)';
    END IF;
END $$;

-- =============================================================================
-- 第三部分：删除匿名用户相关的表和函数
-- =============================================================================

-- 删除清理函数
DROP FUNCTION IF EXISTS cleanup_anonymous_user_data(INTEGER);

-- 删除public_shares表（如果是为匿名用户功能创建的）
-- 注意：如果此表包含重要数据，请先备份
-- DROP TABLE IF EXISTS public_shares;

-- =============================================================================
-- 第四部分：删除审计字段和索引
-- =============================================================================

-- 删除user_type相关的索引
DROP INDEX IF EXISTS idx_conversations_user_type;
DROP INDEX IF EXISTS idx_messages_user_type;
DROP INDEX IF EXISTS idx_chat_messages_user_type;
DROP INDEX IF EXISTS idx_public_shares_user_type;
DROP INDEX IF EXISTS idx_conversations_user_type_created;
DROP INDEX IF EXISTS idx_messages_user_type_created;

-- 删除user_type审计字段
-- 注意：删除列是不可逆操作，请确保不再需要这些数据
DO $$
BEGIN
    -- 删除conversations表的user_type字段
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'conversations' AND column_name = 'user_type') THEN
        ALTER TABLE conversations DROP COLUMN user_type;
    END IF;
    
    -- 删除messages表的user_type字段
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'messages' AND column_name = 'user_type') THEN
        ALTER TABLE messages DROP COLUMN user_type;
    END IF;
    
    -- 删除chat_messages表的user_type字段
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'chat_messages' AND column_name = 'user_type') THEN
        ALTER TABLE chat_messages DROP COLUMN user_type;
    END IF;
    
    -- 删除public_shares表的user_type字段（如果表存在）
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'public_shares') THEN
        IF EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'public_shares' AND column_name = 'user_type') THEN
            ALTER TABLE public_shares DROP COLUMN user_type;
        END IF;
    END IF;
END $$;

-- =============================================================================
-- 第五部分：验证回滚结果
-- =============================================================================

-- 验证策略已删除
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd
FROM pg_policies 
WHERE tablename IN ('conversations', 'messages', 'chat_messages', 'public_shares')
AND policyname LIKE '%anonymous%'
ORDER BY tablename, policyname;

-- 验证user_type字段已删除
SELECT 
    table_name,
    column_name
FROM information_schema.columns 
WHERE table_name IN ('conversations', 'messages', 'chat_messages', 'public_shares')
AND column_name = 'user_type';

-- 验证索引已删除
SELECT 
    tablename,
    indexname
FROM pg_indexes 
WHERE tablename IN ('conversations', 'messages', 'chat_messages', 'public_shares')
AND indexname LIKE '%user_type%';

-- =============================================================================
-- 回滚完成确认
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE '=============================================================================';
    RAISE NOTICE '匿名用户RLS策略回滚完成';
    RAISE NOTICE '=============================================================================';
    RAISE NOTICE '已删除的组件：';
    RAISE NOTICE '1. 所有匿名用户相关的RLS策略';
    RAISE NOTICE '2. user_type审计字段和相关索引';
    RAISE NOTICE '3. cleanup_anonymous_user_data清理函数';
    RAISE NOTICE '4. 匿名用户限制策略';
    RAISE NOTICE '';
    RAISE NOTICE '已恢复的组件：';
    RAISE NOTICE '1. 原始的owner-only RLS策略';
    RAISE NOTICE '2. 服务角色完全访问策略';
    RAISE NOTICE '';
    RAISE NOTICE '注意事项：';
    RAISE NOTICE '1. 请重启应用服务以确保配置生效';
    RAISE NOTICE '2. 请验证现有功能是否正常工作';
    RAISE NOTICE '3. 如需重新启用匿名用户功能，请重新执行ANON_RLS_POLICIES.sql';
    RAISE NOTICE '=============================================================================';
END $$;
