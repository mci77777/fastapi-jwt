---
mode: plan
task: Dashboard 请求/响应 Raw 日志展示（双 Tab）
created_at: "2026-01-05T16:42:49+08:00"
complexity: medium
---

# Plan: Dashboard 请求/响应 Raw 日志展示（双 Tab）

## Goal
- Dashboard「日志」Card 支持双 Tab：`系统日志` + `请求日志`
- 开启开关后，前端可逐条记录并展示每次请求从 Request→Response 的 raw 内容（含失败场景），用于排障

## Scope
- In:
  - 前端：axios 拦截器捕获请求/响应 raw、Pinia 作为请求日志 SSOT、Dashboard 日志卡 UI 重构双 Tab
  - 安全：对敏感字段做默认脱敏（至少 Authorization / Cookie / Set-Cookie）
- Out:
  - 不改后端日志/存储结构与 API（除非明确要求“持久化到后端”）
  - 不覆盖非 axios（如 EventSource/SSE、原生 fetch）请求（除非明确要求）

## Assumptions / Dependencies
- 请求链路主要通过 `web/src/utils/http/interceptors.js`（axios）发出
- Dashboard 日志卡当前组件为 `web/src/components/dashboard/LogWindow.vue`
- Pinia 在 app 启动时已初始化，可用于跨模块写入/读取请求日志
- 详细请求日志默认关闭；开关状态落地 localStorage（或按需接入现有 Dashboard 配置）

## Phases
1. 现状与同义实现扫描（已有请求日志/调试面板/拦截器扩展点）
2. 追加请求日志 SSOT（Pinia store）+ axios 请求/响应采集与关联（request→response）
3. 重构 `LogWindow`：双 Tab + 请求日志展示区 + 开关/清空等最小操作

## Tests & Verification
- `cd web && npm run lint`
- `cd web && npm run build`
- 手动冒烟：Dashboard 打开“请求日志”开关 → 操作触发若干 API → 逐条出现 request/response raw；关闭开关后不再新增

## Issue CSV
- Path: issues/2026-01-05_16-42-49-dashboard-request-raw-logs-tabs.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `functions.exec_command`：`rg` 定位/同义扫描、运行 `npm` 构建校验
- `functions.apply_patch`：最小改动落地
- `functions.mcp__feedback__codebase-retrieval`：语义检索（同义实现扫描、关联调用点）

## Acceptance Checklist
- [ ] Dashboard 日志 Card 支持双 Tab 切换且不破坏现有系统日志能力（筛选/刷新/复制）
- [ ] 请求日志开关可控（默认关闭），开启后开始记录并展示
- [ ] 每条请求日志包含 request+response 的 raw（成功/失败都覆盖），并能按请求关联成一条记录
- [ ] 敏感信息默认脱敏，不在 UI 中明文暴露
- [ ] `npm run build` 通过

## Risks / Blockers
- 响应体过大/二进制/流式内容不适合 raw 展示（需截断/摘要策略）
- axios config/data 可能循环引用导致 stringify 失败（需安全序列化）
- 需求确认：是否要覆盖 EventSource/SSE/fetch；脱敏范围是否允许查看完整敏感头

## Rollback / Recovery
- 单次提交：回滚新增 store + 拦截器采集 + LogWindow tab 改动即可恢复原行为
- 开关默认关闭，出现问题可先关闭功能不影响主流程

## Checkpoints
- Commit after: 请求日志 store + 拦截器采集完成
- Commit after: LogWindow 双 Tab 与展示完成 + 构建通过

## References
- `web/src/components/dashboard/LogWindow.vue`
- `web/src/utils/http/interceptors.js`
- `web/src/views/dashboard/index.vue`
- `web/src/components/dashboard/MonitorPanel.vue`
