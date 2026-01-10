---
mode: plan
task: App SSE 真流式输出模式重构（raw passthrough + xml plaintext）
created_at: "2026-01-10T14:09:26+08:00"
complexity: complex
---

# Plan: App SSE 真流式输出模式重构（raw passthrough + xml plaintext）

## Goal
- App 端对 `GET /api/v1/messages/{id}/events` 持续收到增量（禁止“首段 + 长空白 + 末尾一次性到达”）。
- 必须同时满足两种对外行为（并通过 E2E 测试）：
  - **透明转发**：真实上游 API 响应以流式方式透明转发到 App（RAW 可还原）。
  - **解析纯文本**：后端解析上游响应并流式输出给 App，输出为**纯文本**且**包含 XML 标签**（例如 `<final>` 等）。
- 若上游/中间层导致一次性 body/token：后端必须自动切换为“流式分块输出”，保证 App 端依旧按流式接收。

## Scope
- In:
  - `POST /api/v1/messages`：新增“输出模式开关”（与 prompt 透传/不透传放在同一位置/语义域），并写入 broker meta（SSOT）。
  - `GET /api/v1/messages/{message_id}/events`：依据输出模式返回不同类型的流式事件。
  - provider adapters：统一产出 RAW 帧与解析文本帧；上游非 SSE 时做流式降级。
  - 测试：新增/调整 E2E 覆盖三条路径（raw、xml_plaintext、非 SSE 降级）。
  - 文档：固化 SSOT（事件协议、开关语义、验收方法）。
- Out:
  - 不改 App 端渲染逻辑（仅保证后端输出满足现有订阅能力；若需要 App 增加事件监听，必须先在 E2E 中证明必要性再做）。

## Assumptions / Dependencies
- 假设 App/Web 可以在创建消息时携带新字段（例如 `result_mode`），默认值以“替代现有功能”为准。
- 线上必须先通过 `GET /api/v1/base/sse_probe` 验证无代理缓冲，否则任何后端“真流式”都会被边缘层合并。
- SSE 对外 SSOT：保持 `content_delta/completed/error/heartbeat` 基本集合不破坏；新增事件必须兼容旧客户端（未知 event 可忽略）。

## Phases
1. 定义 SSOT（请求字段 + SSE 事件协议 + 自动检测点）
2. 实现统一流式管线（RAW/解析文本双路产出 + 自动降级）
3. 补齐 E2E（含“非 SSE 一次性响应也必须流式输出”）并回归现有测试

## Tests & Verification
- `result_mode=raw_passthrough`：mock 上游多帧 SSE → App 端应收到多条增量事件（非 1 次），且 RAW 可还原。
- `result_mode=xml_plaintext`：mock 上游多帧 SSE → App 端拼接得到的纯文本包含 XML 标签（例如 `<final>`），且增量分布连续。
- 上游非 SSE/一次性 JSON：mock `content-type: application/json` + 一次性 body → App 端仍应收到多条增量事件（分块输出），不允许一次性落地。
- 代理缓冲前置：`GET /api/v1/base/sse_probe` 在 App 同网络路径下必须按 1s 间隔到达。
- 回归：`uv run -m pytest -q`（至少覆盖 provider adapter + SSE 微型 E2E）。

## Issue CSV
- Path: issues/2026-01-10_14-07-55-app-sse-stream-modes.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描、定位发布/消费点
- `functions:shell_command`：运行 `uv run -m pytest ...`、运行脚本验收
- `functions:apply_patch`：最小变更实现
- `context7:resolve-library-id` + `context7:get-library-docs`：若需要核验上游 SSE 事件形态（OpenAI/Anthropic/Gemini）

## Acceptance Checklist
- [ ] App 端真实对话不再出现“一次性完整 token/raw”
- [ ] 同一条链路支持 raw_passthrough 与 xml_plaintext 两种流式输出（由开关决定）
- [ ] 上游非 SSE 时仍自动分块流式输出（不可一次性）
- [ ] 三条路径均有 E2E 覆盖并通过
- [ ] SSOT 文档更新（开关语义/事件协议/验收方法）

## Risks / Blockers
- 若 `sse_probe` 在真实线上路径被合并到一次性到达，则根因是边缘层缓冲/压缩：需先改网关/Ingress/CF 配置。
- RAW 透明转发可能包含敏感内容：日志必须脱敏且默认不落盘；仅对同一认证用户可见。

## Rollback / Recovery
- 保留旧输出模式作为临时回滚（例如 `result_mode=legacy` 或配置项切回）。
- 保留 `sse_probe` 作为长期验收与发布前置。

## Checkpoints
- Commit after: Phase 1（SSOT 定义 + 合约/文档）
- Commit after: Phase 2（实现 + 自动检测点）
- Commit after: Phase 3（测试闭环 + 回归通过）

## References
- `app/api/v1/messages.py`（SSE `/events`）
- `app/services/ai_service.py`（broker/publish）
- `app/services/providers/*`（上游帧解析）
- `app/api/v1/base.py`（`/api/v1/base/sse_probe`）
- `docs/sse/app_ai_sse_raw_结构体与样本.md`（SSE 事件 SSOT）
- `deploy/web.conf`（网关 SSE 禁缓冲/禁 gzip）
