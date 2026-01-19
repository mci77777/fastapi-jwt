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
      "candidates_count": 1,
      "provider": "xai",
      "dialect": "openai.chat_completions",
      "capabilities": { "supports_tools": true, "supports_vision": false, "max_output_tokens": 4096 },
      "endpoint_hint": { "endpoint_id": 28, "endpoint_name": "xai-default" }
    }
  ],
  "total": 1
}
```

App 侧建议持久化字段（例如 `coach_cloud_model`）：
- `selected_model_key`：使用 `data[].name`（这是发送消息时的 `model`）
- `selected_model_label`：使用 `data[].label`（仅用于 UI 展示，不作为路由输入）
- `dialect/capabilities`：可用于 UI 提示（例如 tool/vision 能力），但不应作为路由输入

---

## 2) 发送消息：`POST /api/v1/messages`

用途：创建异步对话任务，随后用 SSE 拉流。

### SSE 输出模式（SSOT）

`POST /api/v1/messages` 支持可选字段 `result_mode`：

- 若不传 `result_mode`：服务端使用持久化配置 `llm_app_settings.default_result_mode`（管理端 `/api/v1/llm/app/config` 可设置）；未配置则回退 `raw_passthrough`。
- `raw_passthrough`（默认）：服务端解析上游响应并提取 token 文本，按原样以 `event: content_delta` 流式输出（不做 ThinkingML 纠错/标签归一化）。
- `xml_plaintext`：服务端解析上游响应并以 `event: content_delta` 流式输出，同时做 ThinkingML 最小纠错/标签归一化，保证结构契约稳定（允许包含 `<final>...</final>` 等 XML 标签）。
- `auto`：服务端自动判定（优先 `xml_plaintext`；若无法产出 `content_delta` 则降级为 `raw_passthrough`；必要时可能产生 `event: upstream_raw` 诊断帧）。

### Prompt 组装模式（SSOT）

- Dashboard 配置 `llm_app_settings.prompt_mode`（`/api/v1/llm/app/config`）为唯一来源。
- `server`（默认）：后端注入系统 Prompt/Tools（忽略客户端的 `system_prompt` 与 `tools`）。
- `passthrough`：后端跳过默认注入，按客户端请求透传（等价于强制 `skip_prompt=true`）。

### 权限等级与配额（SSOT）

当前仅区分 **2 个权限等级**：
- **普通用户（free）**：与匿名用户保持一致
- **订阅用户（pro）**：拥有更高权限/更高配额（默认不受普通配额限制）

普通用户（free）/匿名用户的**按模型日配额**：
- `deepseek`：无限
- `xai`：50 次/天
- `gpt` / `claude` / `gemini`：20 次/天

超出配额会返回 `429`：
```json
{
  "status": 429,
  "code": "model_daily_quota_exceeded",
  "message": "xai 超出每日对话额度（50/天）",
  "request_id": "<opaque>",
  "model_key": "xai",
  "limit": 50,
  "used": 50
}
```

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
  "skip_prompt": false,
  "result_mode": "xml_plaintext"
}
```

#### 2.2 Passthrough 模式（透传；客户端完全控制 system/messages/tools）

> 如果 App 没有本地工具执行器，建议显式传 `tool_choice: "none"`，避免上游返回 `tool_calls` 影响渲染。

```json
{
  "model": "global:xai",
  "skip_prompt": true,
  "result_mode": "raw_passthrough",
  "messages": [
    { "role": "system", "content": "<redacted system prompt>" },
    { "role": "user", "content": "给我一份三分化训练方案" }
  ],
  "tools": [],
  "tool_choice": "none",
  "metadata": { "client": "app", "client_message_id": "<opaque>" }
}
```

#### 2.3 Provider Payload 模式（新增，4 方言；高级功能）

当 `payload` 存在时：
- 必须同时提供 `dialect`
- `text/messages/tools/...` 等 SSOT 字段与 payload 模式**不可混用**（否则 422）
- 服务端仍会：
  - 强制 `stream=true`（或等价），统一走 GymBro SSE 输出链路
  - 覆盖上游的 `model` 为映射后的 `resolved_model`（客户端不得直接指定真实 model/base_url/api_key）
- `payload` 存在白名单字段校验（非白名单字段会 422：`payload_fields_not_allowed`）

> 权限：payload 只是请求体方言（不作为权限区分点）。普通/订阅用户都可用；实际差异由“模型权限 + 配额”决定。

