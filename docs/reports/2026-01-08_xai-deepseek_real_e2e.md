# Real Upstream E2E 验收报告（xai / deepseek｜ThinkingML v4.5）

日期：2026-01-08（+08:00）

## 目标（SSOT）

- 输出结构契约：`docs/ai预期响应结构.md`（ThinkingML v4.5）
- Prompt SSOT：`assets/prompts/serp_prompt.md`、`assets/prompts/tool.md`、`assets/prompts/standard_serp_v2.json`
- Real E2E Runner：`scripts/monitoring/real_ai_conversation_e2e.py`

## 环境

- 服务启动：`docker compose up -d --build app`
- 健康检查：`GET /api/v1/healthz` = 200 且 `{"status":"ok",...}`
- 前置：已启用 `mapping=xai` / `mapping=deepseek` 的 endpoint + api_key（以 `/api/v1/llm/models?view=mapped` 为准）

## 验收命令与结果（Real Upstream）

为避免上游 tool_calls 差异导致不稳定，测试使用 `--tool-choice ''`（不下发该字段）。

### xai

```bash
.venv/bin/python scripts/monitoring/real_ai_conversation_e2e.py --models xai --runs 10 --turns 3 --tool-choice ''
```

结果：`SUMMARY total=30 passed=30 failed=0 models=xai runs=10 turns=3`

### deepseek

```bash
.venv/bin/python scripts/monitoring/real_ai_conversation_e2e.py --models deepseek --runs 10 --turns 3 --tool-choice ''
```

结果：`SUMMARY total=30 passed=30 failed=0 models=deepseek runs=10 turns=3`

## 关键改动（最小闭环）

- SSE 流式纠错：将常见破坏点（`</thinking>`/重复 `<final>`/`<b>`/`<br>`/重复 `<title>`/`<serp>` 乱序）转为契约允许的纯文本或 Markdown 形式，确保拼接后的 reply 通过结构校验。
- 并发守卫：修复强制断连/清理过期连接的锁重入死锁，避免 E2E 并发时卡死导致异常/重试放大。
- E2E runner：增加节流与 429 诊断输出，降低 IP QPS 限流导致的非业务失败。

## 回滚

- `git revert <commit>` 后执行：`docker compose up -d --build app`

