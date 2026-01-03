---
mode: plan
task: 动作库种子增量更新（JSON Patch 发布）
created_at: "2026-01-03T17:05:16+08:00"
complexity: medium
---

# Plan: 动作库种子增量更新（JSON Patch 发布）

## Goal
- 管理端支持用“增量 JSON”发布新版本（新增/删除/字段级更新），无需每次上传 full。
- 继续复用现有下发契约：`/api/v1/exercise/library/meta|updates|full`，App 增量失败仍可回退 full。
- 更新规则保持简单直接（KISS），不引入复杂 DSL。

## Scope
- In:
  - 后端：新增 admin-only Patch 发布端点；服务端合并后校验并发布新快照版本。
  - Dashboard：在“官方库种子发布”页面增加“增量更新”Tab（JSON 粘贴/上传 + 预览 + 发布）。
  - 测试：pytest 覆盖 patch 行为与权限门禁。
- Out:
  - 不做推送系统本身（只提供版本化数据源与发布能力）。
  - 不做复杂表单编辑器（先 JSON 驱动 + 预览）。

## Assumptions / Dependencies
- SSOT：`assets/exercise/exercise_official_seed.json`（ExerciseSeedData）与 `assets/exercise/exercise_schema.json`。
- 快照 SSOT：`sqlite.exercise_library_snapshots`（已存在）。
- admin SSOT：`app/api/v1/llm_common.py::is_dashboard_admin_user()`（或统一 `require_llm_admin`）。

## Phases
1. 定义 Patch JSON 契约（SSOT）
   - 建议结构：`{ baseVersion, added, updated, deleted, generatedAt? }`
   - `updated` 使用 `id` 匹配；仅覆盖提供的字段（未提供字段保持不变）。
   - 先合并再整体验证（最终对象必须满足 `ExerciseDto`/枚举）。
2. 后端实现
   - 新增 `POST /api/v1/admin/exercise/library/patch`（admin-only）。
   - 在 `ExerciseLibraryService` 增加 `apply_patch_and_publish(...)`：读取最新快照 → 应用 patch → 校验 → publish。
   - baseVersion 冲突：`baseVersion != currentVersion` 时返回 409（防并发覆盖）。
3. Dashboard 增量更新 Tab
   - 解析 JSON → 展示 added/updated/deleted 数量与样例预览 → 发布。
   - 权限：`v-permission="'post/api/v1/admin/exercise/library/patch'"`。
4. 文档与回归
   - 更新 `docs/后端方案/*` 与 `docs/task/2026-01-02_exercise-library-seed-sync.md`：补充 patch 示例与注意事项。
   - 验证：pytest + `cd web && npm run build`。

## Tests & Verification
- Patch 新增：added 1 条 → 版本 +1；`full` 含新 id；`updates` 的 `added` 含该条。
- Patch 更新（字段级）：只改 `description/updatedAt` → 其余字段不变；`updates.updated` 命中该 id。
- Patch 删除：deleted 指定 id → `full` 不含该 id；`updates.deleted` 含该 id。
- 冲突：baseVersion 过期 → 409 且版本不变化。
- 权限：非 admin 调用 patch → 403。

## Issue CSV
- Path: issues/2026-01-03_17-05-16-exercise-seed-incremental-patch.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描、调用链定位。
- `functions:apply_patch`：最小改动落盘。
- `functions:exec_command`：pytest / web build / 冒烟。

## Acceptance Checklist
- [ ] Patch 支持 added/updated/deleted，发布新版本快照（version 单调递增）。
- [ ] updated 支持“只填要改字段”，未填字段保持不变；服务端合并后强校验。
- [ ] baseVersion 冲突检测可用（409）。
- [ ] Dashboard 可预览并发布 patch；权限控制正确。
- [ ] 后端测试与前端构建通过，可部署。

## Risks / Blockers
- 字段级更新可能造成最终对象缺少必填/枚举非法：必须“合并后整体验证”，失败即拒绝发布。

## Rollback / Recovery
- 回滚后端：下线 patch 端点；仍可使用 full 发布。
- 回滚前端：隐藏增量更新 Tab。

## Checkpoints
- Commit after: 后端 patch service + API + pytest
- Commit after: Dashboard patch Tab + 前端 build + 文档

## References
- assets/exercise/exercise_official_seed.json
- app/services/exercise_library_service.py
- app/api/v1/admin_exercise_library.py
- web/src/views/exercise/library/seed/index.vue
