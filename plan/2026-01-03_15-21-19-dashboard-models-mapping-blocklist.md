---
mode: plan
task: Dashboard 模型观测 + 映射管理 + 可用模型屏蔽
created_at: "2026-01-03T15:21:19+08:00"
complexity: complex
---

# Plan: Dashboard 模型观测 + 映射管理 + 可用模型屏蔽

## Goal
- Dashboard 内直接观测并管理：
  - 映射模型（model-groups）
  - App 实际可用模型（/api/v1/llm/app/models 输出为 SSOT）
  - 实际拉取到的供应商模型（各 endpoint 的 model_list）
  - 一键“屏蔽/解除屏蔽”供应商模型（影响映射解析与 App 可用性）
- 形成可观测链路：`映射模型 → 实际模型 → API 供应商 → health/status`。

## Scope
- In:
  - Dashboard 页面内直接操作（不只是跳转）：
    - 映射管理（复用现有组件/接口）
    - 可用模型屏蔽开关（新增）
    - App models 观测面板（新增）
  - 后端：实现“屏蔽模型”的 SSOT 与读写接口；并在模型解析链路中强制生效。
- Out:
  - 不做映射删除（当前前端为占位）。
  - 不实现推送系统本身（只做供推送/拉取消费的可观测与配置）。

## Assumptions / Dependencies
- 映射配置 SSOT：`app/services/model_mapping_service.py`（本地存储文件 + prompt/fallback 读取）。
- 供应商端点与健康 SSOT：`app/services/ai_config_service.py` + `app/api/v1/llm_models.py`（SQLite 中 ai_endpoints.status/latency_ms/model_list）。
- Dashboard 权限 SSOT：本地 admin（`user_metadata.is_admin` 或 `username==admin`）+ `require_llm_admin` 统一收敛。

## Phases
1. SSOT 收敛：在 `ModelMappingService` 增加“blocked models”存储与并发锁；并在 resolve 逻辑中跳过被屏蔽模型。
2. 后端接口：
   - 新增 blocked models 的 list/upsert（admin-only 写）。
   - 扩展 `/api/v1/llm/app/models`：允许 admin 获取 debug 字段；输出包含屏蔽后计算的 resolved_model/candidates（用于 Dashboard 观测）。
3. Dashboard 落地：
   - Dashboard 内嵌 `ModelMappingCard`（映射管理）。
   - 新增“供应商模型列表（可屏蔽）”面板：按 endpoint 聚合 model_list，展示 provider/status/latency，并提供屏蔽开关。
   - 新增“App 实际可用模型”面板：展示 `/llm/app/models`（含 admin debug 字段时展示 resolved_model 与命中 provider）。
4. 验证闭环：
   - 后端 pytest：屏蔽生效（resolve/app models）+ 权限（非 admin 禁写）。
   - 前端构建通过；admin 登录后可在 Dashboard 一屏完成观测与操作。

## Tests & Verification
- 后端：`.venv/bin/python -m pytest -q` 覆盖
  - blocked models API（非 admin 403；admin 可写）
  - `resolve_for_message` 跳过被屏蔽模型（默认/候选被屏蔽时回退到可用项；全被屏蔽则明确失败）
  - `/api/v1/llm/app/models?debug=true` admin 可见 debug 字段且反映屏蔽结果
- 前端：`cd web && npm run build`；人工冒烟：
  - Dashboard 可见映射管理卡片与“供应商模型屏蔽”面板
  - 屏蔽某供应商模型后，App models 观测与映射解析结果即时反映

## Issue CSV
- Path: issues/2026-01-03_15-21-19-dashboard-models-mapping-blocklist.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- `feedback:codebase-retrieval`：同义实现扫描/定位调用链（确保屏蔽在 resolve 与 app models 均生效）。
- `functions:apply_patch`：最小变更落盘。
- `functions:exec_command`：pytest + web build 验证。

## Acceptance Checklist
- [ ] Dashboard 内可直接管理映射（新增/保存/切换默认）且写操作受权限约束。
- [ ] Dashboard 内展示“实际拉取的 models”（聚合 endpoint.model_list），并支持对每个模型进行屏蔽/解除屏蔽。
- [ ] 屏蔽对后端解析链路强制生效：`resolve_for_message` 不会选中被屏蔽模型。
- [ ] Dashboard 可观测链路完整：映射 → resolved_model → provider/status（health）可追踪。
- [ ] 构建/测试通过，变更可回滚。

## Risks / Blockers
- 若仅前端过滤而后端不强制，仍可能被绕过；因此必须在服务端 resolve 处强制执行。
- `/llm/app/models` 当前 debug 字段受 `DEBUG` 开关影响，需要对 admin 放开但不对普通用户泄露。

## Rollback / Recovery
- 回滚前端：移除 Dashboard 新增面板与 API 调用；保留原 /ai 页面。
- 回滚后端：移除 blocked 逻辑与相关 API；恢复 resolve/app models 原行为。

## Checkpoints
- Commit after: 后端 blocked SSOT + API + 测试
- Commit after: Dashboard 面板 + 前端 build 通过

## References
- app/services/model_mapping_service.py
- app/api/v1/llm_models.py
- app/api/v1/llm_mappings.py
- web/src/views/dashboard/index.vue
- web/src/components/dashboard/ModelMappingCard.vue
