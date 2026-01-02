---
mode: plan
task: JWT 测试用户持久化与选择
created_at: 2026-01-02T14:18:23
complexity: medium
---

# Plan: JWT 测试用户持久化与选择

## Goal
- `/ai/jwt` 可一键创建 Mail API 测试用户并写入本地 SQLite；并支持从已保存用户列表中选择/刷新 token 用于 JWT 测试与并发压测。

## Scope
- In:
  - 后端：保存/列出/刷新测试用户 token 的接口与 SQLite 表
  - 前端：JWT 测试页增加“已保存用户”选择与“刷新 token/新建用户”操作区
- Out:
  - 生产级用户管理/权限系统扩展
  - 前端暴露 Mail API Key（仍以后端 env 为 SSOT）

## Assumptions / Dependencies
- 依赖后端已配置 `SUPABASE_*` 与 `MAIL_API_*`（否则返回可诊断的 JSON 错误体，避免 Cloudflare 502 HTML）。

## Phases
1. 设计并落地 SQLite 表 `llm_test_users`（最小字段 + 兼容升级）
2. 升级 `create-mail-user`：创建后持久化；支持“优先复用已保存用户并 refresh”
3. 新增接口：列出用户、按用户刷新 access_token（用于选择/并发）
4. 前端 `/ai/jwt`：增加用户选择、刷新 token、快速回填 email/password（可选）并接入现有 SSE 测试链路
5. 最小验证：后端启动 + 探针 + 关键接口冒烟；可回滚

## Tests & Verification
- 创建测试用户 -> DB 有记录 -> 列表可见 -> 刷新 token 成功 -> 用 token 发起 `/messages` + SSE 成功

## Issue CSV
- Path: issues/2026-01-02_14-18-23-jwt-mail-user-db-persistence.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `functions.exec_command`：检索/构建/运行
- `functions.apply_patch`：最小变更落地

## Acceptance Checklist
- [ ] 创建 Mail 测试用户后写入本地 SQLite，刷新/选择可复用
- [ ] `/ai/jwt` 可选择已保存用户并刷新 token 后完成 SSE 测试
- [ ] 错误体不依赖 5xx（避免 Cloudflare HTML），可定位（含 `request_id/hint`）

## Risks / Blockers
- Supabase refresh token 失效/被回收：需提示用户“强制新建”

## Rollback / Recovery
- 直接 `git revert` 本次提交；SQLite 新表为新增，不影响既有路径

## Checkpoints
- Commit after: 后端接口落地 + 前端 UI 接入 + 最小冒烟通过

## References
- app/api/v1/llm_tests.py
- app/db/sqlite_manager.py
- web/src/views/test/real-user-sse.vue
