---
mode: plan
task: JSONSeq v1：事件流协议 + Prompt + Dashboard 开关
created_at: "2026-01-20T09:19:10+08:00"
complexity: complex
---

# Plan: JSONSeq v1：事件流协议 + Prompt + Dashboard 开关

## Goal
- 为 GymBro App 新增 **JSONSeq v1（事件流）** 输出：客户端只处理事件（thinking/phase/final），语义与现有 ThinkingML(XML) 一致。
- **保持兼容**：默认仍使用现有 SSE 协议（status/content_delta/completed/...）。仅在 Dashboard 配置开启后，才切换为 JSONSeq v1 事件流。
- 先在 `xai` 上把“事件顺序 + 字段约束 + SERP 事件”迭代到 100% PASS，再扩展到 `claude/gemini/gpt/deepseek`。

## Scope
- In:
  - 新增协议 SSOT：`docs/ai_jsonseq_v1_预期响应结构.md`（与 `docs/ai预期响应结构.md` 语义对齐）
  - 新增 Prompt SSOT（assets）：
    - `assets/prompts/serp_prompt_jsonseq_v1.md`（system：要求模型输出 JSON Lines 事件序列）
    - `assets/prompts/tool_jsonseq_v1.md`（tools 补丁：ToolCall 语义对齐，禁止输出 tool JSON）
    - `assets/prompts/standard_jsonseq_v1.json`（profile 元数据）
  - 后端新增 App 配置项（SQLite SSOT）：`llm_app_settings.app_output_protocol`（`thinkingml_v45` / `jsonseq_v1`）
  - 当 `app_output_protocol=jsonseq_v1`：
    - SSE 对外输出 **统一事件类型**：`thinking_start / phase_start / phase_delta / thinking_end / final_delta / final_end`（可扩展：`serp_summary / serp_queries`）
    - 对上游输出（XML/JSON/PlainText）做最小解析与兜底映射，保证“客户端只认事件”可用
  - Dashboard 增加开关：选择 App 默认输出协议（ThinkingML/XML vs JSONSeq/v1）
  - E2E/校验：新增 JSONSeq v1 validator + 真实模型/本地 mock 回归
- Out:
  - 不替换现有 ThinkingML v4.5 协议 SSOT（保持默认行为不变）
  - 不在本仓库实现 GymBro App 端解析（只提供契约与后端输出；App 侧另跟进）

## Assumptions / Dependencies
- SSE 仍使用 Server-Sent Events；JSONSeq v1 以 **SSE event name + JSON data** 承载（不是单纯 content_delta 拼接 NDJSON）。
- 现有 Provider Adapter 仍负责把上游响应归一化为文本流；JSONSeq v1 只改变“对 App 的输出事件形态”。
- Prompt 注入 SSOT 仍来自 `ai_prompts` active prompt；为避免与现有 system/tools 冲突，将新增独立 prompt_type（例如 `system_jsonseq_v1/tools_jsonseq_v1`）。

## Phases
1. 同义实现扫描 + 协议定稿（JSONSeq v1 SSOT + validator 规则）
2. 后端：新增 `app_output_protocol` 配置读写 + SSE 事件输出管线（含 XML/JSON/PlainText 兜底映射）
3. Prompt：新增 jsonseq prompts + 启动期种子化（不影响现有 active prompts）
4. Dashboard：新增 App 输出协议开关（落库 `llm_app_settings`）
5. 验证：先跑 xai（迭代 prompt 直到 100% PASS），再扩展其它模型并记录结果

## Tests & Verification
- JSONSeq v1 validator（单测）：
  - 事件序列合法（thinking_start → phase_* → thinking_end → final_* → final_end）
  - 字段白名单/类型校验（phase_start/phase_delta 必须携带 id；phase_start 必须携带 title）
  - SERP：`serp_summary`（1–2 句）可选；`serp_queries` 数组（1–3 默认，最多 5）可选
- 回归：`make test` + `GET /api/v1/healthz`=200
- E2E：
  - 本地 mock：覆盖 JSONSeq v1 事件输出（不出网）
  - 真实模型：先 `xai` runs/turns 达标，再逐个扩展

## Issue CSV
- Path: issues/2026-01-20_08-57-12-jsonseq-v1-events-protocol-dashboard.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描、定位 SSE/Prompt 注入链路
- `context7:resolve-library-id` + `context7:get-library-docs`：必要时校验 SSE/SDK/JSON streaming 的边界
- Shell：本地构建/pytest/E2E

## Acceptance Checklist
- [ ] `docs/ai_jsonseq_v1_预期响应结构.md` 完成，且与 ThinkingML(XML) 语义一致
- [ ] `llm_app_settings.app_output_protocol` 可配置，默认 `thinkingml_v45` 不变
- [ ] 开启 `jsonseq_v1` 后，SSE 事件仅依赖统一事件类型（含可选 SERP 事件），客户端无需解析 XML/JSON 文本
- [ ] `xai` 在 JSONSeq v1 模式下 E2E 100% PASS（记录在 `docs/prompt_jsonseq/test_results.md`）
- [ ] Dashboard 可配置开关并生效
- [ ] `make test` + `/healthz` 通过

## Risks / Blockers
- 部分模型可能输出非 JSON/夹带解释文字：需要“按行解析 + 字段白名单 + fallback 到 PlainText→final_delta”兜底
- 流式拆包导致 JSON 行边界被打断：后端输出以事件为单位可规避；若仍需 NDJSON 备用再补
- 兼容性：默认不变；新协议仅在显式开启后生效

## Rollback / Recovery
- Dashboard 将 `app_output_protocol` 切回 `thinkingml_v45`
- 单提交回滚：`git revert <commit>`

## Checkpoints
- Commit after: Phase 2（后端协议开关 + 单测）
- Commit after: Phase 4（Dashboard 开关）
- Commit after: Phase 5（xai 验证通过 + 文档归档）

## References
- `docs/ai预期响应结构.md`
- `docs/api-contracts/api_gymbro_cloud_app_min_contract.md`
- `assets/prompts/serp_prompt.md`
- `assets/prompts/tool.md`
- `app/services/ai_service.py`
- `app/api/v1/messages.py`
- `app/api/v1/llm_models.py`
