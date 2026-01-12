# Web 调试点：SSE 真流式 + ThinkingML（SSOT）

目的：在 **Web 管理台**上对账「是否真流式」以及「拼接后的 reply 是否符合 `docs/ai预期响应结构.md`（ThinkingML v4.5）」。

## 入口
- 页面：`web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue`
- 菜单：`AI 模型管理` → `JWT 测试`

## 使用步骤（最短路径）
1) 先在页面顶部获取/粘贴 **JWT Token**（匿名或测试用户均可）。  
2) 选择 `model`（来源：`GET /api/v1/llm/app/models`，即 App 会发送的 model key）。  
3) 选择 `prompt_mode` / `result_mode` / `tool_choice`（下文解释）。  
4) 点击 `发送并拉流`，观察：
   - `SSE 指标（接收侧）`：TTFT、delta_count、avg_delta_len、max_gap_ms
   - `SSE 事件（最近 200）`：是否持续收到 `content_delta`
   - `ThinkingML: ok`（或失败原因码）

## 开关语义（与后端 SSOT 对齐）

### `result_mode`
- `xml_plaintext`：后端在 SSE 中输出 `event: content_delta`，拼接得到的 reply 为 **纯文本**，并包含 `<thinking>...</thinking><final>...</final>` 等标签（用于 App 直接渲染/校验）。
- `raw_passthrough`：后端在 SSE 中输出 `event: content_delta`，但 **不做 ThinkingML 纠错/标签归一化**（用于对账“原始 token 文本”与上游真实输出）。
- `auto`：后端自动选择；页面会显示 `effective: ...`，并在 `completed`/`error` 带回 `result_mode_effective`。

### `prompt_mode`
- `server`：由后端 SSOT 组装 prompt（参考 `assets/prompts/*`），页面的「附加 Prompt」不会注入。
- `passthrough`：按 OpenAI 兼容字段透传；页面会把「附加 Prompt」作为 `system` message 发送（便于你快速调参）。

### `tool_choice`
- `默认（不传）`：交给后端/上游默认策略。
- `none`：强制禁用 tools（推荐做结构/流式稳定性验证时使用）。
- `auto`：允许 tools（可能导致某些上游/代理对工具 schema 更严格，出现 400）。

## ThinkingML 校验（前端对齐后端 E2E）
页面 `completed 自动校验 ThinkingML` 与按钮 `立即校验` 使用与后端 E2E 同口径的原因码（SSOT：`docs/ai预期响应结构.md`）：
- `final_not_immediately_after_thinking`：`</thinking>` 与 `<final>` 之间出现了非空白内容
- `unexpected_tag:...`：出现了不允许的 XML 标签
- `missing_or_invalid_serp_queries_block`：`<final>` 末尾缺少 `<!-- <serp_queries> ... -->`
- 其余原因码参考：`scripts/monitoring/local_mock_ai_conversation_e2e.py::_validate_thinkingml`

## SSE 探针（判断网关/代理缓冲）
页面 `SSE 探针` 会调用 `GET /api/v1/base/sse_probe`，正常应每秒到达一条 `probe`（共 8 条）。  
若 `gaps(ms)` 大幅聚合（例如几乎同时到达），优先排查：
- Nginx：`proxy_buffering off;`、`gzip off;`
- 负载均衡/网关：关闭响应缓冲与压缩（SSE 路径必须放行）

## 推荐的 passthrough 附加 Prompt（用于快速调参）
> 若你只想验证“结构合规 + 真流式”，推荐先用 `tool_choice=none` + `result_mode=xml_plaintext`。

```
请严格按原样输出 Strict-XML（ThinkingML v4.5）：
1) 必须输出且仅输出一个 XML 文本：<thinking>...</thinking> 紧接 <final>...</final>
2) 只允许标签：think/serp/thinking/phase/title/final（phase 必须有 id="1..N" 且递增）
3) <final> 内容最后必须追加：
<!-- <serp_queries>
["q1","q2","q3"]
</serp_queries> -->
4) 不要解释协议，不要使用 Markdown 代码块包裹 XML；若无法满足，输出 <<ParsingError>>
```
