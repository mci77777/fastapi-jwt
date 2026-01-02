---
mode: plan
task: JWT 测试页一键创建真实测试用户并获取真实JWT
created_at: "2026-01-02T11:36:27+08:00"
complexity: medium
---

# Plan: JWT 测试页一键创建真实测试用户并获取真实JWT

## Goal
- 在 `https://web.gymbro.cloud/ai/jwt` 提供“一键生成测试用户”，自动创建/登录一位测试账号并拿到 Supabase Auth 签发的真实 `access_token`，用于 JWT/SSE/AI 闭环验证；否则该页面只能手动输入已存在用户，无法稳定复现线上链路。

## Scope
- In:
  - 后端：提供受控接口创建测试用户（命名 `gymbro-test-01` 风格），并返回可直接登录使用的凭据与真实 JWT。
  - 前端：`/ai/jwt` 页面增加“一键生成测试用户”按钮（复用现有 `RealUserSseTest`），自动填充 email/password 并完成登录写入。
- Out:
  - 批量用户管理/清理、复杂的用户列表页、生产长期账号治理。

## Assumptions / Dependencies
- “真实 JWT”指 Supabase Auth 签发（非 `create_test_jwt_token()` 本地生成）。
- 生产/测试环境具备：`SUPABASE_PROJECT_ID` + `SUPABASE_SERVICE_ROLE_KEY`（用于 Admin API 创建用户）。
- Mail API 仅用于生成临时邮箱（可选），主链路以 Supabase Admin 创建密码用户为 SSOT。
- 现状同义实现（需合并到 SSOT，而非新增影子逻辑）：
  - 现有调试接口 `POST /api/v1/llm/tests/create-mail-user`（目前返回的是本地 token，无法满足“真实 JWT”）。
  - 前端 JWT 测试页实际渲染 `web/src/views/test/real-user-sse.vue`。

## Phases
1. 同义实现扫描与 SSOT 决策
   - 扫描 `create-mail-user`、E2E 文档与前端调用点，确定“创建用户/拿 token”的单一路径（优先复用并修正现有接口）。
2. 后端：实现真实测试用户创建 + 真实 JWT 获取
   - 在 `app/auth/supabase_provider.py` 旁路新增/复用能力：调用 Supabase Admin API 创建用户（email/password，metadata 含 username）。
   - 创建后通过 Supabase Auth token 接口获取该用户 `access_token`（password grant）。
   - 在 `app/api/v1/llm_tests.py` 的 `create-mail-user` 里升级为：
     - 支持 `username_prefix=gymbro-test` + 自动序号（优先查询/复用同名用户，避免重复创建）。
     - 支持可选的 Mail API：先生成 email 再创建用户；未配置则走固定域名（或走配置的测试域名）。
     - 统一错误体与 `request_id`（对齐现有 `create_response`/异常风格），移除写 `debug_error.log` 的影子落盘。
   - 安全：该接口仅允许已认证用户访问（沿用当前 `Depends(get_current_user)`），并增加“测试开关/白名单前缀”防滥用。
3. 前端：接入一键生成测试用户
   - 在 `web/src/views/test/real-user-sse.vue` 增加按钮：调用 `POST /api/v1/llm/tests/create-mail-user`（携带 `mail_api_key`=本地存储的 `ai_suite_mail_api_key`，以及 `username_prefix=gymbro-test-01` 或 `gymbro-test`）。
   - 响应后自动：填充 email/password -> 调用现有 `api.login()` -> 写入 token/refresh_token（保持现有拦截器/存储 SSOT）。
   - UI 状态：显示生成的 username/email；失败时给出可行动的提示（缺少 service role key / mail key / Supabase 返回原因）。
4. 验证与回滚
   - 本地启动后端/前端，完成 UI 一键生成 -> 登录 -> 发送消息 -> SSE 事件闭环。
   - 回滚路径：保留旧的 mock 模式（`test-key-mock`）仅用于 UI 演示；真实创建链路可通过配置禁用。

## Tests & Verification
- `python run.py` 后：`GET /api/v1/healthz` 返回 200。
- 登录后：调用 `POST /api/v1/llm/tests/create-mail-user`，应返回 `email/password/access_token`，且该 token 可通过后端 JWTVerifier 验证。
- 前端：`/ai/jwt` 点击“一键生成测试用户”后可直接跑通“获取 token -> createMessage -> SSE 收到响应”。

## Issue CSV
- Path: `issues/2026-01-02_11-36-27-jwt-real-user-create.csv`
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描与精准定位。
- `functions:exec_command`：本地启动/探针/最小冒烟。
- `functions:apply_patch`：最小范围改动写入。
- `context7:resolve-library-id` + `context7:get-library-docs`：核验 Supabase Auth/Admin API 正确用法。

## Acceptance Checklist
- [ ] `/ai/jwt` 一键生成 `gymbro-test-01` 风格测试用户并自动登录。
- [ ] 返回的 `access_token` 为 Supabase Auth 真实签发（非本地伪造）。
- [ ] 端到端闭环可重复：token 获取 -> SSE -> 收到响应。
- [ ] 接口受控且可回滚：认证保护 + 开关/前缀限制 + 统一错误体。

## Risks / Blockers
- Supabase token 接口对 header/key 的要求可能与现有实现不同（需要权威文档校验并以运行结果为准）。
- 生产开放“创建测试用户”存在滥用风险（需加前缀白名单/速率限制/可禁用开关）。

## Rollback / Recovery
- 配置回滚：禁用“真实创建”分支，仅保留 `test-key-mock` 的 UI 冒烟路径。
- 代码回滚：单次改动集中在 `llm_tests` 与前端测试页，便于 `git revert`。

## Checkpoints
- Commit after: Phase 2（后端真实创建链路可用）
- Commit after: Phase 3（前端一键生成接入完成）

## References
- `app/api/v1/llm_tests.py`
- `app/services/mail_auth_service.py`
- `app/auth/supabase_provider.py`
- `web/src/views/test/real-user-sse.vue`
- `web/src/views/ai/model-suite/jwt/index.vue`
- `e2e/anon_jwt_sse/README.md`
