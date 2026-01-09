-- SCHEMA_PART_5.sql
-- Order: 5/5
-- Purpose: Anonymous user support (audit columns + public_shares + policies) + cleanup function + final verifications
-- Run after SCHEMA_PART_4.sql

-- =========================
-- Audit columns (user_type_audit) and indexes
-- =========================
ALTER TABLE "user" ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;
ALTER TABLE chat_sessions ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;
ALTER TABLE chat_raw ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;
ALTER TABLE workout_sessions ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;
ALTER TABLE workout_plans ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;
ALTER TABLE exercise ADD COLUMN IF NOT EXISTS user_type_audit VARCHAR(20) DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_user_user_type_audit ON "user"(user_type_audit) WHERE user_type_audit IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_profiles_user_type_audit ON user_profiles(user_type_audit) WHERE user_type_audit IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_type_audit ON chat_sessions(user_type_audit) WHERE user_type_audit IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chat_raw_user_type_audit ON chat_raw(user_type_audit) WHERE user_type_audit IS NOT NULL;

-- =========================
-- Public shares (blocked for anonymous users)
-- =========================
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

ALTER TABLE public_shares ENABLE ROW LEVEL SECURITY;

-- Restrictive policies for anonymous users
CREATE POLICY anonymous_cannot_create_public_shares ON public_shares AS RESTRICTIVE FOR INSERT TO authenticated WITH CHECK (COALESCE((auth.jwt()->>'is_anonymous')::boolean, false) = false);
CREATE POLICY anonymous_cannot_update_public_shares ON public_shares AS RESTRICTIVE FOR UPDATE TO authenticated WITH CHECK (COALESCE((auth.jwt()->>'is_anonymous')::boolean, false) = false);

-- Owner policies
CREATE POLICY public_shares_owner_select ON public_shares FOR SELECT TO authenticated USING (auth.uid()::text = user_id);
CREATE POLICY public_shares_owner_insert ON public_shares FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = user_id);
CREATE POLICY public_shares_owner_update ON public_shares FOR UPDATE TO authenticated USING (auth.uid()::text = user_id) WITH CHECK (auth.uid()::text = user_id);
CREATE POLICY public_shares_owner_delete ON public_shares FOR DELETE TO authenticated USING (auth.uid()::text = user_id);

-- Service role
CREATE POLICY public_shares_service_all ON public_shares FOR ALL TO service_role USING (true) WITH CHECK (true);

-- =========================
-- Cleanup function for anonymous data (uses correct column names/types)
-- =========================
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
    DELETE FROM "user"
    WHERE user_type_audit = 'anonymous'
      AND created_at < NOW() - INTERVAL '1 day' * retention_days;
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
    RAISE NOTICE 'Anonymous data cleanup completed: users=%, profiles=%, sessions=%, messages=%, workouts=%, total=%',
      deleted_users, deleted_profiles, deleted_sessions, deleted_messages, deleted_workouts, total_deleted;
    RETURN total_deleted;
END;
$$;

GRANT EXECUTE ON FUNCTION cleanup_anonymous_user_data TO service_role;

-- Grants for public_shares
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public_shares TO authenticated;
GRANT ALL ON public_shares TO service_role;

-- =========================
-- Final verifications
-- =========================
-- Audit columns on 8 tables
SELECT table_name FROM information_schema.columns WHERE column_name='user_type_audit' ORDER BY table_name;
-- Function exists
SELECT proname FROM pg_proc WHERE proname='cleanup_anonymous_user_data';
-- Anonymous policies present
SELECT policyname FROM pg_policies WHERE policyname LIKE '%anonymous%';
