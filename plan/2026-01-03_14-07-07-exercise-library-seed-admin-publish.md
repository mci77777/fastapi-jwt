---
mode: plan
task: Exercise Library 种子管理（Admin 发布 + App 下发）
created_at: "2026-01-03T14:07:07+08:00"
complexity: medium
---

# Plan: Exercise Library 种子管理（Admin 发布 + App 下发）

## Goal
- 管理端可发布新版本官方动作库种子；App 端通过 `/api/v1/exercise/library/{meta,updates,full}` 稳定同步（增量不可得自动触发客户端回退全量）。

## Scope
- In:
  - 以“现状梳理后的结构”为基准（契约 SSOT：`tests/test_exercise_library_contracts.py` + `docs/后端方案/动作库-种子数据库scheme-现状.md`）。
  - 实装“种子管理/发布”入口：仅后端 `admin` 用户可用（鉴权 + 审计/错误处理）。
  - 下发端点保持只读、允许匿名 GET（与 `PolicyGate` 现有白名单一致），并可被限流保护。
- Out:
  - 不做管理后台 UI；不做推送服务本身（线上推送由外部系统触发，后端仅提供版本化数据与发布入口）。

## Assumptions / Dependencies
- App 同步仍以“拉取式”为主（每日一次检测/手动刷新），线上推送仅用于触发 App 更快刷新或提示用户。
- 版本 SSOT 为后端 `sqlite.exercise_library_snapshots`（单调递增），读路径统一走同一服务层。

## Phases
1. 冻结契约与 SSOT 边界：以现状契约为准，明确 meta/updates/full 字段与错误语义。
2. Admin 发布入口：新增/完善 `POST /api/v1/admin/exercise/library/publish`（仅 admin 可用），支持上传 seed JSON（或引用路径）并落库为新版本。
3. 验证闭环：补齐/加固合约测试与冒烟脚本；确保发布后版本推进、增量/回退路径可复现。

## Tests & Verification
- 契约测试：`pytest -q tests/test_exercise_library_contracts.py`。
- 冒烟：
  - 发布新种子后 `GET /api/v1/exercise/library/meta` 的 `version` 递增。
  - `GET /api/v1/exercise/library/full` 返回非空且字段可解析。
  - `GET /api/v1/exercise/library/updates?from=<old>&to=<new>` 成功返回或明确失败以触发客户端回退。
- 鉴权：匿名用户无法调用 publish；admin 用户可调用 publish。

## Issue CSV
- Path: issues/2026-01-03_14-07-07-exercise-library-seed-admin-publish.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描与引用定位（保证 SSOT、避免影子状态）。
- `functions:exec_command`：本地检索/运行测试/冒烟。
- `functions:apply_patch`：最小变更落盘。

## Acceptance Checklist
- [ ] `meta/updates/full` 对外契约以“现状梳理”版本为准且稳定（字段名/类型/camelCase）。
- [ ] 发布入口仅 admin 可用，发布后快照版本单调递增并可被下发端点读到。
- [ ] 增量不可得时返回可预期错误，客户端可回退 `full`（不会因错误结构导致崩溃）。
- [ ] 测试通过且具备可回放的发布/回归步骤。

## Risks / Blockers
- “后端须知”与“现状梳理”文档可能存在字段不一致，需要明确以现状契约为 SSOT，避免双契约漂移。
- seed 内容若与 `ExerciseDto` 严格校验不一致（`extra=forbid`），发布会失败，需要定义校验与迁移策略。

## Rollback / Recovery
- 回滚发布：保留旧 `version` 快照；必要时将 `meta` 指向上一个版本（或删除最新快照并重启服务）。
- 回滚代码：保持只新增/兼容变更，确保单次提交可撤回。

## Checkpoints
- Commit after: Phase 1（契约冻结与测试基线）
- Commit after: Phase 2（publish 入口实装）
- Commit after: Phase 3（验证闭环）

## References
- docs/后端方案/动作库-种子数据库scheme-现状.md
- docs/后端方案/动作库-种子数据库scheme-后端须知.md
- app/api/v1/exercise_library.py
- app/services/exercise_library_service.py
- scripts/publish_exercise_seed.py
- tests/test_exercise_library_contracts.py
