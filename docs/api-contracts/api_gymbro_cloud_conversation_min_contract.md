# api.gymbro.cloud「对话聚合」最小契约（给 App 端 Agent）

生成日期：2025-12-31  
来源：仓库内 `docs/` + 后端实现对齐（commit `2d1f7899bb574abaffa5a4eb59306315c4ca3820`）  
注意：本文是“最小可用契约”，用于 App 端集成；线上如有灰度差异，以 `https://api.gymbro.cloud/openapi.json` 为准（无需携带 token 也通常可访问）。

### 线上 OpenAPI 复核（2025-12-31）

- `POST /api/v1/messages`：
  - `MessageCreateRequest.additionalProperties=false`，与“禁止额外字段（如 model）”一致
  - `202` 返回 schema 为 `MessageCreateResponse`（包含 `message_id` + `conversation_id`）
- `GET /api/v1/messages/{message_id}/events`：
  - OpenAPI 未能表达 `text/event-stream`（文档仍按 SSE 实际行为为准）
- Header 的“required=false”：
  - OpenAPI 显示 `Authorization` 可选，但运行时缺失会返回 `401`（依赖会从 header 中解析 Bearer）

---

## 0. 基础约定

- Base URL：`https://api.gymbro.cloud`
- API 前缀：`/api/v1`
- 命名：服务端字段为 `snake_case`（如 `message_id`）；App 端如需 `camelCase` 自行映射（如 `messageId`）。
- 认证：除“公开端点”外，均要求 `Authorization: Bearer <jwt>`。

---

## 1) 创建消息：`POST /api/v1/messages`

### Headers
- `Authorization: Bearer <redacted>`
- `Content-Type: application/json`

### Request Body（最小字段）
> 重要：请求体 **不允许额外字段**（`additionalProperties=false`）。例如：携带 `model` 会触发 `422`。

```json
{
  "text": "string, required, minLength=1",
  "conversation_id": "string (uuid), optional",
  "metadata": { "any": "object, optional" },
  "skip_prompt": false
}
```

语义说明：
- `text`：用户输入（必填，不能为空字符串）。
- `conversation_id`：会话标识（可选）。
  - 若传入且是合法 UUID，则服务端沿用该值；
  - 若传入但不是合法 UUID，服务端会自动生成新的 UUID（不会报错）。
- `metadata`：客户端附加信息（可选，任意键值对；服务端会透传/落库用于追踪与扩展）。
- `skip_prompt`：是否跳过 system prompt（可选，默认 `false`）。

### Response（202 Accepted）
```json
{
  "message_id": "string",
  "conversation_id": "string (uuid)"
}
```

字段说明：
- `message_id`：本次请求的消息 ID（建议视为 opaque；当前实现通常为 32 位 hex）。
- `conversation_id`：本次请求对应的会话 ID（UUID）。

### Errors（常见）
- `401 Unauthorized`：缺少/非法 JWT（统一错误结构，见下）
- `422 Unprocessable Entity`：请求体校验失败（FastAPI 默认 validation error 结构）
- `429 Too Many Requests`：限流
- `500 Internal Server Error`：内部错误/上游错误

统一错误结构（401/429/500 等常见）：
```json
{
  "status": 401,
  "code": "token_missing",
  "message": "Authorization token is required",
  "request_id": "<request_id>",
  "hint": "optional"
}
```

---

## 2) SSE 拉流：`GET /api/v1/messages/{message_id}/events`

### Headers
- `Authorization: Bearer <redacted>`
-（可选）`Accept: text/event-stream`

### Query
- `conversation_id`：string（uuid）可选，用于 SSE 并发控制/归因

### Response
- `Content-Type: text/event-stream`
- SSE 帧格式：
  - `event: <eventType>`
  - `data: <json>`

### 事件类型集合（最小）

#### `event: status`
- `data.state`：`"queued"` 或 `"working"`
```json
{ "state": "queued", "message_id": "<message_id>" }
```

#### `event: content_delta`
- 增量文本块
```json
{ "message_id": "<message_id>", "delta": "chunk of text" }
```

#### `event: completed`
- 最终完整回复（可用于落地展示与校验）
```json
{ "message_id": "<message_id>", "reply": "full response" }
```

#### `event: error`
- 处理失败（可用于兜底 UI）
```json
{ "message_id": "<message_id>", "error": "error message" }
```

#### `event: heartbeat`
- 心跳（用于保持连接/探活）
```json
{ "message_id": "<message_id>", "event": "heartbeat" }
```

### 何时结束
- 服务端会在发送 `completed` 或 `error` 后关闭该 `message_id` 的 channel，SSE 连接随之结束。
- 客户端提前断开也会结束（服务端检测 `is_disconnected()` 并清理）。

### Errors（常见）
- `401`：缺少/非法 JWT
- `404`：`message_id` 不存在（常见 `detail="message not found"`）
- `429`：SSE 并发超限（`code=SSE_CONCURRENCY_LIMIT_EXCEEDED`），可能包含 `Retry-After` 响应头（秒）

---

## 3) 用户信息（等价 /v1/me）：`GET /api/v1/base/userinfo`

