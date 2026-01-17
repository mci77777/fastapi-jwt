---
mode: plan
task: 模型管理：E2E 记录页 + 可配置频率 + Dashboard 健康点
created_at: "2026-01-16T16:31:05+08:00"
complexity: complex
---

# Plan: 模型管理：E2E 记录页 + 可配置频率 + Dashboard 健康点

## Goal
- 新增一个独立页面承载“映射模型对话 E2E”的运行记录与趋势（健康点/矩阵），入口放在“模型管理”菜单下。
- 支持可配置执行频率（自定义：3 小时~24 小时），并与调度守门脚本判定一致。
- Dashboard 仅展示映射模型“最新实际状态”（健康点），历史记录只在新页面查看。

## Scope
- In:
  - 后端：扩展 `dashboard_config`（新增 E2E 频率字段），新增 E2E 运行记录查询 API（分页/时间窗/用户类型）。
  - 调度：更新 `scripts/monitoring/daily_mapped_model_schedule_check.py` 支持按“间隔小时”判定 due。
  - 前端：新增“E2E 记录”页面（健康点矩阵 + 筛选），Dashboard 卡片仅保留健康点展示。
  - 测试：补齐后端 API 与 schedule gate 的单测/集成测。
- Out:
  - 后端内置定时任务/worker（仍由 cron/CI 触发脚本）。
  - 告警通知（邮件/IM）、多环境聚合、复杂报表导出。

## Assumptions / Dependencies
- E2E 执行仍由外部触发（cron/CI），后端仅提供配置与查询展示。
- E2E 脚本与后端服务读取/写入同一份 `SQLITE_DB_PATH`（否则页面无法显示最新记录）。
- XML 合规性以 `docs/ai预期响应结构.md`（ThinkingML v4.5）为 SSOT。

## Phases
1. 现状/同义扫描：确认现有 E2E 落库表、Dashboard 卡片与接口、配置落点（SSOT）与可复用组件。
2. 后端与调度：
   - 扩展 `DashboardConfig`：新增 `e2e_interval_hours`（int，范围 3~24）。
   - 更新 `daily_mapped_model_schedule_check.py`：优先按 `e2e_interval_hours` 判定；未配置则回退 `e2e_daily_time`（兼容）。
   - 新增 `GET /stats/e2e-mapped-model-runs`：返回运行列表（分页/时间窗），包含每次 run 的 per-model 结果（用于矩阵/详情）。
3. 前端页面与 Dashboard 精简：
   - 新增页面（挂在“模型管理”）：支持用户类型、时间窗、模型筛选；以“行=模型、列=最近 N 次运行”渲染健康点矩阵，hover 展示原因/延迟。
   - 配置区：支持自定义 `e2e_interval_hours`（3~24），与现有 `/stats/config` 同接口保存。
   - Dashboard：仅展示最新状态健康点（不展示历史矩阵/复杂筛选）。
4. 验证与回滚：
   - 本地跑一次 E2E 写入 DB，确认新页面与 Dashboard 同步展示。
   - 文档补充“DB 路径一致性/cron 运行位置”说明。

## Tests & Verification
- 后端：`make test`（新增用例覆盖：配置字段校验、runs 列表 API、schedule gate interval 判定）。
- 前端：`pnpm -C web build`（确保新增页面可编译）。
- 人工验收：跑 `bash scripts/dev/run_daily_mapped_model_e2e.sh` 后刷新新页面与 Dashboard，健康点与落库一致。

## Issue CSV
- Path: issues/2026-01-16_16-31-05-e2e-run-records-page.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- feedback:codebase-retrieval：语义检索复用现有 E2E/配置/页面模式（同义实现扫描）。
- functions:shell_command：运行测试/构建（`make test`、`pnpm -C web build`、脚本 smoke）。
- functions:apply_patch：最小化改动落地（后端/前端/脚本）。

## Acceptance Checklist
- [ ] 新页面可查看映射模型 E2E 历史（健康点矩阵 + 明细 hover/展开）。
- [ ] 可配置 E2E 频率（自定义 3h~24h）并影响 schedule gate 判定。
- [ ] Dashboard 仅展示最新实际状态（健康点）。
- [ ] 后端测试通过（`make test`），前端可构建（`pnpm -C web build`）。
- [ ] 运行脚本写入后，页面展示与 DB 落库一致（同一 `SQLITE_DB_PATH`）。

## Risks / Blockers
- `SQLITE_DB_PATH` 不一致（Docker/宿主机/WSL）导致“脚本写了但页面读不到”。
- 现有前端 `pnpm -C web lint` 存在历史格式问题，验收以 `build` 通过为底线。

## Rollback / Recovery
- 回滚提交即可撤回页面与 API；cron 侧删除 `run_daily_mapped_model_e2e.sh` 任务行可立即停止自动跑。

## Checkpoints
- Commit after: Phase 2（后端+调度）
- Commit after: Phase 3（前端页面+Dashboard 精简）
- Commit after: Phase 4（测试与文档）

## References
- scripts/monitoring/daily_mapped_model_schedule_check.py
- scripts/monitoring/daily_mapped_model_jwt_e2e.py
- app/api/v1/dashboard.py
- web/src/components/dashboard/DailyE2EStatusCard.vue
- docs/ai预期响应结构.md
