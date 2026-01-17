---
mode: plan
task: 映射模型业务化（可改名）与系统分配调用 SSOT 重构
created_at: "2026-01-03T13:40:05+08:00"
complexity: medium
---

# Plan: 映射模型业务化（可改名）与系统分配调用 SSOT 重构

## Goal
- App 侧仅使用“业务模型 key”（稳定不随改名变化）进行模型选择与请求发送；映射名称仅用于展示。
- 后端以单一 SSOT 路径完成：业务模型 key → 真实 vendor `model` → 系统分配端点/供应商并完成调用。

## Scope
- In:
  - 定稿并实现 App 模型列表契约：`GET /api/v1/llm/app/models` 返回业务模型 key + label
  - 收敛“映射解析/模型路由”到 SSOT，移除/隔离影子状态（尤其是依赖 name/scope_key 反查）
  - App/测试页/脚本适配：请求 `model` 只传业务模型 key
- Out:
  - 改变系统分配端点/供应商的核心策略（仍使用现有系统分配）
  - 大规模 UI 重做（除非阻塞验收）

## Assumptions / Dependencies
- 用户会自定义并修改“映射名称（展示用）”，但不应影响实际调用。
- 业务模型 key 必须稳定且可被后端可靠解析；兼容期可允许旧输入（如直接传 vendor model 或旧 key），但需明确弃用策略。

## Phases
1. 契约定稿 + 同义实现扫描：确认业务模型 key/label 的字段与兼容期；列出所有“映射解析/模型路由”入口与调用点。
2. 后端 SSOT 改造：统一在 AI 调用前解析业务模型 key；禁止用可变 name 做反查；保持系统分配端点/供应商策略不变。
3. 联调与验证：更新测试页/脚本到新契约；启动 + 健康检查 + 最小对话链路闭环；补回滚路径。

## Tests & Verification
- 健康检查：启动后 `curl http://localhost:9999/api/v1/healthz` 返回 200。
- 合约验证：`GET /api/v1/llm/app/models` 返回的 `model`（业务 key）可直接用于 `POST /api/v1/messages` 并完成对话（含 SSE completed）。
- 兼容验证（如保留）：旧输入形态仍可用或能得到明确错误码/提示。

## Issue CSV
- Path: issues/2026-01-03_13-40-05-mapped-model-ssot-refactor.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `mcp__feedback__codebase-retrieval`: 同义实现扫描/引用定位（模型解析、路由、调用点）。
- `functions.exec_command`: 启动/探针/最小联调验证。
- `functions.apply_patch`: 最小变更落地。

## Acceptance Checklist
- [ ] App 侧模型列表仅暴露“业务模型 key”，映射名称可改但不影响调用。
- [ ] App 请求提交业务模型 key 后，后端能稳定解析出真实 `model` 并完成系统分配调用。
- [ ] 后端不再使用可变 name 反查映射（避免改名/重名导致误路由）。
- [ ] 启动无错误，健康检查通过，最小对话链路闭环可复现。

## Risks / Blockers
- 业务模型 key 唯一性/稳定性不清导致冲突（同名、跨 scope 混用）。
- `model_list` 不完整导致自动路由不稳定（需依赖现有刷新/兜底）。
- 兼容期输入形态增加测试矩阵。

## Rollback / Recovery
- 单提交可回滚：恢复旧解析策略与旧接口行为（不删除接口，仅切换实现）。

## Checkpoints
- Commit after: Phase 1（契约/同义扫描清单）
- Commit after: Phase 2（SSOT 改造完成）
- Commit after: Phase 3（联调通过 + 记录回滚步骤）

## References
- app/api/v1/llm_models.py:68
- app/api/v1/llm_mappings.py:42
- app/services/model_mapping_service.py:117
- app/services/ai_service.py:548
- web/src/views/test/real-user-sse.vue:512

