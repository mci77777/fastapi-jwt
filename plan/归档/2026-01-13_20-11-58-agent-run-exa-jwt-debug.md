---
mode: plan
task: Agent Run + Exa + JWT Debug（SSOT）
created_at: "2026-01-13T20:11:58+08:00"
complexity: complex
---

# Plan: Agent Run（/agent）+ Exa Web 搜索 + JWT 调试页对齐

## Goal
- App 通过 `POST /api/v1/agent/runs` + `GET /api/v1/agent/runs/{run_id}/events` 获得 ThinkingML v4.5（Strict-XML）回复。
- Web 搜索默认走 Exa，Key/开关由 Dashboard 写入 `llm_app_settings` 管理；env 仅作兜底。
- Dashboard 可管理 `agent_system/agent_tools`；JWT 调试页可对账“配置/拼接后的 system prompt + tools schema”。

## Scope
- In:
  - 后端：Agent Run 工具执行（Exa + 动作库）可观测；prompt/tools SSOT 组装与快照；匿名/普通用户可用。
  - 前端：JWT SSE 调试页（messages/agent 双 tab）工具/提示更直观；token 记忆稳定；与 Dashboard 配置对齐。
  - 文档：补齐 `docs/` 下的 Agent Run/Exa 配置与调试说明。
- Out:
  - WebSocket 方案（本期坚持 SSE；仅在文档记录成本评估）。
  - 扩展更多搜索提供商/工具库（仅 Exa + 动作库）。

## Assumptions / Dependencies
- 输出结构 SSOT：`docs/ai预期响应结构.md`（ThinkingML v4.5）。
- 工具执行 SSOT：全部在后端执行，客户端只消费 SSE（不依赖上游 tool_calls）。
- 若用户在调试中手动选择 `tool_choice=auto/required`，可能触发上游 tool_calls；当前后端不执行 tool_calls，需在 UI/文档做护栏与提示。

## Phases
1. 现状核对 + 同义实现扫描（agent_runs、prompt SSOT、llm_app_config、JWT 调试页）
2. 后端对齐：Exa 配置与错误可读；active-agent-prompts 快照增强（含 tools schema）；/agent 工具事件字段对齐
3. 前端对齐：JWT 调试页 token 记忆/不丢；Agent/Messages prompt 注入与 tools 选择更直观且与 Dashboard 一致
4. 文档补齐 + Docker 重启部署 + JWT E2E/调试验证

## Tests & Verification
- Docker 重启后：`GET /api/v1/healthz`=200
- Dashboard 配置 Exa：`web_search.exa` 在 Agent SSE 中 `tool_result.ok=true`
- 未配置 Exa：`tool_result.ok=false` 且 `error.code=missing_api_key`
- JWT 调试页：messages/agent 两种模式下 completed 自动校验 ThinkingML v4.5 可通过（推荐配置）

## Issue CSV
- Path: issues/2026-01-13_20-11-58-agent-run-exa-jwt-debug.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- Context7：核验 OpenAI `tools/tool_choice` 默认行为与注入方式（用于 UI 护栏与文档说明）。
- Shell：构建/重启 docker、跑健康检查。
- apply_patch：最小变更落地（YAGNI / SSOT / KISS）。

## Acceptance Checklist
- [ ] Agent prompts/tools 可在 Dashboard 管理，JWT 页预览与实际请求一致（SSOT）
- [ ] Exa key 从 Dashboard 配置生效（env 兜底），工具事件可观测且错误可读
- [ ] JWT 调试页 token 不因切换/刷新丢失；匿名 JWT 也可跑通 `/agent/runs`
- [ ] ThinkingML v4.5 校验在“推荐配置”下稳定通过；非支持配置有明确提示
- [ ] Docker 重启部署后无错误，健康检查通过

## Risks / Blockers
- 上游返回 tool_calls 时（tool_choice=auto/required + tools schema），当前后端不执行 tool_calls，可能导致空回复/校验失败；需明确护栏或实现 tool loop（本期默认做护栏）。

## Rollback / Recovery
- 回滚代码：`git revert <commit>`
- 回滚配置：Dashboard 清空 `web_search_exa_api_key` 并关闭 `web_search_enabled`
- 回滚部署：`docker compose up -d --build`

## Checkpoints
- Commit after: 后端对齐完成
- Commit after: 前端 JWT 调试页完成
- Commit after: 文档 + 部署验证完成

## References
- app/api/v1/agent_runs.py
- app/api/v1/llm_models.py
- web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue
- docs/api-contracts/api_gymbro_cloud_agent_run_min_contract.md
- docs/ai预期响应结构.md
