# api.gymbro.cloud「App 端对接」最小契约（模型白名单 / 发送消息 / SSE）

生成日期：2026-01-04  
适用场景：App 端（Coach / gymbro_cloud）接入云端模型能力：拉取可用模型 → 用户选择并持久化 → 发送消息 → SSE 获取流式结果与对账信息。

> 重要约束：
> - `POST /api/v1/messages` 的 Body 顶层禁止额外字段（`additionalProperties=false` / `extra="forbid"`）。
> - `model` 是 **必填且强校验** 的白名单字段：必须来自 `GET /api/v1/llm/models`（默认 `view=mapped`）返回的 `data[].name`。
> - 示例中的 `Authorization` 只写 `<redacted>`，不要把真实 token 写进文档/日志。

---

## 0) 基础约定

- Base URL：`https://api.gymbro.cloud`
- API 前缀：`/api/v1`
- 命名：服务端字段使用 `snake_case`
- 认证：除公开端点外均要求 `Authorization: Bearer <redacted>`
- 请求追踪：建议每次 HTTP 调用都传 `X-Request-Id: <opaque>`（服务端会在 SSE `completed/error` 中回传同名 `request_id`，便于端到端对账）
- 通用响应包装（非 SSE）：`{"code": 200, "msg": "success", "data": ..., "total": ...}`

名词（SSOT）：
- `request_id`：单次 HTTP 调用追踪 ID（Header: `X-Request-Id`；一次调用一个）
- `message_id`：单条消息 ID（`POST /api/v1/messages` 返回；用于 SSE 订阅）
- `conversation_id`：云端会话 ID（UUID；由服务端生成并回传；用于归因/并发控制）

---

## 1) 拉取“映射后的模型白名单”（SSOT）：`GET /api/v1/llm/models`

用途：App 顶栏“云端模型”菜单拉取并展示给用户选择；**只展示映射后的模型 key**，避免暴露/依赖具体 provider 的 `model_list`。

### Query（可选）

- `view`：默认 `mapped`（返回白名单）；管理后台才使用 `view=endpoints`
  - 安全策略：非管理员请求 `view=endpoints` 会自动降级为 `mapped`

### Response（成功）

```json
{
  "code": 200,
  "msg": "success",
  "data": [
    {
      "name": "global:xai",
      "label": "xai",
      "scope_type": "global",
      "scope_key": "xai",
      "updated_at": "2026-01-04T00:00:00+00:00",
      "candidates_count": 1
    }
  ],
  "total": 1
}
```

App 侧建议持久化字段（例如 `coach_cloud_model`）：
- `selected_model_key`：使用 `data[].name`（这是发送消息时的 `model`）
- `selected_model_label`：使用 `data[].label`（仅用于 UI 展示，不作为路由输入）

---

## 2) 发送消息：`POST /api/v1/messages`

用途：创建异步对话任务，随后用 SSE 拉流。

### Headers

- `Authorization: Bearer <redacted>`
- `Content-Type: application/json`
- （推荐）`X-Request-Id: <opaque>`

### 请求体（推荐：顶层字段为 SSOT）

#### 2.1 Server 模式（不透传；由服务端注入默认 system/tools）

```json
{
  "model": "global:xai",
  "text": "给我一份三分化训练方案",
  "conversation_id": null,
  "metadata": { "client": "app", "client_message_id": "<opaque>" },
  "skip_prompt": false
}
```

#### 2.2 Passthrough 模式（透传；客户端完全控制 system/messages/tools）

> 如果 App 没有本地工具执行器，建议显式传 `tool_choice: "none"`，避免上游返回 `tool_calls` 影响渲染。

```json
{
  "model": "global:xai",
  "skip_prompt": true,
  "messages": [
    { "role": "system", "content": "<redacted system prompt>" },
    { "role": "user", "content": "给我一份三分化训练方案" }
  ],
  "tools": [],
  "tool_choice": "none",
  "metadata": { "client": "app", "client_message_id": "<opaque>" }
}
```

### 兼容（仅兜底，不推荐）

为兼容历史 App：允许把 OpenAI 兼容请求体放入 `metadata.chat_request` 或 `metadata.openai`。  
但**顶层字段仍是 SSOT**，并且 `model` 仍会按“顶层优先、metadata 兜底”取值并强校验白名单。

### Response（202 Accepted）

```json
{
  "message_id": "32位hex字符串",
  "conversation_id": "uuid字符串"
}
```

常见 `422`（示意，实际会包在 `{"detail": ...}`）：

```json
{
  "code": "model_not_allowed",
  "message": "model 不在白名单内（请以 /api/v1/llm/models 返回的 name 为准）",
  "request_id": "<request_id>"
}
```

---

## 3) SSE 订阅：`GET /api/v1/messages/{message_id}/events`

用途：流式接收模型输出（`content_delta`）与最终结果（`completed`）。

典型事件（示意）：
- `event: status`：
  - `{"state":"queued|working","message_id":"..."}`
  - `{"state":"routed","message_id":"...","request_id":"...","provider":"xai","resolved_model":"grok-4-1-fast-reasoning","endpoint_id":123,"upstream_request_id":null}`
- `event: content_delta`：`{"message_id":"...","delta":"..."}`
- `event: completed`：`{"message_id":"...","reply":"...","request_id":"...","provider":"...","resolved_model":"...","endpoint_id":123,"upstream_request_id":"...|null"}`
- `event: error`：`{"message_id":"...","error":"...","request_id":"...","provider":"...|null","resolved_model":"...|null","endpoint_id":123|null}`

> `completed.reply` 的结构契约见：`docs/ai预期响应结构.md`（Strict-XML / ThinkingML v4.5）。

