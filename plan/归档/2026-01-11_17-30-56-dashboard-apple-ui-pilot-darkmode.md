---
mode: plan
task: Dashboard Apple 风格 UI 试点（兼容暗色模式）
created_at: "2026-01-11T17:30:56+08:00"
complexity: complex
---

# Plan: Dashboard Apple 风格 UI 试点（兼容暗色模式）

## Goal
- Dashboard 信息层级更清晰：概览（KPI）/观测（图表+健康+日志）/操作（快捷入口+系统状态）三段式，降低认知负担。
- 视觉更接近 Apple：克制配色、留白、排版层级清晰、材质与阴影轻量统一。
- 兼容暗色模式：随 `appStore.isDark` 自动切换，不影响其它页面现有主题。

## Scope
- In:
  - 重排 Dashboard 主页面结构与响应式断点：`web/src/views/dashboard/index.vue`
  - 统一 Dashboard 相关组件视觉与容器样式：`web/src/components/dashboard/StatsBanner.vue`、`web/src/components/dashboard/MonitorPanel.vue`、`web/src/components/dashboard/ControlCenter.vue`、`web/src/components/dashboard/ModelObservabilityCard.vue`
  - 增加 Dashboard 局部 tokens（light/dark）与最小样式基座（不改全站 tokens）：新建 `web/src/views/dashboard/dashboard-tokens.scss`（或同目录约定文件）
- Out:
  - 不改后端 API、指标口径与数据流（保持现有 SSOT）
  - 不做全站 Apple 化（仅 Dashboard 试点）
  - 不引入新的重依赖与复杂动效

## Assumptions / Dependencies
- 暗色模式开关由现有 `AppProvider` 控制（`appStore.isDark`），Dashboard 仅做“局部视觉适配”。
- Naive UI 组件色板以现有 `naiveThemeOverrides` 为基线；Dashboard 内优先用 CSS 变量做轻量覆写（避免全局污染）。
- 同义实现扫描：Dashboard 里如存在重复的“卡片/容器/玻璃态”实现，收敛到单一 SSOT（例如 `glass-panel` 样式）。
- MCP 使用 Windows SSOT 路径：`X:/project/vue-fastapi-admin`

## Phases
1. 信息架构与布局线框（不改功能）
   - 定义 3 区：Overview / Observability / Actions，并确定每区包含的现有组件与交互入口
   - 定义断点策略（≥1280 双列；≥960 单列双区；<960 单列顺序流）
2. 结构落地（最小改动）
   - 在 `DashboardIndex` 内完成 DOM 结构重排与布局样式（Grid + sticky/flow 取舍）
   - 保持现有事件/弹窗/拖拽持久化链路不变
3. Apple 风格与暗色适配收口
   - 为 Dashboard 引入局部 tokens（light/dark）：背景、卡片、边框、阴影、分隔线、文本层级
   - 统一 StatsBanner/MonitorPanel/ControlCenter/ModelObservabilityCard 的容器与标题层级
   - 校验暗色模式可读性与对比度，避免“白底组件”在暗色下刺眼

## Tests & Verification
- `cd web && pnpm build`
- `cd web && pnpm lint`（如项目启用）
- 本地启动：`./start-dev.ps1`，手动验收：
  - Dashboard 在 light/dark 下布局稳定、无溢出/抖动
  - 统计卡片、日志、表格、弹窗在暗色下可读
  - 快捷入口拖拽排序仍可保存与恢复

## Issue CSV
- Path: issues/2026-01-11_17-30-56-dashboard-apple-ui-pilot-darkmode.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描、关键样式/组件引用定位（SSOT）
- `functions:apply_patch`：最小范围修改页面与组件
- `functions:shell_command`：`pnpm build/lint` 与本地验证命令
- （可选）`context7:resolve-library-id` + `context7:get-library-docs`：核验 Naive UI 局部主题覆写方式

## Acceptance Checklist
- [ ] Dashboard 形成稳定三段结构（Overview/Observability/Actions），信息层级清晰
- [ ] Apple 风格在 Dashboard 内一致：背景、卡片、分隔、排版、按钮/交互统一
- [ ] 暗色模式可用：关键文本/图表/表格/弹窗对比度正确，无刺眼白底
- [ ] 现有功能不回归：WS/轮询降级、日志刷新、快捷入口拖拽持久化、各弹窗可用
- [ ] `cd web && pnpm build` 通过且无新增报错

## Risks / Blockers
- Naive UI 组件在暗色模式下的默认背景/边框与局部 tokens 冲突：需控制覆写范围（只在 Dashboard 容器内生效）。
- Dashboard 内部已有多套“玻璃态”样式：若不收敛会导致视觉割裂与维护成本上升。

## Rollback / Recovery
- 单提交或分阶段提交；任一阶段不满意可 `git revert <commit>` 回退。

## Checkpoints
- Commit after: Phase 2（结构完成可用）
- Commit after: Phase 3（视觉收口 + 构建通过）

## References
- `web/src/views/dashboard/index.vue`
- `web/src/components/dashboard/StatsBanner.vue`
- `web/src/components/dashboard/MonitorPanel.vue`
- `web/src/components/dashboard/ControlCenter.vue`
- `web/src/components/dashboard/ModelObservabilityCard.vue`
- `web/src/components/common/AppProvider.vue`
- `web/settings/theme.json`
