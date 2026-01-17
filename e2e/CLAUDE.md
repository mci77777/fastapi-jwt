# E2E 测试套件 - AI 辅助开发指令

> 本文档为 Claude/AI 辅助开发提供 E2E 测试模块的上下文和约束

## 模块定位

E2E（端到端）测试套件验证 GymBro 后端 API 的完整业务链路：
- **认证链路**：Supabase JWT（匿名/真实用户）→ 后端验证
- **消息链路**：`POST /api/v1/messages` → SSE 流式响应 → 数据持久化
- **策略链路**：PolicyGate 拦截 → RateLimiter 限流 → 统一错误体

## 核心约束

### 1. SSOT 配置
- **唯一配置源**：`e2e/anon_jwt_sse/.env.local`
- 所有套件复用此配置，禁止创建独立 `.env` 文件
- 必需变量：`SUPABASE_URL`、`SUPABASE_ANON_KEY`、`API_BASE`

### 2. 产物管理
- 每个套件的 `artifacts/` 目录独立
- 产物已加入 `.gitignore`，禁止提交
- 命名规范：`{type}_{model}_{timestamp}_{uuid}.json`

### 3. 依赖管理
- Python 依赖：`e2e/anon_jwt_sse/requirements.txt`（共享）
- Node.js 依赖：`e2e/anon_jwt_sse/package.json`（仅 anon_jwt_sse）

## 套件优先级

| 优先级 | 套件 | 用途 | 稳定性 |
|--------|------|------|--------|
| P0 | `anon_jwt_sse/` | 匿名 JWT + SSE 主力测试 | 稳定 |
| P0 | `real_user_sse/` | 真实用户 SSE 验证 | 稳定 |
| P2 | `real_ai_conversation/` | AI 多轮对话（实验） | 实验 |
| P2 | `real_user_ai_conversation/` | 用户 AI 对话（实验） | 实验 |
| P2 | `prompt_protocol_tuner/` | Prompt 协议调优（实验） | 实验 |

## 脚本入口

### 主力脚本（anon_jwt_sse）

| 脚本 | 用途 | 命令 |
|------|------|------|
| `run_e2e_enhanced.py` | 完整 E2E 测试 | `pnpm run e2e` |
| `verify_setup.py` | 环境体检 | `python scripts/verify_setup.py` |
| `generate_test_token.py` | Token 生成 | `python scripts/generate_test_token.py` |
| `sse_client.py` | SSE 客户端测试 | `pnpm run sse:client` |
| `sse_chaos.py` | SSE 压力测试 | `pnpm run sse:test` |
| `jwt_mutation_tests.py` | JWT 变体测试 | `pnpm run jwt:test` |

### 辅助脚本（scripts/dev）

| 脚本 | 用途 |
|------|------|
| `run_local_real_user_e2e.sh` | 本地真实用户 E2E |
| `sync_e2e_env_to_web.py` | 同步配置到 Web |
| `install_daily_real_user_e2e_cron.sh` | 安装每日 Cron |

## 开发规范

### 新增测试
1. 优先扩展现有脚本，避免创建新文件
2. 使用参数控制行为（如 `--mode`、`--model`）
3. 产物写入对应 `artifacts/` 目录
4. 更新 `e2e/README.md` 和 `docs/SCRIPTS_INDEX.md`

### 修改测试
1. 保持向后兼容，不破坏现有 CI
2. 测试变更后运行 `pnpm run e2e` 验证
3. 实验性功能标记 `[实验]` 并文档化

### 调试技巧
```bash
# 环境体检
python e2e/anon_jwt_sse/scripts/verify_setup.py

# 详细日志
python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py --verbose

# 指定模型
python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py --models "xai"

# 跳过 Prompt
TEST_SKIP_PROMPT=true pnpm run e2e
```

## 验收标准

- [ ] `pnpm run e2e` 通过
- [ ] 产物生成在 `artifacts/` 目录
- [ ] 无新增未文档化的环境变量
- [ ] 无破坏性变更（或明确标注）

## 关联文档

- 项目主文档：`/CLAUDE.md`
- JWT 硬化：`/docs/JWT_HARDENING_GUIDE.md`
- 脚本索引：`/docs/SCRIPTS_INDEX.md`
- 测试策略：`/docs/testing-policy.md`

## 禁止事项

1. ❌ 创建独立 `.env` 文件（违反 SSOT）
2. ❌ 提交 `artifacts/` 内容
3. ❌ 硬编码密钥或敏感信息
4. ❌ 修改共享依赖版本而不测试全套件
5. ❌ 删除或重命名现有脚本而不更新文档
