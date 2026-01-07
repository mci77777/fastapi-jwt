-- SCHEMA_PART_2.sql
-- Order: 2/5
-- Purpose: Chat & Search related tables + their FKs + indexes
-- Run after SCHEMA_PART_1.sql

-- =========================
-- Tables: search, calendar, chat, memory
-- =========================

-- search_content
CREATE TABLE IF NOT EXISTS search_content (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    content TEXT NOT NULL,
    embedding TEXT,
    metadata TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- calendar_events
CREATE TABLE IF NOT EXISTS calendar_events (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
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

-- chat_raw (messages)
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

-- chat_fts (placeholder, not a real FTS5 table in PG)
CREATE TABLE IF NOT EXISTS chat_fts (
    content TEXT NOT NULL,
    rowid BIGINT PRIMARY KEY
);

-- chat_sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    user_id BIGINT NOT NULL,
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

-- chat_vec
CREATE TABLE IF NOT EXISTS chat_vec (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    embedding BYTEA NOT NULL,
    embedding_dim BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id)
);

-- message_embedding
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

-- session_summary
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

-- memory_records
CREATE TABLE IF NOT EXISTS memory_records (
    id UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
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

-- =========================
-- Foreign keys (chat)
-- =========================
ALTER TABLE chat_raw
  ADD CONSTRAINT fk_chat_raw_session_id
  FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE message_embedding
  ADD CONSTRAINT fk_message_embedding_message_id
  FOREIGN KEY (message_id) REFERENCES chat_raw(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE session_summary
  ADD CONSTRAINT fk_session_summary_session_id
  FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;


-- FKs to user table (existing table with id as primary key)
-- Note: Referencing existing 'user' table with 'id' column, not 'users' table
ALTER TABLE calendar_events
  ADD CONSTRAINT fk_calendar_events_user_id
  FOREIGN KEY (user_id) REFERENCES "user"(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE chat_sessions
  ADD CONSTRAINT fk_chat_sessions_user_id
  FOREIGN KEY (user_id) REFERENCES "user"(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

ALTER TABLE memory_records
  ADD CONSTRAINT fk_memory_records_user_id
  FOREIGN KEY (user_id) REFERENCES "user"(id)
  ON DELETE NO ACTION ON UPDATE NO ACTION;

-- =========================
-- Indexes (chat & search & memory)
-- =========================
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

-- =========================
-- Quick verification
-- =========================
SELECT table_name FROM information_schema.tables
WHERE table_schema='public' AND table_name IN (
  'search_content','calendar_events','chat_raw','chat_fts','chat_sessions','chat_vec',
  'message_embedding','session_summary','memory_records')
ORDER BY table_name;
