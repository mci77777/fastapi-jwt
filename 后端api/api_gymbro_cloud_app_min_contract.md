# api.gymbro.cloud「App 端对接」最小契约（模型列表 / 选型 / 发送消息）

生成日期：2025-12-31  
适用场景：App 端（Coach / gymbro_cloud）接入云端模型能力：拉取可用模型 → 选择并持久化 → 发送消息（最小字段）→ SSE 获取流式结果。

> 重要约束：
> - `POST /api/v1/messages` 的 **Body 顶层禁止额外字段**（`additionalProperties=false` / `extra="forbid"`）。  
> - 允许把扩展信息放在 `metadata` 里（`metadata` 是自由对象）。  
> - 示例中的 `Authorization` 只写 `<redacted>`，不要把真实 token 写进文档/日志。

---

## 0) 基础约定

- Base URL：`https://api.gymbro.cloud`
- API 前缀：`/api/v1`
- 命名：服务端字段使用 `snake_case`
- 认证：除公开端点外均要求 `Authorization: Bearer <redacted>`
- 请求追踪：建议每次 HTTP 调用都传 `X-Request-Id: <opaque>`（服务端会在响应头/错误体回传同名 `request_id`，便于端到端对账）
- 通用响应包装（非 SSE）：
  - `{"code": 200, "msg": "success", "data": ..., "total": ..., "page": ..., "page_size": ...}`

### 名词表（SSOT）

- `request_id`：单次 HTTP 请求的追踪 ID（对应 Header：`X-Request-Id`；一次调用一个，不是会话 ID）
- `message_id`：单条消息 ID（`POST /api/v1/messages` 返回；用于 `GET /api/v1/messages/{message_id}/events`）
- `conversation_id`：云端会话 ID（UUID；由服务端生成并回传；用于并发控制/归因，非必传）
- `client_session_id`：App 本地会话 ID（形如 `msg_xxx`；只用于本地路由/历史，**不要**当作 `conversation_id` 传）
- `client_message_id`：App 本地消息 ID（建议放在 `metadata.client_message_id` 用于对账）

### 后端交接清单（SSOT）

后端对齐要求（`request_id` 回传规则 / OpenAI & Claude 兼容策略）见：`后端api/api_gymbro_cloud_conversation_min_contract.md`。

---

## 1) 拉取“映射后的标准模型列表”（默认）：`GET /api/v1/llm/models`

用途：Coach 顶栏“云端模型”菜单拉取列表并展示给用户选择；只展示“映射后的标准模型”（如 `claude/deepseek/grok/gpt`），避免暴露/依赖具体 provider 的 `model_list`。

### Query（可选）

- `view`：默认 `mapped`（返回映射模型）；管理后台如需 endpoint 列表用 `view=endpoints`
- `scope_type`：默认 `tenant`（当 `view=mapped` 时可选 `user/tenant/global/prompt`）
- `only_active`：当 `view=mapped` 时生效（是否仅返回激活映射；默认按 `true` 处理）

### Response（成功）

```json
{
  "code": 200,
  "msg": "success",
  "data": [
    {
      "name": "grok",
      "scope_type": "tenant",
      "scope_key": "grok",
      "default_model": "grok-4-1-fast-reasoning",
      "candidates": ["grok-4-1-fast-reasoning"],
      "candidates_count": 1,
      "updated_at": "2025-12-27T07:12:08+00:00"
    }
  ],
  "total": 1
}
```

备注：

- 管理后台如需 endpoint 列表（包含 base_url、model_list 等），使用 `GET /api/v1/llm/models?view=endpoints`。

建议持久化字段（App 本地，如 `coach_cloud_model`）：

- `selected_model_name`：使用上面的 `data[].name`（如 `grok` / `deepseek` / `gpt` / `claude`）
- （可选）`selected_default_model`：用于 UI 展示（不作为调用依据）

---

## 2) 后端“SSOT 选型结果”查询：`GET /api/v1/llm/model-selection`