> 说明：项目当前等价接口在 `/api/v1/base/userinfo`，并非 `/v1/me`。

### Headers（两种都支持）
- `Authorization: Bearer <redacted>`（推荐）
- 或 `token: <redacted>`（兼容旧前端 header）

### Response（200）
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": "string",
    "username": "string",
    "email": "string|null",
    "avatar": "string|null",
    "roles": [],
    "is_superuser": false,
    "is_active": true
  }
}
```

### 认证与匿名限制
- 需要有效 JWT。
- 匿名用户（`is_anonymous=true`）会被策略门限制访问 `/api/v1/base/*`，因此匿名 token **不能** 调用该接口。

---

## 4) JWT / 匿名能力（最小要求）

### Bearer 规则
- 必须使用：`Authorization: Bearer <jwt>`
- 仅传裸 token 会被判定为格式错误。

### 必需 claims（服务端校验）
- 必需：`iss`, `sub`, `exp`, `iat`
- 可选：`aud`（当服务端配置 audience 时将变为必需）
- `nbf`：默认可选（仅当服务端开启强制时才必需；即使不必需，若存在仍会校验）

### 匿名用户识别
- 通过 claim `is_anonymous: true` 识别为匿名用户（`user_type=anonymous`）。
- 匿名用户白名单（与本文相关）：
  - ✅ `POST /api/v1/messages`
  - ✅ `GET /api/v1/messages/{message_id}/events`
  - ❌ `GET /api/v1/base/userinfo`

---

## 5) 最小 curl 示例（占位符已脱敏）

### 5.1 创建消息
```bash
curl -X POST https://api.gymbro.cloud/api/v1/messages \
  -H "Authorization: Bearer <redacted>" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"Hello\",\"metadata\":{\"client\":\"app\",\"trace\":\"<redacted>\"}}"
```

### 5.2 SSE 拉流
```bash
curl -N "https://api.gymbro.cloud/api/v1/messages/<message_id>/events?conversation_id=<conversation_id>" \
  -H "Authorization: Bearer <redacted>"
```

### 5.3 用户信息（等价 /v1/me）
```bash
curl https://api.gymbro.cloud/api/v1/base/userinfo \
  -H "Authorization: Bearer <redacted>"
```

---

## 6) JSON Schema（最小版，便于 App 端 Agent 落地校验）

### 6.1 `MessageCreateRequest`
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["text"],
  "properties": {
    "text": { "type": "string", "minLength": 1 },
    "conversation_id": { "type": "string", "format": "uuid" },
    "metadata": { "type": "object", "additionalProperties": true },
    "skip_prompt": { "type": "boolean", "default": false }
  }
}
```

### 6.2 `MessageCreateResponse`（202）
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["message_id", "conversation_id"],
  "properties": {
    "message_id": { "type": "string" },
    "conversation_id": { "type": "string", "format": "uuid" }
  }
}
```

### 6.3 SSE 事件（以 `{event,data}` 结构表达，实际传输为 SSE 帧）
```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "oneOf": [
    {
      "type": "object",
      "required": ["event", "data"],
      "properties": {
        "event": { "const": "status" },
        "data": {
          "type": "object",
          "required": ["state", "message_id"],
          "properties": {
            "state": { "enum": ["queued", "working"] },
            "message_id": { "type": "string" }
          }
        }
      }
    },
    {
      "type": "object",
      "required": ["event", "data"],
      "properties": {
        "event": { "const": "content_delta" },
        "data": {
          "type": "object",
          "required": ["message_id", "delta"],
          "properties": {
            "message_id": { "type": "string" },
            "delta": { "type": "string" }
          }
        }
      }
    },
    {
      "type": "object",
      "required": ["event", "data"],
      "properties": {
        "event": { "const": "completed" },
        "data": {
          "type": "object",
          "required": ["message_id", "reply"],
          "properties": {
            "message_id": { "type": "string" },
            "reply": { "type": "string" }
          }
        }
      }
    },
    {
      "type": "object",
      "required": ["event", "data"],
      "properties": {
        "event": { "const": "error" },
        "data": {
          "type": "object",
          "required": ["message_id", "error"],
          "properties": {
            "message_id": { "type": "string" },
            "error": { "type": "string" }
          }
        }
      }
    },
    {
      "type": "object",
      "required": ["event", "data"],
      "properties": {
        "event": { "const": "heartbeat" },
        "data": {
          "type": "object",
          "required": ["message_id", "event"],
          "properties": {
            "message_id": { "type": "string" },
            "event": { "const": "heartbeat" }
          }
        }
      }
    }
  ]
}
```

---

## 7) 已知差异/注意点（避免踩坑）

- `docs/e2e-ai-conversation/QUICK_START.md` 中提到 `model` 字段：当前后端请求体不接受该字段（会 `422`）。App 端集成请以本文为准，或直接以线上 `openapi.json` 为准。
- `POST /api/v1/messages` 返回值：文档示例可能只有 `message_id`；当前实现还会返回 `conversation_id`（建议保存用于并发控制与归档）。
