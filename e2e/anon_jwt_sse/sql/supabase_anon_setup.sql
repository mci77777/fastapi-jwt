-- =====================================================
-- Supabase 匿名用户JWT获取完整SQL脚本
-- 基于 docs/匿名用户获取JWT.md 规范
-- 可直接在Supabase SQL Editor中执行
-- =====================================================

-- 1. 创建匿名用户追踪表
-- =====================================================
CREATE TABLE IF NOT EXISTS public.user_anon (
  user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  ip text,
  expires_at timestamptz NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb DEFAULT '{}'::jsonb,
  -- 索引优化
  CONSTRAINT user_anon_expires_at_check CHECK (expires_at > created_at)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_user_anon_expires_at ON public.user_anon(expires_at);
CREATE INDEX IF NOT EXISTS idx_user_anon_ip ON public.user_anon(ip);
CREATE INDEX IF NOT EXISTS idx_user_anon_active ON public.user_anon(is_active, expires_at);

-- 2. 创建IP限流表
-- =====================================================
CREATE TABLE IF NOT EXISTS public.anon_rate_limits (
  ip text NOT NULL,
  day date NOT NULL,
  count int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (ip, day)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_anon_rate_limits_day ON public.anon_rate_limits(day);

-- 3. 创建匿名用户会话表（用于SSE和消息追踪）
-- =====================================================
CREATE TABLE IF NOT EXISTS public.anon_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  session_token text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_activity timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  ip_address text,
  user_agent text,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb DEFAULT '{}'::jsonb
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_anon_sessions_user_id ON public.anon_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_anon_sessions_token ON public.anon_sessions(session_token);
CREATE INDEX IF NOT EXISTS idx_anon_sessions_expires ON public.anon_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_anon_sessions_active ON public.anon_sessions(is_active, expires_at);

-- 4. 创建匿名用户消息表（用于AI对话）
-- =====================================================
CREATE TABLE IF NOT EXISTS public.anon_messages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  session_id uuid REFERENCES public.anon_sessions(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
  content text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  is_final boolean NOT NULL DEFAULT false,
  metadata jsonb DEFAULT '{}'::jsonb,
  -- 确保消息顺序
  sequence_number integer NOT NULL DEFAULT 0
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_anon_messages_user_id ON public.anon_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_anon_messages_session_id ON public.anon_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_anon_messages_created_at ON public.anon_messages(created_at);
CREATE INDEX IF NOT EXISTS idx_anon_messages_role ON public.anon_messages(role);

-- 5. 创建公共内容表（用于测试RLS策略）
-- =====================================================
CREATE TABLE IF NOT EXISTS public.public_content (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title text NOT NULL,
  content text,
  owner_id uuid REFERENCES auth.users(id) ON DELETE CASCADE,
  is_public boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  metadata jsonb DEFAULT '{}'::jsonb
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_public_content_owner_id ON public.public_content(owner_id);
CREATE INDEX IF NOT EXISTS idx_public_content_is_public ON public.public_content(is_public);
CREATE INDEX IF NOT EXISTS idx_public_content_created_at ON public.public_content(created_at);

-- 6. 启用RLS（行级安全）
-- =====================================================
ALTER TABLE public.user_anon ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.anon_rate_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.anon_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.anon_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.public_content ENABLE ROW LEVEL SECURITY;

-- 7. 创建RLS策略
-- =====================================================

-- 7.1 user_anon表策略
-- 服务角色可以完全访问
CREATE POLICY "service_role_full_access_user_anon" ON public.user_anon
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);

-- 匿名用户只能查看自己的记录且未过期
CREATE POLICY "anon_user_select_own" ON public.user_anon
  FOR SELECT TO public
  USING (
    user_id = auth.uid()
    AND expires_at > now()
    AND is_active = true
  );

-- 7.2 anon_rate_limits表策略
-- 服务角色可以完全访问（用于Edge Function）
CREATE POLICY "service_role_full_access_rate_limits" ON public.anon_rate_limits
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);

-- 7.3 anon_sessions表策略
-- 服务角色可以完全访问
CREATE POLICY "service_role_full_access_sessions" ON public.anon_sessions
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);

-- 匿名用户只能查看自己的会话且未过期
CREATE POLICY "anon_user_select_own_sessions" ON public.anon_sessions
  FOR SELECT TO public
  USING (
    user_id = auth.uid()
    AND expires_at > now()
    AND is_active = true
  );

-- 匿名用户可以更新自己会话的last_activity
CREATE POLICY "anon_user_update_own_sessions" ON public.anon_sessions
  FOR UPDATE TO public
  USING (
    user_id = auth.uid()
    AND expires_at > now()
    AND is_active = true
  )
  WITH CHECK (
    user_id = auth.uid()
    AND expires_at > now()
    AND is_active = true
  );

-- 7.4 anon_messages表策略
-- 服务角色可以完全访问
CREATE POLICY "service_role_full_access_messages" ON public.anon_messages
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);

-- 匿名用户可以查看自己的消息
CREATE POLICY "anon_user_select_own_messages" ON public.anon_messages
  FOR SELECT TO public
  USING (
    user_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.user_anon ua
      WHERE ua.user_id = auth.uid()
        AND ua.expires_at > now()
        AND ua.is_active = true
    )
  );

