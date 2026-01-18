---
id: "25c75577-a10a-4e6c-90ae-899a1a6e82eb"
title: "system prompt 迭代：v7.3 SERP 必须 + meta 兜底"
project: "vue-fastapi-admin"
project_path: "X:/project/vue-fastapi-admin"
created_at: "2026-01-17T22:33:11+08:00"
updated_at: "2026-01-17T22:33:11+08:00"
tags: ["prompt", "thinkingml", "claude-sonnet", "serp", "meta-guard", "e2e"]
summary: "v7.3 强化 SERP 与 meta 请求兜底，修复 claude-sonnet 在“讨论 system prompt/规则/XML/实现细节”场景漏 serp_queries/输出代码围栏导致校验失败。"
type: "development"
version: 1
---

# 会话上下文：system prompt 迭代（v7.3）

## 📋 会话概述
- 目标：让 claude-sonnet 在“讨论 system prompt/规则/XML/实现细节”场景仍输出合规 ThinkingML v4.5
- 触发现象：claude-sonnet 可能把“优化 system prompt”当内容输出，导致 `<final>` 缺少 serp_queries、出现 ``` 代码围栏等
- 修复：强化 `assets/prompts/serp_prompt.md`（SERP 默认必须 + meta 请求拒绝并引导回健身 + serp_queries 主题约束），并在 E2E 脚本增加 `--prompt-text` 便于回归

## 🎯 最小变更清单
- Prompt SSOT：`assets/prompts/serp_prompt.md`（与 `docs/prompt/v7.3_gymbro-serp-must-meta-guard.md` 保持一致）
- Profile：`assets/prompts/standard_serp_v2.json` → `7.3.0`
- 文档：`docs/prompt/CHANGELOG.md`、`docs/prompt/test_results.md`
- E2E：`scripts/monitoring/real_ai_conversation_e2e.py` 新增 `--prompt-text`，并增强 grok/xai 别名解析

## ✅ 验证（脱敏）
- 健康检查：`curl http://127.0.0.1:9999/api/v1/healthz` → 200
- Meta 场景回归：
  - `.venv/bin/python scripts/monitoring/real_ai_conversation_e2e.py --models claude-sonnet --runs 1 --turns 2 --prompt-text "<meta>"`
- 本地无网 E2E：
  - `.venv/bin/python scripts/monitoring/local_mock_ai_conversation_e2e.py`
- pytest：
  - `.venv/bin/python -m pytest -q tests/test_sse_output_modes_e2e.py`

## ⚠️ 备注
- deepseek 若仍返回 472 为端点问题（非 prompt）
- 已按 Context Manager 要求对任何 token/key/用户信息做 `<REDACTED>` 或省略
