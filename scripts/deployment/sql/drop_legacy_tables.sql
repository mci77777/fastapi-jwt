-- 删除 legacy schema 下的历史表（破坏性清理）
-- ⚠️ 仅在确认完成迁移、且不再需要回滚时执行
-- 备注：某些历史表可能仍留在 public（例如 message_embedding）且外键引用 legacy.*，需要先删除以解除依赖。

-- 解除对 legacy.chat_raw 的依赖（如存在）
DROP TABLE IF EXISTS public.message_embedding;
-- 解除对 legacy.chat_sessions 的依赖（如存在）
DROP TABLE IF EXISTS public.session_summary;

DROP VIEW IF EXISTS legacy.conversation_history;
DROP TABLE IF EXISTS legacy.ai_chat_messages;
DROP TABLE IF EXISTS legacy.chat_messages;
DROP TABLE IF EXISTS legacy.chat_raw;
DROP TABLE IF EXISTS legacy.chat_sessions;
DROP TABLE IF EXISTS legacy.chat_vec;
DROP TABLE IF EXISTS legacy.chat_fts;

-- 可选：如果 legacy schema 为空则删除
DROP SCHEMA IF EXISTS legacy;
