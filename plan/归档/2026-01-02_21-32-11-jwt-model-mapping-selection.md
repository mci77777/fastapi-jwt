---
mode: plan
task: JWT测试：映射模型选择与端点模型校验修复
created_at: "2026-01-02T21:32:11+08:00"
complexity: medium
---

# Plan: JWT测试：映射模型选择与端点模型校验修复

## Goal
- 在 `/ai/jwt` 提供“映射模型（model-groups）”可选项，并确保选择后能跑通 JWT → 创建消息 → SSE 对话全链路。

## Scope
- In: 前端 JWT 测试页模型来源/选择；后端模型映射解析与端点 model_list 校验策略；docker 重建与重启；SQLite 重置与验证。
- Out: 完整排障/修复所有 502（仅保证本次改动不会因模型映射导致对话失败，并提供可观测错误输出）。

## Assumptions / Dependencies
- 后端已可访问 `GET /api/v1/llm/model-groups`，且存在至少一条启用映射（`is_active=true`）。
- 端点 `endpoint.model` 可能配置为映射 key（如 `global:global`），需要在后端兜底解析。
- FRP/Cloudflare/上游模型供应商偶发不稳定是外部因素，本次只做最小防护与可观测。

## Phases
1. 前端：在 JWT 测试页增加“模型来源”选项（映射模型 / 端点配置 / 供应商列表），并默认使用映射模型。
2. 后端：统一模型解析（包含 endpoint fallback model），并放宽“映射模型”在指定端点下的 `model_list` 校验。
3. 部署：`docker compose up -d --build app` 重建并重启；重置 SQLite；跑健康检查与手工 E2E。

## Tests & Verification
- 后端启动/健康：`curl http://localhost:9999/api/v1/healthz` 返回 200。
- JWT 页：选择一个映射模型（如 `global:global`）→ 发送消息 → SSE 收到 `completed`。
- 回归：供应商模型列表仍可手动展开（排障用），但不再作为默认可选项。

## Issue CSV
- Path: issues/2026-01-02_21-32-11-jwt-model-mapping-selection.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `functions.exec_command`: 检索/构建/重启 docker/健康检查。
- `functions.apply_patch`: 最小改动修改前后端文件。

## Acceptance Checklist
- [ ] `/ai/jwt` 可选择“映射模型（model-groups）”，并将映射 key 作为 `model` 发送。
- [ ] 后端能把映射 key 解析为真实上游模型，并用于对话调用。
- [ ] 指定 endpoint 时，映射模型不会因 `model_list` 不包含而被错误拦截。
- [ ] `docker compose up -d --build app` 成功，健康检查通过。

## Risks / Blockers
- 上游 `/v1/models` 返回值不是可用 model id（例如返回供应商名），仅用于排障，不作为默认 SSOT。
- 外部网络/FRP 不稳定可能导致 502；需要用 request_id + 统一错误体定位。

## Rollback / Recovery
- `git revert <commit>` 回滚本次提交；`docker compose up -d --build app` 重新部署。
- 如需恢复旧库：备份/替换 `data/db.sqlite3`（本次会按要求重置）。

## Checkpoints
- Commit after: Phase 2（前后端改动完成后合并到 main）。

## References
- `web/src/views/test/real-user-sse.vue`
- `app/services/ai_service.py`
- `app/api/v1/llm_mappings.py`
