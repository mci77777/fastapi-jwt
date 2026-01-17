---
mode: plan
task: xai/deepseek ThinkingML E2E prompt tuning
created_at: "2026-01-08T12:09:31+08:00"
complexity: complex
---

# Plan: xai/deepseek ThinkingML E2E prompt tuning

## Goal
- 让 `mapping=xai` 与 `mapping=deepseek` 在**真实上游**、**多轮对话**、**多次重复**下输出严格匹配 `docs/ai预期响应结构.md`（100% 通过）。
- 增加一个“真实用户对话”E2E runner：按 mapping 逐次跑、拼接 SSE、结构校验、产出可复现证据。

## Scope
- In:
  - 新增/扩展 E2E：真实调用（不 mock 上游），支持指定 `--models xai deepseek`、`--runs N`、`--turns M`
  - 调整 prompt SSOT：`assets/prompts/serp_prompt.md`（必要时联动 `tool.md` / `standard_serp_v2.json` 版本）
  - （必要时）稳定性参数：如对 xai/deepseek 默认 `temperature=0`（仅在 prompt 仍无法 100% 时启用）
  - 文档更新：把 real E2E 用法写入 `docs/e2e-ai-conversation/QUICK_START.md`
- Out:
  - 不改 `docs/ai预期响应结构.md`（它是契约 SSOT）
  - 不改 SSE 事件协议/Provider Adapter 架构（除非为达成 100% 必要且最小）

## Assumptions / Dependencies
- 已在 SQLite 中配置并启用 xai/deepseek endpoint（含可用 API key），且 mapping 可路由。
- 允许真实出网调用上游（当前环境 `network_access=enabled`）。
- 默认验收口径：`runs=10`、`turns=3`、两模型均 100% PASS（后续可按需要提高）。

## Phases
1. **基线 E2E（真实上游）**：新增 `scripts/monitoring/real_ai_conversation_e2e.py`（或扩展现有脚本加 real mode）
   - 启动期用 `assets/prompts/{serp_prompt.md,tool.md,standard_serp_v2.json}` 写入并 activate prompts（避免“DB 里旧 prompt”造成影子状态）
   - 拉取 `/api/v1/llm/models?view=mapped`，确认包含 `xai`、`deepseek`
   - 每次对话走：`POST /api/v1/messages` → SSE `/events` → 拼接 `content_delta.delta` → 用同一校验器校验
   - 输出：每次 `model + request_id + endpoint_id + resolved_model + reason`；失败保存最小脱敏 artifacts（不落密钥）
2. **跑基线并归因失败形态**：统计 xai/deepseek 在多次、多轮下的失败类型（多余文本/标签不在白名单/顺序错误/缺失 serp_queries 等）。
3. **Prompt 迭代（只改 SSOT assets）**：
   - 强化 `serp_prompt.md`：把“必须只输出 XML + 模板 + 失败输出 <<ParsingError>>”前置、去歧义、减少可选表述
   - 必要时微调 `tool.md` 使其不引入额外标签/格式干扰
   - 更新 `standard_serp_v2.json` 的版本字段用于对账
4. **仍不稳则加最小稳定参数（可选）**：
   - 针对 `mapping=xai/deepseek` 默认注入 `temperature=0`（保持 KISS：只对目标模型生效）
5. **回归与扩展**：
   - `xai` 100% PASS → `deepseek` 100% PASS
   - 再扩展到“每个 mapping”全量跑（作为后续阶段 gate）
6. **文档与回滚**：补齐 real E2E 跑法、环境变量、验收口径；提供 `git revert` 与 prompt 回切说明。

## Tests & Verification
- Offline baseline：`.venv/bin/python scripts/monitoring/local_mock_ai_conversation_e2e.py` -> exit=0
- Real E2E：`.venv/bin/python scripts/monitoring/real_ai_conversation_e2e.py --models xai deepseek --runs 10 --turns 3` -> exit=0
- （建议）`PYTHONPATH=. .venv/bin/python -m pytest -q tests` 保持全绿
- Docker：`docker compose up -d --build app` + `curl http://localhost:9999/api/v1/healthz`=200

## Issue CSV
- Path: issues/2026-01-08_12-05-59-xai-deepseek-thinkingml-e2e-prompt-tuning.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：定位 prompt 注入点/路由/模型注册表影响面
- `functions.exec_command`：运行 E2E/pytest/docker/健康检查
- `functions.apply_patch`：最小修改 prompt assets + 新增 real E2E runner

## Acceptance Checklist
- [ ] `mapping=xai`：`runs=10, turns=3` 全部 PASS（严格匹配 `docs/ai预期响应结构.md`）
- [ ] `mapping=deepseek`：`runs=10, turns=3` 全部 PASS
- [ ] E2E 产物不含密钥，且失败可复现（包含 request_id/endpoint_id/resolved_model）
- [ ] 无影子 prompt：测试前会用 assets 写入并 activate prompts（SSOT 一致）
- [ ] docker 重建后健康检查 200

## Risks / Blockers
- 仅靠 prompt 可能仍无法 100%：需要 `temperature=0` 或更强模板；若仍不稳需讨论“服务端拒答/最小修复”的边界。
- xai/deepseek endpoint 或 key 不可用会导致真实 E2E 阻塞：runner 需显式报错缺失项。

## Rollback / Recovery
- `git revert <commit>` 回退 prompt/脚本；Prompt 通过 `/api/v1/llm/prompts` 切回上一版本。

## Checkpoints
- Commit after: real E2E runner 可运行并产出基线报告
- Commit after: xai 100% PASS
- Commit after: deepseek 100% PASS + 文档更新

## References
- `docs/ai预期响应结构.md`
- `assets/prompts/serp_prompt.md`
- `assets/prompts/tool.md`
- `assets/prompts/standard_serp_v2.json`
- `docs/e2e-ai-conversation/QUICK_START.md`
- `app/services/ai_service.py`
