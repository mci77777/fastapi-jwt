---
mode: plan
task: E2E mapped-model structure validation
created_at: "2026-01-08T09:10:50+08:00"
complexity: medium
---

# Plan: E2E mapped-model structure validation

## Goal
- 每次回归对 `view=mapped` 返回的每个模型完成一次对话：注入 prompts → SSE 拼接 reply → 结构校验；全绿则 exit=0。

## Scope
- In:
  - 扩展/新增 E2E runner：逐模型循环、结构校验更严格、输出汇总报告（终端/可选写入文件）
  - （可选）加入 `pytest` 用例把 runner 纳入 `tests/`
- Out:
  - 不改模型映射/路由业务逻辑（只做测试与校验）
  - 不引入新的 prompt 协议（以 `docs/ai预期响应结构.md` 为 SSOT）

## Assumptions / Dependencies
- `/api/v1/base/access_token` 可获取本地 admin JWT（或提供等价凭据）
- `/api/v1/llm/models?view=mapped` 至少返回 1 个模型；若返回空则视为环境配置失败
- 默认使用 in-process + mock 上游（不出网）；如需真实上游，增加显式开关并要求提供对应配置

## Phases
1. 契约落地：把 `docs/ai预期响应结构.md` 的必须项落到校验函数（标签白名单/phase 递增/`</thinking>`→`<final>` 顺序/serp_queries 注释块 JSON 合法）
2. 逐模型 E2E：拉取 mapped models（SSOT），逐个 `POST /api/v1/messages`（带 `model`），消费 `/events` 拼接 reply 并校验；输出 per-model 结果与总体 exit code
3. 集成回归：本地（ASGITransport）跑通；可选支持 docker 模式（base_url=http://localhost:9999）；可选落入 `pytest`（参数化跑模型列表）

## Tests & Verification
- 逐模型 E2E runner：所有模型通过则 exit=0；否则输出失败模型与校验原因（含 request_id）
- SSE 形状验证：至少包含 `status` + `content_delta` + `completed|error`
- （可选）`PYTHONPATH=. .venv/bin/python -m pytest -q tests` 保持通过

## Issue CSV
- Path: issues/2026-01-08_09-10-50-e2e-mapped-model-structure-validation.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `mcp__feedback__codebase-retrieval`：定位模型白名单/路由选择/事件下发链路
- `functions.exec_command`：运行 E2E / pytest / docker compose
- `functions.apply_patch`：最小改动实现 runner 与校验器

## Acceptance Checklist
- [ ] E2E 从 `/api/v1/llm/models?view=mapped` 获取列表并逐个执行（SSOT 无硬编码）
- [ ] 每个模型都能完成 SSE 闭环并拼接 reply
- [ ] reply 严格匹配 `docs/ai预期响应结构.md`（含 serp_queries 注释块校验）
- [ ] 失败时输出 `model + request_id + reason`，方便对账
- [ ] 回归命令写入（或更新）`docs/e2e-ai-conversation/QUICK_START.md`

## Risks / Blockers
- mapped model 中存在不可路由/无 key 的模型会导致 E2E 失败（按预期暴露配置问题）
- 更严格校验可能揭示当前 prompt/模型输出不稳定（需要按 SSOT 调整 prompt 或做明确的容错决策）

## Rollback / Recovery
- 回滚方式：`git revert <commit>`（测试/脚本变更可单提交回滚）

## Checkpoints
- Commit after: Phase 2（runner+校验器可独立通过）
- Commit after: Phase 3（集成到 pytest/文档更新）

## References
- `docs/ai预期响应结构.md`
- `scripts/monitoring/local_mock_ai_conversation_e2e.py`
- `docs/e2e-ai-conversation/QUICK_START.md`
