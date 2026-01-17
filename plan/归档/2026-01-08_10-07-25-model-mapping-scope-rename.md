---
mode: plan
task: "Model mapping: tenant->mapping + SQLite SSOT"
created_at: "2026-01-08T10:07:59+08:00"
complexity: complex
---

# Plan: Model mapping: tenant->mapping + SQLite SSOT

## Goal
- 消除“tenant=映射名”歧义；模型映射默认落库到 SQLite；前端映射页按“映射名+API+模型”清晰配置；E2E/pytest 全绿。

## Scope
- In:
  - 后端：`tenant` → `mapping` 语义更名（保留 legacy alias 兼容）；fallback 映射落 SQLite；一次性导入 legacy `model_mappings.json`
  - 前端：重构“模型映射”页面/卡片的文案与字段；支持选择 API 端点并保存到 `metadata.preferred_endpoint_id`
  - 回归：更新相关测试与文档；完成 E2E + pytest；提交后 docker 重建
- Out:
  - 不变更 `/messages` SSE 事件协议
  - 不新增 provider/adapter 类型
  - 不做与本需求无关的大重构

## Assumptions / Dependencies
- 允许保留 `tenant` 作为 legacy alias（读/写/解析兼容一段时间，避免存量 model key 直接断裂）。
- `SQLiteManager` 可新增表；运行态目录 `AI_RUNTIME_STORAGE_DIR` 可写入 migration marker。

## Phases
1. 后端：新增 `llm_model_mappings` 表；`ModelMappingService` 的 fallback 读写改为 SQLite；启动期一次性导入 legacy `model_mappings.json`（tenant→mapping）。
2. 前端：`scope_type=mapping` 作为“映射名”业务域；表单字段明确为“映射名(scope_key)+显示名(name)+选择 API(endpoint)+默认模型/候选模型”；保存后回显。
3. 回归：更新 tests 中 `tenant` 相关断言；跑 `pytest` + `local_mock_ai_conversation_e2e.py`；更新 docs；提交并 docker compose rebuild。

## Tests & Verification
- `PYTHONPATH=. .venv/bin/python -m pytest -q tests`
- `.venv/bin/python scripts/monitoring/local_mock_ai_conversation_e2e.py`
- （可选）`cd web && pnpm build`

## Issue CSV
- Path: issues/2026-01-08_10-07-25-model-mapping-scope-rename.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `functions.exec_command`：搜索/测试/构建
- `functions.apply_patch`：最小改动实现
- （可选）`mcp__feedback__codebase-retrieval`：语义定位重命名影响面

## Acceptance Checklist
- [ ] API/DB：`scope_type=mapping` 可 CRUD 并落 SQLite；legacy `tenant` 输入仍可解析
- [ ] UI：映射名/选择 API/选择模型/默认模型字段清晰；保存后刷新可见
- [ ] 回归：pytest + E2E 全通过
- [ ] 文档：`docs/features/model_management/implementation.md` 等口径更新
- [ ] 可回滚：单提交 `git revert` 可退

## Risks / Blockers
- 旧数据迁移：bucket/id 前缀兼容不当会导致白名单为空
- 前端依赖：构建环境可能不稳定（优先保证后端+E2E）

## Rollback / Recovery
- `git revert <commit>`；SQLite 新表保留不影响旧版本；必要时删除 migration marker 重新导入。

## Checkpoints
- Commit after: Phase 1（后端+迁移+测试通过）
- Commit after: Phase 2/3（前端+文档+最终回归）

## References
- `docs/sse/2026-01-07/CLOUD_TODO.csv`
- `app/services/model_mapping_service.py`
- `web/src/views/ai/model-suite/mapping/index.vue`
