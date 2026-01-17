---
mode: plan
task: Dashboard 取消 AI 供应商显示，改为映射模型可用性与调用数据
created_at: "2026-01-11T14:19:40+08:00"
complexity: complex
---

# Plan: Dashboard 取消 AI 供应商显示，改为映射模型可用性与调用数据

## Goal
- Dashboard 首页取消“AI 供应商/端点连通性”相关展示（endpoint 维度）。
- 改为展示“映射模型”（mapped model 维度）的：
  - **可用性**（是否可路由 + 原因）
  - **用户调用数据**（按时间窗聚合）
- 端到端闭环：前端展示 → 后端聚合 → SQLite/现有统计表 → 可验证/可回滚。

## Scope
- In:
  - 后端新增/扩展 Dashboard 统计接口：提供映射模型列表、可用性与调用数据的聚合视图（供 Dashboard 首页与 WebSocket stats 推送复用）。
  - 前端 Dashboard：
    - 移除/替换 `EndpointConnectivityCard`（Dashboard 中间栏“Connectivity”）与 `ApiConnectivityModal`（Stats 点击弹窗）。
    - StatsBanner 的第 4 项从“API 连通性（供应商）”替换为“映射模型可用性”。
    - 新增或替换为映射模型卡片：展示 key、可用性、调用数据。
- Out:
  - 不删除 AI endpoint 管理与探针能力（`/system/ai` 仍保留）。
  - 不改变消息链路与 SSE 协议（仅展示维度调整）。

## Assumptions / Open Questions
- “用户调用数据”默认口径（可按你确认调整）：
  - 时间窗：`24h`（Dashboard 现有主窗口），并可切换 `7d`。
  - 指标最小集：`calls_total`（调用次数）、`unique_users`（独立用户）、`success_rate`、`avg_latency_ms`。
- 统计来源优先复用现有 SQLite 表（避免新增影子状态）：
  - `ai_model_daily_usage`（按 model_key 聚合的“用户日使用量”）
  - `ai_request_stats`（成功/失败/平均延迟的聚合）
- 可用性判定由服务端执行（避免前端推导漂移）：
  - 复用 `LlmModelRegistry.resolve_model_key()` 的路由门禁（active、有 key、非 offline、模型可支持等）。
  - 输出 `availability_reason` 用于 UI 可解释性。

## Phases
1. 同义实现扫描与基线确认
   - Dashboard 当前供应商展示链路：
     - `web/src/components/dashboard/EndpointConnectivityCard.vue`
     - `web/src/components/dashboard/ApiConnectivityModal.vue`
     - `app/services/metrics_collector.py::_get_api_connectivity()`
   - 映射模型的既有 SSOT 输出：
     - `/api/v1/llm/models?view=mapped`
     - `/api/v1/llm/app/models`（debug 可带 resolved 信息）
2. 后端：新增“映射模型观测”聚合接口
   - 新增 `/api/v1/dashboard/stats/mapped-models`（或并入 `/stats/dashboard` 返回字段）：
     - 返回 `total/available/unavailable` + `rows[]`
     - 每行包含：`model_key(scope_key)`、`scope_type`、`resolved_model`（可选）、`provider/endpoint_id`（可选）、`availability`、`availability_reason`、
       `calls_total/unique_users/success_rate/avg_latency_ms`（按时间窗）
   - 聚合策略（KISS）：
     - 可用性：对每个 mapping key 调用 `resolve_model_key`，捕获错误码作为 reason。
     - 调用统计：优先按 `ai_model_daily_usage.model_key` 与 mapping `scope_key` 对齐；补充 `ai_request_stats` 的 success/error/latency（若无法可靠对齐则先只展示 calls/unique_users，并在 Notes 标注）。
3. 前端：Dashboard 替换 UI（取消供应商维度）
   - `web/src/components/dashboard/MonitorPanel.vue`：中间栏从 `EndpointConnectivityCard` 替换为 `MappedModelStatusCard`（新组件或复用改造）。
   - `web/src/views/dashboard/index.vue`：
     - StatsBanner 第 4 项：替换 label/detail 与点击行为（弹出映射模型详情，而非供应商端点详情）。
     - QuickAccess：可选移除 “AI 供应商”卡片（按你的确认）。
4. 验证与回滚
   - 后端：`make test`
   - 前端：`pnpm -C web build`
   - Docker：`bash scripts/dev/docker_local_up.sh` + `curl /api/v1/healthz`
   - 回滚：`git revert <sha>` 后 `docker compose up -d --build app`

## Tests & Verification
- 后端新增/更新 pytest：覆盖“映射模型聚合接口”输出结构与可用性 reason（mock/不出网）。
- 前端：构建通过，Dashboard 首页渲染正常。
- 手工：Dashboard 首页不再出现 endpoint 维度的“AI 供应商/连通性”列表；映射模型卡片可看到可用性与调用统计。

## Issue CSV
- Path: `issues/2026-01-11_14-19-40-dashboard-mapped-models-status.csv`
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描、定位统计口径与调用点
- `functions:apply_patch`：最小改动
- `functions:shell_command`：测试/构建/Docker 验证

## Acceptance Checklist
- [ ] Dashboard 首页取消供应商维度展示（卡片/弹窗/文案）
- [ ] 映射模型维度展示可用性（含 reason/命中信息）
- [ ] 映射模型维度展示用户调用数据（按确认的时间窗与指标）
- [ ] `make test` 通过
- [ ] `pnpm -C web build` 通过
- [ ] 可回滚（revert + docker rebuild）

## Risks / Blockers
- 统计口径对齐风险：现有 `ai_model_daily_usage` 的 `model_key` 为配额归一化 key，若 mapping key 多样化可能无法一一对应；需明确“展示范围/映射规则”并避免误导。
- 可用性依赖 endpoint `status` 快照：若 monitor 未跑过，展示可能为 unknown；需提供“刷新/诊断”动作而不是后台自动出网探针。

## Rollback / Recovery
- 回滚提交即可恢复旧 Dashboard 展示。
- 保留 `/system/ai`（供应商管理）不受影响。

## Checkpoints
- Commit after: 后端聚合接口 + 测试
- Commit after: Dashboard UI 替换 + 构建通过

## References
- `web/src/components/dashboard/MonitorPanel.vue`
- `web/src/components/dashboard/EndpointConnectivityCard.vue`
- `web/src/components/dashboard/ApiConnectivityModal.vue`
- `web/src/components/dashboard/ModelObservabilityCard.vue`
- `app/services/metrics_collector.py`
- `app/services/llm_model_registry.py`
- `app/db/sqlite_manager.py`

