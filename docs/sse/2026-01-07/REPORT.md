# SSE 流式链路梳理报告（2026-01-07）

目标：输出一份可与 `gymbro cloud` 后端文档**交叉对照**的材料，覆盖：
- 近期 merge/关键变更（与 SSE/消息链路相关）
- 从用户发消息到后端端点的端到端调用链路（含中间件/并发与限流）
- API contract（App/前端与后端对接的最小 API 集合）
- SSE 帧格式与客户端流式解析方式（Web/E2E 参考实现）
- E2E baseline（最小闭环与现成用例）

> 说明：本文档只固化“现状与契约”；修复设计需等你同步的 `gymbro cloud` 文档对齐后再做。

---

## 1) 近期 Merge/关键变更汇总（main）

> 取 `git log --merges` 的近几次合并 + 与 SSE 高相关的关键非 merge 提交。

### 2026-01-07 · `fd00370` · fix(nginx):avoid-301-for-messages（关键）

- 变更文件：`deploy/web.conf`
- 目的：避免 Nginx 对 `/api/v1/messages`（无尾随 `/`）产生 **301**，导致 **POST 方法丢失/断连**，从而出现“创建消息失败 / SSE 看起来不流”等症状。
- 结论：若线上/网关侧仍存在 `/messages/` → `/messages` 重定向，优先按本提交方式修复 location 匹配。

### 2026-01-07 · `e7c89e0` / `144f887` / `555914e` · Merge branch `feature/user-data-ssot`

- 主要内容：用户数据 SSOT、entitlement gate、mobile routing（`/v1`）等。
- 与 SSE 关联：
  - `app/api/v1/messages.py`：消息创建/订阅链路（SSE 主链路）
  - `app/core/application.py`：路由挂载与中间件顺序（影响鉴权/限流）
  - `app/services/entitlement_service.py`：高级能力门控（避免对主链路产生耦合影响）

### 2026-01-02 · `6aeb722` · merge: jwt测试prompt选项 + sse/anon修复

- 关键变更：
  - `app/core/rate_limiter.py`：SSE `/events` 长连接 **豁免**限流计数（避免 429 重连雪崩）
  - `web/src/api/aiModelSuite.js`：请求体构建对齐后端 schema
- 影响：SSE 连接异常时更可能来自“并发守卫/网关/客户端解析”，而不是 QPS 限流。

---

## 2) 端到端调用链路（用户发送消息 → 后端 → SSE）

### 2.1 前端/客户端入口（本仓库可见）

Web 测试页（参考实现，用于对账与复现）：

- `web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue`
  - 创建消息：`POST /api/v1/messages`
  - 拉流：`GET /api/v1/messages/{message_id}/events?conversation_id=...`
  - 解析：使用 `fetch()` + `ReadableStream.getReader()` 手写 SSE 行协议解析，累计 `content_delta`，遇到 `completed/error` 结束。

请求体构建（与后端 schema 对齐的 SSOT 入口）：

- `web/src/api/aiModelSuite.js::createMessage`
  - 顶层字段为 SSOT；`metadata` 承载扩展信息。
  - `promptMode=server|passthrough` 决定 `skip_prompt` 与 system role 过滤策略。

### 2.2 后端链路（FastAPI）

#### (1) 入口与中间件链

- `app/core/application.py::create_app()`
  - `RequestIDMiddleware`：`app/core/middleware.py`（SSOT：`X-Request-Id`）
  - `PolicyGateMiddleware`：`app/core/policy_gate.py`（匿名白名单允许 `/api/v1/messages` 与 `/events`）
  - `RateLimitMiddleware`：`app/core/rate_limiter.py`（SSE `/events` 豁免 QPS 计数）

#### (2) 创建消息（异步任务 + broker）

- `app/api/v1/messages.py::create_message`
  - 生成 `message_id`（opaque）+ `conversation_id`（UUID）
  - `MessageEventBroker.create_channel()` 固化 owner/conversation（订阅侧只校验，不推导）
  - `BackgroundTasks` 调度 `AIService.run_conversation(...)`（绑定 request_id，保证 SSE 对账一致）

#### (3) 事件 SSOT：broker 发布与终止固化

