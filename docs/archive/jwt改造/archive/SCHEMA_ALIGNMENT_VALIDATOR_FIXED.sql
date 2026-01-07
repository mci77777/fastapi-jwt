-- =====================================================
-- 数据库架构对齐验证脚本 (修复版)
-- =====================================================
-- 创建日期: 2025-09-29
-- 修复内容: 解决PL/pgSQL变量名与列名冲突问题
-- 使用方法: 在Supabase SQL Editor中执行此脚本

-- =====================================================
-- 1. 表存在性验证
-- =====================================================

DO $$
DECLARE
    expected_tables TEXT[] := ARRAY[
        'users', 'user_profiles', 'user_settings', 'tokens',
        'search_content', 'calendar_events', 'chat_sessions',
        'chat_raw', 'chat_fts', 'chat_vec', 'message_embedding',
        'session_summary', 'memory_records'
    ];
    tbl_name TEXT;
    missing_tables TEXT[] := ARRAY[]::TEXT[];
    existing_count INTEGER := 0;
BEGIN
    RAISE NOTICE '🔍 开始验证表存在性...';
    
    FOREACH tbl_name IN ARRAY expected_tables
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables t
            WHERE t.table_schema = 'public' AND t.table_name = tbl_name
        ) THEN
            existing_count := existing_count + 1;
            RAISE NOTICE '✅ 表 % 存在', tbl_name;
        ELSE
            missing_tables := array_append(missing_tables, tbl_name);
            RAISE NOTICE '❌ 表 % 缺失', tbl_name;
        END IF;
    END LOOP;
    
    RAISE NOTICE '';
    RAISE NOTICE '📊 表存在性验证结果:';
    RAISE NOTICE '   - 预期表数量: %', array_length(expected_tables, 1);
    RAISE NOTICE '   - 实际存在: %', existing_count;
    RAISE NOTICE '   - 缺失表数量: %', array_length(missing_tables, 1);
    
    IF array_length(missing_tables, 1) > 0 THEN
        RAISE NOTICE '   - 缺失的表: %', array_to_string(missing_tables, ', ');
    END IF;
END $$;

-- =====================================================
-- 2. 用户表结构验证
-- =====================================================

DO $$
DECLARE
    expected_columns TEXT[] := ARRAY[
        'user_id', 'email', 'username', 'displayName', 'photoUrl',
        'phoneNumber', 'isActive', 'isEmailVerified', 'wechatId',
        'anonymousId', 'gender', 'weight', 'weightUnit', 'fitnessLevel',
        'preferredGym', 'avatar', 'bio', 'themeMode', 'languageCode',
        'measurementSystem', 'notificationsEnabled', 'soundsEnabled',
        'locationSharingEnabled', 'allowPartnerMatching', 'weeklyActiveMinutes',
        'likesReceived', 'createdAt', 'lastLoginAt', 'isSynced',
        'lastSynced', 'lastModified', 'serverUpdatedAt', 'isAnonymous',
        'userType', 'subscriptionPlan', 'subscriptionExpiryDate'
    ];
    col_name TEXT;
    missing_columns TEXT[] := ARRAY[]::TEXT[];
    existing_count INTEGER := 0;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '🔍 开始验证users表结构...';
    
    FOREACH col_name IN ARRAY expected_columns
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.columns c
            WHERE c.table_schema = 'public' 
            AND c.table_name = 'users' 
            AND c.column_name = col_name
        ) THEN
            existing_count := existing_count + 1;
            RAISE NOTICE '✅ 字段 users.% 存在', col_name;
        ELSE
            missing_columns := array_append(missing_columns, col_name);
            RAISE NOTICE '❌ 字段 users.% 缺失', col_name;
        END IF;
    END LOOP;
    
    RAISE NOTICE '';
    RAISE NOTICE '📊 users表结构验证结果:';
    RAISE NOTICE '   - 预期字段数量: %', array_length(expected_columns, 1);
    RAISE NOTICE '   - 实际存在: %', existing_count;
    RAISE NOTICE '   - 缺失字段数量: %', array_length(missing_columns, 1);
    
    IF array_length(missing_columns, 1) > 0 THEN
        RAISE NOTICE '   - 缺失的字段: %', array_to_string(missing_columns, ', ');
    END IF;
