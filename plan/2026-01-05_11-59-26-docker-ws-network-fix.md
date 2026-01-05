---
mode: plan
task: docker 网络冲突与 WebSocket 反代修复
created_at: "2026-01-05T11:59:26+08:00"
complexity: complex
---

# Plan: docker 网络冲突与 WebSocket 反代修复

## Goal
- Docker 内可访问宿主/Windows 本地服务；Dashboard WebSocket 可连接；无敏感 token 日志；微E2E/构建通过

## Scope
- In: docker-compose 网络子网；Nginx WebSocket 反代；移除 WS token 调试日志；补齐缺失 GET /llm/models/{id}
- Out: 供应商/映射全量重构（已在既有 SSOT 链路内迭代）

## Assumptions / Dependencies
- 现网 docker network 使用 `172.19.0.0/16` 与 WSL/Windows host `172.19.32.1` 冲突导致容器访问超时
- 部署使用 `deploy/web.conf` 的 Nginx 作为 80 入口

## Phases
1. 固化计划与 Issues CSV（可回滚）
2. 修复 Docker 网络冲突 + 本地连通性验证（容器内 curl 不再 timeout）
3. 修复 Nginx WebSocket 反代 + 清理 WS 调试日志（禁止泄露 token）
4. 补齐 API 契约（GET /api/v1/llm/models/{id}）并对齐前端/旧产物兼容
5. 跑微E2E/构建（`make test` + `pnpm build`）并产出部署指引

## Tests & Verification
- `make test`（含微E2E：映射/持久化/URL rewrite）
- `cd web && pnpm build`
- `docker exec vue-fastapi-admin curl -sv --max-time 3 http://172.19.32.1:8317/`（仅验证可连通，不输出密钥）
- `nginx -t`（容器内）

## Issue CSV
- Path: issues/2026-01-05_11-59-26-docker-ws-network-fix.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- functions.exec_command（构建/验证/容器探针）
- functions.apply_patch（最小变更）
- mcp__feedback__codebase-retrieval（同义实现扫描/精准定位，必要时）

## Acceptance Checklist
- [ ] 容器内访问 `172.19.32.1:8317` 不再超时
- [ ] `wss://*/api/v1/ws/dashboard` 可握手并稳定推送
- [ ] 后端不记录 token（含前缀）到日志/文件
- [ ] 补齐 GET `/api/v1/llm/models/{id}`，避免前端/旧产物 404
- [ ] `make test` + `pnpm build` 通过

## Risks / Blockers
- 修改 docker 网络子网需要重建网络（`docker compose down` 后再 up），短暂停机

## Rollback / Recovery
- `git revert <commit>`
- `docker compose down && docker compose up -d --build`（重建网络/容器）

## Checkpoints
- Commit after: Docker 网络修复；WebSocket/Nginx 修复；API 补齐与测试通过

## References
- `docker-compose.yml`
- `deploy/web.conf`
- `app/api/v1/dashboard.py`
- `app/api/v1/llm_models.py`
- `tests/test_persistence_delete_micro_e2e.py`
