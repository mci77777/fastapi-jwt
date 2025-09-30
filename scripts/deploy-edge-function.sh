#!/bin/bash
# 简洁的Edge Function部署脚本

set -e

PROJECT_REF=${1:-""}

if [ -z "$PROJECT_REF" ]; then
    echo "使用方法: ./scripts/deploy-edge-function.sh PROJECT_REF"
    echo "例如: ./scripts/deploy-edge-function.sh rykglivrwzcykhhnxwoz"
    exit 1
fi

echo "🚀 部署Edge Function到Supabase..."
echo "项目引用: $PROJECT_REF"

# 检查Supabase CLI
if ! command -v supabase &> /dev/null; then
    echo "❌ Supabase CLI未安装"
    echo "请运行: npm install -g supabase"
    exit 1
fi

# 创建函数目录
mkdir -p supabase/functions/get-anon-token

# 复制Edge Function代码
cp e2e/anon_jwt_sse/edge-functions/get-anon-token/index.ts supabase/functions/get-anon-token/

# 部署函数
echo "📦 部署函数..."
supabase functions deploy get-anon-token --project-ref "$PROJECT_REF"

echo "✅ Edge Function部署完成"
echo "🔗 函数URL: https://$PROJECT_REF.supabase.co/functions/v1/get-anon-token"
