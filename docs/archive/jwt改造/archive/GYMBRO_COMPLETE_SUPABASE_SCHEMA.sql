-- GymBro APP 完整数据库结构
-- 基于Android Room数据库结构生成
-- 生成时间: 2025-09-29 15:41:51
-- 在Supabase Dashboard的SQL Editor中执行此脚本

-- 启用必要的PostgreSQL扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_cron";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- 创建表结构
-- =============================================================================

-- 创建表: users
CREATE TABLE IF NOT EXISTS users (
    user_id UUID NOT NULL,
    email VARCHAR(255),
    username VARCHAR(255) NOT NULL,
    displayName VARCHAR(255),
    photoUrl TEXT,
    phoneNumber TEXT,
    isActive BOOLEAN NOT NULL DEFAULT false,
    isEmailVerified VARCHAR(255) NOT NULL,
    wechatId TEXT,
    anonymousId TEXT,
    gender TEXT,
    weight DECIMAL(10,2),
    weightUnit TEXT,
    fitnessLevel BIGINT,
    preferredGym TEXT,
    avatar TEXT,
    bio TEXT,
    themeMode TEXT NOT NULL,
    languageCode TEXT NOT NULL,
    measurementSystem TEXT NOT NULL,
    notificationsEnabled BOOLEAN NOT NULL DEFAULT false,
    soundsEnabled BOOLEAN NOT NULL DEFAULT false,
    locationSharingEnabled BOOLEAN NOT NULL DEFAULT false,
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
    allowPartnerMatching BIGINT NOT NULL,
    weeklyActiveMinutes BIGINT NOT NULL,
    likesReceived BIGINT NOT NULL,
    createdAt TIMESTAMPTZ DEFAULT NOW(),
    lastLoginAt TIMESTAMPTZ,
    isSynced BOOLEAN NOT NULL DEFAULT false,
    lastSynced TIMESTAMPTZ NOT NULL,
    lastModified TIMESTAMPTZ NOT NULL,
    serverUpdatedAt TIMESTAMPTZ NOT NULL,
    isAnonymous BOOLEAN NOT NULL DEFAULT false,
    userType TEXT NOT NULL,
    subscriptionPlan TEXT NOT NULL,
    subscriptionExpiryDate TIMESTAMPTZ,
    PRIMARY KEY (user_id)
);

-- 创建表: user_profiles
CREATE TABLE IF NOT EXISTS user_profiles (
    userId UUID NOT NULL,
    username VARCHAR(255),
    displayName VARCHAR(255),
    email VARCHAR(255),
    phoneNumber TEXT,
    profileImageUrl TEXT,
    bio TEXT,
    gender TEXT,
    height DECIMAL(10,2),
    heightUnit TEXT,
    weight DECIMAL(10,2),
    weightUnit TEXT,
    fitnessLevel BIGINT,
    fitnessGoals TEXT NOT NULL,
    workoutDays TEXT NOT NULL,
    allowPartnerMatching BIGINT NOT NULL,
    totalWorkoutCount BIGINT NOT NULL,
    weeklyActiveMinutes BIGINT NOT NULL,
    likesReceived BIGINT NOT NULL,
    isAnonymous BOOLEAN NOT NULL DEFAULT false,
    hasValidSubscription BIGINT NOT NULL,
    lastUpdated BIGINT NOT NULL,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    profileSummary TEXT,
    vector BYTEA,
    vectorCreatedAt BIGINT,
    PRIMARY KEY (userId)
);

-- 创建表: user_settings
CREATE TABLE IF NOT EXISTS user_settings (
    userId UUID NOT NULL,
    themeMode TEXT NOT NULL,
    languageCode TEXT NOT NULL,
    measurementSystem TEXT NOT NULL,
    notificationsEnabled BOOLEAN NOT NULL DEFAULT false,
    soundsEnabled BOOLEAN NOT NULL DEFAULT false,
    locationSharingEnabled BOOLEAN NOT NULL DEFAULT false,
    dataSharingEnabled BOOLEAN NOT NULL DEFAULT false,
    allowWorkoutSharing BIGINT NOT NULL,
    autoBackupEnabled BOOLEAN NOT NULL DEFAULT false,
    backupFrequency BIGINT NOT NULL,
    lastBackupTime BIGINT NOT NULL,
    allowPartnerMatching BIGINT NOT NULL,
    preferredMatchDistance BOOLEAN NOT NULL DEFAULT false,
    matchByFitnessLevel BIGINT NOT NULL,
    lastModified TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (userId)
);

-- 创建表: tokens
CREATE TABLE IF NOT EXISTS tokens (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    accessToken TEXT NOT NULL,
    refreshToken TEXT NOT NULL,
    tokenType TEXT NOT NULL,
    expiresIn BIGINT NOT NULL,
    issuedAt BOOLEAN NOT NULL DEFAULT false,
    userId UUID NOT NULL,
    scope TEXT,
    PRIMARY KEY (id)
);

