---
mode: plan
task: Agent Prompt/Tools（ThinkingML v4.5）+ JWT 工具调试一致性
created_at: "2026-01-13T13:04:20+08:00"
complexity: complex
---

# Plan: Agent Prompt/Tools（ThinkingML v4.5）+ JWT 工具调试一致性

## Goal
- Agent（`/api/v1/agent/*`）在使用后端工具时，最终回复 **仍稳定通过 ThinkingML v4.5 校验**（不再出现 `invalid_thinking_block_count`）。
- JWT 测试页把“工具测试”流程做成 **一眼能跑通**：选工具 → 触发 → 看 `tool_*` 事件 → 校验通过。
- Dashboard 的 Prompt/Tools 配置与 JWT 测试页行为 **同一套组装逻辑（SSOT）**，避免“JWT 过了 Dashboard 不行/反之亦然”。

## Scope
- In:
  - 制作/固化 Agent 专用 Prompt 约束（仍输出 `<thinking>...</thinking><final>...</final>`，含 `serp_queries` 注释块）
  - 制作/固化 Agent Tools 配置（后端工具：动作库检索、Web 搜索；工具结果以 **内部 XML** 注入，避免污染输出）
  - JWT 测试页：把 `/messages`（基线）与 `/agent/runs`（工具）分流，默认走工具链路，并可视化 tool 事件
  - 对齐 Prompt 组装 SSOT：`/messages`、Dashboard Prompt Test、JWT 测试页使用同一套“system + tools + tool_choice gating”规则
  - 增加必要的回归测试矩阵（不出网）
- Out:
  - 执行上游 tool_calls（仍坚持“动作尽量在后端实现”）
  - 多 Agent 编排/Planner/并行工具（先保证单轮稳定）
  - WebSocket（继续复用 SSE）

## Assumptions / Dependencies
- ThinkingML v4.5 校验规则以 `docs/ai预期响应结构.md` + `web/src/utils/common/thinkingmlValidator.js` 为 SSOT。
- 工具结果注入采用 `<gymbro_injected_context>` 内部 XML（输入侧），并在 Prompt 中明确“禁止复述内部标签”。

## Phases
1. **SSOT Prompt 组装对齐**
   - 抽一个后端“有效 Prompt 组装器”（system + tools text + tools_json + tool_choice gating），让 `/messages` 与 Dashboard Prompt Test 共用
   - 补一个“预览当前生效 Prompt/Tools”的只读 API（供 JWT 测试页展示，避免前端猜）
2. **Agent Prompt + Tools 注入**
   - 增加 Agent Prompt patch（强调：工具由后端已执行；输出仍必须是 ThinkingML v4.5）
   - Agent 工具结果注入改为内部 XML（escape），并支持请求级工具选择（exercise/web_search on/off、top_k）
3. **JWT 测试页体验升级**
   - 默认：`server prompt` + `xml_plaintext` + `/agent/runs`（工具链路）
   - UI：单独面板展示 `tool_start/tool_result`（结构化），并提供 Prompt/Tools 预览（来自后端 SSOT API）
   - 提供“与 Dashboard 一致/自定义覆盖”的对比开关与最小组合测试矩阵

## Tests & Verification
- `scripts/monitoring/local_mock_ai_conversation_e2e.py`：扩展覆盖 `/agent/runs`（mock 上游 reply），验证拼接后 ThinkingML 校验通过
- 新增 pytest：
  - Prompt 组装器：Dashboard Prompt Test 与 `/messages` 产出的上游 payload 一致（关键字段：system 拼接、tools 是否发送）
  - Agent Run：开启/关闭工具时，SSE 必含 `tool_*` 且 `content_delta/completed` 仍可拼装
- 手动：JWT 测试页点一次 “Agent Run 并拉流”，直接看到工具事件 + 校验 PASS

## Issue CSV
- Path: issues/2026-01-13_13-04-20-agent-prompt-tools-thinkingml-jwt-debug.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描（Prompt 组装 / Prompt Test / JWT 测试页）
- `functions:shell_command`：pytest + docker compose + 本地 e2e 脚本
- `functions:apply_patch`：最小改动落地
- `context7:*`：核验 OpenAI tools 与消息角色（system/tool）最佳实践

## Acceptance Checklist
- [ ] 工具开启时，JWT 测试页不再出现 `invalid_thinking_block_count`
- [ ] `/messages` 与 Dashboard Prompt Test 的 Prompt/Tools 组装逻辑一致（SSOT）
- [ ] `/agent/runs` 工具结果以内部 XML 注入（输入侧），输出仍严格 ThinkingML v4.5
- [ ] 新增/更新的回归测试覆盖上述关键路径（mock，不出网）

## Risks / Blockers
- 上游模型对 Strict XML 服从度波动；必要时需针对 provider 做最小补丁（不引入新协议）

## Rollback / Recovery
- 通过 revert 单提交回滚；Agent Prompt patch/工具注入可用 feature flag 关闭（回退到纯对话）

## Checkpoints
- Commit after: Prompt 组装器 SSOT 对齐
- Commit after: Agent Prompt/Tools 注入
- Commit after: JWT 测试页 UI + 回归测试

## References
- `docs/ai预期响应结构.md`
- `assets/prompts/serp_prompt.md`
- `assets/prompts/tool.md`
- `app/services/ai_service.py`
- `app/services/ai_config_service.py::test_prompt`
- `web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue`
- `web/src/utils/common/thinkingmlValidator.js`
