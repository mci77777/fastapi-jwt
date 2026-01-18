---
mode: plan
task: Dashboard：App SSE 输出模式（透明转发 / XML 文本转发）
created_at: "2026-01-18T11:05:12+08:00"
complexity: medium
---

# Plan: Dashboard：App SSE 输出模式（透明转发 / XML 文本转发）

## Goal
- Dashboard 可配置 App 默认输出模式：`raw_passthrough`（透明转发）/ `xml_plaintext`（XML 文本转发），两者都必须保持 SSE 真流式（`event: content_delta` 分帧）。
- 保持现有后端接口与 SSE 事件契约不变，仅做内部行为/文案对齐与可观测增强。

## Scope
- In:
  - Dashboard 与 System/AI 页面文案与选项收敛（仅两项：透明转发 / XML 文本转发）。
  - 兼容历史值：若后端持久化为 `auto`，Dashboard 给出提示并引导管理员选择并保存为两项之一（不改接口）。
  - 增加“真流式验证”入口（复用现有 `GET /api/v1/base/sse_probe`），用于定位网关缓冲导致的“大 chunk”。
- Out:
  - 不修改 App（Android/iOS）侧 SSE 解析实现（除非另开任务）。
  - 不变更 `/api/v1/messages*`、`/api/v1/llm/app/config` 的字段/枚举（保持接口状态）。

## Assumptions / Dependencies
- 反代/网关需对 `/api/v1/messages` 关闭缓冲与 gzip（参考 `deploy/web.conf`）；否则客户端仍可能出现“假流式/批量到达”。
- App 端必须监听自定义 SSE 事件（`content_delta/completed/...`），不能只用默认 `message` 事件（否则表现异常）。

## Phases
1. 同义实现扫描与 SSOT 对齐：确认当前 `default_result_mode`、SSE 分帧阈值、以及 Dashboard 现有 UI 落点。
2. Dashboard/UI 调整：
   - `ModelSwitcher` 与 `system/ai` 页面仅展示两项（透明转发 / XML 文本转发），移除/隐藏 `auto` 选项；
   - 修正文案：`raw_passthrough` 不再误导为 `upstream_raw`（其仍为 auto/诊断帧）。
   - 加入 `auto` 兼容提示（只读显示 + 需要管理员显式选择一种并保存）。
3. 真流式验证入口：
   - 在上述配置处加入 `SSE 探针`（调用 `/api/v1/base/sse_probe`），展示间隔统计与“是否疑似缓冲”的结论。
4. 回归与文档更新：
   - 更新相关文档/页面提示，强调“App 端消费的是 SSE 自定义事件流”与“网关禁缓冲”。

## Tests & Verification
- 后端健康：`curl http://localhost:9999/api/v1/healthz` -> 200
- SSE 探针：登录后 `GET /api/v1/base/sse_probe` -> 8 秒内每秒到达 1 条 `probe`，非批量聚合
- App 默认模式：
  - Dashboard 设置 `default_result_mode=raw_passthrough` 后，App 不传 `result_mode` 时仍按 SSE `content_delta` 真流式；
  - Dashboard 设置 `default_result_mode=xml_plaintext` 后，输出为可解析的 ThinkingML XML 文本流（仍 `content_delta` 分帧）。
- 回归测试：`make test`

## Issue CSV
- Path: issues/2026-01-18_11-04-44-dashboard-app-sse-stream-mode.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描、定位 UI/后端 SSOT 落点
- `Bash`：本地启动、curl 探针、`make test`

## Acceptance Checklist
- [ ] Dashboard 配置项只展示两项：透明转发 / XML 文本转发（不暴露 auto），且写入仍使用现有 `default_result_mode` 键
- [ ] UI 文案明确两项都是 SSE `content_delta` 流式，不再误导 raw_passthrough=upstream_raw
- [ ] SSE 探针入口可直接定位“网关缓冲/压缩导致的大 chunk”
- [ ] 接口契约不变（路径/字段/事件名不变），`make test` 通过

## Risks / Blockers
- 如果 App 端实际上只读取 `completed.reply` 或未监听自定义事件，仍会出现“大 chunk”；需另开 App 侧任务修复。
- 部署侧若未按 `deploy/web.conf` 配置禁缓冲/禁 gzip，SSE 仍会被聚合。

## Rollback / Recovery
- 仅前端文案/交互与配置引导：回滚对应提交即可；后端接口无变更。

## Checkpoints
- Commit after: UI 选项/文案对齐 + SSE 探针入口 + 回归通过

## References
- app/services/ai_service.py:680
- app/api/v1/messages.py:587
- app/api/v1/base.py:210
- app/api/v1/llm_models.py:193
- web/src/components/dashboard/ModelSwitcher.vue:82
- web/src/views/system/ai/index.vue:813
- deploy/web.conf:46
- docs/sse/app_ai_sse_raw_结构体与样本.md:12
- docs/ai预期响应结构.md:114
