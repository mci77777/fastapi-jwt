---
mode: plan
task: Dashboard 配置 App 默认输出模式（RAW 透明转发 / XML 纯文本）
created_at: "2026-01-11T11:09:56+08:00"
complexity: medium
---

# Plan: Dashboard 配置 App 默认输出模式（RAW 透明转发 / XML 纯文本）

## Goal
- 在 Dashboard 首页「核心配置」区域新增一个**App 输出模式开关**，用于控制 App 端未显式传 `result_mode` 时的默认行为。
- 默认值调整为**透明转发**（`raw_passthrough`），让 App 收到上游 RAW 流（`event: upstream_raw`）。
- 配置需持久化，且对 `/api/v1/messages` **未传** `result_mode` 的请求立即生效（SSOT）。

## Scope
- In:
  - 后端：切换 App 默认 `result_mode` 为 `raw_passthrough`；复用现有持久化表 `llm_app_settings` 与接口 `GET/POST /api/v1/llm/app/config`（避免影子配置）。
  - 前端：在 Dashboard 首页「AI 供应商 / 映射模型」组件内增加选择器，读取/保存 `default_result_mode`。
  - 文档/契约：更新默认值描述，确保与实现一致。
  - 测试：修正受默认值变化影响的用例（若存在）。
- Out:
  - 不改 SSE 事件协议集合（仍以 `content_delta/upstream_raw/completed/error/heartbeat` 为主）。
  - 不改 App 端逻辑（仍允许 App 通过 `result_mode` 覆盖默认值）。

## Assumptions / Open Questions
- 语义对齐（默认按现有实现）：
  - “透明转发” = `raw_passthrough`（输出 `upstream_raw`）
  - “XML 格式” = `xml_plaintext`（输出 `content_delta`，文本可包含 `<final>` 等 XML 标签）
- 需确认：
  1) 该开关是**全局** App 默认（`llm_app_settings.default_result_mode`），还是要**按 endpoint / 映射模型**分别持久化？
  2) “xml格式”是否需要 `Content-Type: application/xml` 的**完整 XML 文档**？（若是，则不等价于现有 `xml_plaintext`）

## Phases
1. 同义实现扫描与 SSOT 复用确认
   - 确认唯一写入点：`llm_app_settings.default_result_mode`（读写路径一致）。
2. 后端默认值切换（raw_passthrough 为默认）
   - 调整默认配置字典与 `/api/v1/messages` 的默认兜底逻辑。
3. Dashboard UI 开关闭环（首页核心配置区）
   - 在 `ModelSwitcher` 增加 `default_result_mode` 的读取/保存；失败时可观测且不落影子状态。
4. 文档/测试对齐
   - 更新合约/说明中的默认值；修正受影响测试并回归。

## Tests & Verification
- 后端回归：`make test`（必要时单跑 `pytest -q tests/test_sse_output_modes_e2e.py`）。
- 手工验证：
  - 切换默认值后，App 不传 `result_mode` 创建消息并订阅 SSE：应分别出现 `upstream_raw`（透明）或 `content_delta`（xml）。
  - 显式传 `result_mode` 时：应覆盖默认值，行为不变。

## Issue CSV
- Path: `issues/2026-01-11_11-09-56-dashboard-app-result-mode-toggle.csv`
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `functions:shell_command`：检索、运行测试/启动、接口验证
- `functions:apply_patch`：最小改动落地
- （可选）`feedback:codebase-retrieval`：同义实现扫描与精准定位引用点

## Acceptance Checklist
- [ ] Dashboard 首页核心配置区新增“App 输出模式”控件并可保存
- [ ] 未配置且未传 `result_mode` 时默认 `raw_passthrough`
- [ ] 合约/文档默认值描述与实现一致
- [ ] 测试通过（至少 `make test`）

## Risks / Blockers
- 改默认值可能影响依赖“默认 xml_plaintext”的旧客户端：需在发布说明强调可通过 `result_mode` 或 Dashboard 立即回切。
- 若 App/网关存在 SSE 缓冲，观测会失真：应优先用探针/E2E 佐证链路无缓冲。

## Rollback / Recovery
- 回滚提交即可恢复旧默认；或将 DB 中 `llm_app_settings.default_result_mode` 设置回 `xml_plaintext`。

## Checkpoints
- Commit after: 后端默认值 + 文档/测试对齐
- Commit after: Dashboard UI 开关闭环

## References
- `app/api/v1/messages.py`（默认 result_mode 兜底）
- `app/api/v1/llm_models.py`（`/llm/app/config` + 默认配置）
- `web/src/components/dashboard/ModelSwitcher.vue`（Dashboard 核心配置 UI）
- `web/src/views/system/ai/index.vue`（既有 App 输出模式配置入口）
- `docs/api-contracts/api_gymbro_cloud_app_min_contract.md`
- `tests/test_sse_output_modes_e2e.py`
