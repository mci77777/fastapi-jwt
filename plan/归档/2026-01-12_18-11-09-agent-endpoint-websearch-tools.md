---
mode: plan
task: Agent 对话端点（后端工具：Web 搜索 + 动作库检索）
created_at: "2026-01-12T18:42:52+08:00"
complexity: complex
---

# Plan: `/agent` 对话端点（后端工具：Web 搜索 + 动作库检索）

## Goal
- App 端只调用 `/api/v1/agent/*` 即可发起一次 Agent 对话，并通过 SSE 收到：状态→工具结果→模型回复（ThinkingML）→完成/错误；且具备稳定的返回结构体与可对账字段（`request_id/run_id/conversation_id`）。

## Scope
- In:
  - 新增 Agent Run 入口：创建 run + 订阅事件（优先 SSE）
  - 定义并固化返回结构体（Pydantic + JSON Schema + 文档）
  - 后端工具执行：`web_search`、`exercise_library.search/get_detail`
  - 最小缓存与配额：Web 搜索可控成本（TTL 缓存/限流/去重）
- Out:
  - 多 Agent 编排（planner/critic/worker 多角色）
  - WebSocket 双向（中断/补充输入/并行多 run）
  - 全网网页抓取与长文总结（v1 仅搜索结果+摘要，抓取后置）

## Assumptions / Dependencies
- 复用现有 SSE SSOT：`app/services/ai_service.py::MessageEventBroker`（避免另起一套长连接/事件协议）。
- 工具触发采用“后端规划+执行”，不依赖上游 `tool_calls`（多方言/多供应商兼容）。
- Web 搜索 Provider 选型：**Exa**；通过环境变量提供 `EXA_API_KEY`（不落库、不开源提交）；v1 提供 `mock` 兜底与 feature flag 控制是否允许外网搜索。

## Phases
1. 统一合约与结构体（SSOT）
2. 后端 Agent Runner（规划→工具→生成）与 SSE 事件打通
3. 成本控制（缓存/限流）+ 测试/E2E + 文档落地

## Tests & Verification
- 合约：新增 JSON Schema 校验（request/response/events）并与文档一致
- 集成：本地启动后执行一次 run，SSE 事件序列完整且可拼接 `content_delta`
- 回归：`make test` + 现有 `/api/v1/messages` SSE 契约不回归
- E2E：新增最小脚本（或复用 `scripts/monitoring/local_mock_ai_conversation_e2e.py` 思路）验证工具事件与最终输出

## Issue CSV
- Path: issues/2026-01-12_18-11-09-agent-endpoint-websearch-tools.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描（复用 `/messages` SSE、现有 `/agents` WS stub）
- `functions:shell_command`：检索/构建/测试/启动/冒烟验证
- `functions:apply_patch`：最小改动新增端点/结构体/schema/文档
- `functions:mcp__context7__resolve-library-id` + `functions:mcp__context7__get-library-docs`：核验 FastAPI SSE/Web 搜索 Provider SDK 用法（如需）

## Acceptance Checklist
- [ ] `POST /api/v1/agent/runs` 返回稳定结构体（含 `run_id/conversation_id/request_id`，可对账）
- [ ] `GET /api/v1/agent/runs/{run_id}/events` SSE 可稳定产出 `status/tool_result/content_delta/completed|error`
- [ ] Web 搜索与动作库检索均由后端执行，App 无需 functioncall/解析 tool JSON
- [ ] Web 搜索具备最小成本控制（缓存 TTL、去重、限流/配额、超时）
- [ ] 不破坏现有 `/api/v1/messages`、`docs/ai预期响应结构.md` 与 SSE 事件契约

## Risks / Blockers
- Web 搜索外呼成本与合规（Exa 计费、配额、超时、缓存命中率）需要在测试环境可控开关
- 长连接规模：SSE 连接数上升需评估（反代超时、心跳频率、并发限制）
- 工具结果注入 prompt 的长度控制（避免 token 暴涨）

## Rollback / Recovery
- 增加 feature flag：关闭 `/agent` 路由注册即可快速回滚；或 revert 单提交恢复（不触碰 `/messages` 主链路）

## Checkpoints
- Commit after: 合约/结构体 + 文档 + schema
- Commit after: Agent Runner + 工具执行 + SSE 事件
- Commit after: 缓存/限流 + 测试/E2E + 回归通过

## References
- `docs/ai预期响应结构.md`
- `assets/prompts/tool.md`
- `docs/api-contracts/api_gymbro_cloud_conversation_min_contract.md`
- `app/services/ai_service.py`
- `app/api/v1/messages.py`
- `app/api/v1/agents.py`
- `app/api/v1/exercise_library.py`
