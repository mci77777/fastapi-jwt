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
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_ai_model_updated_at
    BEFORE UPDATE ON public.ai_model
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

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
CREATE TRIGGER update_ai_prompt_updated_at
    BEFORE UPDATE ON public.ai_prompt
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 启用 Row Level Security (RLS)
ALTER TABLE public.ai_model ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.ai_prompt ENABLE ROW LEVEL SECURITY;

-- 创建 RLS 策略：所有认证用户可以读取
CREATE POLICY "Authenticated users can view ai_model"
ON public.ai_model
FOR SELECT
TO authenticated
USING (true);

CREATE POLICY "Authenticated users can view ai_prompt"
ON public.ai_prompt
FOR SELECT
TO authenticated
USING (true);

-- 创建 RLS 策略：service_role 可以进行所有操作
CREATE POLICY "Service role can manage ai_model"
ON public.ai_model
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

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
GRANT USAGE, SELECT ON SEQUENCE ai_model_id_seq TO service_role;
GRANT USAGE, SELECT ON SEQUENCE ai_prompt_id_seq TO service_role;

-- 插入默认数据
INSERT INTO public.ai_model (name, model, base_url, api_key, description, timeout, is_active, is_default)
VALUES 
    ('DeepSeek R1', 'deepseek-r1', 'https://zzzzapi.com', 'sk-VkX00c7dM8LOVtrMI9Zo3RarcvDSSsoYbHZjz5WRGzBsMCJJ', '默认 AI 模型', 60, true, true)
ON CONFLICT DO NOTHING;

INSERT INTO public.ai_prompt (name, version, system_prompt, description, is_active)
VALUES 
    ('GymBro Assistant', 'v1.0', 'You are GymBro''s AI assistant. Help users with their fitness and workout questions.', '默认健身助手 Prompt', true)
ON CONFLICT DO NOTHING;

