-- SCHEMA_PART_4.sql
-- Order: 4/5
-- Purpose: Enable Row Level Security (RLS) and create policies for all tables; grant permissions
-- Run after SCHEMA_PART_3.sql

-- Note: Policies use auth.uid() (uuid) compared to uuid columns to avoid type mismatch.

-- =========================
-- Enable RLS
-- =========================
-- Note: Using existing 'user' table instead of 'users'
ALTER TABLE "user" ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE calendar_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_raw ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_fts ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_vec ENABLE ROW LEVEL SECURITY;
ALTER TABLE message_embedding ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_summary ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_fts ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_search_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_usage_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE workout_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_days ENABLE ROW LEVEL SECURITY;
ALTER TABLE plan_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE workout_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_exercises ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_sets ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_history_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_autosave ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE workout_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE template_exercises ENABLE ROW LEVEL SECURITY;
ALTER TABLE template_versions ENABLE ROW LEVEL SECURITY;

-- =========================
-- Policies (compact, owner-only + service_role)
-- =========================
-- user (existing table)
-- Note: auth.uid() returns UUID, but user.id is BIGINT, so we need to cast
CREATE POLICY user_user_select ON "user" FOR SELECT TO authenticated USING (auth.uid()::text = id::text);
CREATE POLICY user_user_insert ON "user" FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = id::text);
CREATE POLICY user_user_update ON "user" FOR UPDATE TO authenticated USING (auth.uid()::text = id::text) WITH CHECK (auth.uid()::text = id::text);
CREATE POLICY user_user_delete ON "user" FOR DELETE TO authenticated USING (auth.uid()::text = id::text);
CREATE POLICY user_service_all ON "user" FOR ALL TO service_role USING (true) WITH CHECK (true);

-- user_profiles
-- Note: auth.uid() returns UUID, but userId is BIGINT, so we need to cast
CREATE POLICY user_profiles_user_select ON user_profiles FOR SELECT TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY user_profiles_user_insert ON user_profiles FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY user_profiles_user_update ON user_profiles FOR UPDATE TO authenticated USING (auth.uid()::text = userId::text) WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY user_profiles_user_delete ON user_profiles FOR DELETE TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY user_profiles_service_all ON user_profiles FOR ALL TO service_role USING (true) WITH CHECK (true);

-- user_settings
-- Note: auth.uid() returns UUID, but userId is BIGINT, so we need to cast
CREATE POLICY user_settings_user_select ON user_settings FOR SELECT TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY user_settings_user_insert ON user_settings FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY user_settings_user_update ON user_settings FOR UPDATE TO authenticated USING (auth.uid()::text = userId::text) WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY user_settings_user_delete ON user_settings FOR DELETE TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY user_settings_service_all ON user_settings FOR ALL TO service_role USING (true) WITH CHECK (true);

-- tokens
-- Note: auth.uid() returns UUID, but userId is BIGINT, so we need to cast
CREATE POLICY tokens_user_select ON tokens FOR SELECT TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY tokens_user_insert ON tokens FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY tokens_user_update ON tokens FOR UPDATE TO authenticated USING (auth.uid()::text = userId::text) WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY tokens_user_delete ON tokens FOR DELETE TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY tokens_service_all ON tokens FOR ALL TO service_role USING (true) WITH CHECK (true);

-- calendar_events
-- Note: auth.uid() returns UUID, but user_id is BIGINT, so we need to cast
CREATE POLICY calendar_events_user_select ON calendar_events FOR SELECT TO authenticated USING (auth.uid()::text = user_id::text);
CREATE POLICY calendar_events_user_insert ON calendar_events FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = user_id::text);
CREATE POLICY calendar_events_user_update ON calendar_events FOR UPDATE TO authenticated USING (auth.uid()::text = user_id::text) WITH CHECK (auth.uid()::text = user_id::text);
CREATE POLICY calendar_events_user_delete ON calendar_events FOR DELETE TO authenticated USING (auth.uid()::text = user_id::text);
CREATE POLICY calendar_events_service_all ON calendar_events FOR ALL TO service_role USING (true) WITH CHECK (true);