- `app/services/ai_service.py::MessageEventBroker`
  - `publish()`：将事件写入队列；对 `completed/error` 固化 `terminal_event`（用于“晚订阅兜底”）
  - `close()`：写入 `None` 关闭 channel

#### (4) SSE 拉流：并发守卫 + 心跳 + 终止兜底

- `app/api/v1/messages.py::stream_message_events`
  - 并发守卫：`app/core/sse_guard.py`（同用户同 conversation 默认 1 条活跃 SSE）
  - 心跳：`SSE_HEARTBEAT_SECONDS`（默认 5s）
  - 终止兜底：若未收到 `completed/error` 而 channel 关闭/断连，尽力补发 fallback `error`（便于客户端“明确失败”）

---

## 3) API Contract（App/前端与后端对接的最小 API 集合）

仓库内 SSOT（避免复制漂移）：

- `docs/api-contracts/api_gymbro_cloud_app_min_contract.md`
- `docs/api-contracts/api_gymbro_cloud_conversation_min_contract.md`

本链路最小集合：

1) 模型白名单（强约束，`model` 必须来自白名单）
- `GET /api/v1/llm/models`（App 侧建议只用 `view=mapped`）
- `GET /api/v1/llm/app/models`（Web 测试页在用）

2) 创建消息（异步任务）
- `POST /api/v1/messages`

3) SSE 拉流
- `GET /api/v1/messages/{message_id}/events?conversation_id=<uuid?>`

---

## 4) SSE 帧格式与客户端流式解析

### 4.1 服务端帧格式（当前实现）

- `Content-Type: text/event-stream`
- 每条事件：
  - `event: <eventType>`
  - `data: <json>`
  - 空行结束

事件最小集合：`status` / `content_delta` / `completed` / `error` / `heartbeat`。

### 4.2 客户端解析（本仓库可见参考实现）

- Web（fetch reader）：`web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue::streamSse`
- Python E2E（httpx lines）：`scripts/monitoring/real_user_sse_e2e.py::consume_sse`
- 测试解析器：`tests/test_request_id_ssot_e2e.py::_collect_sse_events`

### 4.3 与 App 端对齐的高风险点（重点）

1) **EventSource 默认只分发 `message`**：若服务端使用 `event: content_delta`，App 必须 `addEventListener('content_delta', ...)`，否则会“看起来没流”。  
2) **301/302 重定向会破坏 SSE/POST**：网关若把 `/api/v1/messages` 重定向（尤其 POST），会出现断连/方法丢失；需按 `deploy/web.conf` 修复 location 规则。  
3) **运行时对 fetch 流式支持不一致**：部分移动端/WebView 不支持 `ReadableStream`，需 SSE 专用库或降级策略。

---

## 5) E2E baseline（推荐双方对齐的验收用例）

### 5.1 最小闭环（联调验收）

1. `GET /api/v1/llm/models` → 取 `data[].name` 作为 `model`
2. `POST /api/v1/messages`（带 `X-Request-Id`）→ 得到 `message_id`/`conversation_id`
3. `GET /api/v1/messages/{message_id}/events?conversation_id=...`（SSE）
   - 至少收到 1 次 `content_delta`（或允许“晚订阅只收到 completed”，需双方明确）
   - 最终必须收到 `completed` 或 `error`
   - `completed/error.data.request_id` 与 Header `X-Request-Id` 对账一致

### 5.2 现成用例/脚本（本仓库）

- 合约/解析：`tests/test_request_id_ssot_e2e.py`
- 真用户：`scripts/monitoring/real_user_sse_e2e.py`（需环境变量）
- 匿名套件：`e2e/anon_jwt_sse/README.md`

---

## 6) 等待 gymbro cloud 与 App 文档对齐的确认清单（用于后续修复设计）

- 事件命名：服务端是否自定义 `event:`（`content_delta/completed/error/...`）？App 订阅是否一致？
- 解析方式：App 用 `EventSource` 还是 `fetch` 流？是否支持自定义事件监听？
- 终止条件：以 `completed` 结束还是以连接关闭结束？是否允许“晚订阅只拿到 completed/error”？
- 网关行为：是否存在 `/messages` 相关重定向或缓冲（需验证 `proxy_buffering off` 等是否生效）？
- 心跳/超时：`SSE_HEARTBEAT_SECONDS` 与客户端超时策略是否匹配？

