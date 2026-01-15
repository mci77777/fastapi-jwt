---
mode: plan
task: Dashboard 管理端账号/权限管理（本地 admin + 次级权限）
created_at: "2026-01-15T17:58:11+08:00"
complexity: complex
---

# Plan: Dashboard 管理端账号/权限管理（本地 admin + 次级权限）

## Goal
- Dashboard 支持多个本地登录账号（用户名/密码），并提供改密/重置/禁用的闭环管理能力。
- 支持次级权限账号：菜单/按钮权限与后端 API 强制校验一致（不依赖前端隐藏）。
- 权限与账号状态落地到 SQLite（SSOT），变更后立即生效且可追溯（含 request_id）。

## Scope
- In:
  - 后端：扩展 `local_users` 作为 Dashboard 本地账号 SSOT；新增后台账号管理 Admin API；改造 `/api/v1/base/*` 登录与权限返回；为敏感写接口补齐权限依赖。
  - 前端：新增“后台账号”管理页（创建/改角色/启禁用/重置密码），并接入 `v-permission`。
  - 测试：pytest 覆盖登录、越权、账号管理 API 的端到端链路。
- Out:
  - 不实现通用 RBAC 配置器（菜单/角色/权限可视化编辑）；仅固定角色集合与映射表。
  - 不实现找回密码/邮件/MFA；不把 Dashboard 本地账号同步到 Supabase。

## Assumptions / Dependencies
- Dashboard 本地账号 SSOT：SQLite `local_users`（不依赖 Supabase）。
- Token 仅承载 username 等最小信息；角色/权限以 SQLite 实时查询为准，避免“影子权限”。
- 系统权限固定 3 级（显示为 1/2/3）：`admin`（1）/ `manager`（2）/ `user`（3），并兼容旧 role 字符串折叠到三档。
- 既有前端权限机制：`/base/userapi` 返回 `accessApis`，由 `v-permission` 判断；后端必须同步强校验。

## Phases
1. 现状与同义实现扫描（SSOT 定稿）
   - 扫描 `/api/v1/base/*`、`app/api/v1/llm_common.py::is_dashboard_admin_user`、现有 `/api/v1/admin/*` 的鉴权点与前端 `v-permission` 使用方式。
   - 定义单处映射：`DashboardRole -> allowed_menus/allowed_apis/capabilities`（SSOT）。
2. 后端：账号与权限模型（SQLite SSOT）
   - 为 `local_users` 增列：`role`、`is_active`、`last_login_at`（必要时补 `created_at/updated_at` 已存在）。
   - 统一密码哈希/校验逻辑复用现有 scrypt 实现（避免重复）。
3. 后端：后台账号管理 Admin API（仅 admin）
   - 新增 `/api/v1/admin/dashboard-users/*`：
     - `GET /list`：账号列表（不返回 password_hash）。
     - `POST /create`：创建账号（用户名唯一、写入 role/is_active/password_hash）。
     - `POST /{username}/role`：更新角色（禁止降级最后一个 active admin）。
     - `POST /{username}/enable|disable`：启/禁用（同上保护）。
     - `POST /{username}/reset-password`：重置密码（一次性返回明文，仅响应体展示）。
4. 后端：登录/菜单/API 权限返回与强校验
   - `/base/access_token`：支持任意本地账号登录（保留首次启动 seed `admin/123456`）。
   - `/base/update_password`：支持本地账号自助改密（受 is_active/旧密码校验约束）。
   - `/base/userinfo|usermenu|userapi`：按 role 返回 `is_superuser`、菜单树与 api 列表。
   - 为敏感写接口补齐依赖：新增 `require_dashboard_capability(...)` 或 `require_dashboard_roles(...)` 并在关键路由使用。
5. 前端：后台账号管理页面
   - 新增 `web/src/views/system/admin-accounts/index.vue`（或复用 system 目录约定）：
     - 列表、创建、改角色、启禁用、重置密码（危险操作二次确认 + 复制密码）。
   - `web/src/api/index.js` 增加 dashboard-users API 封装；按钮使用 `v-permission`。
6. 验证与回滚
   - pytest：覆盖“创建账号→登录→权限生效→越权拒绝→重置密码”的闭环与错误路径（含 request_id）。
   - 构建：`make test` + `cd web && pnpm build`。
   - 回滚：`git revert`；SQLite 仅增列，向前兼容。

## Tests & Verification
- 本地账号登录：`POST /api/v1/base/access_token` -> 200；随后 `GET /api/v1/base/userinfo|usermenu|userapi` -> 200。
- 越权：非 `admin` 调用 `/api/v1/admin/dashboard-users/*` -> 403。
- 权限裁剪：次级角色菜单/按钮不可见，且直接调用未授权写接口同样 403。
- 构建：`make test`；`cd web && pnpm build`。

## Issue CSV
- Path: issues/2026-01-15_17-58-07-dashboard-admin-accounts-rbac.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描/入口定位与引用追踪
- `context7:resolve-library-id` + `context7:get-library-docs`：必要时核验依赖用法边界
- `Bash`：构建/测试/本地探针

## Acceptance Checklist
- [ ] 可创建多个 Dashboard 本地账号并登录成功
- [ ] 支持自助改密 + 管理员重置密码（一次性展示明文）
- [ ] 次级角色菜单/按钮权限裁剪正确
- [ ] 后端对敏感写接口强制校验（越权 403），不依赖前端隐藏
- [ ] `make test` 与前端构建通过且无错误

## Risks / Blockers
- 现有 admin 判定分散：需统一到新的依赖与 SSOT 映射，避免漏网接口。
- 误操作导致锁死：必须保证至少存在 1 个 active `admin`。

## Rollback / Recovery
- 代码：`git revert <commit>` 回滚。
- SQLite：仅新增列可向前兼容；无需强制回滚数据结构。

## Checkpoints
- Commit after: 后端账号 API + 登录/菜单/权限闭环跑通
- Commit after: 前端页面可用 + pytest/构建通过

## References
- `app/api/v1/base.py`
- `app/db/sqlite_manager.py`
- `app/api/v1/llm_common.py`
- `app/api/v1/admin_app_users.py`
- `web/src/views/system/app-users/index.vue`
- `web/src/directives/permission.js`
- `web/src/api/index.js`