用途：App 端需要“后端最终会选哪个 model/endpoint”的 **权威结果**（用于 UI 展示、排障、或作为发送前的建议）。

### Query（可选）

- `tenant_id`：租户（如果你的 App 侧有租户概念）
- `prompt_id`：指定 prompt（如果你的 App 侧会绑定某个 prompt）

### Response（成功）

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "model": "grok-4-1-fast-reasoning",
    "model_source": "mapping",
    "temperature": null,
    "mapping": {
      "hit": null,
      "chain": [],
      "reason": "mapping_not_found"
    },
    "endpoint": { "id": 2, "name": "openai_compat_xxx" },
    "endpoint_reason": null
  }
}
```

说明：

- `model_source`：
  - `mapping`：来自模型映射（SSOT：model-mapping）
  - `endpoint_default`：映射未命中时，回退到默认 endpoint 的模型（SSOT：ai_endpoints）

---

## 3) 发送消息（最小字段）：`POST /api/v1/messages`

用途：gymbro_cloud 发送对齐最小契约：只发 `text/conversation_id/metadata/skip_prompt`，并通过 `metadata` 携带 `model/system_prompt/tools/function_call`。

### Headers

- `Authorization: Bearer <redacted>`
- `Content-Type: application/json`

### Request Body（最小字段）

```json
{
  "text": "用户输入（最后一条 user message）",
  "conversation_id": "string(uuid) | null",
  "metadata": {
    "model": "grok-4-1-fast-reasoning",
    "system_prompt": "string（建议截断到 2k）",
    "tools": ["tool_name_a", "tool_name_b"],
    "function_call": "auto"
  },
  "skip_prompt": false
}
```

字段说明：

- `text`：必填（当你不传 `messages` 顶层字段时）。  
- `conversation_id`：**仅当是 UUID 才建议传**；如果你的客户端侧是 `msg_xxx` 这类非 UUID，直接省略/传 `null`，由服务端生成并回传。  
- `metadata.model`：App 端“用户选择的模型字符串”。服务端会按 SSOT（endpoint active + api_key + resolved_endpoints）匹配并调用对应 provider。  
- 推荐：传 `GET /api/v1/llm/models`（默认 `view=mapped`）返回的 `data[].name`（映射名/别名，如 `grok` / `deepseek` / `gpt` / `claude`），服务端会解析为该映射的 `default_model` 再去选 endpoint。  
- `metadata.system_prompt`：App 端的 system prompt（如你需要完全控制提示词）。服务端会将其作为 system message 透传到上游（覆盖默认 prompt）。  
- `metadata.tools`：支持两种形态：
  - `string[]`：**工具名白名单**（服务端将过滤 prompt.tools_json，只保留同名工具；不直接作为上游 tools schema）。  
  - `object[]`：OpenAI 兼容的 `tools` schema（服务端会直接透传为上游 `tools`）。  
- `metadata.function_call`：legacy 形态（`"auto"|"none"|{"name":"xxx"}`），服务端会映射为上游 `tool_choice`。  
- `skip_prompt`：是否跳过后端默认 prompt（一般保持 `false`；若 `true`，服务端不会注入默认 prompt）。

### Response（创建成功，异步）

```json
{
  "message_id": "32位hex字符串",
  "conversation_id": "uuid字符串"
}
```

> `message_id` 用于后续 SSE 订阅：`GET /api/v1/messages/{message_id}/events`

---

## 4) SSE 订阅：`GET /api/v1/messages/{message_id}/events`

用途：流式接收模型输出（`content_delta` 增量 + `completed` 完整结果）。

### 典型事件（示意）

- `event: status`：`{"state":"queued|working","message_id":"..."}`
- `event: content_delta`：`{"message_id":"...","delta":"..."}`
- `event: completed`：`{"message_id":"...","reply":"..."}`
- `event: error`：`{"message_id":"...","error":"...","reason":"..."}`

> 连接关闭：服务端在任务结束（成功或失败）后会关闭 channel，SSE 连接自然结束；不是异常断开。
