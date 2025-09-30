-- 创建 Supabase 数据库表
-- 在 Supabase Dashboard 的 SQL Editor 中运行此脚本

-- 创建 ai_chat_messages 表
CREATE TABLE IF NOT EXISTS public.ai_chat_messages (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    -- 索引
    CONSTRAINT ai_chat_messages_role_check CHECK (role IN ('user', 'assistant'))
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_conversation_id 
ON public.ai_chat_messages(conversation_id);

CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_user_id 
ON public.ai_chat_messages(user_id);

CREATE INDEX IF NOT EXISTS idx_ai_chat_messages_timestamp 
ON public.ai_chat_messages(timestamp DESC);

-- 启用 Row Level Security (RLS)
ALTER TABLE public.ai_chat_messages ENABLE ROW LEVEL SECURITY;

-- 创建 RLS 策略：用户只能访问自己的消息
CREATE POLICY "Users can view their own messages" 
ON public.ai_chat_messages 
FOR SELECT 
USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own messages" 
ON public.ai_chat_messages 
FOR INSERT 
WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own messages" 
ON public.ai_chat_messages 
FOR UPDATE 
USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own messages" 
ON public.ai_chat_messages 
FOR DELETE 
USING (auth.uid() = user_id);

-- 创建一个视图来方便查询对话历史
CREATE OR REPLACE VIEW public.conversation_history AS
SELECT 
    id,
    conversation_id,
    role,
    content,
    timestamp,
    user_id,
    metadata
FROM public.ai_chat_messages
ORDER BY conversation_id, timestamp ASC;

-- 为服务端操作创建一个函数（使用 service role）
CREATE OR REPLACE FUNCTION public.insert_ai_message(
    p_conversation_id TEXT,
    p_role TEXT,
    p_content TEXT,
    p_user_id UUID,
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    message_id UUID;
BEGIN
    INSERT INTO public.ai_chat_messages (
        conversation_id,
        role,
        content,
        user_id,
        metadata
    ) VALUES (
        p_conversation_id,
        p_role,
        p_content,
        p_user_id,
        p_metadata
    ) RETURNING id INTO message_id;
    
    RETURN message_id;
END;
$$;

-- 授予必要的权限
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.ai_chat_messages TO authenticated;
GRANT SELECT ON public.conversation_history TO authenticated;
GRANT EXECUTE ON FUNCTION public.insert_ai_message TO service_role;