-- chat_sessions
-- Note: auth.uid() returns UUID, but user_id is BIGINT, so we need to cast
CREATE POLICY chat_sessions_user_select ON chat_sessions FOR SELECT TO authenticated USING (auth.uid()::text = user_id::text);
CREATE POLICY chat_sessions_user_insert ON chat_sessions FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = user_id::text);
CREATE POLICY chat_sessions_user_update ON chat_sessions FOR UPDATE TO authenticated USING (auth.uid()::text = user_id::text) WITH CHECK (auth.uid()::text = user_id::text);
CREATE POLICY chat_sessions_user_delete ON chat_sessions FOR DELETE TO authenticated USING (auth.uid()::text = user_id::text);
CREATE POLICY chat_sessions_service_all ON chat_sessions FOR ALL TO service_role USING (true) WITH CHECK (true);

-- memory_records
-- Note: auth.uid() returns UUID, but user_id is BIGINT, so we need to cast
CREATE POLICY memory_records_user_select ON memory_records FOR SELECT TO authenticated USING (auth.uid()::text = user_id::text);
CREATE POLICY memory_records_user_insert ON memory_records FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = user_id::text);
CREATE POLICY memory_records_user_update ON memory_records FOR UPDATE TO authenticated USING (auth.uid()::text = user_id::text) WITH CHECK (auth.uid()::text = user_id::text);
CREATE POLICY memory_records_user_delete ON memory_records FOR DELETE TO authenticated USING (auth.uid()::text = user_id::text);
CREATE POLICY memory_records_service_all ON memory_records FOR ALL TO service_role USING (true) WITH CHECK (true);

-- exercise
-- Note: auth.uid() returns UUID, but userId is BIGINT, so we need to cast
CREATE POLICY exercise_user_select ON exercise FOR SELECT TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY exercise_user_insert ON exercise FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY exercise_user_update ON exercise FOR UPDATE TO authenticated USING (auth.uid()::text = userId::text) WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY exercise_user_delete ON exercise FOR DELETE TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY exercise_service_all ON exercise FOR ALL TO service_role USING (true) WITH CHECK (true);

-- exercise_search_history
-- Note: auth.uid() returns UUID, but userId is BIGINT, so we need to cast
CREATE POLICY exercise_search_history_user_select ON exercise_search_history FOR SELECT TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY exercise_search_history_user_insert ON exercise_search_history FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY exercise_search_history_user_update ON exercise_search_history FOR UPDATE TO authenticated USING (auth.uid()::text = userId::text) WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY exercise_search_history_user_delete ON exercise_search_history FOR DELETE TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY exercise_search_history_service_all ON exercise_search_history FOR ALL TO service_role USING (true) WITH CHECK (true);

-- exercise_usage_stats
-- Note: auth.uid() returns UUID, but userId is BIGINT, so we need to cast
CREATE POLICY exercise_usage_stats_user_select ON exercise_usage_stats FOR SELECT TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY exercise_usage_stats_user_insert ON exercise_usage_stats FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY exercise_usage_stats_user_update ON exercise_usage_stats FOR UPDATE TO authenticated USING (auth.uid()::text = userId::text) WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY exercise_usage_stats_user_delete ON exercise_usage_stats FOR DELETE TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY exercise_usage_stats_service_all ON exercise_usage_stats FOR ALL TO service_role USING (true) WITH CHECK (true);

-- workout_plans
-- Note: auth.uid() returns UUID, but userId is BIGINT, so we need to cast
CREATE POLICY workout_plans_user_select ON workout_plans FOR SELECT TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY workout_plans_user_insert ON workout_plans FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY workout_plans_user_update ON workout_plans FOR UPDATE TO authenticated USING (auth.uid()::text = userId::text) WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY workout_plans_user_delete ON workout_plans FOR DELETE TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY workout_plans_service_all ON workout_plans FOR ALL TO service_role USING (true) WITH CHECK (true);

