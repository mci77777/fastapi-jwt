---
mode: plan
task: App 模型 key 映射闭环（provider→mapping→app）
created_at: 2026-01-04T16:44:21+08:00
complexity: complex
---

# Plan: App 模型 key 映射闭环（provider→mapping→app）

## Goal
- App 发送 `model=<业务 key>`（如 `xai`）时，后端可稳定解析为真实供应商 endpoint + model，并完成 create→SSE 端到端闭环。

## Scope
- In:
  - `/api/v1/llm/models` 返回 App 期望结构（`{code,msg,total,data}`，`data[*]={name,default_model,candidates}`，`name=业务 key`）
  - `/api/v1/messages` 支持 `model=业务 key` 并映射到真实上游模型（避免将 `xai` 透传给供应商导致 404）
  - SSE 最小事件集合可用（status/content_delta/completed/error/heartbeat）
  - 微 E2E 覆盖：models→messages→SSE，并断言上游 payload.model 为真实模型名
- Out:
  - Dashboard 端点管理 UI 改造
  - 供应商全量协议差异（仅保证 OpenAI 兼容最小集）

## Assumptions / Dependencies
- ModelMapping 以 `scope_type=tenant/global` + `scope_key=<业务 key>` 作为 App SSOT；legacy `mapping_id`（如 `global:global`）继续兼容。

## Phases
1. 统一模型 key 解析：业务 key 与 legacy mapping_id 双兼容
2. 对齐模型列表 API：`/llm/models` mapped 视图直接服务 App
3. 对齐消息链路：create→映射→上游请求→SSE 事件输出
4. 微 E2E + 全量回归：确保无真实外网调用与测试稳定

## Tests & Verification
- 微 E2E：`PYTHONPATH=. .venv/bin/pytest -q tests/test_app_models_messages_sse_micro_e2e.py`
- 全量回归：`make test`

## Issue CSV
- Path: issues/2026-01-04_16-44-06-llm-provider-mapping-app-closure.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `functions.exec_command`: 运行 `pytest/make` 与最小验证
- `functions.apply_patch`: 最小化修改与新增测试

## Acceptance Checklist
- [ ] `model=<业务 key>` 发送时不会被原样透传到供应商
- [ ] `/api/v1/llm/models` 返回 App 结构且 `name=业务 key`
- [ ] SSE 可正常返回 completed/error 等最小事件集
- [ ] `make test` 全绿（无真实外网调用）

## Risks / Blockers
- 测试环境后台探针/外网调用导致用例抖动（需显式开关/Mock）

## Rollback / Recovery
- 回滚提交后，恢复旧的 `/llm/models` mapped schema 与 `model` 解析逻辑（风险：App 仍会触发 404）。

## Checkpoints
- Commit after: 微 E2E 通过 + `make test` 全绿

## References
- `app/services/ai_service.py`
- `app/services/model_mapping_service.py`
- `app/api/v1/llm_models.py`
- `tests/test_app_models_messages_sse_micro_e2e.py`
