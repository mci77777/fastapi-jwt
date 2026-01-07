-- =====================================================
-- GymBro 对齐架构 - 基于Android Room Schema v31
-- =====================================================
-- 创建日期: 2025-09-29
-- 目标: 彻底删除现有表结构，重建为Android Room数据库完全对齐
-- 兼容性: Supabase PostgreSQL + Android Room SQLite
-- ⚠️ 警告: 此脚本会删除所有现有数据！

-- 启用必要的扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_cron";

-- =====================================================
-- 第一步：彻底删除所有现有表（按依赖关系顺序）
-- =====================================================

-- 删除所有可能存在的表（CASCADE会自动处理依赖关系）
DROP TABLE IF EXISTS session_summary CASCADE;
DROP TABLE IF EXISTS message_embedding CASCADE;
DROP TABLE IF EXISTS chat_raw CASCADE;
DROP TABLE IF EXISTS chat_sessions CASCADE;
DROP TABLE IF EXISTS chat_vec CASCADE;
DROP TABLE IF EXISTS chat_fts CASCADE;
DROP TABLE IF EXISTS memory_records CASCADE;
DROP TABLE IF EXISTS calendar_events CASCADE;
DROP TABLE IF EXISTS search_content CASCADE;
DROP TABLE IF EXISTS tokens CASCADE;
DROP TABLE IF EXISTS user_settings CASCADE;
DROP TABLE IF EXISTS user_profiles CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS "user" CASCADE;

-- 删除可能存在的健身相关表
DROP TABLE IF EXISTS template_versions CASCADE;
DROP TABLE IF EXISTS template_exercises CASCADE;
DROP TABLE IF EXISTS workout_templates CASCADE;
DROP TABLE IF EXISTS session_sets CASCADE;
DROP TABLE IF EXISTS session_exercises CASCADE;
DROP TABLE IF EXISTS session_autosave CASCADE;
DROP TABLE IF EXISTS workout_sessions CASCADE;
DROP TABLE IF EXISTS plan_templates CASCADE;
DROP TABLE IF EXISTS plan_days CASCADE;
DROP TABLE IF EXISTS workout_plans CASCADE;
DROP TABLE IF EXISTS exercise_usage_stats CASCADE;
DROP TABLE IF EXISTS exercise_search_history CASCADE;
DROP TABLE IF EXISTS exercise_history_stats CASCADE;
DROP TABLE IF EXISTS exercise_fts CASCADE;
DROP TABLE IF EXISTS exercise CASCADE;
DROP TABLE IF EXISTS daily_stats CASCADE;
DROP TABLE IF EXISTS public_shares CASCADE;

-- 删除可能存在的函数
DROP FUNCTION IF EXISTS cleanup_anonymous_user_data(INTEGER);
DROP FUNCTION IF EXISTS update_modified_timestamp();
DROP FUNCTION IF EXISTS update_user_profiles_timestamp();
DROP FUNCTION IF EXISTS unix_timestamp_ms();

-- 删除可能存在的域
DROP DOMAIN IF EXISTS boolean_int;

-- =====================================================
-- 辅助函数定义
-- =====================================================

-- Unix时间戳生成函数（毫秒）
CREATE OR REPLACE FUNCTION unix_timestamp_ms()
RETURNS BIGINT AS $$
BEGIN
    RETURN extract(epoch from now()) * 1000;
END;
$$ LANGUAGE plpgsql;

-- 布尔整数域定义（兼容Android）
CREATE DOMAIN boolean_int AS INTEGER CHECK (VALUE IN (0, 1));

-- =====================================================
-- 第二步：重建核心用户表（基于Android Room users表）
-- =====================================================

