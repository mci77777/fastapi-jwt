# 匿名用户（Anonymous）支持 · API 契约增补
**版本**: v1.0  
**更新时间**: 2025-09-28 23:43 PDT

## 认证与上下文
- Header: `Authorization: Bearer <access_token>`（Supabase 匿名会话）
- 解析字段：`sub`, `iss`, `exp`, `iat`, `is_anonymous`（后端仅用于授权，不回传给客户端）

## 策略门（Policy Gate）
- **仅匿名受限** 的端点样例：
  - `POST /api/v1/conversations/{id}/share` → 403（匿名禁用公开分享）
  - `GET /api/v1/admin/*` → 403（后台管理禁止匿名）
  - `POST /api/v1/messages/batch` → 429/403（按配额或直接禁用）

## 速率与并发（摘要）
- 匿名用户：默认 `QPS=5`、`日配额=1,000`、`SSE并发=2`
- 永久用户：按 K3 既定阈值；具体见 ANON_RATE_LIMITING.md

## 统一错误体
- 复用 K1 标准：`status/code/message/trace_id/hint`；其中 `hint` 可提示“升级账号以提升配额”。
