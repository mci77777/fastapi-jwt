# 工具补充（Tool Supplement｜SemTool Registry）

## 能力本体（Capabilities）

### 代码智能（Code Intelligence）
- **Serena（LSP）**：语义检索/引用分析/精准编辑（支持 Micro-pull；写入前必须同义扫描）。
- **ast-grep**：AST 模式匹配与批量定位（优先于纯文本）。
- **Grep**：正则文本搜索（仅回退，必须 `--glob` 限域）。

### 文件与内容（Core File Operations）
- **Read**（带行号）、**Write**（新建/覆盖）、**Edit**（精确字符串替换）、**Glob**（如 `**/*.kt`）、**Grep**（正则）。

### 执行与外壳（Execution & Shell）
- **Bash**（执行命令）、**BashOutput**（读取后台输出）、**KillShell**（终止后台进程）。

### 导航与检索（Navigation & Search）
- **WebSearch**（时鲜信息/价格/新闻/规则），**WebFetch**（抓取与分析网页内容）。

### 文档与依赖（Docs & Deps）
- **Context7**：
  - **resolve-library-id（必先）**：把"包/产品名"解析为 `/org/project[/version]`；择优顺序：名称相似度 → 相关性 → 文档片段覆盖度 → 信任分(7–10)。返回**选定库 ID + 选择理由**；多候选说明但直接择优；无匹配给出改写建议。
  - **get-library-docs**：用库 ID 拉取**最新文档/片段**，校验 API 用法与边界。

### 开发协作（Development Tools）
- **Task**（调度专用 agent：`code`/`bugfix`/`debug`/`optimize`/`requirements-*`/`memory-search`/`memory-ingest`…）
- **TodoWrite**（任务清单/进度追踪）
- **SlashCommand**（工作流内自定义命令）

### Jupyter 支持
- **NotebookEdit**（编辑 Notebook 单元）

### 规划
- **ExitPlanMode**（结束规划阶段，进入实现）

## Base Core Tools（默认优先组）
1) **Serena（LSP）**  
2) **ast-grep**  
3) **Core File Operations**（Read/Glob/Grep → Edit/Write）  

> 说明：优先"读→判→最小写入"，必要时再调度 Execution & Shell、Context7、或专用 agent。

## 选择与仲裁（从 BASE 调用）
- 将任务拆为能力需求向量：{读取/定位/比对/编辑/编译/启动/探针/文档校验/外网事实核验/Notebook/任务编排…}。
- 打分选择（权重建议）：精确度 40% / 安全性(只读优先/可回滚) 25% / 成本 15% / 鲁棒 10% / 一致性(与 PBR) 10%。
- 冲突规则：读 > 写；LSP > AST > 文本；本地构建/探针 > 猜测；优先**最小充分工具集**。
- 复杂流程再用 **Task** 调度专用 agent；减少上下文切换与失败面。

## 使用纪律
- 已安装工具**直接调用**，禁止再包一层 shell。
- **禁止以日志为主要定位手段**；日志仅作佐证（说明"为何必须使用"和"非唯一依据"）。
- 写入前**必须**做"同义实现扫描"；能复用就合并到 **SSOT**。
- 不确定就做 **Serena Micro-pull**（小范围多次拉取，逐步放大）。
- 验收以"**构建或启动成功且无错误**"为底线，并执行健康检查/探针/必要测试。

## 语义→工具映射示例
- 「定位入口与被调关系」→ Serena.find_symbol / find_referencing_symbols；必要时 ast-grep 模式补充
- 「是否已有等价实现」→ Serena 同义扫描 + Grep(限域)
- 「小改并验证」→ Serena 精准替换 → Write/Edit 小步提交 → Bash 构建/启动 → 健康检查
- 「三方 API 正确用法」→ Context7：resolve-library-id → get-library-docs（返回库 ID 与选择理由）
- 「新闻/规则/价格等时鲜」→ WebSearch → WebFetch（标注来源与日期）
- 「性能专项/多步骤」→ Task(optimize) + Serena/ast-grep 组合；TodoWrite 跟踪；完结 ExitPlanMode
