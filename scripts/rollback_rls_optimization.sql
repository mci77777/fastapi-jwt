-- =====================================================
-- Supabase RLS 性能优化回滚脚本
-- =====================================================
-- 目的：紧急情况下回滚 RLS 策略优化
-- 版本：v1.0
-- 创建日期：2025-01-09
-- 
-- 回滚内容：
-- 1. 恢复原始的 auth.uid() 调用（不使用 select）
-- 2. 拆分合并的策略为原始的 service_all + xxx_own 模式
-- 3. 重建被删除的重复索引
-- 
-- ⚠️  警告：
-- 此脚本会将数据库恢复到优化前的状态
-- 仅在出现严重问题时使用
-- 
-- 执行方式：
-- 在 Supabase Dashboard 的 SQL Editor 中执行此脚本
-- =====================================================

DO $$
BEGIN
  RAISE NOTICE '';
  RAISE NOTICE '========================================';
  RAISE NOTICE '⚠️  开始回滚 RLS 性能优化';
  RAISE NOTICE '========================================';
  RAISE NOTICE '';
END $$;

-- =====================================================
-- 第一部分：恢复原始策略（拆分合并的策略）
-- =====================================================

-- -----------------------------------------------------
-- 1. users 表策略回滚
-- -----------------------------------------------------
DO $$
BEGIN
  RAISE NOTICE '回滚 users 表策略...';
  
  -- 删除合并后的策略
  DROP POLICY IF EXISTS users_select ON public.users;
  DROP POLICY IF EXISTS users_insert ON public.users;
  DROP POLICY IF EXISTS users_update ON public.users;
  
  -- 恢复原始策略
  CREATE POLICY users_select_own ON public.users
    FOR SELECT
    USING (user_id::text = auth.uid()::text);
  
  CREATE POLICY users_insert_own ON public.users
    FOR INSERT
    WITH CHECK (user_id::text = auth.uid()::text);
  
  CREATE POLICY users_update_own ON public.users
    FOR UPDATE
    USING (user_id::text = auth.uid()::text);
  
  CREATE POLICY users_service_all ON public.users
    FOR ALL
    USING (auth.role() = 'service_role');
  
  RAISE NOTICE '✅ users 表策略已回滚';
END $$;

-- -----------------------------------------------------
-- 2. user_profiles 表策略回滚
-- -----------------------------------------------------
DO $$
BEGIN
  RAISE NOTICE '回滚 user_profiles 表策略...';
  
  -- 删除合并后的策略
  DROP POLICY IF EXISTS user_profiles_select ON public.user_profiles;
  DROP POLICY IF EXISTS user_profiles_insert ON public.user_profiles;
  DROP POLICY IF EXISTS user_profiles_update ON public.user_profiles;
  
  -- 恢复原始策略
  CREATE POLICY user_profiles_select_own ON public.user_profiles
    FOR SELECT
    USING (userId::text = auth.uid()::text);
  
  CREATE POLICY user_profiles_insert_own ON public.user_profiles
    FOR INSERT
    WITH CHECK (userId::text = auth.uid()::text);
  
  CREATE POLICY user_profiles_update_own ON public.user_profiles
    FOR UPDATE
    USING (userId::text = auth.uid()::text);
  
  CREATE POLICY user_profiles_service_all ON public.user_profiles
    FOR ALL
    USING (auth.role() = 'service_role');
  
  RAISE NOTICE '✅ user_profiles 表策略已回滚';
END $$;

-- -----------------------------------------------------
-- 3. user_settings 表策略回滚
-- -----------------------------------------------------
DO $$
BEGIN
  RAISE NOTICE '回滚 user_settings 表策略...';
  
  -- 删除合并后的策略
  DROP POLICY IF EXISTS user_settings_select ON public.user_settings;
  DROP POLICY IF EXISTS user_settings_insert ON public.user_settings;
  DROP POLICY IF EXISTS user_settings_update ON public.user_settings;
  
  -- 恢复原始策略
  CREATE POLICY user_settings_select_own ON public.user_settings
    FOR SELECT
    USING (userId::text = auth.uid()::text);
  
  CREATE POLICY user_settings_insert_own ON public.user_settings
    FOR INSERT
    WITH CHECK (userId::text = auth.uid()::text);
  
  CREATE POLICY user_settings_update_own ON public.user_settings
    FOR UPDATE
    USING (userId::text = auth.uid()::text);
  
  CREATE POLICY user_settings_service_all ON public.user_settings
    FOR ALL
    USING (auth.role() = 'service_role');
  
  RAISE NOTICE '✅ user_settings 表策略已回滚';
END $$;