-- 创建表: search_content
CREATE TABLE IF NOT EXISTS search_content (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding TEXT,
    metadata TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- 创建表: calendar_events
CREATE TABLE IF NOT EXISTS calendar_events (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    workout_id TEXT,
    event_type TEXT NOT NULL,
    "date" BIGINT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    duration_minutes BIGINT,
    color TEXT,
    is_all_day BOOLEAN NOT NULL DEFAULT false,
    reminder_minutes_before BIGINT,
    is_completed BOOLEAN NOT NULL DEFAULT false,
    completion_date BIGINT,
    cancelled BIGINT NOT NULL,
    recurrence_rule TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modified_at BIGINT NOT NULL,
    is_synced BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (id)
);

-- 创建表: chat_raw
CREATE TABLE IF NOT EXISTS chat_raw (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    "timestamp" BIGINT NOT NULL,
    metadata TEXT NOT NULL,
    message_id TEXT NOT NULL,
    in_reply_to_message_id TEXT,
    thinking_nodes TEXT,
    final_markdown TEXT,
    PRIMARY KEY (id)
);

-- 创建表: chat_fts
CREATE TABLE IF NOT EXISTS chat_fts (
    content TEXT NOT NULL,
    rowid BIGINT PRIMARY KEY
);

-- 创建表: chat_sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active_at BIGINT NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT false,
    "status" BIGINT NOT NULL,
    message_count BIGINT NOT NULL,
    summary TEXT,
    metadata TEXT,
    db_created_at BIGINT NOT NULL,
    db_updated_at BIGINT NOT NULL,
    PRIMARY KEY (id)
);

