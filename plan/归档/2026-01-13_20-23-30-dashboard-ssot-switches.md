---
mode: plan
task: dashboard-ssot-switches
created_at: "2026-01-13T20:23:30+08:00"
complexity: medium
---

# Plan: dashboard-ssot-switches

## Goal
- dashboard 配置作为 SSOT，所有 app 请求必经总开关
- prompt 组装可控，默认启用 GymBro system prompt + tools
- 响应转发两模式可配置：XML 解析转发 / 透明流式转发
- 配置可被 dashboard 读写并落库

## Scope
- In:
  - 后端配置模型/服务的读取与开关执行
  - 请求路由/流式响应转发接入总开关
  - dashboard 配置 UI 与 API 对接
- Out:
  - 新增模型供应商或大规模架构重构

## Assumptions / Dependencies
- dashboard 总配置已落在数据库
- app 端以 JWT 方式请求后端
- 现有配置管理 API/UI 需扩展或新建（待现状核对）
- 现有 SSE/流式实现可被开关包裹而不破坏限流与 PolicyGate

## Phases
1. 现状与同义扫描：定位配置、请求入口、流式转发与 prompt 组装点
2. 方案对齐：配置 schema/默认值/接口契约/回滚路径
3. 实施与验证：后端接入 → 前端接入 → 端到端验证

## Tests & Verification
- `/api/v1/healthz` 返回 200
- 两种流式转发模式端到端冒烟验证
- JWT 鉴权与 API 合约回归
- dashboard 配置保存/生效链路验证

## Issue CSV
- Path: issues/2026-01-13_20-23-30-dashboard-ssot-switches.csv
- Must share the same timestamp/slug as this plan.

## Tools / MCP
- codebase-retrieval：定位现有实现与同义扫描
- Read/Grep：规则与接口核对
- Edit/Write：最小改动
- Bash：构建/启动/健康检查

## Acceptance Checklist
- [ ] dashboard 配置为唯一真值源，无影子开关
- [ ] app 请求路由强制经过总开关
- [ ] prompt 组装默认启用，开关可切换
- [ ] XML 解析转发与透明流式转发可配置且稳定

## Risks / Blockers
- 配置分散导致合并成本与回归风险
- 流式转发与中间件链兼容性风险
- 前后端配置不一致引发行为漂移

## Rollback / Recovery
- 单提交回滚
- 保留旧配置读取路径到回滚点
- 回滚后复测健康检查

## Checkpoints
- Commit after: 方案对齐完成
- Commit after: 后端开关接入完成
- Commit after: 前端与验证完成

## References
- AGENTS.md
- app/core/application.py
- app/core/policy_gate.py
- web/src/api/
