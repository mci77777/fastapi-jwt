---
mode: plan
task: request_id + OpenAI/Claude 源码收敛（清理 trace_id 旧实现）
created_at: "2026-01-01T14:35:00+08:00"
complexity: complex
---

# Plan: request_id + OpenAI/Claude 源码收敛（清理 trace_id 旧实现）

## Goal
- 全仓只认/只回传 `X-Request-Id`，不再出现 `X-Trace-Id/trace_id` 的“新旧交替”实现与文档误导。
- Web 侧可配置「使用后端 prompt 组装」vs「OpenAI 字段透传」，且调用口径唯一。

## Scope
- In:
  - 后端周边：`e2e/anon_jwt_sse/**`、`scripts/dump_handover.py`、`docs/**` 中遗留 `trace_id/X-Trace-Id` 全量收敛
  - Web：SSE 示例与 `/messages` 调用入口收口到 `web/src/api/aiModelSuite.js::createMessage`
- Out:
  - 不引入新的追踪 header（坚持 SSOT）
  - 不做协议重构/新架构层（仅做收敛与替换）

## Assumptions / Dependencies
- 当前后端 SSOT 已生效：`app/core/middleware.py::REQUEST_ID_HEADER_NAME = "X-Request-Id"`。
- 部分 `trace_id` 仍在 e2e/postman/脚本/旧文档中存在（同义实现扫描已定位）。
- 本仓库缺少 `docs/mcp-tools.md` 与 `assets/_template.md`：计划按同等结构输出，并在执行阶段补齐/或在 Notes 记录缺失。

## Phases
1. 同义实现扫描与分组
   - 统计 `trace_id/X-Trace-Id/x-trace-id/get_current_trace_id` 出现场景，划分为：运行时必须改 / 文档必须改 / archive 可保留。
2. 后端周边收敛（不改核心链路）
   - e2e 脚本与 postman：统一使用 `X-Request-Id`，变量名与断言统一 `request_id`。
   - `scripts/dump_handover.py`：入参改为 `--request-id`（兼容旧 `--trace-id` 一段时间可选），输出字段统一 `request_id`。
3. 文档契约收敛
   - runbooks/api-contracts/jwt 改造文档：全部改为 `request_id`，并明确“只认 `X-Request-Id`”。
   - `.env.example` 与示例 payload：移除 `trace_id` 文案与旧 header。
4. Web 端点配置收敛
   - 示例页/调用处：用 `createMessage({ promptMode, openai, requestId })`；不再散落自组装与旧 SSE 事件解析。

## Tests & Verification
- `pytest -q` -> 全绿
- `rg "\\btrace_id\\b|X-Trace-Id|x-trace-id|get_current_trace_id"` -> 仅允许出现在 `docs/**/archive/**`
- Web（可选）：`pnpm -C web install && pnpm -C web lint`

## Issue CSV
- Path: issues/2026-01-01_14-35-00-request-id-ssot-consolidation.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描/入口定位
- `rg/git/pytest`：全仓替换与回归验证

## Acceptance Checklist
- [ ] 运行时与文档：只出现 `X-Request-Id` / `request_id`
- [ ] e2e/postman/脚本：不再使用 `X-Trace-Id/trace_id`
- [ ] Web：`/messages` 仅通过 `createMessage` 统一封装，具备 promptMode 配置

## Risks / Blockers
- e2e/postman 变更可能影响外部流程，需要同步更新使用说明。
- Web SSE 若要带 `Authorization`，EventSource 受限，可能需要 `fetch` SSE 解析器（执行阶段再定）。

## Rollback / Recovery
- 分阶段提交：先“文档/脚本”再“Web”；逐 commit `git revert <sha>` 可回滚。

## Checkpoints
- Commit after: Phase 2；Phase 3；Phase 4

## References
- `app/core/middleware.py:13`
- `app/api/v1/messages.py:25`
- `e2e/anon_jwt_sse/scripts/sse_client.py:66`
- `scripts/dump_handover.py:26`
- `docs/runbooks/README.md:8`
