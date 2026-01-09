-- Supabase 数据库表（SSOT）
-- ✅ B2 方案：统一对话落库到 public.conversations / public.messages
-- 在 Supabase Dashboard 的 SQL Editor 中运行此脚本

-- UUID 生成（Supabase 默认已启用，但这里做幂等兜底）
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- updated_at 自动更新触发器（幂等）
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

-- 1) conversations（会话）
CREATE TABLE IF NOT EXISTS public.conversations (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  title text,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  is_active boolean NOT NULL DEFAULT true,
  user_type text,
  CONSTRAINT conversations_pkey PRIMARY KEY (id)
);

-- 统一 user_id -> auth.users（避免依赖 public.users 镜像表）
ALTER TABLE IF EXISTS public.conversations
  DROP CONSTRAINT IF EXISTS conversations_user_id_fkey;
ALTER TABLE IF EXISTS public.conversations
  ADD CONSTRAINT conversations_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON public.conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON public.conversations(created_at DESC);

DROP TRIGGER IF EXISTS update_conversations_updated_at ON public.conversations;
CREATE TRIGGER update_conversations_updated_at
  BEFORE UPDATE ON public.conversations
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- 2) messages（消息）
CREATE TABLE IF NOT EXISTS public.messages (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL,
  user_id uuid NOT NULL,
  content text NOT NULL,
  role text NOT NULL DEFAULT 'user',
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  user_type text,
  CONSTRAINT messages_pkey PRIMARY KEY (id)
);

ALTER TABLE IF EXISTS public.messages
  DROP CONSTRAINT IF EXISTS messages_conversation_id_fkey;
ALTER TABLE IF EXISTS public.messages
  ADD CONSTRAINT messages_conversation_id_fkey
  FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;

ALTER TABLE IF EXISTS public.messages
  DROP CONSTRAINT IF EXISTS messages_user_id_fkey;
ALTER TABLE IF EXISTS public.messages
  ADD CONSTRAINT messages_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON public.messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON public.messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.messages(created_at DESC);

DROP TRIGGER IF EXISTS update_messages_updated_at ON public.messages;
CREATE TRIGGER update_messages_updated_at
  BEFORE UPDATE ON public.messages
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- 3) RLS（可选：如果未来要开放前端直连 DB，就需要；后端使用 service_role 时也建议保留）
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS conversations_select_own ON public.conversations;
CREATE POLICY conversations_select_own
  ON public.conversations
  FOR SELECT TO authenticated
  USING (user_id = (select auth.uid()));

DROP POLICY IF EXISTS conversations_insert_own ON public.conversations;
CREATE POLICY conversations_insert_own
  ON public.conversations
  FOR INSERT TO authenticated
  WITH CHECK (user_id = (select auth.uid()));

DROP POLICY IF EXISTS messages_select_own ON public.messages;
CREATE POLICY messages_select_own
  ON public.messages
  FOR SELECT TO authenticated
  USING (user_id = (select auth.uid()));

DROP POLICY IF EXISTS messages_insert_own ON public.messages;
CREATE POLICY messages_insert_own
  ON public.messages
  FOR INSERT TO authenticated
  WITH CHECK (
    user_id = (select auth.uid())
    AND conversation_id IN (SELECT id FROM public.conversations WHERE user_id = (select auth.uid()))
  );

-- 基础授权（保守：仅给 authenticated 查询/写入）
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT ON public.conversations TO authenticated;
GRANT SELECT, INSERT ON public.messages TO authenticated;

-- 4) user_entitlements（管理端权益登记；后端通过 service_role 访问）
CREATE TABLE IF NOT EXISTS public.user_entitlements (
  user_id uuid NOT NULL,
  tier text NOT NULL DEFAULT 'free',
  expires_at bigint NULL, -- epoch ms
  flags jsonb NOT NULL DEFAULT '{}'::jsonb,
  last_updated bigint NOT NULL DEFAULT (floor(extract(epoch from now()) * 1000))::bigint,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  updated_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT user_entitlements_pkey PRIMARY KEY (user_id)
);

ALTER TABLE IF EXISTS public.user_entitlements
  DROP CONSTRAINT IF EXISTS user_entitlements_user_id_fkey;
ALTER TABLE IF EXISTS public.user_entitlements
  ADD CONSTRAINT user_entitlements_user_id_fkey
  FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_user_entitlements_tier ON public.user_entitlements(tier);
CREATE INDEX IF NOT EXISTS idx_user_entitlements_expires_at ON public.user_entitlements(expires_at);
CREATE INDEX IF NOT EXISTS idx_user_entitlements_last_updated ON public.user_entitlements(last_updated DESC);

DROP TRIGGER IF EXISTS update_user_entitlements_updated_at ON public.user_entitlements;
CREATE TRIGGER update_user_entitlements_updated_at
  BEFORE UPDATE ON public.user_entitlements
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

ALTER TABLE public.user_entitlements ENABLE ROW LEVEL SECURITY;
GRANT USAGE ON SCHEMA public TO service_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_entitlements TO service_role;

-- View: list all users with their entitlements (SSOT: auth.users)
-- 说明：匿名用户只用于统计/审计；默认列表过滤掉匿名用户即可。
DROP VIEW IF EXISTS public.user_entitlements_list;
CREATE VIEW public.user_entitlements_list AS
SELECT
  au.id AS user_id,
  COALESCE(e.tier, 'free') AS tier,
  e.expires_at,
  COALESCE(e.flags, '{}'::jsonb) AS flags,
  e.last_updated,
  (e.user_id IS NOT NULL) AS exists,
  COALESCE(au.is_anonymous, false) AS is_anonymous
FROM auth.users au
LEFT JOIN public.user_entitlements e ON e.user_id = au.id;

GRANT SELECT ON public.user_entitlements_list TO service_role;

-- View: App user admin list (auth.users is SSOT for user existence)
-- 用于 Dashboard 的 App 用户管理列表：支持分页/过滤/统计，并确保 user_id 一定存在于 auth.users。
DROP VIEW IF EXISTS public.app_users_admin_view;
CREATE VIEW public.app_users_admin_view AS
SELECT
  au.id AS user_id,
  au.email,
  COALESCE(NULLIF(au.raw_user_meta_data ->> 'username', ''), NULLIF(au.raw_user_meta_data ->> 'name', '')) AS username,
  au.is_anonymous AS is_anonymous,
  au.created_at AS created_at,
  au.last_sign_in_at AS last_sign_in_at,
  au.banned_until AS banned_until,
  (CASE WHEN au.banned_until IS NOT NULL AND au.banned_until > now() THEN false ELSE true END) AS is_active,
  COALESCE(ue.tier, 'free') AS tier,
  ue.expires_at,
  COALESCE(ue.flags, '{}'::jsonb) AS flags,
  ue.last_updated,
  (ue.user_id IS NOT NULL) AS entitlements_exists
FROM auth.users au
LEFT JOIN public.user_entitlements ue ON ue.user_id = au.id;

GRANT SELECT ON public.app_users_admin_view TO service_role;

-- PostgREST schema cache refresh (best-effort).
NOTIFY pgrst, 'reload schema';
