# E2E · Real User SSE（真实用户 JWT → /messages → SSE）

## 目的

- 用**真实 Supabase 用户 JWT**走完整链路：登录 → 创建消息 → SSE 拉流（直到 `completed`/`error`）。
- 与 Web 端一致：请求头使用 `X-Request-Id` 对账；请求体按 OpenAI 兼容字段白名单透传（扩展信息进 `metadata`）。

## SSOT 配置

本套件不单独维护 `.env`，统一复用：

- `e2e/anon_jwt_sse/.env.local`（不要提交）

至少需要：

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `API_BASE`（本地建议 `http://localhost:9999`）

若要“自动创建真实用户”（推荐，用于每日跑）还需要：

- `SUPABASE_SERVICE_ROLE_KEY`

## 本地运行（推荐）

1) 启动本地 Docker（Web=3101 / API=9999）：

```bash
bash scripts/dev/docker_local_up.sh
```

2) 跑真实用户 E2E：

```bash
bash scripts/dev/run_local_real_user_e2e.sh
```

产物默认写入：

- `e2e/real_user_sse/artifacts/*.json`

## Web 侧配置对齐（可选）

把 E2E 的 Supabase 配置同步到 Web（写入 `web/.env.development.local`，已被 gitignore 忽略）：

```bash
python3 scripts/dev/sync_e2e_env_to_web.py
```

然后用 `pnpm dev` 启动 Web（默认 3102）。

## 每日自动验证

- CI：`.github/workflows/daily-real-user-e2e.yml`
- 本地（WSL）：`bash scripts/dev/install_daily_real_user_e2e_cron.sh`

