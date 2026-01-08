# Real User JWT + ThinkingML E2E 验收报告（Supabase｜xai/deepseek）

日期：2026-01-08（+08:00）

## 目标（SSOT）

- 输出结构契约：`docs/ai预期响应结构.md`（ThinkingML v4.5）
- Prompt SSOT：`assets/prompts/serp_prompt.md`、`assets/prompts/tool.md`、`assets/prompts/standard_serp_v2.json`
- Real Upstream Runner：`scripts/monitoring/real_ai_conversation_e2e.py`
- Real User JWT Runner：`scripts/monitoring/real_user_ai_conversation_e2e.py`

## 环境

- 服务启动：`docker compose up -d --build app`
- 健康检查：`GET /api/v1/healthz` = 200 且 `{"status":"ok",...}`

## 验收命令与结果

### 1) Real Upstream E2E（结构校验）

```bash
.venv/bin/python scripts/monitoring/real_ai_conversation_e2e.py --models xai deepseek --runs 1 --turns 1 --tool-choice ''
```

结果：`SUMMARY total=2 passed=2 failed=0 models=xai,deepseek runs=1 turns=1`

### 2) Real User JWT E2E（Supabase signup + 负例 + 结构校验）

> 推荐 `signup`：避免依赖固定测试账号；脚本会创建临时用户并在结束时清理。

```bash
.venv/bin/python scripts/monitoring/real_user_ai_conversation_e2e.py --auth-mode signup --models xai deepseek --runs 1 --turns 1 --tool-choice ''
```

结果：
- `SUMMARY_JWT total=3 passed=3 failed=0`
- `SUMMARY total=2 passed=2 failed=0 models=xai,deepseek runs=1 turns=1 auth_mode=signup`

## 关键修复（最小闭环）

- ThinkingML 兼容性：服务端在 `<thinking>` 内将 `<Title>` 等大小写漂移归一化为 `<title>`，避免 phase title 解析与结构校验误判。

## 回滚

- `git revert <commit>` 后执行：`docker compose up -d --build app`

