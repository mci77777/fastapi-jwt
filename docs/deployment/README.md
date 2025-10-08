# Supabase 匿名 JWT 部署摘要

本摘要整合原 `supabase-anon-jwt-setup.md` 的操作要点，详细脚本仍位于 `e2e/anon_jwt_sse/` 与 `scripts/` 目录。

## 🚀 三步上线
1. 在 Supabase 控制台执行 `e2e/anon_jwt_sse/sql/supabase_anon_setup.sql`，初始化数据库结构与 RLS。
2. 安装并登录 Supabase CLI，运行 `scripts/deploy-edge-function.sh <PROJECT_REF>` 发布匿名登录 Edge Function。
3. 更新 `.env` 中的 `SUPABASE_URL`、`SUPABASE_ANON_KEY`、`SUPABASE_SERVICE_ROLE_KEY` 与 `API_BASE`，确保后端指向正确环境。

## ✅ 验证与排查
- 使用 `pnpm run validate` 与 `pnpm run e2e:full` 校验匿名登录、SSE 流式会话与策略门。
- 确认 SQL 执行、Edge Function 部署、环境变量更新、E2E 测试均通过后再放量。
- 常见问题可通过 Supabase Dashboard 日志与 `scripts/` 目录下的排障脚本定位。