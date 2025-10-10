# GymBro 模型管理能力 Spec & Plan

## 背景与动机（WHY）
- 现有 Supabase ↔ SQLite ↔ 前端 已完成基础同步，但本地仍依赖 JSON 缓存，调试和离线回放困难。
- 新需求要求模型选择、模型映射以及 JWT 对话压测端到端可用，同时保持既有表结构不变，确保上线风险可控。

## 目标与成功标准
1. 后台模型列表支持追加候选模型、切换默认模型，并保持 Supabase → SQLite → 前端 单一真源，无需新增 Supabase/SQLite 表结构。
2. 模型映射页面利用现有字段（如 `ai_endpoints.model_list`、`ai_prompts.tools_json`）记录业务域 → 模型集合关系；SQLite/JSON 仅作为冗余或 fallback。
3. 新增“JWT 对话模拟”页面可执行单次对话及 1~1000 并发压测，运行结果优先写入 `ai_prompt_tests` 等现有表列，失败时降级到 JSON fallback；支持本地检索与导出。
4. 新能力遵循“一页面一功能集”“一子包一功能+UI”，新增代码遵守单文件 < 500 行约束。
5. 开发完成后 `make test` 通过，并完成一次端到端冒烟（模型选择 → 映射 → 压测 → 结果读取）。

## 范围界定
- **In Scope**：AI 模型管理相关 API/Service/DAO、Vue 端视图与 Store、SQLite/JSON fallback 逻辑、压测调度及日志、文档更新。
- **Out of Scope**：Supabase schema 变更、OAuth/权限模型重构、外部队列/消息系统、移动端适配、全局监控体系重塑。

## 约束与 PBR
- 坚持 YAGNI / SSOT / KISS：沿用 Supabase 现有 `ai_model`/`ai_prompt` 定义，不新增表或字段；所有写入仍以 Supabase 为权威源，SQLite/JSON 仅做本地缓存。
- 复用 `app/db/sqlite_manager.py` 与 `AIConfigService` 现有同步能力，必要时仅扩展方法，不改变初始化脚本。
- 前端遵循 Naive UI + Pinia + Vue Router 既定模式，目录按功能聚合：`web/src/views/ai/model-suite` + 对应 `store` / `api`。
- 并发压测统一通过已有 HTTP 客户端封装执行，优先利用 `EndpointMonitor`/`AIConfigService`，避免自建线程池。
- JSON fallback 输出需统一命名并在恢复后补写 SQLite，确保数据可回放。

## 数据模型与存储策略
- **Supabase**：继续使用 `ai_model`、`ai_prompt`、`ai_prompt_tests` 等表；默认模型标记利用 `is_default`；映射信息通过字符串/JSON 字段记录附加元数据。
- **SQLite**：复用 `ai_endpoints.model_list`、`ai_endpoints.resolved_endpoints` 等 JSON 字段保存可用模型集合；对话/压测结果写入 `ai_prompt_tests` 的 `request_message`、`response_message`、`latency_ms`、`error` 字段，可在 JSON 中嵌入批次 ID。
- **JSON fallback**：于 `storage/ai_runtime/`（新建目录）输出结构化记录，字段与 SQLite 对齐；SQLite 可用时自动补写并删除对应 JSON。
- **DAO/Service**：在 `AIConfigService` 内追加封装，确保 Supabase ↔ SQLite ↔ JSON 只有一条写入路径，避免影子状态。

## 后端设计
- **路由拆分**
  - 新建 `app/api/v1/llm_models.py`：候选模型 CRUD、默认模型切换、模型同步触发。
  - 新建 `app/api/v1/llm_mappings.py`：业务域与模型集合映射 CRUD，读写 `model_list` 等字段。
  - 新建 `app/api/v1/llm_tests.py`：JWT 对话调用、压测任务启动/查询、结果落地。
  - `app/api/v1/base.py` 注入新路由，保留旧 `/llm` 兼容行为。
- **服务层**
  - `AIConfigService`：新增方法用于读写映射、更新默认模型、批量写入测试结果；内部保证单模型默认唯一。
  - `jwt_test_service.py`（新文件，< 500 行）：封装单次对话与批量压测逻辑，复用现有 http client，增加取消/状态轮询。
  - `model_mapping_service.py`（新文件，< 500 行）：负责解析/写入 `model_list` JSON，提供 scope 级约束与 Supabase 同步。
  - 记录监控指标：成功率、平均延迟、错误摘要写入 `app/log/`，并通知 `EndpointMonitor`。
