---
mode: plan
task: 供应商配置→模型映射SSOT→JWT&Models 统一闭环与持久化治理
created_at: "2026-01-04T18:33:18+08:00"
complexity: complex
---

# Plan: 供应商配置→模型映射SSOT→JWT&Models 统一闭环与持久化治理

## Goal
- 强制唯一链路：自定义供应商配置（endpoints）→ 模型映射（mapping）→ 对外提供 JWT&models（SSOT）。
- 彻底消除“JWT/测试/脚本/后台”绕过 mapping 直连供应商的调用点。
- 修复持久化与删除：配置重启不丢、可删除且不回弹、避免无限生成测试模型。
- 前端归并入口：`/ai/catalog` 作为 AI 页 Tab 的别名（无歧义）。
- `GET /api/v1/llm/models/check-all` 不再超时：改为 202 触发后台刷新 + UI 可观测。

## Scope
- In:
  - 全面盘点并收敛供应商调用点（base_url/api_key/model 的直接透传）。
  - 统一 SSOT：App/JWT/业务只消费“映射后的 models”（业务 key + default_model + candidates）。
  - endpoints 列表仅管理端可见/可写（admin gate），禁止普通 Bearer 误用。
  - 修复持久化：endpoints/mapping/blocked/runtime/backups 的落盘位置与 Docker volume 对齐。
  - 修复删除：模型/映射/目录可删除、删除后不被启动/探针自动重建。
  - 前端 AI 供应商页面简化与优化（仅保留必要信息与动作，去除歧义入口）。
- Out:
  - 不做供应商协议全覆盖（仅保证 OpenAI-compatible 最小集 + 现有供应商接入不绕过 mapping）。
  - 不做无关 UI 大改（除非为 SSOT/持久化/删除修复所必需）。

## Assumptions / Dependencies
- SSOT 选型：A）SQLite(volume) 为主 + Supabase 仅可选同步层（运行时不依赖 Supabase）。
- App 业务模型 key = mapping 的 `scope_key`（如 `xai/deepseek/gpt-5`）；legacy `scope_type:scope_key` 仅兼容读路径。
- `check-all` 接口采纳：202 立即返回 + 后台探针刷新（前端轮询/刷新状态）。
- `/ai/catalog` 仅做路由别名（不做 301/302）。

## Phases
1. 现状审计：供应商调用点/影子状态/持久化落点/自动 seed 全清单
2. SSOT 合同落地：只暴露 mapped models；禁止 JWT/测试/脚本直连 endpoints
3. 持久化与删除治理：落盘统一到 volume；删除不回弹；清理测试模型泛滥
4. `check-all` 超时修复：异步触发 + 并发控制 + 可观测状态
5. 前端重构：`/ai/catalog` 归并 AI Tab；AI 供应商页面简化与权限边界一致
6. 验证与上线：微E2E + 全量回归 + Docker 健康检查；提供回滚路径

## Tests & Verification
- 后端：`make test`（必须全绿、无真实外网调用）。
- 前端：`cd web && pnpm build`。
- Docker：`docker compose -f docker-compose.yml up -d --build app` + `GET /api/v1/healthz`=200。
- 新增微E2E：持久化（重启后仍在）、删除（删除后不回弹）、check-all（快速返回且最终状态可见）。

## Issue CSV
- Path: issues/2026-01-04_18-33-18-api-suppliers-mapping-ssot-cleanup.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `mcp__feedback__codebase-retrieval`：语义扫描调用点/同义实现/影子状态
- `functions.exec_command`：跑测试/构建/Docker/探针
- `functions.apply_patch`：最小化重构与可回滚变更
- 备注：仓库缺少 `docs/mcp-tools.md`，后续可补齐工具目录（不阻塞本计划）。

## Acceptance Checklist
- [ ] 全项目只有 mapping→resolved 才能触达供应商；JWT/业务/测试不再直连 endpoints
- [ ] App/JWT/业务仅消费 mapped models（业务 key）作为 SSOT
- [ ] endpoints/mapping/blocked/runtime 可持久化（容器重建/重启不丢）
- [ ] 删除可用：能删、删干净、不回弹、不自动重建
- [ ] `check-all` 202 立即返回且不超时；UI 可看到刷新后的状态
- [ ] `/ai/catalog` 作为 AI Tab 别名且无歧义；AI 供应商页面简化完成
- [ ] `make test` + `pnpm build` + Docker 健康检查通过

## Risks / Blockers
- 存量数据/旧路径迁移不当会导致“看似丢配置”，需做兼容读取与迁移策略。
- 历史脚本/测试依赖 endpoints 视图或 legacy id，需明确兼容期与禁写策略。

## Rollback / Recovery
- 分阶段提交：每阶段可 `git revert` 单独回滚；Docker 侧重新 `docker compose up -d --build app`。
- 保留兼容开关：旧结构只读/别名，不允许继续写入旧路径。

## Checkpoints
- Commit after: Phase 2（SSOT 合同落地）
- Commit after: Phase 3（持久化/删除治理）
- Commit after: Phase 5（前端路由与页面收敛）
- Commit after: Phase 6（全量回归通过）

## References
- 后端：`app/services/ai_service.py`、`app/services/ai_config_service.py`、`app/services/model_mapping_service.py`、`app/api/v1/llm_models.py`、`app/api/v1/messages.py`
- 前端：`web/src/router/*`、`web/src/views/ai/*`（以仓库实际结构为准）
- 部署：`docker-compose.yml`
