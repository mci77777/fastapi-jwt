# App 端 SSE（流式 + RAW）响应结构体与近期 E2E 样本（SSOT）

面向：移动端 / Web 端消费 `GET /api/v1/messages/{message_id}/events`（`Content-Type: text/event-stream`）。

> 结构 SSOT：
> - 服务端事件：`app/services/ai_service.py::MessageEventBroker.publish()` + `app/api/v1/messages.py::stream_message_events()`
> - ThinkingML 输出结构：`docs/ai预期响应结构.md`
> - App 最小 API 契约：`docs/api-contracts/api_gymbro_cloud_app_min_contract.md`

---

## 1) 你最终会“收到什么”（手机端视角）

手机端接收的是 **SSE 行协议**（RAW）：

```text
event: <event_name>
data: <one-line-json>

```

其中 `<event_name>` 是 GymBro 自定义事件（统一对外）：`status` / `content_delta` / `upstream_raw` / `completed` / `error` / `heartbeat`。

> 重要：**最终答案（reply）优先由 `content_delta.delta` 流式拼接得到（SSOT）**；`completed.reply` 仅作兜底（例如晚订阅/漏订阅）。

---

## 1.1 SSE 输出模式（SSOT）

`POST /api/v1/messages` 可指定 `result_mode`（创建消息时固化，订阅侧只读）：

- `xml_plaintext`：服务端解析上游响应，向 App 发送 `content_delta`（`delta` 为纯文本，允许包含 XML 标签如 `<final>...</final>`）。
- `raw_passthrough`：服务端透明转发上游 RAW，向 App 发送 `upstream_raw`（App 侧可自行回放/解析；仍会收到 `completed/error` 终止事件）。
- `auto`：服务端自动判定（优先 `xml_plaintext`；若长期无法产出 `content_delta`，则降级为 `raw_passthrough`）。

---

## 2) 事件结构体（JSON 形状，App 端建议实现）

### 2.1 通用字段（服务端自动补齐）

所有事件 `data` 都会尽力包含：

- `message_id: string`（opaque）
- `request_id: string`（与请求头 `X-Request-Id` 对账；若未提供则服务端生成）

### 2.2 TypeScript（建议）

```ts
export type GymBroSseEventName =
  | "status"
  | "content_delta"
  | "upstream_raw"
  | "completed"
  | "error"
  | "heartbeat";

export type GymBroSseEnvelope =
  | { event: "status"; data: StatusEventData }
  | { event: "content_delta"; data: ContentDeltaEventData }
  | { event: "upstream_raw"; data: UpstreamRawEventData }
  | { event: "completed"; data: CompletedEventData }
  | { event: "error"; data: ErrorEventData }
  | { event: "heartbeat"; data: HeartbeatEventData };

export interface StatusEventData {
  message_id: string;
  request_id?: string;
  state: "queued" | "working" | "routed";
  // routed 后通常会带上这些字段（便于对账“映射模型”结果）
  provider?: string | null;
  resolved_model?: string | null;
  endpoint_id?: number | null;
  upstream_request_id?: string | null;
}

export interface ContentDeltaEventData {
  message_id: string;
  request_id?: string;
  seq: number; // 从 1 开始单调递增
  delta: string; // 追加到 reply_text
}

export interface UpstreamRawEventData {
  message_id: string;
  request_id?: string;
  seq: number; // 从 1 开始单调递增（RAW 序列）
  dialect?: string | null; // openai.chat_completions/openai.responses/anthropic.messages/gemini.generate_content
  upstream_event?: string | null; // 上游 SSE 的 event 名（若上游未使用 event 行则为 null）
  raw: string; // 上游 data 文本（不含 "data:" 前缀）
}

export interface CompletedEventData {
  message_id: string;
  request_id: string;
  provider: string | null;
  resolved_model: string | null;
  endpoint_id: number | null;
  upstream_request_id: string | null;
  result_mode?: string | null; // 客户端请求的 result_mode（创建时固化）
  result_mode_effective?: string | null; // auto 模式的最终判定（或与 result_mode 相同）
  reply: string; // 兜底全文（客户端仍建议优先拼接 content_delta）
  reply_len: number;
  metadata: Record<string, unknown> | null; // provider 侧额外信息（可选）
}

export interface ErrorEventData {
  message_id: string;
  request_id: string;
  code: string;
  message: string;
  error: string; // legacy：兼容旧客户端（与 message 语义一致）
  provider: string | null;
  resolved_model: string | null;
  endpoint_id: number | null;
}

export interface HeartbeatEventData {
  message_id: string;
  request_id: string;
  ts: number; // ms
}
```

---

## 3) “流式 + 原始内容”的落地方式（推荐）

移动端建议同时维护两份 SSOT：