- **任务与容错**
  - 压测任务使用 asyncio.gather + 限流 semaphore；遇到 Supabase/SQLite 故障写 JSON fallback 并记录告警。
  - 结果查询接口支持分页、按 run_id 过滤、导出 CSV/JSON。

## 前端设计
- **视图结构**
  - `ModelDashboard.vue`：提供端点状态、映射覆盖与快捷入口。
  - `ModelCatalog.vue`：展示模型列表、启停、默认切换、 Supabase 同步按钮。
  - `ModelMapping.vue`：按业务域（例如 Prompt、租户、模块）配置可用模型；数据从 `model_list` JSON 解析。
  - `JwtSimulation.vue`：JWT 生成/模拟对话、压测配置（批次、并发、停错策略）、实时展示 run 状态与结果下载。
- **状态与 API**
  - `store/aiModelSuite.ts`：集中管理模型/映射/压测状态，与后端交互保持规范化数据结构。
  - `api/aiModelSuite.ts`：封装新路由调用，处理默认模型切换、压测轮询、结果下载。
  - UI 使用 Naive UI 表格、Steps、Drawer 等组件，保证交互简洁。

## 核心流程
1. 管理员在模型列表新增模型 → 服务层写 Supabase → 同步至 SQLite → 前端刷新。
2. 映射页面从现有字段解析业务域配置 → 修改后写回 `model_list` JSON → Supabase/SQLite 保持一致。
3. JWT 对话模拟调用现有 chat 能力 → 结果写入 `ai_prompt_tests` → UI 展示会话详情。
4. 并发压测创建批次 run_id → 限流执行调用 → 结果按消息写入 SQLite/JSON → 前端轮询显示统计与导出。
5. 当 SQLite 写入失败时落 JSON fallback，待恢复后通过后台任务补写。

## 非功能性考虑
- **性能**：并发上限默认 200（可配置），超过则排队；记录响应时间、错误率。
+- **容错**：任何写入失败需保留 JSON 备份并上报日志；提供补写命令。
- **权限**：沿用 `Depends(get_current_user)` 与管理员角色判断。
+- **观察性**：关键操作写入审计日志，并在 monitor service 中打点。

## 实施计划
### Phase 0 预研（1d）
- 复核 `AIConfigService`、`SQLiteManager`、`EndpointMonitor` 当前能力，确认可复用接口。
- 列出 Supabase/SQLite 可利用字段与 JSON 结构定义，确定命名约定。
- 明确压测上限、速率限制与运维约束。

### Phase 1 服务层与数据合同（1.5d）
- 扩展 `AIConfigService`，实现模型读取/写入、映射解析、结果写入；补充单元测试（mock Supabase）。
- 编写 JSON fallback 帮助类（读写 storage/ai_runtime）。
- 更新文档说明字段用途与 JSON schema。

### Phase 2 后端 API（2d）
- 拆分 `llm.py`，实现 `llm_models.py`、`llm_mappings.py`、`llm_tests.py`。
- 实现压测任务调度、状态查询、CSV/JSON 导出。
- 新增 FastAPI 层测试（TestClient + 临时 SQLite 文件），覆盖模型切换、映射保存、压测 run 流程。

### Phase 3 前端实现（2d）
- 建立 `model-suite` 子包，完成三页 UI、Pinia store、API 封装。
- 实现轮询获取 run 状态、错误提示、导出功能；编写基本组件测试或手工验证脚本。

### Phase 4 验证与优化（1d）
- 运行 `make test`，针对压测服务新增 pytest 用例（respx/asyncio）。
- 手动执行 10/200/1000 并发压测，确认 SQLite 记录与 JSON fallback 一致。
- 调整日志级别、监控指标阈值，确保出现异常时易于定位。

### Phase 5 文档与交付（0.5d）
- 更新 README / `docs/features/model_management/` 文档，描述新页面入口与使用说明。
- 编写回滚指引：移除新路由、删除前端子包、清理 storage JSON。
- 准备演示数据与运维手册（压测配额、fallback 补写步骤）。

## 影响面扫描
- 后端：`app/api/v1`、`app/services/ai_config_service.py`、新增服务文件、监控/日志配置。
- 前端：`web/src/views/ai/model-suite/`、`web/src/store`、`web/src/api`、`web/src/router`。
- 工具/文档：`storage/ai_runtime/`、`docs/features`、运维脚本（fallback 补写、CSV 导出）。

## 回滚策略
- 单提交改动，可通过 Git revert 撤销；删除新 API 路由与服务文件即可恢复。
- 前端移除 `model-suite` 子包与路由项，回退至旧构建。
- 清理 storage JSON 备份，保持 Supabase/SQLite 数据不受影响。