-- 匿名用户可以插入自己的消息
CREATE POLICY "anon_user_insert_own_messages" ON public.anon_messages
  FOR INSERT TO public
  WITH CHECK (
    user_id = auth.uid()
    AND EXISTS (
      SELECT 1 FROM public.user_anon ua
      WHERE ua.user_id = auth.uid()
        AND ua.expires_at > now()
        AND ua.is_active = true
    )
  );

-- 7.5 public_content表策略
-- 服务角色可以完全访问
CREATE POLICY "service_role_full_access_content" ON public.public_content
  FOR ALL TO service_role
  USING (true)
  WITH CHECK (true);

-- 认证用户可以查看自己的内容
CREATE POLICY "authenticated_user_select_own" ON public.public_content
  FOR SELECT TO authenticated
  USING (owner_id = auth.uid());

-- 匿名用户只能查看公共内容，且token有效
CREATE POLICY "anon_user_select_public" ON public.public_content
  FOR SELECT TO public
  USING (
    is_public = true
    AND EXISTS (
      SELECT 1 FROM public.user_anon ua
      WHERE ua.user_id = auth.uid()
        AND ua.expires_at > now()
        AND ua.is_active = true
    )
  );

-- 8. 创建触发器函数
-- =====================================================

-- 8.1 更新updated_at字段的触发器函数
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 8.2 自动清理过期匿名用户的函数
CREATE OR REPLACE FUNCTION public.cleanup_expired_anon_users()
RETURNS void AS $$
BEGIN
  -- 标记过期的匿名用户为非活跃状态
  UPDATE public.user_anon
  SET is_active = false
  WHERE expires_at <= now() AND is_active = true;

  -- 标记过期的会话为非活跃状态
  UPDATE public.anon_sessions
  SET is_active = false
  WHERE expires_at <= now() AND is_active = true;

  -- 清理超过7天的过期记录
  DELETE FROM public.user_anon
  WHERE expires_at <= now() - INTERVAL '7 days';

  DELETE FROM public.anon_sessions
  WHERE expires_at <= now() - INTERVAL '7 days';

  -- 清理超过30天的限流记录
  DELETE FROM public.anon_rate_limits
  WHERE day <= CURRENT_DATE - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 8.3 验证匿名用户是否有效的函数
CREATE OR REPLACE FUNCTION public.is_valid_anon_user(user_uuid uuid)
RETURNS boolean AS $$
BEGIN
  RETURN EXISTS (
    SELECT 1 FROM public.user_anon ua
    WHERE ua.user_id = user_uuid
      AND ua.expires_at > now()
      AND ua.is_active = true
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 9. 创建触发器
-- =====================================================

-- 9.1 为需要updated_at的表创建触发器
CREATE TRIGGER update_anon_rate_limits_updated_at
  BEFORE UPDATE ON public.anon_rate_limits
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_anon_messages_updated_at
  BEFORE UPDATE ON public.anon_messages
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_public_content_updated_at
  BEFORE UPDATE ON public.public_content
  FOR EACH ROW
  EXECUTE FUNCTION public.update_updated_at_column();

-- 10. 插入测试数据
-- =====================================================

-- 插入一些公共内容用于测试
INSERT INTO public.public_content (title, content, is_public, metadata) VALUES
  ('公共文档1', '这是一个公共可访问的文档内容', true, '{"type": "test", "category": "public"}'),
  ('公共文档2', '匿名用户可以查看这个内容', true, '{"type": "test", "category": "public"}'),
  ('私有文档', '这是私有内容，匿名用户无法访问', false, '{"type": "test", "category": "private"}')
ON CONFLICT DO NOTHING;

-- 11. 创建定时清理任务（需要pg_cron扩展）
-- =====================================================
-- 注意：这需要在Supabase中启用pg_cron扩展
-- SELECT cron.schedule('cleanup-expired-anon', '0 */6 * * *', 'SELECT public.cleanup_expired_anon_users();');

-- 12. 权限设置
-- =====================================================

-- 授予anon角色必要的权限
GRANT USAGE ON SCHEMA public TO anon;
GRANT SELECT ON public.user_anon TO anon;
GRANT SELECT ON public.anon_sessions TO anon;
GRANT UPDATE ON public.anon_sessions TO anon;
GRANT SELECT, INSERT ON public.anon_messages TO anon;
GRANT SELECT ON public.public_content TO anon;

-- 授予authenticated角色权限
GRANT USAGE ON SCHEMA public TO authenticated;
GRANT ALL ON public.user_anon TO authenticated;
GRANT ALL ON public.anon_sessions TO authenticated;
GRANT ALL ON public.anon_messages TO authenticated;
GRANT ALL ON public.public_content TO authenticated;

-- 授予service_role完全权限
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO service_role;

-- =====================================================
-- 脚本执行完成
-- =====================================================
--
-- 使用说明：
-- 1. 在Supabase SQL Editor中执行此脚本
-- 2. 确保已启用必要的扩展（如pg_cron用于定时任务）
-- 3. 配置Edge Function使用相应的环境变量
-- 4. 测试匿名用户JWT获取和权限验证
--
-- 验证脚本：
-- SELECT * FROM public.user_anon;
-- SELECT * FROM public.anon_rate_limits;
-- SELECT * FROM public.public_content WHERE is_public = true;
-- SELECT public.is_valid_anon_user('your-test-uuid');
--
-- =====================================================
