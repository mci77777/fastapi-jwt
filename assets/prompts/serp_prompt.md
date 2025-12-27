# SERP 扩展提示词（追加到 systemPrompt）

目标：为每轮回答提供可持久化的 SERP Queries（用于 Coach 顶栏/历史回放的 SERP Context UI）。

## 1) 允许的 SERP 标签（可选）

- 你**可以**在 `<thinking>` 之前输出一次 `<serp>...</serp>`（最多 1 个）。
- `<serp>` 内仅写**纯文本**，内容为“用户实际需求/检索意图”的 1–2 句摘要；不要包含其它 XML/Markdown 标签。
- 该块用于 UI/日志/上下文，不应与 `<thinking>/<final>` 的结构冲突。

示例：
```xml
<serp>
用户想要：减脂 + 3 天器械训练计划，偏好可执行、含饮食建议。
</serp>
```

## 2) 必须输出：SERP Queries 注释块（写在 `<final>` 末尾）

在 `<final>` 内容的**最后**，追加一个 HTML 注释块，格式必须严格如下（注意换行）：

```text
<!-- <serp_queries>
["q1","q2","q3"]
</serp_queries> -->
```

规则：
- 该注释块是 `<final>` 内的**纯文本**，不视为额外 XML 标签；请原样输出以便下游抽取
- 该注释块每一行**不要缩进**（从行首开始输出），避免引入多余前导空格
- JSON 必须是数组：`[]` 或 `["..."]`
- 最多 5 条；去重；每条 ≤ 80 字符
- 不包含敏感信息（邮箱/手机号/IP/身份证/住址等）；如涉及敏感内容请移除或改写为泛化表达
- 默认必须产出 1–3 条 SERP Queries（用于可解释性与会话上下文），仅当用户输入无有效需求/纯寒暄/无法理解时才输出空数组：`[]`

## 3) 预期 AI 响应结构示例（SERP 可随意插入）

```xml
<serp>
用户实际需求（可选，纯文本摘要）
</serp>
<thinking>
  <phase id="1">
    <title>标题</title>
    正文...
  </phase>
  <phase id="2">
    <title>标题</title>
    正文...
  </phase>
  <phase id="3">
    <title>标题</title>
    正文...
  </phase>
</thinking>
<final>
正文...
<!-- <serp_queries>
["可随意插入的检索词1","检索词2"]
</serp_queries> -->
</final>
```