CREATE TABLE users (
    user_id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT,
    username TEXT NOT NULL,
    displayName TEXT,
    photoUrl TEXT,
    phoneNumber TEXT,
    isActive INTEGER NOT NULL DEFAULT 1,
    isEmailVerified INTEGER NOT NULL DEFAULT 0,
    wechatId TEXT,
    anonymousId TEXT,
    gender TEXT,
    weight REAL,
    weightUnit TEXT,
    fitnessLevel INTEGER,
    preferredGym TEXT,
    avatar TEXT,
    bio TEXT,
    themeMode TEXT NOT NULL DEFAULT 'system',
    languageCode TEXT NOT NULL DEFAULT 'zh',
    measurementSystem TEXT NOT NULL DEFAULT 'metric',
    notificationsEnabled INTEGER NOT NULL DEFAULT 1,
    soundsEnabled INTEGER NOT NULL DEFAULT 1,
    locationSharingEnabled INTEGER NOT NULL DEFAULT 0,
    settingsJson JSONB,
    fitnessGoalsJson JSONB,
    privacySettingsJson JSONB,
    workoutDaysJson JSONB,
    preferredWorkoutTimesJson JSONB,
    preferredFoodsJson JSONB,
    notificationSettingsJson JSONB,
    soundSettingsJson JSONB,
    backupSettingsJson JSONB,
    partnerMatchPreferencesJson JSONB,
    blockedUsersJson JSONB,
    allowPartnerMatching INTEGER NOT NULL DEFAULT 0,
    weeklyActiveMinutes INTEGER NOT NULL DEFAULT 0,
    likesReceived INTEGER NOT NULL DEFAULT 0,
    createdAt BIGINT DEFAULT unix_timestamp_ms(),
    lastLoginAt BIGINT,
    isSynced INTEGER NOT NULL DEFAULT 0,
    lastSynced BIGINT NOT NULL DEFAULT 0,
    lastModified BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    serverUpdatedAt BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    isAnonymous INTEGER NOT NULL DEFAULT 0,
    userType TEXT NOT NULL DEFAULT 'regular',
    subscriptionPlan TEXT NOT NULL DEFAULT 'free',
    subscriptionExpiryDate BIGINT
);

-- =====================================================
-- 用户档案表（基于Android Room user_profiles表）
-- =====================================================

CREATE TABLE user_profiles (
    userId UUID PRIMARY KEY,
    username TEXT,
    displayName TEXT,
    email TEXT,
    phoneNumber TEXT,
    profileImageUrl TEXT,
    bio TEXT,
    gender TEXT,
    height REAL,
    heightUnit TEXT,
    weight REAL,
    weightUnit TEXT,
    fitnessLevel INTEGER,
    fitnessGoals TEXT NOT NULL DEFAULT '[]',
    workoutDays TEXT NOT NULL DEFAULT '[]',
    allowPartnerMatching INTEGER NOT NULL DEFAULT 0,
    totalWorkoutCount INTEGER NOT NULL DEFAULT 0,
    weeklyActiveMinutes INTEGER NOT NULL DEFAULT 0,
    likesReceived INTEGER NOT NULL DEFAULT 0,
    isAnonymous INTEGER NOT NULL DEFAULT 0,
    hasValidSubscription INTEGER NOT NULL DEFAULT 0,
    lastUpdated BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    createdAt BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    profileSummary TEXT,
    vector BYTEA,
    vectorCreatedAt BIGINT,
    FOREIGN KEY (userId) REFERENCES users(user_id) ON DELETE CASCADE
);

-- =====================================================
-- 用户设置表（基于Android Room user_settings表）
-- =====================================================

CREATE TABLE user_settings (
    userId UUID PRIMARY KEY,
    themeMode TEXT NOT NULL DEFAULT 'system',
    languageCode TEXT NOT NULL DEFAULT 'zh',
    measurementSystem TEXT NOT NULL DEFAULT 'metric',
    notificationsEnabled INTEGER NOT NULL DEFAULT 1,
    soundsEnabled INTEGER NOT NULL DEFAULT 1,
    locationSharingEnabled INTEGER NOT NULL DEFAULT 0,
    dataSharingEnabled INTEGER NOT NULL DEFAULT 0,
    allowWorkoutSharing INTEGER NOT NULL DEFAULT 0,
    autoBackupEnabled INTEGER NOT NULL DEFAULT 0,
    backupFrequency INTEGER NOT NULL DEFAULT 7,
    lastBackupTime BIGINT NOT NULL DEFAULT 0,
    allowPartnerMatching INTEGER NOT NULL DEFAULT 0,
    preferredMatchDistance INTEGER NOT NULL DEFAULT 10,
    matchByFitnessLevel INTEGER NOT NULL DEFAULT 1,
    lastModified BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    FOREIGN KEY (userId) REFERENCES users(user_id) ON DELETE CASCADE
);

-- =====================================================
-- 令牌表（基于Android Room tokens表）
-- =====================================================

CREATE TABLE tokens (
    id SERIAL PRIMARY KEY,
    accessToken TEXT NOT NULL,
    refreshToken TEXT NOT NULL,
    tokenType TEXT NOT NULL DEFAULT 'Bearer',
    expiresIn INTEGER NOT NULL,
    issuedAt BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    userId UUID NOT NULL,
    scope TEXT,
    FOREIGN KEY (userId) REFERENCES users(user_id) ON DELETE CASCADE
);

-- =====================================================
-- 搜索内容表（基于Android Room search_content表）
-- =====================================================

CREATE TABLE search_content (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at BIGINT NOT NULL DEFAULT unix_timestamp_ms()
);

