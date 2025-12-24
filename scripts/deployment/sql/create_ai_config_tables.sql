-- 创建 AI 配置相关表
-- 在 Supabase Dashboard 的 SQL Editor 中运行此脚本

-- 创建 ai_model 表
CREATE TABLE IF NOT EXISTS public.ai_model (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    model TEXT NOT NULL,
    base_url TEXT,
    api_key TEXT,
    description TEXT,
    timeout INTEGER DEFAULT 60,
    is_active BOOLEAN DEFAULT TRUE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ai_model_is_active ON public.ai_model(is_active);
CREATE INDEX IF NOT EXISTS idx_ai_model_is_default ON public.ai_model(is_default);

-- 创建更新时间触发器
-- 与 B2（conversations/messages）保持一致：使用 public.update_updated_at_column()
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_ai_model_updated_at ON public.ai_model;
CREATE TRIGGER update_ai_model_updated_at
    BEFORE UPDATE ON public.ai_model
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- 创建 ai_prompt 表
CREATE TABLE IF NOT EXISTS public.ai_prompt (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    tools_json TEXT,
    description TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ai_prompt_is_active ON public.ai_prompt(is_active);
CREATE INDEX IF NOT EXISTS idx_ai_prompt_name ON public.ai_prompt(name);

-- 创建更新时间触发器
DROP TRIGGER IF EXISTS update_ai_prompt_updated_at ON public.ai_prompt;
CREATE TRIGGER update_ai_prompt_updated_at
    BEFORE UPDATE ON public.ai_prompt
    FOR EACH ROW
    EXECUTE FUNCTION public.update_updated_at_column();

-- 启用 Row Level Security (RLS)
ALTER TABLE public.ai_model ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_prompt ENABLE ROW LEVEL SECURITY;

-- 创建 RLS 策略：所有认证用户可以读取
DROP POLICY IF EXISTS "Authenticated users can view ai_model" ON public.ai_model;
CREATE POLICY "Authenticated users can view ai_model"
ON public.ai_model
FOR SELECT
TO authenticated
USING (true);

DROP POLICY IF EXISTS "Authenticated users can view ai_prompt" ON public.ai_prompt;
CREATE POLICY "Authenticated users can view ai_prompt"
ON public.ai_prompt
FOR SELECT
TO authenticated
USING (true);

-- 创建 RLS 策略：service_role 可以进行所有操作
DROP POLICY IF EXISTS "Service role can manage ai_model" ON public.ai_model;
CREATE POLICY "Service role can manage ai_model"
ON public.ai_model
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "Service role can manage ai_prompt" ON public.ai_prompt;
CREATE POLICY "Service role can manage ai_prompt"
ON public.ai_prompt
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- 授予必要的权限
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT SELECT ON public.ai_model TO authenticated;
GRANT SELECT ON public.ai_prompt TO authenticated;
GRANT ALL ON public.ai_model TO service_role;
GRANT ALL ON public.ai_prompt TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.ai_model_id_seq TO service_role;
GRANT USAGE, SELECT ON SEQUENCE public.ai_prompt_id_seq TO service_role;

-- ✅ 安全默认：不在建表脚本中插入示例数据（避免重复插入与误提交敏感 key）
-- 如需初始化数据，建议通过后台 UI 或单独的“种子脚本”在受控环境下执行。
