# Agent Run（/api/v1/agent）对接契约与 Web 调试

## 1) 契约（Contract / 对接文档）

- Agent Run 最小契约（SSOT）：`docs/api-contracts/api_gymbro_cloud_agent_run_min_contract.md`
- ThinkingML 输出结构（SSOT）：`docs/ai预期响应结构.md`

> 说明：App/Web 只消费 SSE 事件与最终 reply；所有工具（Web 搜索 / 动作库检索）均由后端执行。

## 2) Web 搜索（Exa）配置

两种方式二选一：

1) **推荐：Web 管理端填写（持久化）**
   - 进入管理端「系统 → AI」页
   - 在「Web 搜索（Exa）」卡片中填写 Key → 保存 → 开启开关

2) **容器环境变量（快速临时）**
   - 设置 `EXA_API_KEY`（优先级低于 DB 配置）

安全约束：
- 后端读取配置时只回显 `web_search_exa_api_key_masked`，不会返回明文 key。

## 3) JWT E2E（Web 调试页）

前端已在 JWT 测试页增加 **Agent / Messages** 两个 Tab（默认 Agent Run，复用同一套 token / model / SSE 解析能力）：

- 组件实现：`web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue`
- 默认 Tab：`Agent（后端工具）`
- 支持：请求级禁用工具 / top_k、独立展示 `tool_start`/`tool_result`、并预览 Dashboard 生效的 system/tools prompts（SSOT）

相关只读接口（用于预览 SSOT 配置）：
- `GET /api/v1/llm/tests/active-prompts`

推荐流程：
1) 在页面上先获取 JWT（匿名/永久均可；建议先用永久 token 便于排障）
2) 选择模型（来自 `/api/v1/llm/models`）
3) 输入消息内容
4) 点击 `Agent Run 并拉流`，在 SSE 事件列表中观察：
   - `tool_start` / `tool_result`
   - `content_delta`（拼接 reply）
   - `completed` / `error`
   
说明：
- 匿名用户也允许执行 `web_search.exa`（仍受 `web_search_enabled` 开关、限流与配额影响）。

## 4) Docker 重启/重新部署

```bash
docker compose up -d --build
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
curl -fsS http://localhost/api/v1/healthz
```
