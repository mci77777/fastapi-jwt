# Supabase匿名用户JWT系统部署指南

## 📋 快速部署

三步完成部署：
1. 执行SQL脚本
2. 部署Edge Function
3. 运行测试验证

## 🗄️ 1. 数据库设置

1. 登录 [Supabase Dashboard](https://app.supabase.com)
2. 选择项目 → SQL Editor → 新查询
3. 复制粘贴 `e2e/anon_jwt_sse/sql/supabase_anon_setup.sql` 内容
4. 点击 Run 执行

## 🔧 2. Edge Function部署

```bash
# 安装Supabase CLI
npm install -g supabase

# 登录并部署
supabase login
./scripts/deploy-edge-function.sh YOUR_PROJECT_REF
```

## ⚙️ 3. 环境变量配置

更新 `.env` 文件：

```bash
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_ANON_KEY=your_anon_public_key_here
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
API_BASE=http://localhost:9999
```

## 🧪 4. 测试验证

```bash
cd e2e/anon_jwt_sse

# 运行验证测试
pnpm run validate

# 运行完整E2E测试
pnpm run e2e:full
```

## ✅ 部署检查清单

- [ ] SQL脚本执行完成
- [ ] Edge Function部署成功
- [ ] 环境变量配置正确
- [ ] E2E测试通过

## 🔗 相关链接

- [Supabase Dashboard](https://app.supabase.com)
- [Edge Functions文档](https://supabase.com/docs/guides/functions)
- [RLS文档](https://supabase.com/docs/guides/auth/row-level-security)
