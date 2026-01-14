# api.gymbro.cloud「Agent Run」最小契约（后端工具：Web 搜索 + 动作库检索）

生成日期：2026-01-13  
适用场景：App 端只发起一次 Agent Run，由后端完成工具执行（Web 搜索/动作库检索）并通过 SSE 流式返回最终回答与工具结果。

> 重要：本契约是“最小可用”版本。对话正文结构仍以 `docs/ai预期响应结构.md` 为 SSOT（ThinkingML v4.5）。

---

## 0) 基础约定

- Base URL：`https://api.gymbro.cloud`
- API 前缀：`/api/v1`
- 认证：除公开端点外均要求 `Authorization: Bearer <jwt>`
- 命名：服务端字段为 `snake_case`
- SSE：事件 `data` 会自动带 `message_id` 与 `request_id`（若请求侧传 `X-Request-Id`，则用于对账）
- Prompt（SSOT）：Agent Run 默认使用 `agent_system` + `agent_tools`（可在 Dashboard 的 Prompt 管理页配置/启用）

---

## 1) 创建 Agent Run：`POST /api/v1/agent/runs`

用途：创建一次 Agent Run（异步），随后用 SSE 拉流。

### Headers
- `Authorization: Bearer <redacted>`
- `Content-Type: application/json`
-（推荐）`X-Request-Id: <opaque>`

### Request Body（SSOT）

```json
{
  "model": "global:xai",
  "text": "帮我查一下今天的训练相关新闻，并给出一份三分化建议",
  "conversation_id": null,
  "metadata": { "client": "app", "client_run_id": "<opaque>" },
  "result_mode": "xml_plaintext",
  "enable_exercise_search": true,
  "exercise_top_k": 5,
  "enable_web_search": false,
  "web_search_top_k": 5
}
```

说明：
- `model`：必填，必须来自 `GET /api/v1/llm/models`（默认 `view=mapped`）返回的 `data[].name`
- `text`：必填，用户输入
- `conversation_id`：可选（UUID），非法会自动生成新 UUID
- `metadata`：可选（不做字段白名单），仅用于对账与扩展
- `result_mode`：可选（默认走 Dashboard 持久化 `llm_app_settings.default_result_mode`）
- `enable_exercise_search`：可选（默认 true）
- `exercise_top_k`：可选（默认 5，范围 1–10）
- `enable_web_search`：可选（默认跟随 Dashboard 配置；**请求侧主要用于关闭**，控成本）
- `web_search_top_k`：可选（默认 5，范围 1–10）

### Response（202 Accepted）

```json
{
  "run_id": "32位hex字符串",
  "message_id": "32位hex字符串",
  "conversation_id": "uuid字符串"
}
```

> 当前实现中 `run_id == message_id`，用于复用现有 SSE/broker；未来可能解耦，但字段会保留。

### JSON Schema（机读）
- request：`docs/api-contracts/schemas/agent_run_create_request.schema.json`
- response：`docs/api-contracts/schemas/agent_run_create_response.schema.json`

---

## 2) SSE 拉流：`GET /api/v1/agent/runs/{run_id}/events`

### Headers
- `Authorization: Bearer <redacted>`
-（可选）`Accept: text/event-stream`

### Query
- `conversation_id`：string（uuid）可选，用于 SSE 并发控制/归因（推荐与创建时一致）

### 事件类型集合（最小）

与 `/api/v1/messages/{message_id}/events` 兼容，并新增工具事件：

- `status`
- `tool_start`
- `tool_result`
- `content_delta`
- `completed`
- `error`
- `heartbeat`
-（auto 模式可选）`upstream_raw`

### `tool_start`

```json
{
  "tool_name": "web_search.exa",
  "args": { "query": "xxx", "top_k": 5 }
}
```

### `tool_result`

```json
{
  "tool_name": "web_search.exa",
  "ok": true,
  "elapsed_ms": 123,
  "result": { "provider": "exa", "total": 3, "results": [] }
}
```

失败时：

```json
{
  "tool_name": "web_search.exa",
  "ok": false,
  "elapsed_ms": 120,
  "error": { "code": "missing_api_key", "message": "EXA api key is required" }
}
```

### JSON Schema（机读）
- SSE frame：`docs/api-contracts/schemas/agent_run_sse_frame.schema.json`

---

## 3) Dashboard 配置（Exa Key / 开关）

通过管理端配置写入 `llm_app_settings`：

- `GET /api/v1/llm/app/config`：读取（只回显 `web_search_exa_api_key_masked`）
- `POST /api/v1/llm/app/config`：写入（字段 `web_search_exa_api_key` 为写入专用）

> 安全：Key 不应写入日志；对外只回显 masked。
