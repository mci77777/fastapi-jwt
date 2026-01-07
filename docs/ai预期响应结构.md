# AI 预期响应结构（SSOT）

本文件定义「GymBro 对话接口」在 **Strict-XML / ThinkingML v4.5** 模式下的**响应结构契约**，用于：

- App / Web / 脚本在拼接 `content_delta.delta` 得到 reply 后做结构校验；
- 后端在组装 `system prompt` 时作为“输出格式约束”的权威说明；
- E2E 对账与回归测试。

> SSOT 来源（prompt）：
> - `assets/prompts/serp_prompt.md`（Strict XML + SERP 规则）
> - `assets/prompts/tool.md`（ToolCall 规范补丁，不改变 Strict XML 输出协议）
> - `assets/prompts/standard_serp_v2.json`（profile 元数据：版本/协议等）
>
> SSOT 来源（SSE 事件）：`app/services/ai_service.py::MessageEventBroker.publish()` + `app/api/v1/messages.py::stream_message_events()`

---

## 1) 总体结构（必须）

响应必须是一个 **XML 文本**，并遵循以下顺序（不可乱序）：

1. （可选）`<think>...</think>`：草稿，仅纯文本（最多 1 个）
2. （可选）`<serp>...</serp>`：检索意图摘要，仅纯文本（最多 1 个，且必须位于 `<thinking>` 之前）
3. `<thinking> ... </thinking>`：推理阶段块（必须且仅 1 个）
4. `<final> ... </final>`：最终可渲染答案（必须且仅 1 个，紧跟在 `</thinking>` 之后）

**关键约束**：
- `</thinking>` 后必须立即出现 `<final>`（否则视为格式错误）
- `<final>` 内允许使用 Markdown 进行排版（标题/列表/代码块等）
- 禁止在 `<thinking>` 的**内容文本**中出现 `<final>` / `</final>` 字面量（会被解析为嵌套标签）；如需提及必须转义为 `&lt;final&gt;` / `&lt;/final&gt;`

> 兼容性：后端会对 `<thinking>...</thinking>` 区间内的 `<final>` / `</final>` 字面量做最小转义，避免生成非法结构。

---

## 2) 允许的标签白名单（必须）

仅允许出现下列标签（大小写必须一致）：

- `<think>` `</think>`
- `<serp>` `</serp>`
- `<thinking>` `</thinking>`
- `<phase id="N">` `</phase>`（`N` 为严格递增的正整数）
- `<title>` `</title>`
- `<final>` `</final>`

**禁止**出现其它任何 XML 标签；如校验失败，模型应输出 `<<ParsingError>>`（该字符串必须是整段输出的唯一内容）。

---

## 3) `<thinking>` 结构（必须）

`<thinking>` 内必须包含 **≥ 1 个** `<phase id="N"> ... </phase>`，并满足：

- `id` 为正整数且严格递增（1,2,3,...）
- 每个 `<phase>` 内必须包含且仅包含 1 个 `<title>...</title>`
- `<title>` 后可跟随纯文本推理内容

示例（仅示意）：

```xml
<thinking>
  <phase id="1">
    <title>理解需求</title>
    ...
  </phase>
  <phase id="2">
    <title>规划输出</title>
    ...
  </phase>
</thinking>
<final>
# 三分化训练方案（示例）
- ...
<!-- <serp_queries>
["三分化训练计划怎么安排","三分化训练动作选择","三分化训练频率与恢复"]
</serp_queries> -->
</final>
```

---

## 4) `<final>` 末尾 SERP Queries 注释块（默认必须）

在 `<final>` 内容的**最后**，追加一个 HTML 注释块（纯文本，不视为额外 XML 标签），格式必须严格如下（注意换行与无缩进）：

```text
<!-- <serp_queries>
["q1","q2","q3"]
</serp_queries> -->
```

