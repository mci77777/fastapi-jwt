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
- GET `/api/v1/seed/manifest`
- GET `/api/v1/seed/files/{name}`（当前实现：`exercise_library`）

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
当前实现（SSOT：`/api/v1/seed/manifest` + `/api/v1/exercise/library/*`）：
- `seed/manifest`：返回资源列表（name/version/checksum/download_url/增量策略）
- `exercise/library/full`：支持 `?version=` 并返回 `ETag`；客户端可用 `If-None-Match` 命中 `304`
- 回滚策略：客户端可“钉住旧版本”（使用 `downloadUrl` 或 `?version=`），或增量失败时回退 full

## 7. 联调 / E2E 验收（最小闭环）

对齐口径（SSOT）：
- AI 输出结构：`docs/ai预期响应结构.md`
- Quick Start：`docs/e2e-ai-conversation/QUICK_START.md`

最小闭环（推荐双方统一验收用例）：
1) `GET /api/v1/llm/models?view=mapped` → 取 `data[].name` 作为 `model`
2) `POST /api/v1/messages` → 得到 `message_id` / `conversation_id`
3) `GET /api/v1/messages/{message_id}/events?conversation_id=...`（SSE）
   - 至少收到 1 次 `content_delta`
   - 最终必须收到 `completed` 或 `error`
   - reply 只能由 `content_delta.delta` 拼接得到；`completed.reply_len` 仅作摘要/长度校验参考

本地可复现（mock 上游，不出网）：
- `.venv/bin/python scripts/monitoring/local_mock_ai_conversation_e2e.py`

真实上游 E2E（xai / deepseek，多轮可配置）：
- `.venv/bin/python scripts/monitoring/real_ai_conversation_e2e.py --models xai deepseek --runs 10 --turns 3 --tool-choice ''`

真实用户 JWT E2E（Supabase，含 JWT 负例 + 结构校验）：
- `.venv/bin/python scripts/monitoring/real_user_ai_conversation_e2e.py --auth-mode signup --models xai deepseek --runs 1 --turns 1 --tool-choice ''`
