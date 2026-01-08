# /messages + SSE API（对接摘要）· 2026-01-07

SSOT：详细契约以仓库内文档为准，避免复制漂移：
- `docs/api-contracts/api_gymbro_cloud_app_min_contract.md`
- `docs/api-contracts/api_gymbro_cloud_conversation_min_contract.md`

---

## 0) 基础约定

- API 前缀：`/api/v1`
- 认证：`Authorization: Bearer <redacted>`
- 追踪：推荐 `X-Request-Id: <opaque>`（服务端在 SSE `completed/error` 中回传 `request_id` 对账）
- Body：`snake_case`
- 严格校验：`POST /api/v1/messages` 顶层 `extra="forbid"`（禁止额外字段）

---

## 1) 模型白名单（强约束）

客户端必须先拉白名单，并使用返回的 `name` 作为 `model`：

- `GET /api/v1/llm/models`（App 建议 `view=mapped`）
- `GET /api/v1/llm/app/models`（Web 测试页在用）

---

## 2) 创建消息：`POST /api/v1/messages`

### Headers（最小）
- `Authorization: Bearer <redacted>`
- `Content-Type: application/json`
- `X-Request-Id: <opaque>`（推荐）

### Body（最小）

`text` 与 `messages` 至少提供一个；`model` 必填且必须来自白名单。

Server 模式（默认，服务端注入默认 prompt）：
```json
{
  "model": "xai",
  "text": "hello",
  "conversation_id": null,
  "metadata": { "client": "app" },
  "skip_prompt": false
}
```

Passthrough 模式（客户端完全控制 messages/system/tools）：
```json
{
  "model": "xai",
  "skip_prompt": true,
  "messages": [
    { "role": "system", "content": "<redacted>" },
    { "role": "user", "content": "hello" }
  ],
  "tools": [],
  "tool_choice": "none",
  "metadata": { "client": "app" }
}
```

### Provider Payload 模式（新增，4 方言）

当 `payload` 存在时，必须同时提供 `dialect`，并进入 provider passthrough 分支（仍强制 `stream=true`）：  
`dialect ∈ openai.chat_completions | openai.responses | anthropic.messages | gemini.generate_content`。

示例（OpenAI Chat Completions）：
```json
{
  "model": "xai",
  "dialect": "openai.chat_completions",
  "payload": {
    "messages": [{ "role": "user", "content": "hello" }],
    "temperature": 0.7
  },
  "metadata": { "client": "app" }
}
```

### Response（202）
```json
{ "message_id": "<opaque>", "conversation_id": "<uuid>" }
```

---

## 3) SSE 拉流：`GET /api/v1/messages/{message_id}/events`

### Headers（最小）
- `Authorization: Bearer <redacted>`
- `Accept: text/event-stream`（推荐）
- `X-Request-Id: <opaque>`（推荐）

### Query（可选）
- `conversation_id=<uuid>`（推荐使用创建消息返回值，用于并发控制/归因）

### 事件格式

- `Content-Type: text/event-stream`
- 每条事件：
  - `event: <eventType>`
  - `data: <json>`
  - 空行结束

事件集合（最小）：`status` / `content_delta` / `completed` / `error` / `heartbeat`。

### 并发限制

同用户同 conversation 默认只允许 1 条活跃 SSE：
- 超限返回 `429`，`code=SSE_CONCURRENCY_LIMIT_EXCEEDED`（可能带 `Retry-After`）

---

## 4) 客户端解析要点（避免“看起来不流”）

1) **EventSource**：必须监听自定义事件：
`status/content_delta/completed/error/heartbeat`（使用 `addEventListener`）。

2) **fetch 流式**：需运行时支持 `ReadableStream`；移动端/WebView 需评估兼容或引入 SSE 库。

3) **网关 301**：若 `/api/v1/messages` 存在重定向，会破坏 POST/SSE；参考 `deploy/web.conf` 的 location 修复。
