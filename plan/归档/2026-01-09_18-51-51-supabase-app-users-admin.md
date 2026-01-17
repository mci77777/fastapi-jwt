---
mode: plan
task: Supabase App 用户管理（订阅/权限/密码重置）
created_at: "2026-01-09T18:54:43+08:00"
complexity: complex
---

# Plan: Supabase App 用户管理（订阅/权限/密码重置）

## Goal
- Dashboard 管理端可稳定拉取 App 用户（以 Supabase `auth.users` 为全集，`public.users` 为资料扩展）并提供一致的“用户快照”。
- 提供最小闭环的管理能力：订阅等级（`user_entitlements`）、权限/角色、账号禁用、密码重置；所有写入可追溯（审计）且错误可诊断（含 `request_id`）。

## Scope
- In:
  - 后端：新增 App 用户管理 Admin API（列表/详情/禁用/密码重置/订阅/权限）
  - Supabase：新增/补齐 SSOT 视图/表以支撑聚合查询与最小权限模型
  - 前端：新增“App 用户管理”页（与现有 `web/src/views/system/user/*` 分离），并复用现有“权益等级预设”页作为订阅编辑辅助
- Out:
  - 不以 `web/src/views/system/user/*` 作为实现目标（那套是历史 RBAC UI/占位，且后端未实现 `/api/v1/user/*`）
  - 不实现复杂组织/多租户/层级 RBAC（先做单用户：role + permissions JSON）

## Assumptions / Dependencies
- Supabase：已存在 `auth.users` 与 `public.users`，且两者数量可能不一致（例如 `auth.users` 远多于 `public.users`）。
- 订阅 SSOT：`public.user_entitlements`（已存在）；App 侧按 `tier/expires_at/flags` 门控。
- Dashboard 管理鉴权：复用 `app/api/v1/llm_common.py::is_dashboard_admin_user()`（仅 admin 可访问 `/api/v1/admin/*`）。

## Phases
1. SSOT 设计与同义实现扫描
   - 同义扫描：`/me`、`EntitlementService/UserRepository`、`admin_user_entitlements`、前端现有“用户管理/权益管理”页面，明确“App 用户管理”的数据源与边界。
   - 定稿字段字典（SSOT）：统一将 `auth.users` 的字段（`id,email,is_anonymous,last_sign_in_at,created_at,banned_until` 等）与 `public.users` 的字段（`user_id,isactive,username,avatar,...`）做一个“聚合快照”。

2. Supabase 结构（SSOT）
   - 新增视图：`public.app_users_admin_view`
     - `FROM auth.users au`
     - `LEFT JOIN public.users pu ON pu.user_id = au.id`
     - `LEFT JOIN public.user_entitlements ue ON ue.user_id = au.id`
     - 权限信息来源（SSOT 选择）：优先写入 `auth.users.raw_app_meta_data`（通过 Auth Admin API 更新）并在视图中映射为 `role/permissions`；避免额外 `public.user_permissions` 影子状态。
     - 仅授予 `service_role` SELECT（避免 PostgREST 暴露给客户端）。
   - 如必须持久化“细粒度权限”且不放入 `auth.users`：再新增 `public.user_permissions`（`user_id pk` + `role` + `permissions_json`），并明确与 JWT claims 的映射策略（SSOT）。

3. 后端：Supabase Auth Admin 客户端封装（KISS）
   - 新增 `SupabaseAuthAdminClient`（或集中到现有 `SupabaseAdminClient`）
     - List users（分页）
     - Get user by id
     - Update user（禁用/解禁、设置 app_metadata/user_metadata、设置密码）
     - Reset password 策略：管理员直接设置随机密码（可选强制下次登录改密）；不依赖邮件系统。
   - 用 `supabase-mcp-server:search_docs` 核验 Admin API 的正确路径/能力边界。

4. 后端：App 用户管理 API（端到端闭环）
   - 新增路由：`/api/v1/admin/app-users/*`
     - `GET /list`：分页 + keyword（email/username）+ filters（仅匿名/仅活跃/仅有资料/仅有订阅/订阅 tier）
     - `GET /{user_id}`：返回聚合快照（auth 摘要 + public 资料 + entitlements + role/permissions）
     - `POST /{user_id}/entitlements`：写 `public.user_entitlements`（复用 `SupabaseAdminClient.upsert_one`）
     - `POST /{user_id}/permissions`：写入 `auth.users` app_metadata（SSOT）
     - `POST /{user_id}/disable` / `enable`：写 `public.users.isactive`（并按需同步 `auth.users.banned_until`）
     - `POST /{user_id}/reset-password`：管理员重置密码（返回一次性明文密码仅在响应中展示，且强制前端二次确认）
   - 审计：写入 `public.audit_logs`（已有表）记录 admin 操作（action/resource/resource_id/target user）。
   - 错误响应：统一走 `app/core/exceptions.py::create_error_response()`（含 `hint`）。

