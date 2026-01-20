---
mode: plan
task: JWT 测试页追加 JSONSeq v1 协议开关与校验
created_at: "2026-01-20T10:53:54+08:00"
complexity: medium
---

# Plan: JWT 测试页追加 JSONSeq v1 开关与校验

## Goal
- 在 `JWT SSE SSOT` 测试页内完成 `app_output_protocol` 的查看/切换/生效验证（`thinkingml_v45` ↔ `jsonseq_v1`）。
- 在 `jsonseq_v1` 模式下：按统一事件流拼接并展示 `final_delta`，并提供序列校验 + 失败原因（对齐 `docs/ai_jsonseq_v1_预期响应结构.md`）。
- 保持现有 ThinkingML 校验与展示不变（默认仍以 Dashboard SSOT 为准）。

## Scope
- In:
  - `web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue`：新增协议切换 UI（读/写 `/api/v1/llm/app/config`）、新增 JSONSeq v1 校验与展示逻辑。
  - （可选）抽一个最小前端 validator 工具函数（仅当不增加心智负担）。
- Out:
  - 不改后端协议与事件类型（已完成）。
  - 不改 App 端（这里仅 Dashboard/JWT 测试页）。

## PBR / 同义实现扫描
- 复用既有配置读写模式：`web/src/views/system/ai/index.vue`（`app_output_protocol` 的 NSelect + 保存）。
- 复用既有 SSE 读流/事件记录模式：`web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue`。
- 说明：仓库无 `assets/_template.md`，本计划沿用既有 `plan/*.md` 结构（与 `plan/2026-01-20_08-57-12-jsonseq-v1-events-protocol-dashboard.md` 一致）。

## Phases
1. 同义扫描：确认 JWT 页现有 AppConfig 读取/刷新逻辑与可复用 UI/方法。
2. UI：在 JWT 页增加 `protocol` 选择器（`thinkingml_v45/jsonseq_v1`）+ 保存按钮 + “恢复默认协议”按钮。
3. 校验：
   - `thinkingml_v45`：沿用现有 ThinkingML validator。
   - `jsonseq_v1`：新增事件序列 validator（顺序、phase id 递增、title 必填、final_delta ≥1、serp_queries 约束）。
4. 展示：
   - `jsonseq_v1`：拼接 `final_delta.text` 到 reply 预览；在事件列表里补充 `phase_* / serp_* / final_*` 的可读摘要。
5. 验证：`cd web && ./node_modules/.bin/vite build`；手工冒烟：切换协议→发送→校验 PASS→切回。

## Tests & Verification
- Frontend build：`cd web && ./node_modules/.bin/vite build`
- 手工冒烟（JWT 页）：
  - protocol=thinkingml_v45：content_delta 拼接 + ThinkingML 校验 PASS。
  - protocol=jsonseq_v1：出现 `thinking_start/phase_*/*final_*` + JSONSeq 校验 PASS。

## Issue CSV
- Path: `issues/2026-01-20_10-51-42-jwt-sse-jsonseq-v1-ui.csv`

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描（JWT 页 / Dashboard 页 config UI）。
- `functions:apply_patch`：实现 UI/validator。
- `functions:shell_command`：`vite build` 验证。

## Acceptance Checklist
- [x] JWT 页可读到当前 `app_output_protocol`，并可保存切换。
- [x] `jsonseq_v1` 模式下 reply 使用 `final_delta` 拼接，且事件序列校验可用（给出失败 reason）。
- [x] 不影响 `thinkingml_v45` 既有校验与展示。
- [x] `vite build` 通过。

## Risks / Rollback
- 风险：切换协议会影响其它页面/用户（这是 SSOT 配置）；通过“恢复默认协议”按钮降低误操作。
- 回滚：切回 `thinkingml_v45` 或 `git revert` 本次提交。

## References
- `docs/ai_jsonseq_v1_预期响应结构.md`
- `web/src/views/system/ai/index.vue`
- `web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue`
