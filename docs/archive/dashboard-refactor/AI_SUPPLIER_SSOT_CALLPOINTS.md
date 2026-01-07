# AI 供应商 → 映射 → Models(JWT/App) SSOT：调用点清单

## 单一链路（对外契约）

1. **供应商 endpoints（仅管理后台）**
   - 入口：`app/api/v1/llm_models.py`
   - 读写：`app/services/ai_config_service.py`（SQLite：`ai_endpoints` / `ai_prompts`）

2. **模型映射（SSOT 配置入口）**
   - 入口：`app/api/v1/llm_mappings.py`
   - 读写：`app/services/model_mapping_service.py`
   - 落盘：`AI_RUNTIME_STORAGE_DIR/model_mappings.json` + `AI_RUNTIME_STORAGE_DIR/blocked_models.json`

3. **对外只暴露 mapped models（App/JWT 统一消费）**
   - 入口：`GET /api/v1/llm/models`（默认 `view=mapped`）
   - 计算：`app/services/ai_service.py::list_app_model_scopes()`
   - 契约：`data[].name` 即客户端可发送的 `model`（映射名）；后端负责映射到真实供应商 model + endpoint

4. **消息闭环（JWT/App 真实调用）**
   - 创建：`POST /api/v1/messages`（`app/api/v1/messages.py`）
   - SSE：`GET /api/v1/messages/{message_id}/events`（`app/api/v1/messages.py`）
   - 上游调用：`app/services/ai_service.py::_select_endpoint_and_model()` → `_call_openai_chat_completions()` / `_call_anthropic_messages()`

## 允许的“直连供应商”位置（内部实现）

- **连通性探测 / 拉取模型列表**：`app/services/ai_config_service.py`（用于 endpoints 管理与监控）
- **对话上游请求**：`app/services/ai_service.py`（仅通过“映射解析后的 endpoint + model”发起请求）

## 禁止/已移除的旁路（避免影子状态）

- ✅ 已移除：`app/services/jwt_test_service.py`、`/api/v1/llm/tests/(dialog|load|runs)`
- ✅ 脚本默认只读：`scripts/testing/api/test_api.py`（需显式 `--apply` 才允许创建端点/Prompt）

## 持久化 SSOT（容器重启/重建不丢）

- SQLite：`./data` volume（Docker 内 `/opt/vue-fastapi-admin/data`）
- 运行态目录：`AI_RUNTIME_STORAGE_DIR`（默认 `data/ai_runtime`，Docker 已挂载到同一 volume）
