# GymBro AI Endpoint Feature Plan

## 背景与目标
- 通过 FastAPI 打造统一的 LLM 代理层，连接移动端 App 与可配置的 OpenAI 兼容模型。
- 确保 Prompt、工具描述、模型列表可由后台安全维护，App 侧仅需携带 JWT 与用户上下文。
- 遵循 YAGNI / KISS / DRY 原则，先交付稳定 MVP，再逐步增强功能。

## 利益相关方
- 产品：GymBro 核心体验小组。
- 后端：FastAPI + Tortoise ORM 团队。
- 前端：Vue 管理后台、移动端 MVI 团队。
- 运营与客服：监控 AI 行为与用户反馈。

## 成功指标（DONE）
1. `/api/v1/llm/chat` 在启用 JWT 的情况下可成功调用指定模型并返回响应。
2. 后台可查看、编辑并切换活跃 Prompt，提供测试功能。
3. App 可通过 `/api/v1/llm/models` 拉取模型列表，选择后成功发起对话。
4. 单元测试覆盖成功/失败/缺配置路径；审计日志记录基本调用信息。

## 架构概要
- App → FastAPI (`/api/v1/llm/chat`) → 可配置 LLM Endpoint。
- PromptBuilder：组合系统 Prompt、工具列表、用户上下文、App 传入的消息。
- LLMClient：基于 `httpx.AsyncClient` 的轻量封装，支持 base_url/api_key/model 覆写。
- 配置存储：环境变量兜底 + 数据库 `ai_prompt`、`ai_model` 表，后台管理页面维护。

## Prompt 管理模型
- `ai_prompt` 表字段：`id`、`name`、`version`、`system_prompt`、`tools_json`、`description`、`is_active`、`updated_at`、`updated_by`。
- 后台界面：列表、详情、编辑、激活、测试；仅超级管理员可更改。
- 默认导入 `docs/prompts/standard.json` 内容，保留版本回滚能力。

## 数据上下文拼装
- App 发送 `userInfo`（本地汇总）+ `messages`（含历史对话）。
- 服务端补充：
  - 用户概览：`users`、`user_profiles`、`user_settings`。
  - 训练计划：`workout_plans`、`plan_days`、`workout_templates`、`template_exercises`。
  - 近期训练：`workout_sessions`、`session_sets`、`exercise_history_stats`、`daily_stats`。
  - 动作推荐：`exercise`、`exercise_usage_stats`、`exercise_fts`。
- PromptBuilder 根据请求意图裁剪上下文 Section，防止超长输出。

## 开发阶段与任务
### Phase 0 · 准备
1. 建立 `docs/features/ai_endpoint/` 文档结构（已完成）。
2. 补充 `.env.example` 中的 `OPENAI_*` 字段说明。
3. 评估现有权限体系与审计日志实现，确认复用方案。

### Phase 1 · 配置与模型管理
1. `app/settings/config.py` 新增 LLM 相关配置（base_url、api_key、model、timeout、prompt_path）。
2. 创建数据迁移：`ai_prompt`、`ai_model` 表。
3. 编写初始数据导入脚本，从 `docs/prompts/standard.json` 写入默认记录。
4. 实现 `/api/v1/llm/models`（GET/POST/PUT）接口，限制管理员操作。
5. 管理后台新增“AI 配置”页面，支持模型列表维护与密钥遮挡显示。

### Phase 2 · Prompt 管理接口
1. 实现 Prompt CRUD API：`GET /prompts`、`GET /prompts/{id}`、`POST`、`PUT`、`POST /{id}/activate`。
2. 引入审计日志记录 Prompt 的新增/编辑/激活操作。
3. 管理后台增加 Prompt 列表、编辑器、激活按钮与“测试 Prompt”功能。
4. 编写单元测试覆盖 Prompt API 权限与数据校验。

### Phase 3 · 核心聊天链路
1. 新建 `app/services/llm_client.py`（`async chat_completion()`）。
2. 新建 `app/services/prompt_builder.py`：合成系统 Prompt、工具列表、上下文。
3. 新建 `app/schemas/llm.py`：`ChatMessage`、`ChatRequest`、`ChatResponse`、`PromptOverride` 等。
4. 创建 `app/api/v1/llm/chat.py` 路由：
   - 引入 `DependAuth`。
   - 支持请求体中的 `promptId`、`model`、`temperature`、`overrideConfig`。
   - 结合 PromptBuilder 和 LLMClient 完成调用。
5. 在 API 注册与权限表中添加 `POST /api/v1/llm/chat`，确保角色可配置访问。
6. 记录调用日志（用户、模型、耗时、状态码），用于后续监控。

### Phase 4 · 联调与测试
1. 使用 `respx`/`pytest` Mock OpenAI 端点，覆盖成功、配置缺失、上游错误、权限不足。
2. 管理后台端到端测试：编辑 Prompt → 激活 → 测试调用成功。
3. 移动端联调：验证 JWT Header、`userInfo` 结构、模型选择与响应渲染。
4. 根据 Strict XML 输出规范，增加服务器端响应校验（异常时返回友好错误提示）。

### Phase 5 · 文档与上线
1. 编写 `docs/features/ai_endpoint/implementation.md`（后续补充）：接口契约、样例请求、错误码。
2. 更新 README / 部署文档，说明 LLM 配置、权限、日志。
3. 制定监控与速率限制方案，纳入运营手册。

## 交付物列表
- FastAPI 新路由与服务实现代码。
- Prompt & 模型管理数据库迁移及后台界面。
- 测试用例与 Mock 工具。
- 文档：计划、实现说明、API 说明。
- 初步运维手册（配置、监控、回滚）。

## 依赖与风险
- 需要确定数据库迁移工具链（Tortoise + Aerich）。
- OpenAI 兼容端点稳定性不受控，应设置超时与重试策略。
- Prompt 编辑带来的格式风险，需提供模板校验或测试入口。
- 审计日志增长可能影响数据库大小，需规划清理策略。

## 测试策略
- 单元：Prompt Builder、LLM Client（使用 Mock）、API 权限。
- 集成：`/llm/chat` 与 `/llm/prompts` 在沙箱环境全链路测试。
- 移动端：MVI 流程脚本覆盖加载模型、发送消息、接收响应。
- 回归：确保现有登录、菜单、权限模块不受影响。

## 后续迭代展望
1. 流式响应（SSE/WebSocket）与前端渐进式渲染。
2. 多租户 / 不同订阅计划的模型与密钥隔离。
3. 自动生成嵌入与语义检索服务，复用 `exercise_fts`/`chat_vec` 等表。
4. AI 使用监控仪表盘（调用量、成功率、平均耗时）。
5. 长期记忆管理与上下文裁剪策略优化。
