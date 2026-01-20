---
id: "a133a1ee-dd61-4f82-bf0d-6b4eb32c53a2"
title: "JWT SSE 测试页：协议切换 + JSONSeq v1 校验"
project: "vue-fastapi-admin"
project_path: "X:/project/vue-fastapi-admin"
created_at: "2026-01-20T11:10:36+08:00"
updated_at: "2026-01-20T11:10:36+08:00"
tags: ["jsonseq", "jwt", "sse", "validator", "dashboard", "ui"]
summary: "在 JWT SSE SSOT 测试页新增 app_output_protocol（thinkingml_v45/jsonseq_v1）切换/保存/恢复默认，并实现 JSONSeq v1 事件流 validator（顺序/phase/serp_queries）。"
type: "development"
version: 1
---

# 会话上下文：JWT SSE 测试页追加 JSONSeq v1 协议开关与校验

## 🎯 用户需求
- 在 Dashboard 的 JWT SSE SSOT 测试页内：可切换全局 `app_output_protocol`（`thinkingml_v45` ↔ `jsonseq_v1`），并能验证协议是否生效。
- 在 `jsonseq_v1` 下：对 SSE 事件流做校验（事件顺序、phase id 递增、title 必填、`final_delta`、`serp_queries` 约束），并展示 PASS/FAIL reason。
- 保持 `thinkingml_v45` 既有行为不变（仍可做 ThinkingML 校验）。

## 📌 核心变更（SSOT/KISS）
- 前端：`web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue`
  - 新增输出协议选择器（绑定 `/api/v1/llm/app/config` 的 `app_output_protocol`）+ 保存/恢复默认按钮。
  - 新增 `jsonseq_v1` validator：只校验 JSONSeq v1 事件（忽略 `status/heartbeat/upstream_raw/...` 等系统事件）。
  - SSE 事件缓存上限从 200 提到 600（仅测试页）。
- 计划与 Issue：
  - `plan/2026-01-20_10-51-42-jwt-sse-jsonseq-v1-ui.md`
  - `issues/2026-01-20_10-51-42-jwt-sse-jsonseq-v1-ui.csv`

## ✅ 验证（DONE）
- 前端构建：`cd web && ./node_modules/.bin/vite build` ✅

## ⚠️ 注意事项 / 风险
- `app_output_protocol` 是全局 SSOT 配置；切换会影响 App/其它页面。测试后应恢复默认 `thinkingml_v45`。

## 🚀 下次继续（建议）
- 若要更强校验：把 JSONSeq validator 抽到 `web/src/utils/` 并复用到更多测试页/回归页。
- 若要对齐 App 渲染：在 JWT 页增加“按 phase 展示 thinking 内容”的可视化（当前主要用于校验与事件摘要）。
