# 模型管理测试记录

> 2026-01 更新：`JWTTestService` 与 `/llm/tests/(dialog|load|runs)` 已移除；JWT 验证统一走真实链路 `POST /api/v1/messages` + SSE（`/api/v1/messages/{id}/events`）。
> “模型目录”页面已删除，`/ai/catalog` 仅保留为 `/ai`（模型映射）路由别名。运行态目录 SSOT 为 `AI_RUNTIME_STORAGE_DIR`（默认 `data/ai_runtime`）。

## 自动化（推荐）

- 统一命令：`make test`
- 关键用例：
  - `tests/test_model_mapping_service.py`
  - `tests/test_app_models_messages_sse_micro_e2e.py`
  - `tests/test_ai_config_service_push.py`

## 手工验证（最小清单）

1. **路由别名**：访问 `/ai` 与 `/ai/catalog` 均落到“模型映射”页面（同一状态）。
2. **模型白名单（SSOT）**：`GET /api/v1/llm/models`（默认 `view=mapped`）返回 `{ code, msg, total, data }`，且 `data[].name` 为 App 发送的 `model`（映射名）。
3. **消息闭环**：`POST /api/v1/messages` 创建（202）后，`GET /api/v1/messages/{message_id}/events?conversation_id=...` 拉 SSE，事件包含 `status/content_delta/completed/error/heartbeat`。
4. **权限边界**：非管理员菜单不展示 `/system/ai` 与 `/ai`；即便手工请求 `view=endpoints` 也会降级为 `mapped`（只读）。