-- -----------------------------------------------------
-- 4. chat_sessions 表策略回滚
-- -----------------------------------------------------
DO $$
BEGIN
  RAISE NOTICE '回滚 chat_sessions 表策略...';
  
  -- 删除合并后的策略
  DROP POLICY IF EXISTS chat_sessions_select ON public.chat_sessions;
  DROP POLICY IF EXISTS chat_sessions_insert ON public.chat_sessions;
  DROP POLICY IF EXISTS chat_sessions_update ON public.chat_sessions;
  
  -- 恢复原始策略
  CREATE POLICY chat_sessions_select_own ON public.chat_sessions
    FOR SELECT
    USING (user_id::text = auth.uid()::text);
  
  CREATE POLICY chat_sessions_insert_own ON public.chat_sessions
    FOR INSERT
    WITH CHECK (user_id::text = auth.uid()::text);
  
  CREATE POLICY chat_sessions_update_own ON public.chat_sessions
    FOR UPDATE
    USING (user_id::text = auth.uid()::text);
  
  CREATE POLICY chat_sessions_service_all ON public.chat_sessions
    FOR ALL
    USING (auth.role() = 'service_role');
  
  RAISE NOTICE '✅ chat_sessions 表策略已回滚';
END $$;

-- -----------------------------------------------------
-- 5. chat_raw 表策略回滚
-- -----------------------------------------------------
DO $$
BEGIN
  RAISE NOTICE '回滚 chat_raw 表策略...';
  
  -- 删除合并后的策略
  DROP POLICY IF EXISTS chat_raw_select ON public.chat_raw;
  DROP POLICY IF EXISTS chat_raw_insert ON public.chat_raw;
  
  -- 恢复原始策略
  CREATE POLICY chat_raw_select_own ON public.chat_raw
    FOR SELECT
    USING (
      session_id IN (
        SELECT id FROM public.chat_sessions
        WHERE user_id::text = auth.uid()::text
      )
    );
  
  CREATE POLICY chat_raw_insert_own ON public.chat_raw
    FOR INSERT
    WITH CHECK (
      session_id IN (
        SELECT id FROM public.chat_sessions
        WHERE user_id::text = auth.uid()::text
      )
    );
  
  CREATE POLICY chat_raw_service_all ON public.chat_raw
    FOR ALL
    USING (auth.role() = 'service_role');
  
  RAISE NOTICE '✅ chat_raw 表策略已回滚';
END $$;

-- -----------------------------------------------------
-- 6. user_anon 表策略回滚
-- -----------------------------------------------------
DO $$
BEGIN
  RAISE NOTICE '回滚 user_anon 表策略...';
  
  DROP POLICY IF EXISTS anon_user_select_own ON public.user_anon;
  
  CREATE POLICY anon_user_select_own ON public.user_anon
    FOR SELECT TO public
    USING (
      user_id = auth.uid()
      AND expires_at > now()
      AND is_active = true
    );
  
  RAISE NOTICE '✅ user_anon 表策略已回滚';
END $$;

-- -----------------------------------------------------
-- 7. anon_sessions 表策略回滚
-- -----------------------------------------------------
DO $$
BEGIN
  RAISE NOTICE '回滚 anon_sessions 表策略...';
  
  DROP POLICY IF EXISTS anon_user_select_own_sessions ON public.anon_sessions;
  DROP POLICY IF EXISTS anon_user_update_own_sessions ON public.anon_sessions;
  
  CREATE POLICY anon_user_select_own_sessions ON public.anon_sessions
    FOR SELECT TO public
    USING (
      user_id = auth.uid()
      AND expires_at > now()
      AND is_active = true
    );
  
  CREATE POLICY anon_user_update_own_sessions ON public.anon_sessions
    FOR UPDATE TO public
    USING (
      user_id = auth.uid()
      AND expires_at > now()
      AND is_active = true
    )
    WITH CHECK (
      user_id = auth.uid()
      AND expires_at > now()
      AND is_active = true
    );
  
  RAISE NOTICE '✅ anon_sessions 表策略已回滚';
END $$;

-- -----------------------------------------------------
-- 8. anon_messages 表策略回滚
-- -----------------------------------------------------
DO $$
BEGIN
  RAISE NOTICE '回滚 anon_messages 表策略...';
  
  DROP POLICY IF EXISTS anon_user_select_own_messages ON public.anon_messages;
  DROP POLICY IF EXISTS anon_user_insert_own_messages ON public.anon_messages;
  
  CREATE POLICY anon_user_select_own_messages ON public.anon_messages
    FOR SELECT TO public
    USING (
      user_id = auth.uid()
      AND EXISTS (
        SELECT 1 FROM public.user_anon ua
        WHERE ua.user_id = auth.uid()
          AND ua.expires_at > now()
          AND ua.is_active = true
      )
    );
  
  CREATE POLICY anon_user_insert_own_messages ON public.anon_messages
    FOR INSERT TO public
    WITH CHECK (
      user_id = auth.uid()
      AND EXISTS (
        SELECT 1 FROM public.user_anon ua
        WHERE ua.user_id = auth.uid()
          AND ua.expires_at > now()
          AND ua.is_active = true
      )
    );
  
  RAISE NOTICE '✅ anon_messages 表策略已回滚';
END $$;