-- 创建表: chat_vec
CREATE TABLE IF NOT EXISTS chat_vec (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    embedding BYTEA NOT NULL,
    embedding_dim BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- 创建表: message_embedding
CREATE TABLE IF NOT EXISTS message_embedding (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    vector BYTEA NOT NULL,
    vector_dim BIGINT NOT NULL,
    embedding_status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    model_version TEXT NOT NULL,
    generation_time_ms BIGINT,
    text_length BIGINT NOT NULL,
    PRIMARY KEY (id)
);

-- 创建表: session_summary
CREATE TABLE IF NOT EXISTS session_summary (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    range_start BIGINT NOT NULL,
    range_end BIGINT NOT NULL,
    summary_content TEXT NOT NULL,
    summary_type TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    original_message_count BIGINT NOT NULL,
    original_token_count BIGINT NOT NULL,
    summary_token_count BIGINT NOT NULL,
    compression_ratio DECIMAL(10,2) NOT NULL,
    model_used TEXT NOT NULL,
    generation_time_ms BIGINT,
    quality_score DECIMAL(10,2),
    PRIMARY KEY (id)
);

-- 创建表: memory_records
CREATE TABLE IF NOT EXISTS memory_records (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    tier TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at BIGINT,
    importance BIGINT NOT NULL,
    embedding BYTEA,
    embedding_dim BIGINT NOT NULL,
    embedding_status TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    content_length BIGINT NOT NULL,
    model_version TEXT NOT NULL,
    generation_time_ms BIGINT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- 创建表: exercise
CREATE TABLE IF NOT EXISTS exercise (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    muscleGroup TEXT NOT NULL,
    equipment TEXT NOT NULL,
    description TEXT,
    imageUrl TEXT,
    videoUrl TEXT,
    defaultSets BIGINT NOT NULL,
    defaultReps BIGINT NOT NULL,
    defaultWeight DECIMAL(10,2),
    steps TEXT NOT NULL,
    tips TEXT NOT NULL,
    userId UUID,
    isCustom BOOLEAN NOT NULL DEFAULT false,
    isFavorite BOOLEAN NOT NULL DEFAULT false,
    difficultyLevel BIGINT NOT NULL,
    calories BIGINT,
    targetMuscles TEXT NOT NULL,
    instructions TEXT NOT NULL,
    embedding TEXT,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updatedAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    createdByUserId TEXT,
    PRIMARY KEY (id)
);

-- 创建表: exercise_fts
CREATE TABLE IF NOT EXISTS exercise_fts (
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    muscleGroup TEXT NOT NULL,
    equipment TEXT NOT NULL,
    steps TEXT NOT NULL,
    tips TEXT NOT NULL,
    instructions TEXT NOT NULL,
    rowid BIGINT PRIMARY KEY
);

-- 创建表: exercise_search_history
CREATE TABLE IF NOT EXISTS exercise_search_history (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    query TEXT NOT NULL,
    resultCount BIGINT NOT NULL,
    userId UUID,
    "timestamp" BIGINT NOT NULL,
    PRIMARY KEY (id)
);

-- 创建表: exercise_usage_stats
CREATE TABLE IF NOT EXISTS exercise_usage_stats (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    exerciseId TEXT NOT NULL,
    userId UUID,
    usageCount BIGINT NOT NULL,
    lastUsed BIGINT NOT NULL,
    totalSets BIGINT NOT NULL,
    totalReps BIGINT NOT NULL,
    maxWeight DECIMAL(10,2),
    PRIMARY KEY (id)
);

-- 创建表: workout_plans
CREATE TABLE IF NOT EXISTS workout_plans (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    userId UUID NOT NULL,
    targetGoal TEXT,
    difficultyLevel BIGINT NOT NULL,
    estimatedDuration BIGINT,
    isPublic BOOLEAN NOT NULL DEFAULT false,
    isTemplate BOOLEAN NOT NULL DEFAULT false,
    isFavorite BOOLEAN NOT NULL DEFAULT false,
    isAIGenerated BOOLEAN NOT NULL DEFAULT false,
    tags TEXT NOT NULL,
    totalDays BIGINT NOT NULL,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updatedAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- 创建表: plan_days
CREATE TABLE IF NOT EXISTS plan_days (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    planId UUID NOT NULL,
    dayNumber BIGINT NOT NULL,
    isRestDay BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    orderIndex BIGINT NOT NULL,
    estimatedDuration BIGINT,
    isCompleted BOOLEAN NOT NULL DEFAULT false,
    progress TEXT NOT NULL,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- 创建表: plan_templates
CREATE TABLE IF NOT EXISTS plan_templates (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    planDayId UUID NOT NULL,
    templateId TEXT NOT NULL,
    "order" BIGINT NOT NULL,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- 创建表: workout_sessions
CREATE TABLE IF NOT EXISTS workout_sessions (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    userId UUID NOT NULL,
    templateId TEXT NOT NULL,
    templateVersion BIGINT,
    planId TEXT,
    name VARCHAR(255) NOT NULL,
    "status" TEXT NOT NULL,
    startTime TIMESTAMPTZ NOT NULL,
    endTime TIMESTAMPTZ,
    totalDuration BIGINT,
    totalVolume DECIMAL(10,2),
    caloriesBurned BIGINT,
    notes TEXT,
    rating BIGINT,
    lastAutosaveTime TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (id)
);

-- 创建表: session_exercises
CREATE TABLE IF NOT EXISTS session_exercises (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    sessionId UUID NOT NULL,
    exerciseId TEXT NOT NULL,
    "order" BIGINT NOT NULL,
    name VARCHAR(255) NOT NULL,
    targetSets BIGINT NOT NULL,
    completedSets BIGINT NOT NULL,
    restSeconds BIGINT,
    restSecondsOverride BIGINT,
    imageUrl TEXT,
    videoUrl TEXT,
    "status" TEXT NOT NULL,
    startTime TIMESTAMPTZ,
    endTime TIMESTAMPTZ,
    notes TEXT,
    isCompleted BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (id)
);

-- 创建表: session_sets
CREATE TABLE IF NOT EXISTS session_sets (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    sessionExerciseId UUID NOT NULL,
    setNumber BIGINT NOT NULL,
    weight DECIMAL(10,2),
    weightUnit TEXT,
    reps BIGINT,
    timeSeconds BIGINT,
    rpe DECIMAL(10,2),
    isCompleted BOOLEAN NOT NULL DEFAULT false,
    isWarmupSet BOOLEAN NOT NULL DEFAULT false,
    notes TEXT,
    "timestamp" BIGINT NOT NULL,
    PRIMARY KEY (id)
);

-- 创建表: exercise_history_stats
CREATE TABLE IF NOT EXISTS exercise_history_stats (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    userId UUID NOT NULL,
    exerciseId TEXT NOT NULL,
    personalBestWeight DECIMAL(10,2),
    personalBestReps BIGINT,
    totalSetsCompleted BIGINT NOT NULL,
    totalVolumeLifted DECIMAL(10,2) NOT NULL,
    lastPerformanceDate BIGINT NOT NULL,
    lastUpdated BIGINT NOT NULL,
    PRIMARY KEY (id)
);

-- 创建表: session_autosave
CREATE TABLE IF NOT EXISTS session_autosave (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    sessionId TEXT NOT NULL,
    saveType TEXT NOT NULL,
    saveTime BIGINT NOT NULL,
    sessionSnapshot TEXT NOT NULL,
    progressSnapshot TEXT NOT NULL,
    currentState TEXT NOT NULL,
    nextAction TEXT NOT NULL,
    isValid BOOLEAN NOT NULL DEFAULT false,
    expiresAt BIGINT,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- 创建表: daily_stats
CREATE TABLE IF NOT EXISTS daily_stats (
    userId UUID NOT NULL,
    "date" TEXT NOT NULL,
    completedSessions BIGINT NOT NULL,
    completedExercises BIGINT NOT NULL,
    completedSets BIGINT NOT NULL,
    totalReps BIGINT NOT NULL,
    totalWeight DECIMAL(10,2) NOT NULL,
    avgRpe DECIMAL(10,2),
    sessionDurationSec BIGINT NOT NULL,
    planId TEXT,
    dayOfWeek BIGINT NOT NULL,
    caloriesBurned BIGINT,
    averageHeartRate BIGINT,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updatedAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (userId, "date")
);

-- 创建表: workout_templates
CREATE TABLE IF NOT EXISTS workout_templates (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    targetMuscleGroups TEXT NOT NULL,
    difficulty BIGINT NOT NULL,
    estimatedDuration BIGINT,
    userId UUID NOT NULL,
    isPublic BOOLEAN NOT NULL DEFAULT false,
    isFavorite BOOLEAN NOT NULL DEFAULT false,
    tags TEXT NOT NULL,
    currentVersion BIGINT NOT NULL,
    isDraft BOOLEAN NOT NULL DEFAULT false,
    isPublished BOOLEAN NOT NULL DEFAULT false,
    lastPublishedAt TIMESTAMPTZ,
    versionTag BIGINT NOT NULL,
    jsonData TEXT,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updatedAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- 创建表: template_exercises
CREATE TABLE IF NOT EXISTS template_exercises (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    templateId UUID NOT NULL,
    exerciseId TEXT NOT NULL,
    "order" BIGINT NOT NULL,
    sets BIGINT NOT NULL,
    repsPerSet TEXT NOT NULL,
    weightSuggestion TEXT,
    restSeconds BIGINT NOT NULL,
    notes TEXT,
    superset BIGINT NOT NULL,
    supersetGroupId TEXT,
    PRIMARY KEY (id)
);

-- 创建表: template_versions
CREATE TABLE IF NOT EXISTS template_versions (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    templateId UUID NOT NULL,
    versionNumber BIGINT NOT NULL,
    contentJson JSONB NOT NULL,
    createdAt TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    description TEXT,
    isAutoSaved BOOLEAN NOT NULL DEFAULT false,
    PRIMARY KEY (id)
);

-- =============================================================================
-- 创建索引
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_users_isActive ON users(isActive);
CREATE INDEX IF NOT EXISTS idx_users_createdAt ON users(createdAt);
CREATE INDEX IF NOT EXISTS idx_users_lastLoginAt ON users(lastLoginAt);
CREATE INDEX IF NOT EXISTS idx_users_lastSynced ON users(lastSynced);
CREATE INDEX IF NOT EXISTS idx_users_lastModified ON users(lastModified);
CREATE INDEX IF NOT EXISTS idx_users_serverUpdatedAt ON users(serverUpdatedAt);
CREATE INDEX IF NOT EXISTS idx_users_subscriptionExpiryDate ON users(subscriptionExpiryDate);
CREATE INDEX IF NOT EXISTS idx_user_profiles_createdAt ON user_profiles(createdAt);
CREATE INDEX IF NOT EXISTS idx_user_settings_lastModified ON user_settings(lastModified);
CREATE INDEX IF NOT EXISTS idx_tokens_userId ON tokens(userId);
CREATE INDEX IF NOT EXISTS idx_search_content_created_at ON search_content(created_at);
CREATE INDEX IF NOT EXISTS idx_calendar_events_user_id ON calendar_events(user_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_created_at ON calendar_events(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_created_at ON chat_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_status ON chat_sessions("status");
CREATE INDEX IF NOT EXISTS idx_chat_vec_created_at ON chat_vec(created_at);
CREATE INDEX IF NOT EXISTS idx_message_embedding_created_at ON message_embedding(created_at);
CREATE INDEX IF NOT EXISTS idx_session_summary_created_at ON session_summary(created_at);
CREATE INDEX IF NOT EXISTS idx_memory_records_user_id ON memory_records(user_id);
CREATE INDEX IF NOT EXISTS idx_memory_records_created_at ON memory_records(created_at);
CREATE INDEX IF NOT EXISTS idx_memory_records_updated_at ON memory_records(updated_at);
CREATE INDEX IF NOT EXISTS idx_exercise_userId ON exercise(userId);
CREATE INDEX IF NOT EXISTS idx_exercise_isFavorite ON exercise(isFavorite);
CREATE INDEX IF NOT EXISTS idx_exercise_createdAt ON exercise(createdAt);
CREATE INDEX IF NOT EXISTS idx_exercise_updatedAt ON exercise(updatedAt);
CREATE INDEX IF NOT EXISTS idx_exercise_search_history_userId ON exercise_search_history(userId);
CREATE INDEX IF NOT EXISTS idx_exercise_usage_stats_userId ON exercise_usage_stats(userId);
CREATE INDEX IF NOT EXISTS idx_workout_plans_userId ON workout_plans(userId);
CREATE INDEX IF NOT EXISTS idx_workout_plans_isPublic ON workout_plans(isPublic);
CREATE INDEX IF NOT EXISTS idx_workout_plans_isFavorite ON workout_plans(isFavorite);
CREATE INDEX IF NOT EXISTS idx_workout_plans_createdAt ON workout_plans(createdAt);
CREATE INDEX IF NOT EXISTS idx_workout_plans_updatedAt ON workout_plans(updatedAt);
CREATE INDEX IF NOT EXISTS idx_plan_days_createdAt ON plan_days(createdAt);
CREATE INDEX IF NOT EXISTS idx_plan_templates_createdAt ON plan_templates(createdAt);
CREATE INDEX IF NOT EXISTS idx_workout_sessions_userId ON workout_sessions(userId);
CREATE INDEX IF NOT EXISTS idx_workout_sessions_status ON workout_sessions("status");
CREATE INDEX IF NOT EXISTS idx_workout_sessions_startTime ON workout_sessions(startTime);
CREATE INDEX IF NOT EXISTS idx_workout_sessions_endTime ON workout_sessions(endTime);
CREATE INDEX IF NOT EXISTS idx_workout_sessions_lastAutosaveTime ON workout_sessions(lastAutosaveTime);
CREATE INDEX IF NOT EXISTS idx_session_exercises_status ON session_exercises("status");
CREATE INDEX IF NOT EXISTS idx_session_exercises_startTime ON session_exercises(startTime);
CREATE INDEX IF NOT EXISTS idx_session_exercises_endTime ON session_exercises(endTime);
CREATE INDEX IF NOT EXISTS idx_exercise_history_stats_userId ON exercise_history_stats(userId);
CREATE INDEX IF NOT EXISTS idx_session_autosave_createdAt ON session_autosave(createdAt);
CREATE INDEX IF NOT EXISTS idx_daily_stats_createdAt ON daily_stats(createdAt);
CREATE INDEX IF NOT EXISTS idx_daily_stats_updatedAt ON daily_stats(updatedAt);
CREATE INDEX IF NOT EXISTS idx_workout_templates_userId ON workout_templates(userId);
CREATE INDEX IF NOT EXISTS idx_workout_templates_isPublic ON workout_templates(isPublic);
CREATE INDEX IF NOT EXISTS idx_workout_templates_isFavorite ON workout_templates(isFavorite);
CREATE INDEX IF NOT EXISTS idx_workout_templates_lastPublishedAt ON workout_templates(lastPublishedAt);
CREATE INDEX IF NOT EXISTS idx_workout_templates_createdAt ON workout_templates(createdAt);
CREATE INDEX IF NOT EXISTS idx_workout_templates_updatedAt ON workout_templates(updatedAt);
CREATE INDEX IF NOT EXISTS idx_template_versions_createdAt ON template_versions(createdAt);

-- =============================================================================
-- 创建外键约束
-- =============================================================================

ALTER TABLE user_settings ADD CONSTRAINT fk_user_settings_userId FOREIGN KEY (userId) REFERENCES users(user_id) ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE chat_raw ADD CONSTRAINT fk_chat_raw_session_id FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE message_embedding ADD CONSTRAINT fk_message_embedding_message_id FOREIGN KEY (message_id) REFERENCES chat_raw(id) ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE session_summary ADD CONSTRAINT fk_session_summary_session_id FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE plan_days ADD CONSTRAINT fk_plan_days_planId FOREIGN KEY (planId) REFERENCES workout_plans(id) ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE plan_templates ADD CONSTRAINT fk_plan_templates_planDayId FOREIGN KEY (planDayId) REFERENCES plan_days(id) ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE session_exercises ADD CONSTRAINT fk_session_exercises_sessionId FOREIGN KEY (sessionId) REFERENCES workout_sessions(id) ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE session_sets ADD CONSTRAINT fk_session_sets_sessionExerciseId FOREIGN KEY (sessionExerciseId) REFERENCES session_exercises(id) ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE template_exercises ADD CONSTRAINT fk_template_exercises_templateId FOREIGN KEY (templateId) REFERENCES workout_templates(id) ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE template_versions ADD CONSTRAINT fk_template_versions_templateId FOREIGN KEY (templateId) REFERENCES workout_templates(id) ON DELETE NO ACTION ON UPDATE NO ACTION;

-- =============================================================================
-- 创建RLS策略（行级安全）
-- =============================================================================

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_user_select" ON users
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "users_user_insert" ON users
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users_user_update" ON users
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "users_user_delete" ON users
    FOR DELETE TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "users_service_all" ON users
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_profiles_user_select" ON user_profiles
    FOR SELECT TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "user_profiles_user_insert" ON user_profiles
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "user_profiles_user_update" ON user_profiles
    FOR UPDATE TO authenticated
    USING (auth.uid() = userId)
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "user_profiles_user_delete" ON user_profiles
    FOR DELETE TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "user_profiles_service_all" ON user_profiles
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user_settings_user_select" ON user_settings
    FOR SELECT TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "user_settings_user_insert" ON user_settings
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "user_settings_user_update" ON user_settings
    FOR UPDATE TO authenticated
    USING (auth.uid() = userId)
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "user_settings_user_delete" ON user_settings
    FOR DELETE TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "user_settings_service_all" ON user_settings
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "tokens_user_select" ON tokens
    FOR SELECT TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "tokens_user_insert" ON tokens
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "tokens_user_update" ON tokens
    FOR UPDATE TO authenticated
    USING (auth.uid() = userId)
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "tokens_user_delete" ON tokens
    FOR DELETE TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "tokens_service_all" ON tokens
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE calendar_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "calendar_events_user_select" ON calendar_events
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "calendar_events_user_insert" ON calendar_events
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "calendar_events_user_update" ON calendar_events
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "calendar_events_user_delete" ON calendar_events
    FOR DELETE TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "calendar_events_service_all" ON calendar_events
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "chat_sessions_user_select" ON chat_sessions
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "chat_sessions_user_insert" ON chat_sessions
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "chat_sessions_user_update" ON chat_sessions
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "chat_sessions_user_delete" ON chat_sessions
    FOR DELETE TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "chat_sessions_service_all" ON chat_sessions
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE memory_records ENABLE ROW LEVEL SECURITY;

CREATE POLICY "memory_records_user_select" ON memory_records
    FOR SELECT TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "memory_records_user_insert" ON memory_records
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "memory_records_user_update" ON memory_records
    FOR UPDATE TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "memory_records_user_delete" ON memory_records
    FOR DELETE TO authenticated
    USING (auth.uid() = user_id);

CREATE POLICY "memory_records_service_all" ON memory_records
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE exercise ENABLE ROW LEVEL SECURITY;

CREATE POLICY "exercise_user_select" ON exercise
    FOR SELECT TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "exercise_user_insert" ON exercise
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "exercise_user_update" ON exercise
    FOR UPDATE TO authenticated
    USING (auth.uid() = userId)
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "exercise_user_delete" ON exercise
    FOR DELETE TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "exercise_service_all" ON exercise
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE exercise_search_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "exercise_search_history_user_select" ON exercise_search_history
    FOR SELECT TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "exercise_search_history_user_insert" ON exercise_search_history
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "exercise_search_history_user_update" ON exercise_search_history
    FOR UPDATE TO authenticated
    USING (auth.uid() = userId)
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "exercise_search_history_user_delete" ON exercise_search_history
    FOR DELETE TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "exercise_search_history_service_all" ON exercise_search_history
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE exercise_usage_stats ENABLE ROW LEVEL SECURITY;

CREATE POLICY "exercise_usage_stats_user_select" ON exercise_usage_stats
    FOR SELECT TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "exercise_usage_stats_user_insert" ON exercise_usage_stats
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "exercise_usage_stats_user_update" ON exercise_usage_stats
    FOR UPDATE TO authenticated
    USING (auth.uid() = userId)
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "exercise_usage_stats_user_delete" ON exercise_usage_stats
    FOR DELETE TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "exercise_usage_stats_service_all" ON exercise_usage_stats
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE workout_plans ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workout_plans_user_select" ON workout_plans
    FOR SELECT TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "workout_plans_user_insert" ON workout_plans
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "workout_plans_user_update" ON workout_plans
    FOR UPDATE TO authenticated
    USING (auth.uid() = userId)
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "workout_plans_user_delete" ON workout_plans
    FOR DELETE TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "workout_plans_service_all" ON workout_plans
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE workout_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workout_sessions_user_select" ON workout_sessions
    FOR SELECT TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "workout_sessions_user_insert" ON workout_sessions
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "workout_sessions_user_update" ON workout_sessions
    FOR UPDATE TO authenticated
    USING (auth.uid() = userId)
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "workout_sessions_user_delete" ON workout_sessions
    FOR DELETE TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "workout_sessions_service_all" ON workout_sessions
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE exercise_history_stats ENABLE ROW LEVEL SECURITY;

CREATE POLICY "exercise_history_stats_user_select" ON exercise_history_stats
    FOR SELECT TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "exercise_history_stats_user_insert" ON exercise_history_stats
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "exercise_history_stats_user_update" ON exercise_history_stats
    FOR UPDATE TO authenticated
    USING (auth.uid() = userId)
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "exercise_history_stats_user_delete" ON exercise_history_stats
    FOR DELETE TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "exercise_history_stats_service_all" ON exercise_history_stats
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE daily_stats ENABLE ROW LEVEL SECURITY;

CREATE POLICY "daily_stats_user_select" ON daily_stats
    FOR SELECT TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "daily_stats_user_insert" ON daily_stats
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "daily_stats_user_update" ON daily_stats
    FOR UPDATE TO authenticated
    USING (auth.uid() = userId)
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "daily_stats_user_delete" ON daily_stats
    FOR DELETE TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "daily_stats_service_all" ON daily_stats
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

ALTER TABLE workout_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "workout_templates_user_select" ON workout_templates
    FOR SELECT TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "workout_templates_user_insert" ON workout_templates
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "workout_templates_user_update" ON workout_templates
    FOR UPDATE TO authenticated
    USING (auth.uid() = userId)
    WITH CHECK (auth.uid() = userId);

CREATE POLICY "workout_templates_user_delete" ON workout_templates
    FOR DELETE TO authenticated
    USING (auth.uid() = userId);

CREATE POLICY "workout_templates_service_all" ON workout_templates
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- =============================================================================
-- 权限授予
-- =============================================================================

-- 授予authenticated角色对所有表的基本权限
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON users TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_profiles TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON user_settings TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON tokens TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON search_content TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON calendar_events TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON chat_raw TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON chat_fts TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON chat_sessions TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON chat_vec TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON message_embedding TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON session_summary TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON memory_records TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON exercise TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON exercise_fts TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON exercise_search_history TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON exercise_usage_stats TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON workout_plans TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON plan_days TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON plan_templates TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON workout_sessions TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON session_exercises TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON session_sets TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON exercise_history_stats TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON session_autosave TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON daily_stats TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON workout_templates TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON template_exercises TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON template_versions TO authenticated;

-- 授予service_role完全权限
GRANT ALL ON users TO service_role;
GRANT ALL ON user_profiles TO service_role;
GRANT ALL ON user_settings TO service_role;
GRANT ALL ON tokens TO service_role;
GRANT ALL ON search_content TO service_role;
GRANT ALL ON calendar_events TO service_role;
GRANT ALL ON chat_raw TO service_role;
GRANT ALL ON chat_fts TO service_role;
GRANT ALL ON chat_sessions TO service_role;
GRANT ALL ON chat_vec TO service_role;
GRANT ALL ON message_embedding TO service_role;
GRANT ALL ON session_summary TO service_role;
GRANT ALL ON memory_records TO service_role;
GRANT ALL ON exercise TO service_role;
GRANT ALL ON exercise_fts TO service_role;
GRANT ALL ON exercise_search_history TO service_role;
GRANT ALL ON exercise_usage_stats TO service_role;
GRANT ALL ON workout_plans TO service_role;
GRANT ALL ON plan_days TO service_role;
GRANT ALL ON plan_templates TO service_role;
GRANT ALL ON workout_sessions TO service_role;
GRANT ALL ON session_exercises TO service_role;
GRANT ALL ON session_sets TO service_role;
GRANT ALL ON exercise_history_stats TO service_role;
GRANT ALL ON session_autosave TO service_role;
GRANT ALL ON daily_stats TO service_role;
GRANT ALL ON workout_templates TO service_role;
GRANT ALL ON template_exercises TO service_role;
GRANT ALL ON template_versions TO service_role;

-- =============================================================================
-- 匿名用户支持策略（基于T3实现）
-- =============================================================================

-- 为所有用户相关表添加user_type审计字段
ALTER TABLE users ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;
ALTER TABLE chat_raw ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;
ALTER TABLE workout_sessions ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;
ALTER TABLE workout_plans ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;
ALTER TABLE exercise ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;

-- 创建用户类型审计索引
CREATE INDEX IF NOT EXISTS idx_users_user_type_audit ON users(user_type_audit) WHERE user_type_audit IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_type_audit ON user_profiles(user_type_audit) WHERE user_type_audit IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_type_audit ON chat_sessions(user_type_audit) WHERE user_type_audit IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chat_raw_user_type_audit ON chat_raw(user_type_audit) WHERE user_type_audit IS NOT NULL;

-- 创建公开分享表（支持匿名用户限制）
CREATE TABLE IF NOT EXISTS public_shares (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id UUID NOT NULL,
    user_id TEXT NOT NULL,
    share_token VARCHAR(255) NOT NULL UNIQUE,
    title TEXT,
    description TEXT,
    is_public BOOLEAN DEFAULT true,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    user_type_audit VARCHAR(20) DEFAULT NULL
);

-- 启用公开分享表的RLS
ALTER TABLE public_shares ENABLE ROW LEVEL SECURITY;

-- 匿名用户禁止创建公开分享
CREATE POLICY "anonymous_cannot_create_public_shares" ON public_shares
    AS RESTRICTIVE
    FOR INSERT TO authenticated
    WITH CHECK (
        COALESCE((auth.jwt()->>'is_anonymous')::boolean, false) = false
    );

-- 匿名用户禁止更新公开分享
CREATE POLICY "anonymous_cannot_update_public_shares" ON public_shares
    AS RESTRICTIVE
    FOR UPDATE TO authenticated
    WITH CHECK (
        COALESCE((auth.jwt()->>'is_anonymous')::boolean, false) = false
    );

-- 公开分享表的基础owner策略
CREATE POLICY "public_shares_owner_select" ON public_shares
    FOR SELECT TO authenticated
    USING (auth.uid()::text = user_id);

CREATE POLICY "public_shares_owner_insert" ON public_shares
    FOR INSERT TO authenticated
    WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "public_shares_owner_update" ON public_shares
    FOR UPDATE TO authenticated
    USING (auth.uid()::text = user_id)
    WITH CHECK (auth.uid()::text = user_id);

CREATE POLICY "public_shares_owner_delete" ON public_shares
    FOR DELETE TO authenticated
    USING (auth.uid()::text = user_id);

-- 服务角色对公开分享表的完全访问
CREATE POLICY "public_shares_service_all" ON public_shares
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- 创建匿名用户数据清理函数
CREATE OR REPLACE FUNCTION cleanup_anonymous_user_data(retention_days INTEGER DEFAULT 30)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    deleted_users INTEGER := 0;
    deleted_profiles INTEGER := 0;
    deleted_sessions INTEGER := 0;
    deleted_messages INTEGER := 0;
    deleted_workouts INTEGER := 0;
    total_deleted INTEGER := 0;
BEGIN
    -- 删除过期的匿名用户数据
    DELETE FROM users
    WHERE user_type_audit = 'anonymous'
    AND createdAt < NOW() - INTERVAL '1 day' * retention_days;
    GET DIAGNOSTICS deleted_users = ROW_COUNT;

    DELETE FROM user_profiles
    WHERE user_type_audit = 'anonymous'
    AND createdAt < NOW() - INTERVAL '1 day' * retention_days;
    GET DIAGNOSTICS deleted_profiles = ROW_COUNT;

    DELETE FROM chat_sessions
    WHERE user_type_audit = 'anonymous'
    AND created_at < NOW() - INTERVAL '1 day' * retention_days;
    GET DIAGNOSTICS deleted_sessions = ROW_COUNT;

    DELETE FROM chat_raw
    WHERE user_type_audit = 'anonymous'
    AND "timestamp" < EXTRACT(EPOCH FROM NOW() - INTERVAL '1 day' * retention_days);
    GET DIAGNOSTICS deleted_messages = ROW_COUNT;

    DELETE FROM workout_sessions
    WHERE user_type_audit = 'anonymous'
    AND startTime < NOW() - INTERVAL '1 day' * retention_days;
    GET DIAGNOSTICS deleted_workouts = ROW_COUNT;

    total_deleted := deleted_users + deleted_profiles + deleted_sessions + deleted_messages + deleted_workouts;

    -- 记录清理日志
    RAISE NOTICE 'Anonymous data cleanup completed: users=%, profiles=%, sessions=%, messages=%, workouts=%, total=%',
        deleted_users, deleted_profiles, deleted_sessions, deleted_messages, deleted_workouts, total_deleted;

    RETURN total_deleted;
END;
$$;

-- 授予服务角色执行清理函数的权限
GRANT EXECUTE ON FUNCTION cleanup_anonymous_user_data TO service_role;

-- 授予公开分享表权限
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public_shares TO authenticated;
GRANT ALL ON public_shares TO service_role;

-- =============================================================================
-- 脚本执行完成
-- =============================================================================

-- 验证表创建
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- 验证RLS策略
SELECT
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd
FROM pg_policies
WHERE tablename IN ('users', 'user_profiles', 'chat_sessions', 'chat_raw', 'public_shares')
ORDER BY tablename, policyname;

-- 验证审计字段
SELECT
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_name IN ('users', 'user_profiles', 'chat_sessions', 'chat_raw', 'public_shares')
AND column_name = 'user_type_audit'
ORDER BY table_name;