**(A) OpenAI Chat Completions**：`dialect=openai.chat_completions`
```json
{
  "model": "global:xai",
  "dialect": "openai.chat_completions",
  "payload": {
    "messages": [
      { "role": "user", "content": "给我一份三分化训练方案" }
    ],
    "temperature": 0.7,
    "tool_choice": "none"
  },
  "metadata": { "client": "app", "save_history": true }
}
```

**(B) OpenAI Responses**：`dialect=openai.responses`
```json
{
  "model": "global:xai",
  "dialect": "openai.responses",
  "payload": {
    "input": "给我一份三分化训练方案",
    "max_output_tokens": 512
  },
  "metadata": { "client": "app", "save_history": true }
}
```

**(C) Anthropic Messages**：`dialect=anthropic.messages`
```json
{
  "model": "global:claude",
  "dialect": "anthropic.messages",
  "payload": {
    "messages": [
      { "role": "user", "content": "给我一份三分化训练方案" }
    ],
    "max_tokens": 512,
    "temperature": 0.7
  },
  "metadata": { "client": "app", "save_history": true }
}
```

**(D) Gemini streamGenerateContent**：`dialect=gemini.generate_content`
```json
{
  "model": "global:gemini",
  "dialect": "gemini.generate_content",
  "payload": {
    "contents": [
      { "role": "user", "parts": [{ "text": "给我一份三分化训练方案" }] }
    ],
    "generationConfig": { "temperature": 0.7 }
  },
  "metadata": { "client": "app", "save_history": true }
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

### JSON Schema（SSOT，可机读）

- `POST /api/v1/messages` request：`docs/api-contracts/schemas/message_create_request.schema.json`
- `POST /api/v1/messages` response（202）：`docs/api-contracts/schemas/message_create_response.schema.json`

### create_message 请求体白名单（SSOT）与冲突/优先级规则

顶层字段白名单（**额外字段一律 422**，`additionalProperties=false`）：
- `model`（必填）
- `text` / `messages`（至少一个；payload 模式除外）
- `conversation_id`（可选，UUID；null/缺省表示由服务端生成）
- `metadata`（可选，object；不做字段白名单）
- `skip_prompt`（可选；默认 false）
- `system_prompt` / `tools` / `tool_choice` / `temperature` / `top_p` / `max_tokens`（可选，OpenAI 兼容透传）
- `dialect` + `payload`（可选；payload 模式专用）

模式与语义（以服务端实现为准）：
- **server 模式**（默认，`skip_prompt=false`）：服务端注入默认 system prompt；并**忽略**客户端 `messages[].role=system`（防绕过）。
- **passthrough 模式**（`skip_prompt=true`）：服务端不注入默认 prompt/tools，完整透传 `messages/tools/...`。
  - 若 `system_prompt` 非空且 `messages` 内**没有** `role=system`：服务端会将 `system_prompt` 作为首条 system message 注入。
  - 若 `system_prompt` 非空且 `messages` 内**存在** `role=system`：**直接 422**（`code=system_prompt_conflict_with_messages_system`），避免歧义。
- **payload 模式**（`payload` 存在）：必须同时提供 `dialect`；且 **禁止混用** `text/messages/system_prompt/tools/tool_choice/temperature/top_p/max_tokens`（否则 422：`code=payload_mode_conflict`）。

兼容兜底（不推荐）：
- 允许把 OpenAI 兼容字段放入 `metadata.chat_request` / `metadata.openai`（仅兜底）；顶层同名字段优先。

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

用途：流式接收模型输出（`content_delta`）与最终结果（`completed`；`upstream_raw` 仅 auto/诊断用）。

### Headers（最小）

- `Authorization: Bearer <redacted>`
- （推荐）`Accept: text/event-stream`
- （推荐）`X-Request-Id: <opaque>`（用于本次 SSE GET 调用追踪；**不参与**与 create_message 的对账）

### Query（可选）

- `conversation_id=<uuid>`：推荐传 `POST /api/v1/messages` 返回值；用于并发控制/归因校验（不匹配会 404）

典型事件（示意）：
- `event: status`：
  - `{"state":"queued|working","message_id":"...","request_id":"..."}`
  - `{"state":"routed","message_id":"...","request_id":"...","provider":"xai","resolved_model":"grok-4-1-fast-reasoning","endpoint_id":123,"upstream_request_id":null}`
- `event: content_delta`：`{"message_id":"...","request_id":"...","seq":1,"delta":"..."}`
- `event: upstream_raw`：`{"message_id":"...","request_id":"...","seq":1,"dialect":"openai.chat_completions","upstream_event":null,"raw":"..."}`
- `event: completed`：`{"message_id":"...","request_id":"...","reply_len":1234,"reply_snapshot_included":false,"result_mode_effective":"raw_passthrough|xml_plaintext","provider":"...","resolved_model":"...","endpoint_id":123,"upstream_request_id":"...|null","metadata":null}`
- `event: error`：`{"message_id":"...","request_id":"...","code":"...","message":"...","error":"...","provider":"...|null","resolved_model":"...|null","endpoint_id":123|null}`
- `event: heartbeat`：`{"message_id":"...","request_id":"...","ts":1736253242000}`

> `result_mode=xml_plaintext` 时，reply **只能**由 `content_delta.delta` 拼接得到（Strict-XML / ThinkingML v4.5），结构契约见：`docs/ai预期响应结构.md`。  
> `result_mode=raw_passthrough` 时，reply 同样只能以 `content_delta.delta` 拼接为准（透明转发 token 文本，不做 XML/ThinkingML 修复）。  
> `completed` **不再**返回 `reply` 全文；`reply_len` 仅用于统计/校验参考（不保证逐字一致）。

### SSE 事件字典（SSOT，可机读）

SSE 是 `text/event-stream`，每一帧可等价视为：
```json
{ "event": "<eventType>", "data": { ... } }
```
其 JSON Schema（含 `additionalProperties`、必填/可选字段）见：`docs/api-contracts/schemas/message_sse_frame.schema.json`。

### 终止条件（SSOT）

- 正常结束：服务端发送 `event: completed` 后关闭连接（无 `[DONE]` 语义）。
- 失败结束：服务端发送 `event: error` 后关闭连接；若通道异常关闭且未出现终止事件，服务端会**尽力补发** `event: error`（可能 `code=sse_stream_closed_without_terminal_event`）。
- 例外：若客户端提前断开连接，服务端无法保证客户端一定收到终止事件。

### Header + request_id 对账规则（SSOT）

- `request_id` 的来源：以 **create_message 的 Request ID** 为准（`POST /api/v1/messages` 的 `X-Request-Id`；未传则由服务端生成）。
- SSE 对账：`status/content_delta/completed/error/heartbeat` 的 `data.request_id` 与 create_message 的 `X-Request-Id` 对齐；用于“创建请求 ↔ SSE 结果”的端到端关联。
- `GET /events` 的 `X-Request-Id` 仅用于本次 SSE GET 调用追踪（与上面的对账无关）。

### 最小可用样例（可复制）

创建消息（server 模式）：
```http
POST /api/v1/messages HTTP/1.1
Authorization: Bearer <redacted>
Content-Type: application/json
X-Request-Id: req_demo_001

