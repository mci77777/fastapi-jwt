# Supabase 命名与引用审计报告

- 生成时间(UTC)：`2025-12-24T04:53:23.914982+00:00`
- 后端归属表（SSOT）：`ai_model, ai_prompt, anon_messages, anon_rate_limits, anon_sessions, conversations, messages, user_anon`
- 扫描到的表引用数量：`23`
- 发现项数量：`2`

## 发现项（Findings）

- `ddl/public_non_backend/high` `public.message_embedding`：SQL 触达 public 非后端归属表；需人工确认 App 端不依赖/允许变更
- `ddl/public_non_backend/high` `public.session_summary`：SQL 触达 public 非后端归属表；需人工确认 App 端不依赖/允许变更

## 仓库内引用的 Supabase 表（去重）

- `ai_chat_messages`
- `ai_model`
- `ai_prompt`
- `anon_messages`
- `anon_rate_limits`
- `anon_sessions`
- `audit_logs`
- `chat_fts`
- `chat_messages`
- `chat_raw`
- `chat_sessions`
- `chat_vec`
- `conversation_history`
- `conversations`
- `message_embedding`
- `messages`
- `public_content`
- `session_summary`
- `user_anon`
- `user_metrics`
- `user_profiles`
- `user_settings`
- `users`

## DDL 触达的表（schema.table）

- `legacy.ai_chat_messages`
- `legacy.chat_fts`
- `legacy.chat_messages`
- `legacy.chat_raw`
- `legacy.chat_sessions`
- `legacy.chat_vec`
- `legacy.conversation_history`
- `public.ai_chat_messages`
- `public.ai_model`
- `public.ai_prompt`
- `public.anon_messages`
- `public.anon_sessions`
- `public.audit_logs`
- `public.chat_fts`
- `public.chat_messages`
- `public.chat_raw`
- `public.chat_sessions`
- `public.chat_vec`
- `public.conversations`
- `public.message_embedding`
- `public.messages`
- `public.public_content`
- `public.session_summary`
- `public.user_anon`
- `public.user_metrics`
- `public.user_profiles`
- `public.user_settings`
- `public.users`

## DDL DROP TABLE（破坏性）

- `legacy.ai_chat_messages`
- `legacy.chat_fts`
- `legacy.chat_messages`
- `legacy.chat_raw`
- `legacy.chat_sessions`
- `legacy.chat_vec`
- `public.message_embedding`
- `public.session_summary`

## 单文件引用明细（节选）

- `app/auth/supabase_provider.py`：conversations, messages
- `scripts/deployment/sql/archive_legacy_tables.sql`：ai_chat_messages, chat_fts, chat_messages, chat_raw, chat_sessions, chat_vec
- `scripts/deployment/sql/create_ai_config_tables.sql`：ai_model, ai_prompt
- `scripts/deployment/sql/create_supabase_tables.sql`：conversations, messages
- `scripts/deployment/sql/drop_legacy_tables.sql`：ai_chat_messages, chat_fts, chat_messages, chat_raw, chat_sessions, chat_vec, conversation_history, message_embedding, session_summary
- `scripts/deployment/sql/optimize_rls_performance.sql`：anon_messages, anon_sessions, audit_logs, chat_raw, chat_sessions, public_content, user_anon, user_metrics, user_profiles, user_settings, users
- `scripts/deployment/sql/rollback_rls_optimization.sql`：anon_messages, anon_sessions, audit_logs, chat_raw, chat_sessions, public_content, user_anon, user_metrics, user_profiles, user_settings, users
- `e2e/anon_jwt_sse/edge-functions/get-anon-token/index.ts`：anon_rate_limits, user_anon
- `docs/features/SUPABASE_KEEPALIVE.md`：ai_model
