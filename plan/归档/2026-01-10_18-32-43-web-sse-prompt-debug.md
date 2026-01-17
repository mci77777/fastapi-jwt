---
mode: plan
task: Web 调试点 + 文档（Prompt/协议迭代，ThinkingML v4.5 验收）
created_at: "2026-01-10T18:32:43+08:00"
complexity: complex
---

# Plan: Web 调试点 + 文档（Prompt/协议迭代，ThinkingML v4.5 验收）

## Goal
- 提供一个可交互的 Web 调试入口：可切换 `prompt_mode/result_mode/tool_choice`，实时跑 `/messages + SSE`，并在浏览器端对拼接后的 XML 做 **ThinkingML v4.5** 校验（SSOT：`docs/ai预期响应结构.md`）。
- 补齐对应文档：把“怎么调 prompt / 怎么验证 / 怎么定位失败原因（validator reason + sse_probe）”固化为可执行 runbook。

## Scope
- In:
  - Web：新增/增强调试页（含参数开关、SSE raw/text 展示、validator 结果、`/api/v1/base/sse_probe` 一键探针）。
  - Web：实现一份前端 ThinkingML v4.5 校验器（对齐 `scripts/monitoring/local_mock_ai_conversation_e2e.py::_validate_thinkingml` 的规则与 reason）。
  - Docs：新增/更新 SSE 调试与 Prompt/协议迭代文档（含入口路由、失败 reason 对照表、推荐调参流程）。
- Out:
  - 不改业务 prompt 的内容（`assets/prompts/*` 本身由人迭代；这里只提供调试/验收工具与文档）。
  - 不引入第三方校验依赖（KISS：纯 JS/TS 正则+最小解析）。

## Assumptions / Dependencies
- 现有调试页 `web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue` 可作为基座；后端已提供 `GET /api/v1/base/sse_probe`。
- ThinkingML SSOT：`docs/ai预期响应结构.md`；前端校验逻辑需与其一致（至少 reason 名一致）。
- 真模型可能受 429/400 等影响；需在 UI/文档中区分“结构失败”与“上游/限流错误”。

## Phases
1. Web 调试入口落位（路由/菜单/直达链接）
2. 前端校验器实现（ThinkingML v4.5 SSOT 对齐）
3. 调试页增强（参数开关、SSE 事件流览、拼接 XML、validator、probe）
4. 文档固化（runbook + 入口索引）
5. 回归验证（web build + 关键 pytest）

## Tests & Verification
- Web 手动验收：
  - `result_mode=xml_plaintext`：SSE 拼接全文 validator 必须 `ok=true`。
  - `result_mode=raw_passthrough`：能连续看到 `upstream_raw`；默认不做 ThinkingML 校验。
  - `result_mode=auto`：最终 validator `ok=true`，并展示 `result_mode_effective`。
  - `sse_probe`：事件应按 1s 间隔到达（否则提示“边缘层缓冲”）。
- 构建回归：`cd web && npm run build`
- 后端回归：`uv run -m pytest -q tests/test_sse_output_modes_e2e.py`

## Issue CSV
- Path: issues/2026-01-10_18-32-43-web-sse-prompt-debug.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `functions.shell_command`：检索/构建/回归运行
- `functions.apply_patch`：最小改动落地（web + docs）
-（可选）`feedback:codebase-retrieval`：若需要快速定位路由/菜单接入点

## Acceptance Checklist
- [ ] Web 有清晰入口可直达调试页（含菜单或固定路由）
- [ ] 调试页可切换协议参数并跑通 `/messages + SSE`
- [ ] 拼接 XML 在 Web 端严格校验 ThinkingML v4.5，并输出明确 reason
- [ ] 文档说明“如何迭代 prompt/协议并闭环验证”，步骤可复制
- [ ] Web build 与关键 pytest 回归通过

## Risks / Blockers
- 上游不稳定/限流导致 false negative：需要输出结构化错误与对账字段。

## Rollback / Recovery
- 调试功能集中在 debug 页与 utils；可通过回退单次提交撤销，不影响业务路径。

## Checkpoints
- Commit after: Phase 3（调试点可用 + 校验器）
- Commit after: Phase 4（文档完善 + 回归通过）

## References
- `docs/ai预期响应结构.md`
- `web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue`
- `scripts/monitoring/prompt_protocol_tuner.py`
- `app/api/v1/base.py`（`/api/v1/base/sse_probe`）
