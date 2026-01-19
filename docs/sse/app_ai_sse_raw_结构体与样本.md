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
**App 端最小必实现集合（推荐）**：`status` / `content_delta` / `completed` / `error` / `heartbeat`（`upstream_raw` 仅用于调试/诊断，可忽略）。

> 重要：**最终答案（reply_text）只能由 `content_delta.delta` 流式拼接得到（SSOT）**；`completed` 不再返回 `reply` 全文。

---

## 1.1 SSE 输出模式（SSOT）

`POST /api/v1/messages` 可指定 `result_mode`（创建消息时固化，订阅侧只读；**App 端默认不传**）：

- **默认值**：当客户端未显式传 `result_mode` 时，服务端使用持久化配置 `llm_app_settings.default_result_mode`（可由管理端 `POST /api/v1/llm/app/config` 设置）；未配置时回退 `raw_passthrough`。
- `raw_passthrough`（默认）：服务端解析上游响应并提取 token 文本，按原样以 `content_delta` 流式输出（不做 ThinkingML 纠错/标签归一化）。
- `xml_plaintext`：服务端解析上游响应并以 `content_delta` 流式输出，同时做 ThinkingML 最小纠错/标签归一化，保证结构契约稳定（允许包含 `<final>...</final>` 等 XML 标签）。
- `auto`：服务端自动判定（优先 `xml_plaintext`；若无法产出 `content_delta`，则降级为 `raw_passthrough`；必要时可能产生 `upstream_raw` 诊断帧）。

> 提示：**透明转发 / XML 文本转发**都走 SSE `event: content_delta`；`upstream_raw` 仅用于 `auto`/诊断（可忽略）。

### 1.2 现状：后端会“拆分转发”超长块（避免单个超长 SSE 事件）

问题场景（历史）：上游可能一次性返回一整段大文本（例如 3k+ chars），若后端直接透传为单个 `content_delta`/`upstream_raw`，App 侧会呈现“像单个大 token 一次性到达”，无法体现流式体验。

现状（已落地的服务端兜底策略）：
- 对 `content_delta.delta` 与 `upstream_raw.raw`：当单次字段长度 > `256` 字符时，服务端会在 SSE 输出前按断点优先拆分为多个事件，每块目标大小约 `128` 字符。
- 拆分仅影响“分帧”，**不会改变最终拼接后的全文语义**；客户端按 `seq`（或到达顺序）拼接即可还原。
- 断点优先级：`\n` → `。？！` → `.?!` → 空格/制表符 → 固定位置兜底。

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
  delta: string; // 追加到 reply_text（可能被服务端拆分为多段）
}

export interface UpstreamRawEventData {
  message_id: string;
  request_id?: string;
  seq: number; // 从 1 开始单调递增（RAW 序列）
  dialect?: string | null; // openai.chat_completions/openai.responses/anthropic.messages/gemini.generate_content
  upstream_event?: string | null; // 上游 SSE 的 event 名（若上游未使用 event 行则为 null）
  raw: string; // 上游 data 文本（不含 "data:" 前缀；可能被服务端拆分为多段）
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
  reply_len: number;
  reply_snapshot_included: boolean; // 固定为 false（不下发 reply 全文）
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

## 3) “流式内容”的落地方式（App 最小实现）

移动端最小建议只维护 1 份 SSOT：

1. **流式文本 SSOT**：`reply_text = concat(content_delta.delta by seq)`

可选（仅调试/诊断）：若你需要对账上游 RAW，可额外维护 `raw_frames[]`（依赖 `upstream_raw` 事件；App 端通常不需要实现）。

兜底策略：
- 若只收到 `completed`（未收到 `content_delta`），应视为异常（已无 `reply` 全文可还原）；建议重试并上报 `request_id`。
- 若收到 `error`，本次对话以失败终止（即使之前已收到部分 `content_delta`）。

> 注意：App 侧默认不传 `result_mode`，服务端默认使用持久化配置（未配置则 `raw_passthrough`）；因此正常只需要处理 `content_delta`。

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
data: {"message_id":"0ffae7ec7fdf40b48f3ccd814560df1b","request_id":"7f317393-24fe-4229-bef9-208cede90b6b","provider":"openai","resolved_model":"gpt-5.2","endpoint_id":31,"upstream_request_id":null,"reply_len":416,"reply_snapshot_included":false,"result_mode_effective":"xml_plaintext","metadata":null}
```

### 4.3 RAW（SSE 行协议）示例：passthrough + prompt 注入（输出尖括号标签）

来自：`e2e/anon_jwt_sse/artifacts/anon_e2e_trace_20260109_124106_passthrough_2models.txt`

```text
event: content_delta
data: {"delta":"<thinking>\n用","message_id":"f5a03dc5a6d240afa2a4fe6ce77328eb","request_id":"5bccf6cd-ca32-4254-8c0d-42e8a5be803d","seq":1}

event: completed
data: {"message_id":"f5a03dc5a6d240afa2a4fe6ce77328eb","request_id":"5bccf6cd-ca32-4254-8c0d-42e8a5be803d","provider":"openai","resolved_model":"claude-sonnet-4-5-20250929","endpoint_id":31,"upstream_request_id":null,"reply_len":132,"reply_snapshot_included":false,"result_mode_effective":"raw_passthrough","metadata":null}
```

### 4.4 RAW（SSE 行协议）示例：`error`（终止）

来自：`e2e/anon_jwt_sse/artifacts/anon_e2e_trace_20260109_124106_passthrough_2models.txt`

```text
event: error
data: {"code":"internal_error","message":"Client error '403 Forbidden' for url 'https://api.x.ai/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403","error":"Client error '403 Forbidden' for url 'https://api.x.ai/v1/chat/completions'\nFor more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403","provider":null,"resolved_model":null,"endpoint_id":null,"message_id":"c48cf46dd2b146b08d75406ba228d852","request_id":"75820944-acfe-4656-acc1-1a45536c9e1e"}
```

### 4.5 RAW（SSE 行协议）示例：超长块被服务端拆分（示意）

> 说明：以下为“分帧形态示意”，用于帮助 App 侧对齐“拆分转发”现状；实际 delta 文本内容以真实业务为准。

```text
event: content_delta
data: {"message_id":"msg_xxx","request_id":"rid_xxx","seq":1,"delta":"<thinking>\\n<phase id=\\\"1\\\">\\n<title>..."}

event: content_delta
data: {"message_id":"msg_xxx","request_id":"rid_xxx","seq":2,"delta":"...（中间略）..."}

event: content_delta
data: {"message_id":"msg_xxx","request_id":"rid_xxx","seq":3,"delta":"...\\n</final>"}

event: completed
data: {"message_id":"msg_xxx","request_id":"rid_xxx","reply_len":3799,"reply_snapshot_included":false,"result_mode_effective":"xml_plaintext"}
```

---

## 5) App 端最容易踩坑的 3 点（务必对齐）

1. **自定义事件监听**：若用 `EventSource`，必须 `addEventListener('content_delta'|'completed'|...)`，否则会“看起来没流”。  
2. **301/302 会破坏 SSE/POST**：网关重定向 `/api/v1/messages` 可能导致 POST 丢失/断连；对照 `deploy/web.conf`。  
3. **结构校验**：拼接后的 `reply_text` 的 ThinkingML 规则见 `docs/ai预期响应结构.md`；server 模式默认应满足 v4.5。
