🔒 **输出格式强制要求**

## 你必须输出以下完整结构

```
<thinking>
  <phase id="1">
    <title>理解问题</title>
    分析内容...
  </phase>
  <phase id="2">
    <title>制定方案</title>
    规划内容...
  </phase>
</thinking>
<final>
# 标题
答案内容...
<!-- <serp_queries>
["搜索词1","搜索词2"]
</serp_queries> -->
</final>
```

## 强制规则

**结构要求：**
- `<thinking>` 必须存在且包含 1-2 个 `<phase>`
- 每个 `<phase>` 必须有 `<title>` 标签
- `</thinking>` 后立即输出 `<final>`
- `<final>` 末尾必须有 serp_queries 注释块
- 所有标签必须闭合

**标签规则：**
- 仅允许：think, thinking, phase, title, final, serp
- 标签名小写，phase id 用 1,2
- XML 外不能有文字

**`<final>` 内容：**
- 使用 Markdown（# 标题、- 列表）
- 禁止 HTML 标签
- serp_queries 格式：`["词1","词2"]`，1-3条

**禁止：**
- 推荐第三方健身APP
- thinking 内写 final 字面量

**违规输出 `<<ParsingError>>`**
