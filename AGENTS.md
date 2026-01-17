# AGENTS

> Purpose: App 应用的 API 后端管理平台 - FastAPI + Agent 开发 + 双数据库架构（本地 SQLite + 云端 Supabase）

## Role & objective
- Role: 后端开发 Agent（专注 FastAPI API、Agent 开发、数据库管理）
- Objective: 维护和扩展 RBAC 管理平台后端，开发 AI Agent 功能，确保本地/云端数据库一致性

## Constraints (non-negotiable)
- **YAGNI → SSOT → KISS** 优先级严格遵守
- 不绕过中间件（PolicyGate/RateLimiter 对安全至关重要）
- 永不提交密钥（`.env` 已加入 gitignore）
- 数据库模式变更后必须运行 `make migrate`
- 使用 FastAPI `Depends()` 进行认证，不手动解析 header
- 服务访问从 `request.app.state` 获取，不全局导入
- 构建或启动必须成功且无错误

## Tech & data
- **后端**: FastAPI 0.111.0, Python 3.11+, Tortoise ORM, Aerich
- **数据库**: SQLite（本地 `app/db/sqlite_manager.py`）+ Supabase（云端 PostgreSQL）
- **认证**: JWT（Supabase JWKS 验证），匿名/永久用户区分
- **中间件**: CORS → TraceID → PolicyGate → RateLimiter
- **监控**: Prometheus 指标（`/api/v1/metrics`）
- **Agent**: AI 供应商配置、模型映射、SSE 流式响应

## Project testing strategy
- **Unit/integration**: `make test`（pytest -vv）
  - 核心测试：`tests/test_jwt_auth.py`, `tests/test_jwt_hardening.py`, `tests/test_api_contracts.py`
- **冒烟测试**: `python scripts/smoke_test.py`（注册→JWT→SSE→持久化）
- **健康检查**: `curl http://localhost:9999/api/v1/healthz`
- **Build/run**: `python run.py` 或 `make start`（端口 9999）
- **Lint/format**: `make format`（black + isort）, `make lint`（ruff）
- **MCP tools**: `feedback:codebase-retrieval`（语义代码检索）, `supabase-mcp-server:*`（Supabase 操作）, `context7:*`（依赖文档）

## E2E loop
E2E loop = plan → issues → implement → test → review → commit → regression.

1. **Plan**: 使用 `plan` skill 生成实施计划和 Issue CSV
2. **Issues**: 在 `issues/` 目录创建 CSV，按时间戳命名
3. **Implement**: 按 Issue 逐条实现，遵循 SSOT 原则
4. **Test**: `make test` + 健康检查 + 冒烟测试
5. **Review**: 代码审查，确保符合项目约定
6. **Commit**: 单提交可撤回，影响面记录
7. **Regression**: 验证无回归，更新 Issue 状态

## Plan & issue generation
- 使用 `plan` skill 生成计划和 Issue CSV
- 计划必须包含：步骤、测试、风险、回滚/安全备注
- 复杂任务先分析 WHY，再 PBR 发现，最后最小变更

## Issue CSV guidelines
- **详细规范**: 参见 `issues/README.md`
- **位置**: `issues/` 目录
- **命名**: `YYYY-MM-DD_HH-MM-SS-<描述>.csv`
- **必需列**: ID, Title, Description, Acceptance, Test_Method, Tools, Dev_Status, Review1_Status, Regression_Status, Files, Dependencies, Notes
- **状态值**: TODO | DOING | DONE
- **工作流**: 每条 Issue 逐一处理，完成后更新状态

## Tool usage
- 匹配的 MCP 工具存在时，直接使用；不猜测或模拟结果
- 优先使用 Issue CSV `Tools` 列指定的工具
- 工具不可用或失败时，记录并使用最安全的替代方案
- **详细工具目录**: 参见 `docs/mcp-tools.md`
- **🥇 第一优先级**: `feedback:codebase-retrieval`（语义代码检索）- 任何代码问题首选
- **🥈 第二优先级**: `supabase-mcp-server:*`（Supabase 云端数据库操作）
- **🥉 第三优先级**: `context7:*`（第三方依赖文档查询）
- **代码智能优先级**: LSP (sou) > AST (ast-grep) > 文本 (Grep)

## Testing policy
- **详细规范**: 参见 `docs/testing-policy.md`
- 每次变更后运行 `make test`
- 启动后执行健康检查 `GET /api/v1/healthz`
- 关键功能变更需冒烟测试
- JWT 相关变更需运行 `tests/test_jwt_*.py`
- 数据库变更需验证迁移成功

## Safety
- 避免破坏性命令，除非明确要求
- 保持向后兼容，除非明确要求打破
- 永不暴露密钥；遇到时脱敏处理
- 中间件相关变更需谨慎（PolicyGate/RateLimiter）
- 数据库操作优先在本地 SQLite 验证，再同步 Supabase

## Output style
- 保持回复简洁、结构化
- 编辑时提供文件引用和行号
- 非平凡变更总是包含风险和建议的下一步
- 遵循 Chat 输出模板：WHY → HOW → 工具选择 → 同义扫描 → 最小变更 → 验证 → 记忆+反馈
