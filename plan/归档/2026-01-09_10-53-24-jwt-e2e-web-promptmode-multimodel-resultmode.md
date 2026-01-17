---
mode: plan
task: JWT 测试增强：E2E+Web prompt模式/多模型并发/RAW-TXT 输出
created_at: "2026-01-09T10:53:55+08:00"
complexity: complex
---

# Plan: JWT 测试增强：E2E+Web prompt模式/多模型并发/RAW-TXT 输出

## Goal
- JWT 真实链路测试同时覆盖：prompt 注入/透传切换、多 models 并发、结果 RAW/Text 可选输出。
- Web 端 `AiJwtSimulation` 页面可直接展示 AI 回复（含 `<...>` 标签原样显示），并可切换 prompt 模式。
- E2E 脚本默认产出 TXT 报告（包含 `<...>` 标签），并保留原有 JSON 报告用于机器分析。

## Scope
- In:
  - 增强 `e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py`：新增参数（prompt 模式、models 并发、输出模式）并补齐产物。
  - 增强 Web JWT 页面：新增 prompt 模式与附加 prompt、结果展示模式（text/raw）。
  - 文档更新：`e2e/anon_jwt_sse/scripts/README.md`、`docs/SCRIPTS_INDEX.md`。
- Out:
  - 不新增/恢复已删除的旁路服务（`JWTTestService` 等），所有验证仍走 `POST /api/v1/messages` + SSE。
  - 不改后端 prompt/映射 SSOT 逻辑（仅复用既有字段 `skip_prompt/messages/system_prompt`）。

## Assumptions / Dependencies
- 后端已启动且可访问 `POST /api/v1/messages` 与 `GET /api/v1/messages/{id}/events`。
- 可用模型 key 来源：优先 `GET /api/v1/llm/app/models`（SSOT），为空时允许 `--models` 手工指定。
- 并发上限受 SSE 并发守卫影响（详见 `app/core/sse_guard.py`）；并发默认值需保守。

## Phases
1. 同义实现扫描与基线确认
   - 复用 `skip_prompt` + `messages/system_prompt` 语义（参考 `app/services/ai_service.py::_build_openai_request()`）。
   - 复用现有 SSE completed 事件的 `reply` 字段作为“最终全文 SSOT”。
2. E2E：多 models 并发 + prompt 模式 + 报告输出
   - 参数：`--prompt-mode {server|passthrough}`、`--extra-system-prompt <text>`、`--models a,b,c`、`--concurrency N`、`--result {text|raw|both}`。
   - 默认：
     - `prompt-mode=passthrough` 且携带一段“附加 prompt”（用于强调 `<...>` 标签原样输出）。
     - 输出：默认写 TXT 报告（含 `<...>` 标签原样），同时继续写 JSON（脱敏/机器可读）。
3. Web：AI JWT 页面增强
   - UI 增加：prompt 模式（server/passthrough）、附加 prompt（默认非空）、结果展示模式（text/raw）。
   - SSE 处理：在 `completed` 事件到达时，确保把 `data.reply` 写入展示区（避免仅靠 delta 拼接丢失）。
4. 文档与回归
   - 更新脚本 README 与脚本索引，补齐参数说明与示例命令。
   - 运行 `make test`，并做一次本地 E2E 冒烟（至少 1 model）。

## Tests & Verification
- CLI：`python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py --help` 展示新增参数与默认值。
- E2E：`python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py --models xai --concurrency 1` 产出：`anon_e2e_trace.txt` + `anon_e2e_trace.json`，且最终事件为 `completed`。
- Web：在 `AiJwtSimulation` 页面切换 `prompt-mode` 与 `result-mode` 后，回复区能看到包含 `<thinking>/<final>` 等标签的原文。
- 回归：`make test` 通过。

## Issue CSV
- Path: issues/2026-01-09_10-53-24-jwt-e2e-web-promptmode-multimodel-resultmode.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `functions:exec_command`：运行脚本、检索与回归测试。
- `functions:apply_patch`：最小改动更新脚本/前端/文档。
- `feedback:codebase-retrieval`（可选）：用于同义实现扫描与精准定位调用点。

## Acceptance Checklist
- [x] `run_e2e_enhanced.py` 新增参数生效，默认输出 TXT 报告（包含 `<...>` 标签原样），并保留 JSON。
- [x] 支持 `server/passthrough` 两种 prompt 模式，且两者均能输出 `completed` 或明确失败汇总（例如上游 4xx / upstream_empty_content）。
- [x] 支持多 models 并发（受并发守卫限制时要有明确错误与汇总）。
- [x] Web JWT 页面支持同样的 prompt 模式与附加 prompt，并能展示最终回复（含标签）。
- [x] 文档更新到位；`make test` 通过。

## Risks / Blockers
- 多 SSE 并发可能触发 429（并发守卫），需要把失败原因汇总到报告而不是“卡死”。
- “附加 prompt”默认非空会改变模型输出：需提供一键关闭（空字符串/开关）并在报告中记录实际使用值。

## Rollback / Recovery
- 仅涉及脚本/前端/文档：可通过 `git revert <sha>` 回滚；不影响后端数据结构。

## Checkpoints
- Commit after: E2E 脚本功能闭环
- Commit after: Web 页面增强与文档更新

## References
- `docs/features/model_management/testing.md`
- `e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py`
- `web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue`
- `app/services/ai_service.py`
