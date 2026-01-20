# AI 预期响应结构（JSONSeq v1，SSOT）

本文件定义 GymBro App 在 **JSONSeq v1（事件流）** 模式下的**对外响应契约**，用于：

- App 端：只基于事件渲染（不解析 XML/Markdown/代码块外壳）
- 后端：将上游输出（XML/JSON/PlainText）**统一映射为同一套事件类型**并流式发送
- 测试：E2E/回归对账与 validator 校验

> 兼容性：默认仍使用现有 SSE 协议（`status/content_delta/completed/...`）。仅当 Dashboard 配置 `llm_app_settings.app_output_protocol=jsonseq_v1` 时才启用本协议。

---

## 1) 事件类型（SSOT）

客户端只需要处理以下事件（SSE `event:`）：

### 1.1 SERP（可选扩展）

- `serp_summary`（可选）：用户需求/检索意图摘要（1–2 句纯文本）
  - `data.text: string`
- `serp_queries`（可选）：用于落库与 UI 展示的查询词数组
  - `data.queries: string[]`（默认 1–3 条；最多 5 条；去重；每条 ≤ 80 字符；不含敏感信息）

### 1.2 Thinking（必须）

- `thinking_start`（必须）
  - 无额外字段
- `phase_start`（必须）
  - `data.id: int`（正整数；严格递增：1,2,3...）
  - `data.title: string`（不可为空）
- `phase_delta`（可多次）
  - `data.id: int`（必须与最近一次 `phase_start.id` 对应）
  - `data.text: string`（纯文本；可分片）
- `thinking_end`（必须）
  - 无额外字段

### 1.3 Final（必须）

- `final_delta`（可多次）
  - `data.text: string`（Markdown 文本片段；可分片）
- `final_end`（必须）
  - 无额外字段

> 说明：为保持与 ThinkingML(XML) 语义一致，`thinking_* / phase_*` 表示“推理/过程”，`final_*` 表示“可渲染给用户的最终答案”。

---

## 2) 事件顺序（必须）

整体顺序约束：

1. （可选）`serp_summary`
2. `thinking_start`
3. `phase_start(id=1,title=...)`
4. `phase_delta(id=1,...)`（0 次或多次）
5. `phase_start(id=2,title=...)`（可选，但建议 ≥2 个 phase）
6. `phase_delta(id=2,...)`（0 次或多次）
7. `thinking_end`
8. `final_delta(...)`（1 次或多次）
9. （可选）`serp_queries`
10. `final_end`

禁止：
- `final_delta` 出现在 `thinking_end` 之前
- `phase_delta` 出现在未发生 `phase_start` 时
- `final_end` 之后继续输出任何事件（除 `heartbeat/status` 等系统事件外）

---

## 3) SSE 数据字段（服务端通用补齐）

为端到端对账，服务端会在所有事件 `data` 中补齐（与现有 SSE 一致）：

- `message_id: string`
- `request_id: string`

并保留现有系统事件（客户端可忽略）：
- `status`、`heartbeat`、`error`、`completed`

---

## 4) 与 ThinkingML(XML) 的语义映射（对齐说明）

当上游输出为 ThinkingML v4.5（XML）时，服务端应做如下映射：

- `<serp>...</serp>` → `serp_summary(text)`
- `<thinking>` → `thinking_start`
- `<phase id="N"><title>T</title> ... </phase>` → `phase_start(id=N,title=T)` + 若干 `phase_delta(id=N,text=...)`
- `</thinking>` → `thinking_end`
- `<final>...</final>` → 若干 `final_delta(text=...)` + `final_end`
- `<!-- <serp_queries> [...] </serp_queries> -->` → `serp_queries(queries=[...])`（并从 `final_delta` 中剔除该注释块）

当上游输出为 PlainText（无结构）时：
- 直接发 `thinking_start`/`phase_start(id=1,title="...")`（可选兜底）或跳过 thinking，仅使用 `final_delta`/`final_end`（以实现为准）

当上游输出为 JSON Lines（模型直接输出 JSONSeq）时：
- 按每行 JSON 的 `event` 字段解析并直接转为 SSE 事件（同名）

---

## 5) 示例（仅示意）

以下为同一条回复的事件流示意（省略通用字段）：

```text
event: serp_summary
data: {"text":"用户要一份三分化训练计划，包含频率与动作选择。"}

event: thinking_start
data: {}

event: phase_start
data: {"id":1,"title":"需求拆解"}

event: phase_delta
data: {"id":1,"text":"目标=增肌；器械=健身房；每周3-4练。"}

event: thinking_end
data: {}

event: final_delta
data: {"text":"# 三分化训练方案\\n- Day1 推...\\n"}

event: serp_queries
data: {"queries":["三分化训练怎么安排","三分化训练动作选择","三分化训练频率与恢复"]}

event: final_end
data: {}
```

---

## 6) 校验建议（validator）

validator 至少校验：

1. 事件顺序满足第 2 节约束
2. `phase_start.id` 正整数且严格递增
3. `phase_start.title` 非空
4. `phase_delta.id` 必须引用已开始的 phase
5. `serp_queries.queries` 去重、≤5、无敏感信息（如出现敏感内容应丢弃或泛化）

