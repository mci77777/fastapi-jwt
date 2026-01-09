# Supabase Schema 归属与命名规范（后端 SSOT，不改动 App 端）

## 目标与边界

- **目标**：在本项目内将 Supabase 表结构的“归属”与“命名规范”说清楚，并以此作为后续变更与审计的**唯一权威来源（SSOT）**。
- **边界**：本仓库的后端/Edge Function 只应使用并维护“后端归属表”；**App 端（移动端/其他客户端）依赖的表不做破坏性改动**。

> 备注：Supabase 的 `auth.users` 是 Auth 系统用户表；`public.users` 是业务用户表（App 侧常用），两者不要混用。

## 表归属（Ownership）

### public 表清单（快照）

以下为当前项目 `public` schema 下的表名快照（生成日期：2026-01-09）。该清单用于“最初解释清晰”，后续以审计脚本生成的报告为准。

- `ai_model`
- `ai_prompt`
- `anon_messages`
- `anon_rate_limits`
- `anon_sessions`
- `api_endpoints`
- `audit_logs`
- `calendar_events`
- `conversations`
- `gateway_configs`
- `memory_records`
- `messages`
- `public_content`
- `public_shares`
- `search_content`
- `system_prompts`
- `tokens`
- `user_anon`
- `user_entitlements`
- `user_metrics`
- `user_profiles`
- `user_settings`
- `users`

### A. 后端归属表（本仓库负责维护）

#### 1) 对话/消息（B2 SSOT）

- `public.conversations`：会话主表（后端写入/查询）
- `public.messages`：消息明细表（后端写入/查询）

#### 2) AI 配置（可选初始化）

- `public.ai_model`：模型端点/供应商配置（后端读写；可配合 Dashboard）
- `public.ai_prompt`：Prompt 配置（后端读写；可配合 Dashboard）

#### 3) 匿名链路/Edge Function（后端或 Edge 负责）

- `public.user_anon`
- `public.anon_sessions`
- `public.anon_messages`
- `public.anon_rate_limits`

> 上述匿名相关表名在 Edge Functions 中通过 `rest/v1/<table>` 被直接访问。

### B. App 端归属表（禁止破坏性改动；仅允许“加字段/加索引”等兼容性变更）

- `public.users` / `public.user_profiles` / `public.user_settings` / `public.user_metrics` 等：业务用户资料与设置
- 以及任何由 App 侧直连/SDK 直连访问的其他 `public.*` 表（如 `public_content`、`public_shares` 等，需以实际客户端为准）

## 后端 SSOT 表结构（权威说明）

### `public.conversations`

- **主键**：`id uuid`（默认 `gen_random_uuid()`）
- **归属用户**：`user_id uuid`，**外键指向 `auth.users(id)`**
- **字段**：`title text`、`is_active boolean`、`user_type text`
- **时间戳**：`created_at timestamptz`、`updated_at timestamptz`（由触发器自动更新）
- **索引**：`idx_conversations_user_id`、`idx_conversations_created_at`
- **RLS**：`authenticated` 仅能 SELECT/INSERT 自己的数据（后端使用 `service_role` 时不受限）

### `public.messages`

- **主键**：`id uuid`（默认 `gen_random_uuid()`）
- **外键**：
  - `conversation_id uuid` → `public.conversations(id)`（ON DELETE CASCADE）
  - `user_id uuid` → `auth.users(id)`（ON DELETE CASCADE）
- **字段**：`role text`（如 `user/assistant`）、`content text`、`user_type text`
- **时间戳**：`created_at timestamptz`、`updated_at timestamptz`（由触发器自动更新）
- **索引**：`idx_messages_conversation_id`、`idx_messages_user_id`、`idx_messages_created_at`
- **RLS**：`authenticated` 仅能 SELECT/INSERT 自己的数据，且 INSERT 必须属于自己的 conversation

### `public.ai_model` / `public.ai_prompt`

- 以 `id`（自增）为主键，配套 `created_at/updated_at` 与 RLS 策略。
- **注意**：`api_key` 属于敏感字段，建议仅由后端 `service_role` 写入/读取；不要在建表脚本中写入示例 key。

## 命名规范（本仓库统一执行）

### 1) 适用范围

- 对 **“后端归属表”**：强制执行本规范（表名/字段名/索引名/约束名/触发器名/策略名）
- 对 **“App 端归属表”**：不强制改名（避免破坏客户端），但新增对象应尽量遵循本规范

### 2) 规则

- **表名/字段名**：`snake_case`（小写 + 下划线），避免缩写歧义
- **时间字段**：统一 `created_at` / `updated_at`
- **外键字段**：统一 `<ref>_id`（例如 `user_id`、`conversation_id`）
- **索引**：`idx_<table>_<column>`（必要时追加复合字段）
- **约束**：
  - 主键：`<table>_pkey`
  - 外键：`<table>_<column>_fkey`
- **触发器/函数**：
  - `public.update_updated_at_column()` 作为唯一通用实现
  - 触发器命名：`update_<table>_updated_at`

## 配套审计脚本

- 运行：`python scripts/verification/audit_supabase_naming.py`
- 输出：`report/audit/supabase_naming_report.md`、`report/audit/supabase_naming_report.json`
- 归属配置：`docs/schemas/supabase_ownership_map.json`
