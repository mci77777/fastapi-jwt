---
mode: plan
task: Dashboard 主体布局重构 + 统计/监控/日志/SQLite 开关
created_at: "2026-01-06T15:58:02+08:00"
complexity: complex
---

# Plan: Dashboard 主体布局重构 + 统计/监控/日志/SQLite 开关

## Goal
- Dashboard 作为“控制中枢”：AI 供应商、模型映射、Prompt 选择位于主体区可直接操作/直达
- 所有展示数据可追溯且准确：禁止 mock、禁止“无数据但恒 0”的误导状态
- 系统日志/请求日志体验可用：可切换、可查看单次请求完整 rawlog、可按需写入 SQLite 并可控保留策略

## Scope
- In:
  - 前端：重构 Dashboard 布局，把核心配置（AI 供应商/模型映射/Prompt）移动到主体区
  - 前端：修正用户活跃度、服务器负载、API 监控的数据源与解析逻辑（以服务端 SSOT 为准）
  - 前端：日志卡片支持系统日志 + 请求日志切换；单条请求 rawlog 详情展示/复制
  - 后端：增加请求 rawlog 持久化到 SQLite 的可选能力（开关、保留/清理、最小查询接口）
- Out:
  - 不引入新的可观测平台/链路追踪系统（保持最小闭环，避免超纲）
  - 不重做全站 RBAC/菜单系统（仅调整 Dashboard 呈现与入口）

## Assumptions / Dependencies
- 组件可复用（避免重复实现）：`web/src/components/dashboard/ModelSwitcher.vue`、`web/src/components/dashboard/PromptSelector.vue`、`web/src/components/dashboard/ModelMappingCard.vue`、`web/src/components/dashboard/EndpointConnectivityCard.vue`、`web/src/components/dashboard/LogWindow.vue`
- 后端接口 SSOT（避免前端自检造假）：`/api/v1/stats/dashboard`、`/api/v1/metrics`、`/api/v1/llm/monitor/status`、`/api/v1/logs/recent`
- MCP 使用 Windows SSOT 路径：`D:/GymBro/vue-fastapi-admin`

## Phases
1. 复盘近期提交 + 同义实现扫描（SSOT）
   - 用 `git log/show` 复盘 Dashboard 相关提交影响面（重点：`8353657`、`5f9a931`）
   - 用 `feedback:codebase-retrieval` 扫描：Dashboard 指标/监控/日志的等价实现与权威数据源，收敛到单一 SSOT
2. Dashboard 主体区重排（菜单入口仍保留，但不作为唯一入口）
   - 将 AI 供应商、模型映射、Prompt 选择控件从侧栏/次要区移动到主体区
   - 主体区提供“关键控制 + 直达入口”，避免嵌入全功能页面造成复杂度
3. 指标/监控修复（去伪存真）
   - 用户活跃度：无真实数据时显示“未采集/未配置”状态与启用路径，不以 0 误导
   - 服务器负载：统一使用 `/api/v1/metrics` 解析；移除前端“探测前 5 个端点”这种不可靠做法
   - API 监控：以 `EndpointMonitor`/`/api/v1/llm/monitor/status` + `ai_endpoints.status` 为准，展示一致口径
4. 日志体验完善 + SQLite 可选持久化（端到端闭环）
   - 系统日志：展示结构与筛选逻辑校正（不破坏现有 `/logs/recent`）
   - 请求日志：支持查看单条请求 request/response raw（含 request_id、错误），提供可复制导出
   - 后端：新增/调整请求日志写入 SQLite 的开关与保留策略；提供最小查询/清理接口

## Tests & Verification
- 前端：`cd web && pnpm lint`；`cd web && pnpm build`
- 后端：`make test`（如需先快检可用 `make lint`）
- 冒烟：
  - 启动后访问 Dashboard：主体区可操作 AI 供应商/模型映射/Prompt；不存在 mock
  - 指标：`GET /api/v1/metrics` 可解析关键指标，Dashboard 展示与其一致
  - 监控：触发/等待一次探针后，Dashboard API 端点健康与后端状态一致
  - 日志：请求日志开关开启后，触发 3 个接口能看到单条 rawlog；关闭后不再新增
  - SQLite：开启落库后重启仍可查询到历史请求日志（或明确保留策略后自动清理）

## Issue CSV
- Path: issues/2026-01-06_15-58-02-dashboard-ui-refactor-main-controls-logs-sqlite.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描、关键符号定位、调用链确认（SSOT）
- `sequential-thinking:sequentialthinking`：关键决策校验（YAGNI→SSOT→KISS）
- `git log/show`：基于近期提交 messageID 复盘变更与回归风险
- `rg`：限域检索辅助；`pnpm/make`：构建与测试验证

## Acceptance Checklist
- [ ] Dashboard 主体区可直接访问/操作：AI 供应商、模型映射、Prompt 选择（不再依赖侧边菜单）
- [ ] 用户活跃度无 mock；无数据时明确提示并给出启用路径，不误报为 0
- [ ] 服务器负载与 API 监控数据源准确：以 `/api/v1/metrics` + `/api/v1/llm/monitor/status` 为准
- [ ] 日志 UI 可切换，支持查看单条请求完整 rawlog（含 request_id、request/response、错误）
- [ ] 请求日志写入 SQLite 可配置（默认关闭），并具备最小保留/清理策略
- [ ] `cd web && pnpm build` 与 `make test` 通过

## Risks / Blockers
- 用户活跃度“时间序列”口径可能与当前后端实现不一致：需统一 UI 口径或补齐序列接口
- rawlog 体积与敏感信息：必须脱敏/截断/配额，否则落库存在风险
- SQLite 写入频率：需限流与保留策略，避免拖慢主流程

## Rollback / Recovery
- 分阶段单提交：任一阶段可 `git revert` 回滚
- SQLite 落库默认关闭；出现问题可先关闭开关退回到仅内存/仅展示模式

## Checkpoints
- Commit after: 同义扫描 + SSOT 决策落地
- Commit after: Dashboard 主体布局与指标/监控修正完成
- Commit after: 日志详情 + SQLite 可选持久化完成并通过构建/测试

## References
- `docs/dashboard-refactor/ARCHITECTURE_OVERVIEW.md`
- `web/src/views/dashboard/index.vue`
- `web/src/components/dashboard/ServerLoadCard.vue`
- `web/src/components/dashboard/EndpointConnectivityCard.vue`
- `web/src/components/dashboard/LogWindow.vue`
- `app/api/v1/dashboard.py`
- `app/services/metrics_collector.py`
- `app/services/log_collector.py`
- `app/db/sqlite_manager.py`
- 近期提交：`8353657 feat(dashboard): add request raw logs tab`；`5f9a931 fix: dashboard 422 + perplexity models 404`