-- -----------------------------------------------------
-- 9. public_content 表策略回滚
-- -----------------------------------------------------
DO $$
BEGIN
  RAISE NOTICE '回滚 public_content 表策略...';

  DROP POLICY IF EXISTS anon_user_select_public ON public.public_content;
  DROP POLICY IF EXISTS authenticated_user_select_own ON public.public_content;

  CREATE POLICY anon_user_select_public ON public.public_content
    FOR SELECT TO public
    USING (is_public = true);

  CREATE POLICY authenticated_user_select_own ON public.public_content
    FOR SELECT TO authenticated
    USING (owner_id = auth.uid() OR is_public = true);

  RAISE NOTICE '✅ public_content 表策略已回滚';
END $$;

-- -----------------------------------------------------
-- 10. user_metrics 表策略回滚
-- -----------------------------------------------------
DO $$
DECLARE
  user_id_type TEXT;
BEGIN
  RAISE NOTICE '回滚 user_metrics 表策略...';

  -- 检测 user_id 字段类型
  SELECT data_type INTO user_id_type
  FROM information_schema.columns
  WHERE table_schema = 'public' AND table_name = 'user_metrics' AND column_name = 'user_id';

  DROP POLICY IF EXISTS user_metrics_user_own ON public.user_metrics;

  -- 根据字段类型恢复原始策略
  IF user_id_type IN ('character varying', 'text', 'character') THEN
    CREATE POLICY user_metrics_user_own ON public.user_metrics
      FOR SELECT
      USING (user_id = auth.uid()::text);
    RAISE NOTICE '✅ user_metrics 表策略已回滚（varchar 类型）';
  ELSE
    CREATE POLICY user_metrics_user_own ON public.user_metrics
      FOR SELECT
      USING (user_id = auth.uid());
    RAISE NOTICE '✅ user_metrics 表策略已回滚（uuid 类型）';
  END IF;
END $$;

-- -----------------------------------------------------
-- 11. audit_logs 表策略回滚
-- -----------------------------------------------------
DO $$
DECLARE
  user_id_type TEXT;
BEGIN
  RAISE NOTICE '回滚 audit_logs 表策略...';

  -- 检测 user_id 字段类型
  SELECT data_type INTO user_id_type
  FROM information_schema.columns
  WHERE table_schema = 'public' AND table_name = 'audit_logs' AND column_name = 'user_id';

  DROP POLICY IF EXISTS audit_logs_user_read_own ON public.audit_logs;

  -- 根据字段类型恢复原始策略
  IF user_id_type IN ('character varying', 'text', 'character') THEN
    CREATE POLICY audit_logs_user_read_own ON public.audit_logs
      FOR SELECT
      USING (user_id = auth.uid()::text);
    RAISE NOTICE '✅ audit_logs 表策略已回滚（varchar 类型）';
  ELSE
    CREATE POLICY audit_logs_user_read_own ON public.audit_logs
      FOR SELECT
      USING (user_id = auth.uid());
    RAISE NOTICE '✅ audit_logs 表策略已回滚（uuid 类型）';
  END IF;
END $$;

-- =====================================================
-- 第二部分：重建被删除的索引
-- =====================================================

DO $$
BEGIN
  RAISE NOTICE '';
  RAISE NOTICE '重建被删除的索引...';

  -- 重建 user_settings 表的重复索引
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname = 'public'
    AND tablename = 'user_settings'
    AND indexname = 'idx_user_settings_userid'
  ) THEN
    CREATE INDEX idx_user_settings_userid ON public.user_settings(userId);
    RAISE NOTICE '✅ 已重建索引：idx_user_settings_userid';
  ELSE
    RAISE NOTICE 'ℹ️  索引已存在，跳过：idx_user_settings_userid';
  END IF;
END $$;

-- =====================================================
-- 第三部分：回滚总结
-- =====================================================

DO $$
DECLARE
  policy_count INTEGER;
BEGIN
  RAISE NOTICE '';
  RAISE NOTICE '========================================';
  RAISE NOTICE '回滚完成统计';
  RAISE NOTICE '========================================';

  -- 统计回滚后的策略数量
  SELECT COUNT(*) INTO policy_count
  FROM pg_policies
  WHERE schemaname = 'public'
  AND tablename IN ('users', 'user_profiles', 'user_settings', 'chat_sessions', 'chat_raw',
                    'user_anon', 'anon_sessions', 'anon_messages', 'public_content',
                    'user_metrics', 'audit_logs');

  RAISE NOTICE '✅ 回滚后的策略总数：%', policy_count;
  RAISE NOTICE '✅ 所有策略已恢复为原始状态';
  RAISE NOTICE '✅ 重复索引已重建';
  RAISE NOTICE '';
  RAISE NOTICE '========================================';
  RAISE NOTICE '⚠️  RLS 性能优化已回滚';
  RAISE NOTICE '========================================';
  RAISE NOTICE '';
  RAISE NOTICE '下一步：';
  RAISE NOTICE '1. 运行 E2E 测试确认功能正常';
  RAISE NOTICE '2. 检查 Supabase Linter 警告（预期会恢复到优化前的状态）';
  RAISE NOTICE '3. 如需重新优化，请执行：scripts/optimize_rls_performance.sql';
  RAISE NOTICE '';
END $$;