1. **流式文本 SSOT**：`reply_text = concat(content_delta.delta by seq)`
2. **RAW SSOT**（用于对账/回放/上报）：`raw_frames[] = ["event: ...\\ndata: ...\\n\\n", ...]`

兜底策略：
- 若只收到 `completed`（未收到 `content_delta`），则用 `completed.reply` 作为 `reply_text`。
- 若收到 `error`，本次对话以失败终止（即使之前已收到部分 `content_delta`）。

---

## 4) 近期完成的 E2E 样本（含 prompt 注入）与“映射模型”结果标注

> 说明：以下样本均来自仓库内已产出的 E2E artifacts（可直接作为“手机端真实收到的 RAW 示例”对照）。

### 4.1 样本清单（建议 App 侧按此对账字段）

| 日期 | prompt_mode | 请求 model（App 传入） | 终止事件 | provider | resolved_model | endpoint_id | artifacts |
|---|---|---|---|---|---|---:|---|
| 2026-01-09 | server | `gpt`（recommended） | `completed` | `openai` | `gpt-5.2` | 31 | `e2e/anon_jwt_sse/artifacts/anon_e2e_trace_20260109_124732_server_default_fixed.txt` |
| 2026-01-09 | passthrough | `claude-sonnet-4-5-thinking` | `completed` | `openai` | `claude-sonnet-4-5-20250929` | 31 | `e2e/anon_jwt_sse/artifacts/anon_e2e_trace_20260109_124106_passthrough_2models.txt` |
| 2026-01-09 | passthrough | `xai` | `error` | `null` | `null` | `null` | `e2e/anon_jwt_sse/artifacts/anon_e2e_trace_20260109_124106_passthrough_2models.txt` |
| 2026-01-04 | server | `global:xai` | `completed` | `xai` | `grok-4-1-fast-reasoning` | 28 | `e2e/real_user_sse/artifacts/xai_mapped_model_trace_35366fdc3df84394a43b4cd0bef4fc58.json` |

### 4.2 RAW（SSE 行协议）示例：`completed`

来自：`e2e/anon_jwt_sse/artifacts/anon_e2e_trace_20260109_124732_server_default_fixed.txt`（server 模式，默认 prompt 注入）

```text
event: content_delta
data: {"delta":"<thinking>\n","message_id":"0ffae7ec7fdf40b48f3ccd814560df1b","request_id":"7f317393-24fe-4229-bef9-208cede90b6b","seq":1}

event: completed
data: {"message_id":"0ffae7ec7fdf40b48f3ccd814560df1b","request_id":"7f317393-24fe-4229-bef9-208cede90b6b","provider":"openai","resolved_model":"gpt-5.2","endpoint_id":31,"upstream_request_id":null,"reply":"<thinking>\n<phase id=\"1\">\n<title>理解与回应</title>\n...（略）...\n</final>","reply_len":416,"metadata":null}
```

### 4.3 RAW（SSE 行协议）示例：passthrough + prompt 注入（输出尖括号标签）

来自：`e2e/anon_jwt_sse/artifacts/anon_e2e_trace_20260109_124106_passthrough_2models.txt`

```text
event: content_delta
data: {"delta":"<thinking>\n用","message_id":"f5a03dc5a6d240afa2a4fe6ce77328eb","request_id":"5bccf6cd-ca32-4254-8c0d-42e8a5be803d","seq":1}

event: completed
data: {"message_id":"f5a03dc5a6d240afa2a4fe6ce77328eb","request_id":"5bccf6cd-ca32-4254-8c0d-42e8a5be803d","provider":"openai","resolved_model":"claude-sonnet-4-5-20250929","endpoint_id":31,"upstream_request_id":null,"reply":"<thinking>\n...（略）...\n</final>","reply_len":132,"metadata":null}
```

### 4.4 RAW（SSE 行协议）示例：`error`（终止）

来自：`e2e/anon_jwt_sse/artifacts/anon_e2e_trace_20260109_124106_passthrough_2models.txt`

```text
event: error
data: {"code":"internal_error","message":"Client error '403 Forbidden' for url 'https://api.x.ai/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403","error":"Client error '403 Forbidden' for url 'https://api.x.ai/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403","provider":null,"resolved_model":null,"endpoint_id":null,"message_id":"c48cf46dd2b146b08d75406ba228d852","request_id":"75820944-acfe-4656-acc1-1a45536c9e1e"}
```

---

## 5) App 端最容易踩坑的 3 点（务必对齐）

1. **自定义事件监听**：若用 `EventSource`，必须 `addEventListener('content_delta'|'completed'|...)`，否则会“看起来没流”。  
2. **301/302 会破坏 SSE/POST**：网关重定向 `/api/v1/messages` 可能导致 POST 丢失/断连；对照 `deploy/web.conf`。  
3. **结构校验**：拼接后的 `reply_text` 的 ThinkingML 规则见 `docs/ai预期响应结构.md`；server 模式默认应满足 v4.5。