-- workout_sessions
-- Note: auth.uid() returns UUID, but userId is BIGINT, so we need to cast
CREATE POLICY workout_sessions_user_select ON workout_sessions FOR SELECT TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY workout_sessions_user_insert ON workout_sessions FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY workout_sessions_user_update ON workout_sessions FOR UPDATE TO authenticated USING (auth.uid()::text = userId::text) WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY workout_sessions_user_delete ON workout_sessions FOR DELETE TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY workout_sessions_service_all ON workout_sessions FOR ALL TO service_role USING (true) WITH CHECK (true);

-- exercise_history_stats
-- Note: auth.uid() returns UUID, but userId is BIGINT, so we need to cast
CREATE POLICY exercise_history_stats_user_select ON exercise_history_stats FOR SELECT TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY exercise_history_stats_user_insert ON exercise_history_stats FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY exercise_history_stats_user_update ON exercise_history_stats FOR UPDATE TO authenticated USING (auth.uid()::text = userId::text) WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY exercise_history_stats_user_delete ON exercise_history_stats FOR DELETE TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY exercise_history_stats_service_all ON exercise_history_stats FOR ALL TO service_role USING (true) WITH CHECK (true);

-- daily_stats
-- Note: auth.uid() returns UUID, but userId is BIGINT, so we need to cast
CREATE POLICY daily_stats_user_select ON daily_stats FOR SELECT TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY daily_stats_user_insert ON daily_stats FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY daily_stats_user_update ON daily_stats FOR UPDATE TO authenticated USING (auth.uid()::text = userId::text) WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY daily_stats_user_delete ON daily_stats FOR DELETE TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY daily_stats_service_all ON daily_stats FOR ALL TO service_role USING (true) WITH CHECK (true);

-- workout_templates
-- Note: auth.uid() returns UUID, but userId is BIGINT, so we need to cast
CREATE POLICY workout_templates_user_select ON workout_templates FOR SELECT TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY workout_templates_user_insert ON workout_templates FOR INSERT TO authenticated WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY workout_templates_user_update ON workout_templates FOR UPDATE TO authenticated USING (auth.uid()::text = userId::text) WITH CHECK (auth.uid()::text = userId::text);
CREATE POLICY workout_templates_user_delete ON workout_templates FOR DELETE TO authenticated USING (auth.uid()::text = userId::text);
CREATE POLICY workout_templates_service_all ON workout_templates FOR ALL TO service_role USING (true) WITH CHECK (true);

-- =========================
-- Grants (compact lists)
-- =========================
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON
  "user", user_profiles, user_settings, tokens,
  search_content, calendar_events, chat_raw, chat_fts, chat_sessions, chat_vec,
  message_embedding, session_summary, memory_records,
  exercise, exercise_fts, exercise_search_history, exercise_usage_stats,
  workout_plans, plan_days, plan_templates, workout_sessions, session_exercises, session_sets,
  exercise_history_stats, session_autosave, daily_stats,
  workout_templates, template_exercises, template_versions
TO authenticated;

GRANT ALL ON
  "user", user_profiles, user_settings, tokens,
  search_content, calendar_events, chat_raw, chat_fts, chat_sessions, chat_vec,
  message_embedding, session_summary, memory_records,
  exercise, exercise_fts, exercise_search_history, exercise_usage_stats,
  workout_plans, plan_days, plan_templates, workout_sessions, session_exercises, session_sets,
  exercise_history_stats, session_autosave, daily_stats,
  workout_templates, template_exercises, template_versions
TO service_role;

-- =========================
-- Quick verification
-- =========================
SELECT tablename, policyname FROM pg_policies
WHERE tablename IN ('user','user_profiles','user_settings','tokens','chat_sessions','exercise','workout_sessions')
ORDER BY tablename, policyname;
