-- =====================================================
-- Supabase RLS 性能优化验证脚本
-- =====================================================
-- 目的：验证 RLS 策略优化是否成功
-- 版本：v1.0
-- 创建日期：2025-01-09
-- 
-- 验证内容：
-- 1. 检查 auth.uid() 是否已优化为 (select auth.uid())
-- 2. 验证策略合并是否成功
-- 3. 确认重复索引已删除
-- 4. 生成详细的验证报告
-- 
-- 执行方式：
-- 在 Supabase Dashboard 的 SQL Editor 中执行此脚本
-- =====================================================

DO $$
DECLARE
  table_rec RECORD;
  policy_rec RECORD;
  total_policies INTEGER := 0;
  optimized_tables INTEGER := 0;
  index_exists BOOLEAN;
BEGIN
  RAISE NOTICE '';
  RAISE NOTICE '========================================';
  RAISE NOTICE 'RLS 性能优化验证报告';
  RAISE NOTICE '========================================';
  RAISE NOTICE '';
  
  -- =====================================================
  -- 第一部分：验证策略优化
  -- =====================================================
  RAISE NOTICE '1. 验证策略优化状态';
  RAISE NOTICE '----------------------------------------';
  
  FOR table_rec IN 
    SELECT DISTINCT tablename
    FROM pg_policies
    WHERE schemaname = 'public'
    AND tablename IN ('users', 'user_profiles', 'user_settings', 'chat_sessions', 'chat_raw',
                      'user_anon', 'anon_sessions', 'anon_messages', 'public_content',
                      'user_metrics', 'audit_logs')
    ORDER BY tablename
  LOOP
    RAISE NOTICE '';
    RAISE NOTICE '表：%', table_rec.tablename;
    
    FOR policy_rec IN
      SELECT policyname, cmd, roles::text[], qual, with_check
      FROM pg_policies
      WHERE schemaname = 'public'
      AND tablename = table_rec.tablename
      ORDER BY policyname
    LOOP
      total_policies := total_policies + 1;
      RAISE NOTICE '  ├─ 策略：% (% for %)', 
        policy_rec.policyname, 
        policy_rec.cmd, 
        array_to_string(policy_rec.roles, ', ');
      
      -- 检查是否包含优化后的 auth.uid() 调用
      IF policy_rec.qual IS NOT NULL THEN
        IF position('select auth.uid()' in policy_rec.qual::text) > 0 THEN
          RAISE NOTICE '  │  ✅ USING 子句已优化（包含 select auth.uid()）';
        ELSIF position('auth.uid()' in policy_rec.qual::text) > 0 THEN
          RAISE NOTICE '  │  ⚠️  USING 子句可能未优化（直接使用 auth.uid()）';
        END IF;
      END IF;
      
      IF policy_rec.with_check IS NOT NULL THEN
        IF position('select auth.uid()' in policy_rec.with_check::text) > 0 THEN
          RAISE NOTICE '  │  ✅ WITH CHECK 子句已优化（包含 select auth.uid()）';
        ELSIF position('auth.uid()' in policy_rec.with_check::text) > 0 THEN
          RAISE NOTICE '  │  ⚠️  WITH CHECK 子句可能未优化（直接使用 auth.uid()）';
        END IF;
      END IF;
    END LOOP;
    
    optimized_tables := optimized_tables + 1;
  END LOOP;
  
  -- =====================================================
  -- 第二部分：验证策略合并
  -- =====================================================
  RAISE NOTICE '';
  RAISE NOTICE '========================================';
  RAISE NOTICE '2. 验证策略合并状态';
  RAISE NOTICE '----------------------------------------';
  
  -- 检查 users 表
  DECLARE
    users_policy_count INTEGER;
  BEGIN
    SELECT COUNT(*) INTO users_policy_count
    FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'users';
    
    RAISE NOTICE '表：users';
    RAISE NOTICE '  策略数量：%', users_policy_count;
    
    IF users_policy_count <= 3 THEN
      RAISE NOTICE '  ✅ 策略已合并（预期 ≤ 3 个）';
    ELSE
      RAISE NOTICE '  ⚠️  策略可能未合并（当前 %% 个）', users_policy_count;
    END IF;
  END;
  
  -- 检查 user_profiles 表
  DECLARE
    profiles_policy_count INTEGER;
  BEGIN
    SELECT COUNT(*) INTO profiles_policy_count
    FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'user_profiles';
    
    RAISE NOTICE '';
    RAISE NOTICE '表：user_profiles';
    RAISE NOTICE '  策略数量：%', profiles_policy_count;
    
    IF profiles_policy_count <= 3 THEN
      RAISE NOTICE '  ✅ 策略已合并（预期 ≤ 3 个）';
    ELSE
      RAISE NOTICE '  ⚠️  策略可能未合并（当前 %% 个）', profiles_policy_count;
    END IF;
  END;
  
  -- 检查 user_settings 表
  DECLARE
    settings_policy_count INTEGER;
  BEGIN
    SELECT COUNT(*) INTO settings_policy_count
    FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'user_settings';
    
    RAISE NOTICE '';
    RAISE NOTICE '表：user_settings';
    RAISE NOTICE '  策略数量：%', settings_policy_count;
    
    IF settings_policy_count <= 3 THEN
      RAISE NOTICE '  ✅ 策略已合并（预期 ≤ 3 个）';
    ELSE
      RAISE NOTICE '  ⚠️  策略可能未合并（当前 %% 个）', settings_policy_count;
    END IF;
  END;
  
  -- 检查 chat_sessions 表
  DECLARE
    sessions_policy_count INTEGER;
  BEGIN
    SELECT COUNT(*) INTO sessions_policy_count
    FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'chat_sessions';
    
    RAISE NOTICE '';
    RAISE NOTICE '表：chat_sessions';
    RAISE NOTICE '  策略数量：%', sessions_policy_count;
    
    IF sessions_policy_count <= 3 THEN
      RAISE NOTICE '  ✅ 策略已合并（预期 ≤ 3 个）';
    ELSE
      RAISE NOTICE '  ⚠️  策略可能未合并（当前 %% 个）', sessions_policy_count;
    END IF;
  END;

  -- 检查 chat_raw 表
  DECLARE
    raw_policy_count INTEGER;
  BEGIN
    SELECT COUNT(*) INTO raw_policy_count
    FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'chat_raw';

    RAISE NOTICE '';
    RAISE NOTICE '表：chat_raw';
    RAISE NOTICE '  策略数量：%', raw_policy_count;

    IF raw_policy_count <= 2 THEN
      RAISE NOTICE '  ✅ 策略已合并（预期 ≤ 2 个）';
    ELSE
      RAISE NOTICE '  ⚠️  策略可能未合并（当前 %% 个）', raw_policy_count;
    END IF;
  END;
  
  -- =====================================================
  -- 第三部分：验证索引清理
  -- =====================================================
  RAISE NOTICE '';
  RAISE NOTICE '========================================';
  RAISE NOTICE '3. 验证索引清理状态';
  RAISE NOTICE '----------------------------------------';
  
  SELECT EXISTS (
    SELECT 1 FROM pg_indexes 
    WHERE schemaname = 'public' 
    AND tablename = 'user_settings' 
    AND indexname = 'idx_user_settings_userid'
  ) INTO index_exists;
  
  IF index_exists THEN
    RAISE NOTICE '⚠️  重复索引仍然存在：idx_user_settings_userid';
  ELSE
    RAISE NOTICE '✅ 重复索引已删除：idx_user_settings_userid';
  END IF;
  
  -- 检查主键索引是否保留
  SELECT EXISTS (
    SELECT 1 FROM pg_indexes 
    WHERE schemaname = 'public' 
    AND tablename = 'user_settings' 
    AND indexname = 'user_settings_pkey'
  ) INTO index_exists;
  
  IF index_exists THEN
    RAISE NOTICE '✅ 主键索引已保留：user_settings_pkey';
  ELSE
    RAISE NOTICE '❌ 主键索引丢失：user_settings_pkey（严重错误！）';
  END IF;
  
  -- =====================================================
  -- 第四部分：总结报告
  -- =====================================================
  RAISE NOTICE '';
  RAISE NOTICE '========================================';
  RAISE NOTICE '验证总结';
  RAISE NOTICE '========================================';
  RAISE NOTICE '优化的表数量：%', optimized_tables;
  RAISE NOTICE '策略总数：%', total_policies;
  RAISE NOTICE '';
  RAISE NOTICE '下一步：';
  RAISE NOTICE '1. 在 Supabase Dashboard → Database → Linter 检查警告数量';
  RAISE NOTICE '2. 运行 E2E 测试：python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py';
  RAISE NOTICE '3. 运行 API 冒烟测试：python scripts/smoke_test.py';
  RAISE NOTICE '4. 监控查询性能变化';
  RAISE NOTICE '';
  RAISE NOTICE '========================================';
  RAISE NOTICE '✅ 验证完成';
  RAISE NOTICE '========================================';
END $$;