5. 前端：App 用户管理页面 + 配置项
   - 新增页面：`/system/app-users`（或 `/system/app-user-admin`）
     - 列表：默认不展示匿名用户（但显示匿名数量/占比）
     - 详情抽屉：订阅编辑、权限编辑、禁用/解禁、重置密码
   - 新增“用户管理配置项”（Dashboard 本地配置 SSOT，落地 SQLite）：
     - 默认分页大小、默认排序字段
     - 默认过滤（是否包含匿名、是否仅活跃、是否仅有 profile）
     - 危险操作开关（是否允许删除/重置密码/禁用）
     - 二次确认策略（强制输入 user_id/email 才能执行重置/禁用）

6. 验证与可回滚
   - pytest：覆盖 list/detail/filter、entitlements 写入、permissions 写入、reset-password/disable 的错误路径与审计写入。
   - Supabase 校验脚本：增强 `scripts/verification/verify_supabase_config.py` 校验 `app_users_admin_view` 可访问。
   - Docker 冒烟：重建镜像后前端请求统一走 `/api/v1/*`；避免错误 baseURL 导致 `ERR_CONNECTION_CLOSED`。

## Tests & Verification
- Supabase 结构：`supabase-mcp-server:execute_sql` 校验视图存在且可查询（service_role）。
- API：`make test` 覆盖新增 admin app-users 路由与审计写入。
- 部署：`docker compose ... build --no-cache app && docker compose ... up -d --force-recreate` 后：
  - `curl -f http://localhost/api/v1/healthz`
  - 浏览器 Network：`/api/v1/admin/app-users/list` 返回 200 且响应体结构正确。

## Issue CSV
- Path: issues/2026-01-09_18-51-51-supabase-app-users-admin.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描/入口定位（Windows 路径 SSOT）
- `supabase-mcp-server:execute_sql`：核验 Supabase 实际表/字段/行数
- `supabase-mcp-server:apply_migration`：新增 view/table（DDL）
- `supabase-mcp-server:search_docs`：核验 Auth Admin API（reset password/ban/update metadata）
- `context7:resolve-library-id` + `context7:get-library-docs`：必要时校验 Supabase Admin API 客户端用法

## Acceptance Checklist
- [ ] App 用户列表来自 `auth.users`（即使 `public.users` 缺失也能显示，并明确标注缺失字段）
- [ ] 订阅等级可读写（`public.user_entitlements` SSOT），并在用户详情页可编辑
- [ ] 权限/角色可读写（SSOT 明确：写入 `auth.users` app_metadata 或 `public.user_permissions`），并在用户详情页可编辑
- [ ] 管理动作可用：禁用/解禁、密码重置（最小闭环），且写入 `public.audit_logs`
- [ ] 错误响应统一格式（含 `request_id`），且 Docker 部署下请求路径稳定，无 `ERR_CONNECTION_CLOSED`

## Risks / Blockers
- `auth.users` 与 `public.users` 不一致（历史数据/匿名用户/迁移残留）：需要视图/接口明确“缺失资料”的语义与过滤策略。
- Admin API 权限边界：部分能力（禁用/密码）需严格二次确认与审计，避免误操作。
- 视图跨 schema join 的权限与性能：需限制仅 `service_role` 使用，并必要时加索引/分页策略。

## Rollback / Recovery
- Supabase：回滚为 `DROP VIEW public.app_users_admin_view`（或 `CREATE OR REPLACE` 回到旧定义）；如新增表则 `DROP TABLE public.user_permissions`（前提：无关键数据）。
- 代码：单次提交 `git revert`。

## Checkpoints
- Commit after: Supabase 视图 + 后端 list/detail 路由端到端可用
- Commit after: 订阅/权限/禁用/重置密码闭环 + 审计写入 + pytest 通过

## References
- `app/api/v1/me.py`
- `app/repositories/user_repo.py`
- `app/services/entitlement_service.py`
- `app/api/v1/admin_user_entitlements.py`
- `docs/schemas/SUPABASE_SCHEMA_OWNERSHIP_AND_NAMING.md`
- `docs/mcp-tools.md`
