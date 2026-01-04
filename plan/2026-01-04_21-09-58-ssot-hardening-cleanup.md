---
mode: plan
task: SSOT 最终清理与硬化（Endpoints→Mapping→Models→Messages/SSE）
created_at: "2026-01-04T21:09:58+08:00"
complexity: complex
---

# Plan: SSOT 最终清理与硬化（Endpoints→Mapping→Models→Messages/SSE）

## Goal
- 固化唯一链路：自定义供应商配置（endpoints）→ 模型映射（mapping）→ 对外 models SSOT（`data[].name`）→ messages+SSE。
- 清除/封死任何“绕过 mapping 直连供应商”的调用点与配置入口（含 JWT 测试/脚本/后台任务）。
- 文档/路由/菜单与现状一致，不再出现“模型目录/ai catalog”歧义。

## Scope
- In:
  - 后端：供应商调用点总审计、SSOT 强制、持久化/删除防回弹、API 契约校验与测试兜底。
  - 前端：AI 相关导航/路由/页面文案与入口收敛到 mapping 为主，endpoints 仅 admin 管理。
  - 文档：dashboard-refactor/README/issue CSV 中的残留术语与旧入口统一修正。
- Out:
  - 不新增供应商协议能力（只收敛现有链路与契约）。
  - 不做无关模块重构。

## Assumptions / Dependencies
- SQLite + volume 为 SSOT 落盘；生产环境默认禁用 test endpoints（仅 `ALLOW_TEST_AI_ENDPOINTS=true` 且 admin 才可用）。
- App 只使用映射名（`model=name`）作为业务 key；后端负责解析到真实供应商 endpoint+model。

## Phases
1. 同义实现扫描：全仓检索直连供应商/旧路由/旧文案/旧测试入口，更新调用点清单。
2. SSOT 强制：所有写入/调用统一走 mapping-resolve；JWT/测试/脚本只允许 SSOT key。
3. 持久化与删除硬化：删除后不回弹、无自动 seed 复活；补齐微 E2E 覆盖“重启+删除+不复活”。
4. 前端入口收敛：移除残留“模型目录”概念；仅保留必要路由别名（不做 301/302）。
5. 文档/部署验收：更新 docs；`make test`/`pnpm build`/Docker 健康检查。

## Tests & Verification
- 后端：`make test`（含微 E2E：持久化+删除+重启不回弹）。
- 前端：`cd web && pnpm build`。
- Docker：`docker compose -f docker-compose.yml up -d --build app` + `GET /api/v1/healthz`=200。

## Issue CSV
- Path: issues/2026-01-04_21-09-58-ssot-hardening-cleanup.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `mcp__feedback__codebase-retrieval`：同义扫描/引用定位
- `functions.exec_command`：测试/构建/Docker/探针
- `functions.apply_patch`：最小化修改与可回滚变更

## Acceptance Checklist
- [ ] 项目内不存在绕过 mapping 的供应商直连调用点（含 JWT/测试/脚本）
- [ ] 对外 models 唯一 SSOT：`data[].name`（映射名）
- [ ] 删除可用且不回弹；重启/重建容器配置不丢
- [ ] `/ai/catalog` 不再形成歧义（仅别名或彻底移除）
- [ ] `make test` + `pnpm build` + Docker 健康检查全通过

## Risks / Blockers
- 历史数据迁移导致“看似丢配置”（需一次性迁移标记与只读兼容）。
- 旧文档/旧入口导致误操作（需同步清理）。

## Rollback / Recovery
- 每阶段独立提交，可 `git revert <sha>` 回滚；回滚后 `docker compose -f docker-compose.yml up -d --build app`。

## Checkpoints
- Commit after: Phase 2 / Phase 3 / Phase 4 / Phase 5

## References
- `docs/dashboard-refactor/AI_SUPPLIER_SSOT_CALLPOINTS.md`
- `app/services/ai_config_service.py`
- `app/services/model_mapping_service.py`
- `app/api/v1/llm_models.py`
- `app/api/v1/messages.py`
- `web/src/views/system/ai/index.vue`
- `web/src/views/ai/model-suite/mapping/index.vue`
