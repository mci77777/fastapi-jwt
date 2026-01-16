---
mode: plan
task: AI 映射模型本地导出 + Supabase 同步（表对齐）
created_at: "2026-01-16T16:21:05+08:00"
complexity: medium
---

# Plan: AI 映射模型本地导出 + Supabase 同步（表对齐）

## Goal
- 在 https://web.gymbro.cloud/ai 的“模型映射”页增加：
  - 导出本地 JSON（备份/迁移/回放）
  - 同步到 Supabase（写入 `public.model_mappings`）
- 保持 SSOT：运行态仍以本地 SQLite(`llm_model_mappings`) + Prompt `tools_json` 为准；Supabase 仅作可选同步层，不影响运行。

## Scope
- In:
  - 前端：映射页新增“导出/同步”按钮与交互；复用现有 `/api/v1/llm/model-groups/sync-to-supabase`
  - 后端：补齐 Supabase 表 `model_mappings` 的建表脚本与 RLS；必要时增强同步返回值与错误体稳定性
  - 文档：更新 Supabase ownership/naming SSOT（将 `model_mappings` 归入后端归属表）
- Out:
  - 不做从 Supabase 拉回映射（pull）与冲突合并
  - 不改动现有模型路由/解析策略（除非阻塞同步）

## Assumptions / Dependencies
- `ModelMappingService.sync_to_supabase()` 已存在并可用；Supabase 未配置时返回 skipped。
- Supabase 管理端可执行 SQL 脚本；`service_role` 可写入 `public.model_mappings`。
- “本地保存”优先实现为前端导出下载（不引入新后端接口）。

## Phases
1. 现状审计与同义实现扫描：确认 mapping 页/接口/脚本与文档缺口；确认 Supabase 侧是否已存在 `model_mappings`。
2. Supabase 表对齐：
   - 在 `scripts/deployment/sql/` 增加（或扩展现有）建表脚本：`public.model_mappings` + trigger + RLS + grant。
   - 更新 `docs/schemas/SUPABASE_SCHEMA_OWNERSHIP_AND_NAMING.md`（SSOT 清单）与 `docs/schemas/supabase.sql`（context）。
3. 前端能力：
   - mapping 页新增“导出本地 JSON”（导出当前 `store.mappings`；文件名带时间戳；不包含敏感字段）。
   - mapping 页新增“同步到 Supabase”（调用 `syncMappingsToSupabase()`；展示 `synced_count`/`skipped`）。
4. 验证闭环与回滚说明：
   - `make test`、`cd web && pnpm build`。
   - 手工：在 UI 点击同步；Supabase Dashboard 确认表中 upsert 生效；导出文件可读。

## Tests & Verification
- 后端：
  - Supabase 未配置：同步接口返回 `skipped:supabase_not_configured`（不 500）
  - Supabase 已配置：同步接口返回 `status=synced` 且 `synced_count>0`（有数据时）
- 前端：
  - 导出：下载 JSON，包含 `mappings` 数组与导出时间戳
  - 同步：按钮可重复执行，成功/失败提示明确
- 工程：
  - `make test`
  - `cd web && pnpm build`

## Issue CSV
- Path: `issues/2026-01-16_16-21-05-model-mapping-local-supabase-sync.csv`
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `mcp__feedback__codebase-retrieval`：同义实现扫描（mapping/sync/export）
- `functions.shell_command`：构建/测试/验证命令
- `functions.apply_patch`：实现阶段的最小改动（计划阶段仅生成 issue CSV）

## Acceptance Checklist
- [ ] mapping 页提供“导出本地 JSON”
- [ ] mapping 页提供“同步到 Supabase”
- [ ] Supabase 侧有可复现的 `model_mappings` 建表脚本（RLS/trigger/grant）
- [ ] 同步接口在 Supabase 未配置时可解释且不报 500
- [ ] `make test` 与 `cd web && pnpm build` 通过
- [ ] 回滚步骤清晰

## Risks / Blockers
- 误判“同一张表”：若必须复用 `ai_model` 承载映射，需要新增字段/约定（风险更高），需你确认。
- RLS/权限配置不当导致写入失败；需用 `service_role` 验证。
- 前端导出需避免包含任何密钥字段（当前映射不含，但仍需显式过滤）。

## Rollback / Recovery
- 回滚代码：`git revert <commit>`
- 回滚 Supabase：保留表不影响运行；如需删除需确认无依赖后再 `DROP TABLE`。

## Checkpoints
- Commit after: Supabase SQL + 文档对齐
- Commit after: 前端导出 + 同步按钮
- Commit after: 全量验证通过

## References
- `web/src/views/ai/model-suite/mapping/index.vue`
- `web/src/api/aiModelSuite.js`
- `app/api/v1/llm_mappings.py`
- `app/services/model_mapping_service.py`
- `app/services/ai_config_service.py`
- `scripts/deployment/sql/create_ai_config_tables.sql`
- `docs/features/model_management/implementation.md`
- https://web.gymbro.cloud/ai
