-- 归档历史/重复表（非破坏性清理）
-- 目标：把非 SSOT 的 legacy 表移出 public，避免与 B2（conversations/messages）混淆
--
-- ✅ 推荐先执行本脚本（可回滚：把表 SET SCHEMA 回 public）
-- ⚠️ 执行前请确认这些表没有被任何客户端/Edge Function 直接依赖

CREATE SCHEMA IF NOT EXISTS legacy;

-- chat_* 旧模型
ALTER TABLE IF EXISTS public.chat_fts SET SCHEMA legacy;
ALTER TABLE IF EXISTS public.chat_vec SET SCHEMA legacy;
ALTER TABLE IF EXISTS public.chat_sessions SET SCHEMA legacy;
ALTER TABLE IF EXISTS public.chat_raw SET SCHEMA legacy;
ALTER TABLE IF EXISTS public.chat_messages SET SCHEMA legacy;

-- 其他可能的旧/重复对象（如存在）
ALTER TABLE IF EXISTS public.ai_chat_messages SET SCHEMA legacy;
ALTER VIEW IF EXISTS public.conversation_history SET SCHEMA legacy;

-- 归档完成后，public 侧只保留 B2：public.conversations / public.messages