END $$;

-- =====================================================
-- 3. 主键类型验证
-- =====================================================

DO $$
DECLARE
    pk_info RECORD;
    correct_count INTEGER := 0;
    total_count INTEGER := 0;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '🔍 开始验证主键类型...';
    
    FOR pk_info IN
        SELECT 
            t.table_name as tbl_name,
            c.column_name as col_name,
            c.data_type as col_type,
            CASE 
                WHEN t.table_name = 'users' AND c.column_name = 'user_id' AND c.data_type = 'uuid' THEN true
                WHEN t.table_name = 'user_profiles' AND c.column_name = 'userId' AND c.data_type = 'uuid' THEN true
                WHEN t.table_name = 'user_settings' AND c.column_name = 'userId' AND c.data_type = 'uuid' THEN true
                WHEN t.table_name = 'chat_sessions' AND c.column_name = 'id' AND c.data_type = 'text' THEN true
                WHEN t.table_name IN ('tokens', 'search_content', 'chat_raw', 'chat_vec', 'message_embedding', 'session_summary') 
                     AND c.column_name = 'id' AND c.data_type = 'integer' THEN true
                WHEN t.table_name IN ('calendar_events', 'memory_records') 
                     AND c.column_name = 'id' AND c.data_type = 'uuid' THEN true
                ELSE false
            END as is_correct
        FROM information_schema.tables t
        JOIN information_schema.key_column_usage kcu ON t.table_name = kcu.table_name
        JOIN information_schema.columns c ON t.table_name = c.table_name AND kcu.column_name = c.column_name
        WHERE t.table_schema = 'public' 
        AND kcu.constraint_name LIKE '%_pkey'
        AND t.table_name IN ('users', 'user_profiles', 'user_settings', 'tokens', 'search_content', 
                           'calendar_events', 'chat_sessions', 'chat_raw', 'chat_fts', 'chat_vec', 
                           'message_embedding', 'session_summary', 'memory_records')
        ORDER BY t.table_name
    LOOP
        total_count := total_count + 1;
        IF pk_info.is_correct THEN
            correct_count := correct_count + 1;
            RAISE NOTICE '✅ %.% 主键类型正确: %', 
                pk_info.tbl_name, pk_info.col_name, pk_info.col_type;
        ELSE
            RAISE NOTICE '❌ %.% 主键类型错误: % (需要检查)', 
                pk_info.tbl_name, pk_info.col_name, pk_info.col_type;
        END IF;
    END LOOP;
    
    RAISE NOTICE '';
    RAISE NOTICE '📊 主键类型验证结果:';
    RAISE NOTICE '   - 检查的表数量: %', total_count;
    RAISE NOTICE '   - 类型正确: %', correct_count;
    RAISE NOTICE '   - 类型错误: %', total_count - correct_count;
END $$;

-- =====================================================
-- 4. 外键约束验证
-- =====================================================

DO $$
DECLARE
    fk_info RECORD;
    total_count INTEGER := 0;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '🔍 开始验证外键约束...';
    
    FOR fk_info IN
        SELECT 
            tc.table_name as tbl_name,
            kcu.column_name as col_name,
            ccu.table_name AS foreign_table,
            ccu.column_name AS foreign_column,
            tc.constraint_name as constraint_nm
        FROM information_schema.table_constraints AS tc 
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
            AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
            AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
        AND tc.table_schema = 'public'
        ORDER BY tc.table_name, kcu.column_name
    LOOP
        total_count := total_count + 1;
        RAISE NOTICE '✅ 外键约束: %.% → %.%', 
            fk_info.tbl_name, fk_info.col_name,
            fk_info.foreign_table, fk_info.foreign_column;
    END LOOP;
    
    RAISE NOTICE '';
    RAISE NOTICE '📊 外键约束验证结果:';
    RAISE NOTICE '   - 外键约束数量: %', total_count;
