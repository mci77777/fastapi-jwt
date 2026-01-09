---
mode: plan
task: App 用户管理（Apple 极简交互重构）
created_at: "2026-01-09T22:11:32+08:00"
complexity: complex
---

# Plan: App 用户管理（Apple 极简交互重构）

## Goal
- 只保留一个入口完成基础管理：列表 → 详情抽屉 →（订阅/权限/禁用/重置密码）。
- 默认不展示技术细节（UUID/JSON/错误码/表名），需要时再展开。
- 冷启动更快：首屏请求数最少（bootstrap + list）。

## Scope
- In:
  - 前端：重构「App 用户管理」交互为“列表 + 详情抽屉 + 少量动作”。
  - 后端：提供 `bootstrap` 聚合接口（config + stats + tierPresets + readiness）。
  - 合并：不再提供“手填 user_id 的用户权益管理”入口，订阅编辑统一放在 App 用户详情抽屉。
- Out:
  - 不做复杂组织/多租户/层级 RBAC。
  - 不在 UI 暴露 Supabase 技术实现（表/视图/错误码）。

## Assumptions / Dependencies
- `auth.users` 是用户存在性 SSOT；`public.users` 可能存在孤儿行，不能作为可管理用户来源。
- `public.app_users_admin_view` 已存在并可被 service_role 读取。

## Phases
1. 后端：冷启动优化（KISS）
   - 新增 `GET /api/v1/admin/app-users/bootstrap` 聚合返回：`config`、`stats`、`tier_presets`、`supabase_ready`。
   - 错误返回保持统一 `code/msg/request_id`，但 msg 对用户友好（不暴露 23503/PGRST205）。
2. 前端：Apple 极简交互
   - 列表只保留核心列（email/username/tier/状态），点击行打开详情抽屉。
   - 抽屉内按“账号 / 订阅 / 权限”分区；危险操作折叠并统一二次确认。
   - JSON（flags/permissions）默认隐藏，放入“高级”折叠区。
3. 合并与降噪
   - 菜单只保留「App 用户管理」与必要配置入口；移除重复入口。
   - 提示文案统一短句 + 可诊断 request_id。
4. 验证与可回滚
   - `make test`、`cd web && pnpm build`、`docker compose build --no-cache app && docker compose up -d --force-recreate app`。
   - 回滚：恢复旧页面入口 + 回退新 bootstrap 与 UI 改动（不触碰线上数据）。

## Tests & Verification
- 后端：pytest 覆盖 bootstrap + 关键动作（提权/禁用/重置密码）错误路径。
- 前端：`pnpm build` 通过。
- 部署：Docker 重建后 `GET /api/v1/healthz`=200；页面可用。

## Issue CSV
- Path: issues/2026-01-09_22-11-05-app-users-ui-minimal.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描与最小改动定位。
- `supabase-mcp-server:apply_migration`：调整/重建 Supabase view。
- `supabase-mcp-server:list_tables`：核验 Supabase 实际结构。

## Acceptance Checklist
- [ ] App 用户页首屏 ≤2 个请求（bootstrap + list）。
- [ ] 订阅/权限/禁用/重置密码都在“用户详情抽屉”完成。
- [ ] 默认不展示 UUID/JSON/错误码；错误提示短句 + request_id。
- [ ] 旧“用户权益（手填 user_id）”入口不再出现在导航。

## Risks / Blockers
- Supabase 结构差异导致 view 字段变动：用 `supabase_ready=false` 明确提示，并提供修复引导。

## Rollback / Recovery
- 回退前端路由/菜单与新增 bootstrap 接口；Supabase 仅保留视图不影响数据。

## Checkpoints
- Commit after: 后端 bootstrap + pytest
- Commit after: 前端极简交互 + Docker 冒烟

## References
- `web/src/views/system/app-users/index.vue`
- `app/api/v1/admin_app_users.py`
- `scripts/deployment/sql/create_supabase_tables.sql`