{"model":"global:xai","text":"hello","conversation_id":null,"metadata":{"client":"app"},"skip_prompt":false}
```

响应（202）：
```json
{"message_id":"0123456789abcdef0123456789abcdef","conversation_id":"11111111-2222-3333-4444-555555555555"}
```

SSE transcript（节选）：
```text
event: status
data: {"state":"queued","message_id":"0123456789abcdef0123456789abcdef","request_id":"req_demo_001"}

event: status
data: {"state":"working","message_id":"0123456789abcdef0123456789abcdef","request_id":"req_demo_001"}

event: status
data: {"state":"routed","message_id":"0123456789abcdef0123456789abcdef","request_id":"req_demo_001","provider":"xai","resolved_model":"grok-4-1-fast-reasoning","endpoint_id":123,"upstream_request_id":null}

event: content_delta
data: {"message_id":"0123456789abcdef0123456789abcdef","request_id":"req_demo_001","seq":1,"delta":"Hello"}

event: completed
data: {"message_id":"0123456789abcdef0123456789abcdef","request_id":"req_demo_001","provider":"xai","resolved_model":"grok-4-1-fast-reasoning","endpoint_id":123,"upstream_request_id":null,"reply_len":5,"reply_snapshot_included":false,"result_mode_effective":"raw_passthrough","metadata":null}
```

### 常见“只有 status/heartbeat 无内容”的原因（后端侧）

- 上游请求仍在进行（长推理/网络抖动/超时较大）：短期只看到 `heartbeat`；最终应出现 `completed` 或 `error`。
- 上游无可用 endpoint / key / 全部 offline：通常会尽快 `event: error`（多见 `code=provider_error`，`message=no_active_ai_endpoint`）。
- 流式分片被最小缓冲（ThinkingML 前缀识别/flush）：可能出现短时间没有 `content_delta`，随后补发 `content_delta` 并 `completed`。
- 通道异常关闭：服务端会尽力补发 `event: error`（`code=sse_stream_closed_without_terminal_event`），然后断开。
- 客户端过早断开：服务端进入 `client_disconnected` 路径，客户端可能只看到最后一次 `heartbeat`。