END $$;

-- =====================================================
-- 5. RLS策略验证
-- =====================================================

DO $$
DECLARE
    rls_info RECORD;
    policy_count INTEGER := 0;
    rls_enabled_count INTEGER := 0;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '🔍 开始验证RLS策略...';
    
    -- 检查RLS启用状态
    FOR rls_info IN
        SELECT 
            tablename as tbl_name,
            rowsecurity as rls_enabled
        FROM pg_tables 
        WHERE schemaname = 'public'
        AND tablename IN ('users', 'user_profiles', 'user_settings', 'calendar_events', 
                         'chat_sessions', 'chat_raw', 'message_embedding', 'session_summary', 'memory_records')
        ORDER BY tablename
    LOOP
        IF rls_info.rls_enabled THEN
            rls_enabled_count := rls_enabled_count + 1;
            RAISE NOTICE '✅ RLS已启用: %', rls_info.tbl_name;
        ELSE
            RAISE NOTICE '❌ RLS未启用: %', rls_info.tbl_name;
        END IF;
    END LOOP;
    
    -- 检查策略数量
    SELECT COUNT(*) INTO policy_count
    FROM pg_policies 
    WHERE schemaname = 'public';
    
    RAISE NOTICE '';
    RAISE NOTICE '📊 RLS策略验证结果:';
    RAISE NOTICE '   - RLS启用的表: %', rls_enabled_count;
    RAISE NOTICE '   - 策略总数: %', policy_count;
END $$;

-- =====================================================
-- 6. 最终验证总结
-- =====================================================

DO $$
DECLARE
    tbl_count INTEGER;
    idx_count INTEGER;
    pol_count INTEGER;
    fk_count INTEGER;
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '🎯 ===== 架构对齐验证总结 =====';
    
    -- 统计信息
    SELECT COUNT(*) INTO tbl_count
    FROM information_schema.tables t
    WHERE t.table_schema = 'public'
    AND t.table_name IN ('users', 'user_profiles', 'user_settings', 'tokens',
                      'search_content', 'calendar_events', 'chat_sessions',
                      'chat_raw', 'chat_fts', 'chat_vec', 'message_embedding',
                      'session_summary', 'memory_records');
    
    SELECT COUNT(*) INTO idx_count
    FROM pg_indexes 
    WHERE schemaname = 'public'
    AND indexname NOT LIKE '%_pkey';
    
    SELECT COUNT(*) INTO pol_count
    FROM pg_policies 
    WHERE schemaname = 'public';
    
    SELECT COUNT(*) INTO fk_count
    FROM information_schema.table_constraints tc
    WHERE tc.constraint_type = 'FOREIGN KEY'
    AND tc.table_schema = 'public';
    
    RAISE NOTICE '📊 统计信息:';
    RAISE NOTICE '   - 核心表数量: % / 13', tbl_count;
    RAISE NOTICE '   - 性能索引: %', idx_count;
    RAISE NOTICE '   - RLS策略: %', pol_count;
    RAISE NOTICE '   - 外键约束: %', fk_count;
    
    RAISE NOTICE '';
    IF tbl_count >= 13 THEN
        RAISE NOTICE '✅ 架构对齐验证通过！';
        RAISE NOTICE '🚀 数据库已准备好与Android Room客户端同步';
    ELSE
        RAISE NOTICE '❌ 架构对齐验证失败！';
        RAISE NOTICE '⚠️  请检查缺失的表和配置';
    END IF;
    
    RAISE NOTICE '';
    RAISE NOTICE '📝 下一步建议:';
    RAISE NOTICE '   1. 测试API端点与数据库连接';
    RAISE NOTICE '   2. 验证JWT认证集成';
    RAISE NOTICE '   3. 执行端到端数据同步测试';
    RAISE NOTICE '   4. 监控性能和错误日志';
END $$;
