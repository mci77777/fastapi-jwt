---
id: "2fd9fbb8-6844-46d4-ba46-a4007e5acc11"
title: "JSONSeq v1：统一事件流协议 + Dashboard 开关 + Prompt/测试"
project: "vue-fastapi-admin"
project_path: "X:/project/vue-fastapi-admin"
created_at: "2026-01-20T10:07:51+08:00"
updated_at: "2026-01-20T10:07:51+08:00"
tags: ["jsonseq", "events", "sse", "dashboard", "prompt", "gymbro"]
summary: "新增 JSONSeq v1（事件流）对外协议：后端把上游输出统一映射为事件（thinking/phase/final + 可选 serp），并在 Dashboard 提供开关；补齐 prompts/assets 与 E2E 测试，保持默认兼容。"
type: "development"
version: 1
---

# 会话上下文：JSONSeq v1（事件流）新增

## 🎯 目标（WHY）
- App 端“只认事件”，不再依赖解析 XML/拼接大块 token；同时保持现有 SSE 默认行为不变（兼容旧客户端）。

## ✅ 实现摘要（HOW）
- 新增 App 对外协议开关：`llm_app_settings.app_output_protocol`（`thinkingml_v45` / `jsonseq_v1`）。
- 当开启 `jsonseq_v1`：
  - 后端将上游输出（ThinkingML/XML、JSON Lines、PlainText）统一映射为事件流：`thinking_start/phase_start/phase_delta/thinking_end/final_delta/final_end`（可选 `serp_summary/serp_queries`）。
  - SSE 订阅侧只输出“统一事件类型 + completed/error/status/heartbeat/tool_*”，`completed` 不携带 reply 全文（避免单包大 chunk；以事件为 SSOT）。
- Prompt SSOT（assets）：新增 JSONSeq v1 的 system/tools prompts，并在启动期自动种子化为独立 prompt_type（不影响现有 system/tools）。
- Dashboard：新增“App 输出协议（默认）”配置项；Prompt 管理页支持 `system_jsonseq_v1/tools_jsonseq_v1`。
- JWT SSE 测试页：兼容 `final_delta/phase_*`，可用于 jsonseq_v1 模式下对账。

## 🔒 脱敏/合规（强制）
- 所有内网地址/API Key/Token/JWT 均以 `<REDACTED>` 记述；不写入仓库与会话存档。

## ✅ 验证（DONE）
- 后端：`make test`（pytest 全绿）
- 前端：在 WSL 下用 `./node_modules/.bin/vite build` 验证构建通过（避免使用 Windows `npm` 带来的 PATH/脚本兼容问题）

## 🚀 下次继续
- 用真实 `xai` 端点跑 `jsonseq_v1` 模式回归，更新 `docs/prompt_jsonseq/test_results.md`（仅记录脱敏统计与失败样式）。