-- =====================================================
-- 日历事件表（基于Android Room calendar_events表）
-- =====================================================

CREATE TABLE calendar_events (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    workout_id TEXT,
    event_type TEXT NOT NULL,
    date BIGINT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    duration_minutes INTEGER,
    color TEXT,
    is_all_day INTEGER NOT NULL DEFAULT 0,
    reminder_minutes_before INTEGER,
    is_completed INTEGER NOT NULL DEFAULT 0,
    completion_date BIGINT,
    cancelled INTEGER NOT NULL DEFAULT 0,
    recurrence_rule TEXT,
    created_at BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    modified_at BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    is_synced INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- =====================================================
-- 聊天会话表（基于Android Room chat_sessions表）
-- =====================================================

CREATE TABLE chat_sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    user_id UUID NOT NULL,
    created_at BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    last_active_at BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    is_active INTEGER NOT NULL DEFAULT 0,
    status INTEGER NOT NULL DEFAULT 0,
    message_count INTEGER NOT NULL DEFAULT 0,
    summary TEXT,
    metadata TEXT,
    db_created_at BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    db_updated_at BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- =====================================================
-- 聊天原始数据表（基于Android Room chat_raw表）
-- =====================================================

CREATE TABLE chat_raw (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    timestamp BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    metadata TEXT NOT NULL DEFAULT '{}',
    message_id TEXT NOT NULL,
    in_reply_to_message_id TEXT,
    thinking_nodes TEXT,
    final_markdown TEXT,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

-- =====================================================
-- 聊天全文搜索表（基于Android Room chat_fts表）
-- =====================================================

-- 注意：PostgreSQL使用不同的全文搜索实现
CREATE TABLE chat_fts (
    content TEXT NOT NULL,
    rowid SERIAL PRIMARY KEY,
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

-- =====================================================
-- 聊天向量表（基于Android Room chat_vec表）
-- =====================================================

CREATE TABLE chat_vec (
    id SERIAL PRIMARY KEY,
    embedding BYTEA NOT NULL,
    embedding_dim INTEGER NOT NULL,
    created_at BIGINT NOT NULL DEFAULT unix_timestamp_ms()
);

-- =====================================================
-- 消息嵌入表（基于Android Room message_embedding表）
-- =====================================================

CREATE TABLE message_embedding (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL,
    vector BYTEA NOT NULL,
    vector_dim INTEGER NOT NULL,
    embedding_status TEXT NOT NULL DEFAULT 'pending',
    created_at BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    model_version TEXT NOT NULL DEFAULT 'v1.0',
    generation_time_ms INTEGER,
    text_length INTEGER NOT NULL,
    FOREIGN KEY (message_id) REFERENCES chat_raw(id) ON DELETE CASCADE
);

-- =====================================================
-- 会话摘要表（基于Android Room session_summary表）
-- =====================================================

CREATE TABLE session_summary (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    range_start INTEGER NOT NULL,
    range_end INTEGER NOT NULL,
    summary_content TEXT NOT NULL,
    summary_type TEXT NOT NULL DEFAULT 'auto',
    created_at BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    original_message_count INTEGER NOT NULL,
    original_token_count INTEGER NOT NULL,
    summary_token_count INTEGER NOT NULL,
    compression_ratio REAL NOT NULL,
    model_used TEXT NOT NULL DEFAULT 'gpt-3.5-turbo',
    generation_time_ms INTEGER,
    quality_score REAL,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
);

-- =====================================================
-- 记忆记录表（基于Android Room memory_records表）
-- =====================================================

CREATE TABLE memory_records (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL,
    tier TEXT NOT NULL DEFAULT 'standard',
    created_at BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    expires_at BIGINT,
    importance INTEGER NOT NULL DEFAULT 5,
    embedding BYTEA,
    embedding_dim INTEGER NOT NULL DEFAULT 0,
    embedding_status TEXT NOT NULL DEFAULT 'pending',
    payload_json JSONB NOT NULL DEFAULT '{}',
    content_length INTEGER NOT NULL DEFAULT 0,
    model_version TEXT NOT NULL DEFAULT 'v1.0',
    generation_time_ms INTEGER,
    updated_at BIGINT NOT NULL DEFAULT unix_timestamp_ms(),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- =====================================================
-- 性能索引（基于Android Room索引）
-- =====================================================

-- 用户表索引
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_isActive ON users(isActive);
CREATE INDEX idx_users_userType ON users(userType);
CREATE INDEX idx_users_lastLoginAt ON users(lastLoginAt);
CREATE INDEX idx_users_synced ON users(isSynced);

-- 用户设置表索引
CREATE UNIQUE INDEX idx_user_settings_userId ON user_settings(userId);

-- 日历事件表索引
CREATE INDEX idx_calendar_events_user_id ON calendar_events(user_id);
CREATE INDEX idx_calendar_events_workout_id ON calendar_events(workout_id);
CREATE INDEX idx_calendar_events_date ON calendar_events(date);

-- 聊天会话表索引
CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_sessions_user_id_is_active ON chat_sessions(user_id, is_active);
CREATE INDEX idx_chat_sessions_user_id_last_active_at ON chat_sessions(user_id, last_active_at);
CREATE INDEX idx_chat_sessions_created_at ON chat_sessions(created_at);
CREATE INDEX idx_chat_sessions_status ON chat_sessions(status);

-- 聊天原始数据表索引
CREATE INDEX idx_chat_raw_session_id ON chat_raw(session_id);
CREATE INDEX idx_chat_raw_role ON chat_raw(role);
CREATE INDEX idx_chat_raw_timestamp ON chat_raw(timestamp);
CREATE INDEX idx_chat_raw_session_id_timestamp ON chat_raw(session_id, timestamp);

-- 消息嵌入表索引
CREATE UNIQUE INDEX idx_message_embedding_message_id ON message_embedding(message_id);
CREATE INDEX idx_message_embedding_created_at ON message_embedding(created_at);
CREATE INDEX idx_message_embedding_embedding_status ON message_embedding(embedding_status);

-- 会话摘要表索引
CREATE INDEX idx_session_summary_session_id ON session_summary(session_id);
CREATE INDEX idx_session_summary_range_start_range_end ON session_summary(range_start, range_end);
CREATE INDEX idx_session_summary_created_at ON session_summary(created_at);
CREATE INDEX idx_session_summary_summary_type ON session_summary(summary_type);

-- 全文搜索索引
CREATE INDEX idx_chat_fts_search_vector ON chat_fts USING GIN(search_vector);

-- =====================================================
-- 行级安全策略（RLS）
-- =====================================================

-- 启用RLS
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendar_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_raw ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_embedding ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_records ENABLE ROW LEVEL SECURITY;

-- 用户表RLS策略
CREATE POLICY users_select_own ON users
    FOR SELECT USING (user_id::text = auth.uid()::text);

CREATE POLICY users_update_own ON users
    FOR UPDATE USING (user_id::text = auth.uid()::text);

CREATE POLICY users_insert_own ON users
    FOR INSERT WITH CHECK (user_id::text = auth.uid()::text);

-- 服务角色完全访问
CREATE POLICY users_service_all ON users
    FOR ALL USING (auth.role() = 'service_role');

-- 用户档案表RLS策略
CREATE POLICY user_profiles_select_own ON user_profiles
    FOR SELECT USING (userId::text = auth.uid()::text);

CREATE POLICY user_profiles_update_own ON user_profiles
    FOR UPDATE USING (userId::text = auth.uid()::text);

CREATE POLICY user_profiles_insert_own ON user_profiles
    FOR INSERT WITH CHECK (userId::text = auth.uid()::text);

CREATE POLICY user_profiles_service_all ON user_profiles
    FOR ALL USING (auth.role() = 'service_role');

-- 用户设置表RLS策略
CREATE POLICY user_settings_select_own ON user_settings
    FOR SELECT USING (userId::text = auth.uid()::text);

CREATE POLICY user_settings_update_own ON user_settings
    FOR UPDATE USING (userId::text = auth.uid()::text);

CREATE POLICY user_settings_insert_own ON user_settings
    FOR INSERT WITH CHECK (userId::text = auth.uid()::text);

CREATE POLICY user_settings_service_all ON user_settings
    FOR ALL USING (auth.role() = 'service_role');

-- 聊天会话表RLS策略
CREATE POLICY chat_sessions_select_own ON chat_sessions
    FOR SELECT USING (user_id::text = auth.uid()::text);

CREATE POLICY chat_sessions_update_own ON chat_sessions
    FOR UPDATE USING (user_id::text = auth.uid()::text);

CREATE POLICY chat_sessions_insert_own ON chat_sessions
    FOR INSERT WITH CHECK (user_id::text = auth.uid()::text);

CREATE POLICY chat_sessions_service_all ON chat_sessions
    FOR ALL USING (auth.role() = 'service_role');

-- 聊天原始数据表RLS策略（通过session关联）
CREATE POLICY chat_raw_select_own ON chat_raw
    FOR SELECT USING (
        session_id IN (
            SELECT id FROM chat_sessions
            WHERE user_id::text = auth.uid()::text
        )
    );

CREATE POLICY chat_raw_insert_own ON chat_raw
    FOR INSERT WITH CHECK (
        session_id IN (
            SELECT id FROM chat_sessions
            WHERE user_id::text = auth.uid()::text
        )
    );

CREATE POLICY chat_raw_service_all ON chat_raw
    FOR ALL USING (auth.role() = 'service_role');

-- =====================================================
-- 匿名用户支持
-- =====================================================

-- 匿名用户数据清理函数
CREATE OR REPLACE FUNCTION cleanup_anonymous_user_data(days_old INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER := 0;
    cutoff_timestamp BIGINT;
BEGIN
    -- 计算截止时间戳（毫秒）
    cutoff_timestamp := extract(epoch from (now() - interval '1 day' * days_old)) * 1000;

    -- 删除过期的匿名用户数据
    WITH deleted_users AS (
        DELETE FROM users
        WHERE isAnonymous = 1
        AND createdAt < cutoff_timestamp
        RETURNING user_id
    )
    SELECT COUNT(*) INTO deleted_count FROM deleted_users;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 匿名用户限制策略
CREATE POLICY anonymous_user_restrictions ON users
    FOR ALL USING (
        CASE
            WHEN isAnonymous = 1 THEN
                -- 匿名用户只能访问自己的数据
                user_id::text = auth.uid()::text
            ELSE
                -- 认证用户正常访问
                user_id::text = auth.uid()::text OR auth.role() = 'service_role'
        END
    );

-- =====================================================
-- 触发器和自动化
-- =====================================================

-- 更新时间戳触发器函数
CREATE OR REPLACE FUNCTION update_modified_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.lastModified = unix_timestamp_ms();
    NEW.serverUpdatedAt = unix_timestamp_ms();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 为用户表添加更新触发器
CREATE TRIGGER users_update_timestamp
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_timestamp();

-- 用户档案更新触发器
CREATE OR REPLACE FUNCTION update_user_profiles_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.lastUpdated = unix_timestamp_ms();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_profiles_update_timestamp
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_user_profiles_timestamp();

-- =====================================================
-- 数据验证和约束
-- =====================================================

-- 用户类型检查约束
ALTER TABLE users ADD CONSTRAINT check_user_type
    CHECK (userType IN ('regular', 'premium', 'admin', 'anonymous'));

-- 订阅计划检查约束
ALTER TABLE users ADD CONSTRAINT check_subscription_plan
    CHECK (subscriptionPlan IN ('free', 'basic', 'premium', 'enterprise'));

-- 主题模式检查约束
ALTER TABLE users ADD CONSTRAINT check_theme_mode
    CHECK (themeMode IN ('light', 'dark', 'system'));

-- 语言代码检查约束
ALTER TABLE users ADD CONSTRAINT check_language_code
    CHECK (languageCode IN ('zh', 'en', 'ja', 'ko'));

-- 测量系统检查约束
ALTER TABLE users ADD CONSTRAINT check_measurement_system
    CHECK (measurementSystem IN ('metric', 'imperial'));

-- =====================================================
-- 初始化数据和配置
-- =====================================================

-- 创建系统用户（用于系统操作）
INSERT INTO users (
    user_id,
    username,
    email,
    userType,
    isAnonymous,
    themeMode,
    languageCode,
    measurementSystem
) VALUES (
    '00000000-0000-0000-0000-000000000000'::uuid,
    'system',
    'system@gymbro.app',
    'admin',
    0,
    'system',
    'zh',
    'metric'
) ON CONFLICT (user_id) DO NOTHING;

-- 设置定时清理任务（需要pg_cron扩展）
SELECT cron.schedule(
    'cleanup-anonymous-users',
    '0 2 * * *', -- 每天凌晨2点执行
    'SELECT cleanup_anonymous_user_data(30);'
) WHERE EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron');

-- =====================================================
-- 完成信息
-- =====================================================

-- 验证表创建
DO $$
DECLARE
    table_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public'
    AND table_name IN (
        'users', 'user_profiles', 'user_settings', 'tokens',
        'search_content', 'calendar_events', 'chat_sessions',
        'chat_raw', 'chat_fts', 'chat_vec', 'message_embedding',
        'session_summary', 'memory_records'
    );

    RAISE NOTICE '✅ 架构对齐完成！已创建 % 个核心表', table_count;
    RAISE NOTICE '🔐 RLS策略已启用，支持用户数据隔离';
    RAISE NOTICE '👤 匿名用户支持已配置，包含自动清理';
    RAISE NOTICE '📊 性能索引已创建，优化查询性能';
    RAISE NOTICE '🔄 自动化触发器已设置，维护数据一致性';
END $$;