规则：
- JSON 必须为数组：`[]` 或 `["..."]`
- 最多 5 条；去重；每条 ≤ 80 字符
- 不包含敏感信息（邮箱/手机号/IP/住址等）
- 默认产出 1–3 条；仅当用户无有效需求/纯寒暄/无法理解时才允许 `[]`

---

## 5) E2E 校验建议（供脚本使用）

建议对「拼接后的 reply（由 `content_delta.delta` 拼接得到）」做以下校验：

1. 不允许出现 `<<ParsingError>>`
2. 必须包含 `<thinking>`、`</thinking>`、`<final>`、`</final>`，且顺序正确（`</thinking>` 在 `<final>` 之前）
3. 仅出现白名单标签（允许 `<phase id="...">`）
4. `<thinking>` 内至少 1 个 `<phase id="...">`，且每个 phase 含 `<title>`
5. `<final>` 末尾包含 `<!-- <serp_queries> ... -->`

---

## 6) GymBro SSE 事件契约（对外 SSOT）

> 重要：当前实现 **completed 不包含 reply 原文**；客户端应拼接 `content_delta.delta` 得到完整 reply（SSOT）。

### 6.1 事件集合（最小）
- `status`
- `content_delta`
- `completed`
- `error`
- `heartbeat`

### 6.2 通用字段（服务端自动补齐）
所有事件 `data` 默认包含：
- `message_id: string`
- `request_id: string`（若请求侧提供 `X-Request-Id`，则对账稳定）

`content_delta` 额外自动补齐：
- `seq: int`（从 1 开始单调递增）

### 6.3 各事件 `data` 形状（示例）

`status`（典型：queued → working → routed）：
```json
{"state":"routed","message_id":"<opaque>","request_id":"<opaque>","provider":"openai","resolved_model":"<vendor_model>","endpoint_id":1,"upstream_request_id":null}
```

`content_delta`（客户端拼接为最终 reply）：
```json
{"message_id":"<opaque>","request_id":"<opaque>","seq":12,"delta":"...chunk..."}
```

`completed`（终止事件；不含 reply 原文，只给摘要字段）：
```json
{"message_id":"<opaque>","request_id":"<opaque>","provider":"openai","resolved_model":"<vendor_model>","endpoint_id":1,"upstream_request_id":"<opaque|null>","reply_len":601,"metadata":null}
```

`error`（终止事件；保留 legacy `error` 字段兼容旧客户端）：
```json
{"message_id":"<opaque>","request_id":"<opaque>","code":"provider_error","message":"...","error":"...","provider":"openai","resolved_model":"<vendor_model|null>","endpoint_id":1}
```

`heartbeat`（心跳；用于客户端“连接仍活着”的判定）：
```json
{"message_id":"<opaque>","request_id":"<opaque>","ts":1736253242000}
```

---

## 7) 客户端组装 reply（必须）

1) 订阅 SSE 自定义事件：`status/content_delta/completed/error/heartbeat`  
2) 按 `seq`（或到达顺序）拼接 `content_delta.delta` 得到 `reply_text`  
3) `completed.reply_len` 仅用于校验拼接结果长度（不保证逐字一致，避免因转义/编码差异误判）  
4) 若收到 `error`，应视为失败终止（即使之前收到部分 `content_delta`）

---

## 8) 本地 E2E（mock 上游，不出网）

用于快速验证：prompt 注入（serp/tool）+ tools schema 注入 + GymBro SSE 端到端 + reply 结构校验。

命令：
```bash
.venv/bin/python scripts/monitoring/local_mock_ai_conversation_e2e.py
```

脚本行为：
- admin 登录拿 JWT（不依赖 Supabase）
- 从 `assets/prompts/serp_prompt.md` 与 `assets/prompts/tool.md` 写入并激活 `/api/v1/llm/prompts`
- 从 `tool.md` 解析并注入 OpenAI `tools` schema（配合 `tool_choice=auto`）
- mock 上游返回一个符合本文结构的 ThinkingML reply，并通过 GymBro SSE 流式下发（`content_delta`）
