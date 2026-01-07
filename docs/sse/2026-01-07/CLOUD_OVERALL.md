# GymBro Cloud：模型映射 + 多方言请求体 + SSE 规范化（v1）

## 0. 目标（Why）
- 解决“请求体混乱”：明确 Cloud 接收哪些输入、如何映射、如何流式输出。
- 对外 SSE 行为稳定：App/Web 只需要实现一种消费方式（GymBro SSE）。

## 1. 分界线（Cloud 的职责边界）
Cloud 负责：
1) JWT 校验（Bearer）与 Entitlement gate
2) Model Mapping（mapped → provider real model + dialect + baseUrl + apiKeyRef）
3) Provider Adapter：构建请求、调用上游、解析上游流式帧
4) 向下游（App/Web）输出统一 SSE（status/content_delta/completed/error/heartbeat）
5) 并发守卫（user+conversation）与心跳
6)（可选）seed/动作库数据的远程版本化分发

Cloud 不负责：
- 客户端 UI 状态管理
- 客户端本地历史落库策略
- 用户自带 apiKey 的保管（直连模式下由客户端持有）

## 2. Cloud 对外 API（最小集合）
- GET `/api/v1/llm/models`（建议 `view=mapped`）
- POST `/api/v1/messages`
- GET `/api/v1/messages/{message_id}/events`（SSE）
- （建议新增）GET `/api/v1/seed/manifest` + GET `/api/v1/seed/files/{name}`

## 3. /messages：两种输入模式（关键）
### 3.1 GymBro SSOT 模式（默认）
- `text`（server prompt）
- 或 `messages/system/tools/...`（passthrough）
- `skip_prompt` 决定 server 是否注入默认 prompt 与 system role 过滤策略

### 3.2 Provider Payload 模式（新增，用于“请求体不再混乱”）
- `dialect`: `openai.chat_completions | openai.responses | anthropic.messages | gemini.generate_content`
- `payload`: provider 原生 request JSON
- `model`: 仍必须是 mapped model（用于路由到 registry；禁止用户直接指定真实 model/baseUrl）

服务端策略：
- 仍强制 `stream=true`（或等价）
- 仍走同一条 broker → SSE 输出链路
- payload 只允许白名单字段（防止越权/注入）

## 4. Provider Adapter 规范（需要落地的 4 套）
### 4.1 OpenAI Chat Completions
- Endpoint：`POST {baseUrl}/v1/chat/completions`
- Stream：SSE，chunk 里一般在 `choices[].delta.content`

### 4.2 OpenAI Responses
- Endpoint：`POST {baseUrl}/v1/responses`
- Stream：SSE events（多 event type），需从 delta 事件抽取文本并在 completed 结束

### 4.3 Anthropic Messages
- Endpoint：`POST https://api.anthropic.com/v1/messages`
- Headers：`x-api-key` + `anthropic-version`
- Stream：SSE，content_block_delta 等事件输出增量

### 4.4 Gemini streamGenerateContent
- Endpoint：`POST https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse`
- Stream：SSE，chunk 里一般在 `candidates[0].content.parts[0].text`

## 5. Cloud SSE 输出（对外唯一 SSOT）
输出必须满足：
- 单行 `data:`（避免客户端按行解析丢 JSON）
- 最小事件集合：`status` / `content_delta` / `completed` / `error` / `heartbeat`
- 终止语义：一定要发 completed 或 error（连接关闭不算完成）

推荐 payload 形状：
- `status`: `{"state":"queued|working","message_id":"...","request_id":"..."}`
- `content_delta`: `{"delta":"...","seq":123,"message_id":"...","request_id":"..."}`
- `completed`: `{"message_id":"...","request_id":"...","usage":{...},"provider":"..."}`
- `error`: `{"code":"...","message":"...","request_id":"..."}`
- `heartbeat`: `{"ts": "...", "request_id":"..."}`

## 6. 种子文件/动作库远程更新（需要澄清的契约）
建议（如当前已实现请对齐口径）：
- manifest 返回：version, sha256, files[], updated_at
- file 下载支持：ETag/If-None-Match；支持增量/灰度；失败回滚