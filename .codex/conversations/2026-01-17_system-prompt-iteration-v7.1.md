---
id: "8a042b1f-17f0-4e63-871c-8fecde90982a"
title: "system prompt 迭代：v7.1 讨论规范稳定性 + SSE 尾部收敛"
project: "vue-fastapi-admin"
project_path: "X:/project/vue-fastapi-admin"
created_at: "2026-01-17T20:27:00+08:00"
updated_at: "2026-01-17T20:27:00+08:00"
tags: ["prompt", "thinkingml", "claude-sonnet", "jwt-e2e", "sse"]
summary: "修复 claude-sonnet 在“讨论 prompt/规范”场景夹带标签/marker 导致 ThinkingML 校验失败：prompt v7.1 + SSE 流式最小转义/截断，JWT E2E 通过。"
type: "development"
version: 1
---

# 会话上下文：system prompt 迭代（v7.1）

## 📋 会话概述
- 目标：继续迭代 `assets/prompts/serp_prompt.md`，让 claude-sonnet 在 JWT/E2E 场景也稳定输出 ThinkingML v4.5（Strict XML）
- 关键问题：claude-sonnet 在“讨论 system prompt/协议/规范”类问题时，会在 `<final>` 内输出类似 `<xxx>` / `<<ParsingError>>` 等字面量，触发解析失败；且 `</final>` 后可能继续输出（表现为标签重复）
- 修复策略：prompt 文案最小加强 + 服务端 SSE（xml_plaintext/auto→xml）增加“尾部收敛 + 未知标签/marker 转义”

## 🎯 用户需求
- 继续迭代 system prompt，保证所有模型在 JWT 测试对话中都能通过结构校验
- 修复 claude-sonnet 输出标签重复/夹带非法标签的问题
- 使用 Context Manager 保存对话到项目内 `.codex/conversations/`

## 📊 核心内容
- Prompt（v7.1）
  - 文件：`assets/prompts/serp_prompt.md`
  - 归档：`docs/prompt/v7.1_final-tail-guard.md`
  - 变更：强调 `<final>` 中禁止输出 `<xxx>`/`</xxx>`/`<<...>>` 字面量（需用 `&lt;`/`&gt;`），并避免 prompt 内出现错误标记字面量
  - Profile：`assets/prompts/standard_serp_v2.json` 升级到 `7.1.0`
- 后端 SSE（端到端稳定性兜底）
  - `</final>` 后丢弃任何多余输出（避免标签“重复/尾巴”）
  - 跨 chunk 转义 `<<ParsingError>>`（防止被当成 XML 标签）
  - 跨 chunk 转义非白名单纯字母 XML 标签（如 `<answer>` / `<div>` / `<xxx>`）
  - 新增回归测试覆盖：尾部丢弃 + 跨 chunk 未知标签转义

## 💡 关键决策（WHY）
- 仅靠 prompt 约束无法稳定覆盖“讨论规范/输出 prompt 文本”场景，因此用 SSE 流式最小转义做兜底，保证客户端拼接后的 SSOT 可解析（SSOT：`docs/ai预期响应结构.md`）
- 不改变协议 SSOT（标签集合/顺序/serp_queries 格式保持不变），仅做“非法字面量→纯文本”与“尾部收敛”的最小修复（KISS）

## ✅ 任务进度
- DONE：v7.1 prompt 归档 + SSOT 回写
- DONE：服务端 SSE 兜底修复 + 新增测试
- DONE：Docker 镜像重建并重启服务，验证 E2E/JWT 脚本通过

## 💻 重要代码/命令（脱敏）
- 关键文件：
  - `assets/prompts/serp_prompt.md`
  - `docs/prompt/v7.1_final-tail-guard.md`
  - `app/services/ai_service.py`
  - `tests/test_sse_output_modes_e2e.py`
- 验证命令（示例）：
  - `docker compose build app && docker compose up -d app`
  - `.venv/bin/python scripts/monitoring/real_ai_conversation_e2e.py --models claude-sonnet --runs 1 --turns 1`
  - `.venv/bin/python scripts/monitoring/daily_mapped_model_jwt_e2e.py --models claude-sonnet --prompt-text "<省略>"`
  - `.venv/bin/python -m pytest -q tests/test_sse_output_modes_e2e.py`

## ⚠️ 注意事项
- 已脱敏：本地模型 base_url / api_key、JWT、任何 token/secret（全部用 `<REDACTED>` 或省略）
- grok/deepseek 等模型在 v7.1 未做全量复测（如需可补跑 `real_ai_conversation_e2e.py --runs/--turns`）

## 🚀 下次继续指南
- 若要扩大覆盖：补跑 `real_ai_conversation_e2e.py --models xai deepseek claude-sonnet --runs 3 --turns 2`
- 若要更严格：考虑在 ThinkingML 校验器中增加 “`</final>` 后必须只有空白” 的检查（目前主要靠 SSE 侧丢弃保证）
