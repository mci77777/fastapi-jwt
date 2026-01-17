---
mode: plan
task: Dashboard 登录/WS/真实用户E2E SSOT 收敛
created_at: "2026-01-02T10:34:17+08:00"
complexity: complex
---

# Plan: Dashboard 登录/WS/真实用户E2E SSOT 收敛

## Goal
- 本地 Docker（3101/9999）与 dev（3102/9999）登录/主页卡片/WS 更新一致、可用，错误可用 request_id 对账
- 真实用户 E2E（创建用户→登录→/messages→SSE）可本地运行，并可通过 cron 每日跑一次

## Scope
- In:
  - Web：WS URL 生成与错误展示（含 request_id）
  - Dev proxy：支持 WS 代理
  - E2E：run_local_real_user_e2e.sh 环境加载与闭环输出
  - Docker：提供“重建/重启”一键脚本，回到可登录的默认状态
- Out:
  - App 端（Android/Kotlin）链路与构建
  - 生产云端部署策略调整

## Assumptions / Dependencies
- `.env` 已包含 Supabase 真实配置（含 `SUPABASE_SERVICE_ROLE_KEY` / `SUPABASE_JWT_SECRET`），且不会被打印到日志
- 本地 Docker 启动以 `scripts/dev/docker_local_up.sh` 为 SSOT

## Phases
1. Web/Dashboard：收敛 WS 连接方式与错误可观测（request_id）
2. E2E：补齐环境加载与每日运行脚本，确保“真实用户注册/登录/对话/SSE”闭环
3. Docker：提供一键重建脚本并验证默认 admin 可登录/可改密

## Tests & Verification
- Docker：`bash scripts/dev/docker_local_reset.sh` 后，`POST /api/v1/base/access_token`（admin/123456）成功
- Dashboard：主页 WS 能持续更新（不再固定 9999 端口），并在错误提示中展示 request_id
- E2E：`bash scripts/dev/run_local_real_user_e2e.sh` 返回 exit=0 且产出 trace JSON

## Issue CSV
- Path: issues/2026-01-02_10-33-46-dashboard-ws-e2e-ssot.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `rg`：同义实现扫描与定位
- `apply_patch`：最小变更写入
- `docker compose`：本地启动/重建验证
- `curl`：接口探针

## Acceptance Checklist
- [ ] Docker 本地端口 SSOT：Web=3101、dev=3102；登录/主页卡片/WS 行为一致
- [ ] Web 错误展示包含 request_id（来自 `X-Request-Id` header 或错误 JSON）
- [ ] 真实用户 E2E：支持自动创建用户并输出 trace（含 request_id），可由 cron 每日运行
- [ ] 变更可回滚（单分支单提交合并 main）

## Risks / Blockers
- Supabase 账号/策略变更可能导致真实用户注册/登录失败（需在 trace 中保留 request_id 便于定位）

## Rollback / Recovery
- `git revert <commit>` 回退；Docker 侧可删除 `db.sqlite3` 并重新 `docker_local_up.sh`

## Checkpoints
- Commit after: 完成 Web/WS + E2E + Docker 脚本验证

## References
- `scripts/dev/docker_local_up.sh`
- `scripts/dev/run_local_real_user_e2e.sh`
- `web/src/api/dashboard.js`
