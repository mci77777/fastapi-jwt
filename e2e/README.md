# E2E 测试套件

> GymBro 后端 API 端到端测试集合 — 覆盖 JWT 认证、SSE 流式响应、AI 对话、策略门与限流验证

## 概述

本目录包含多个独立的 E2E 测试套件，验证从用户认证到 AI 响应的完整链路：

| 套件 | 用途 | 状态 |
|------|------|------|
| `anon_jwt_sse/` | 匿名 JWT → SSE 流式响应 → 策略/限流验证 | ✅ 主力 |
| `real_user_sse/` | 真实用户 JWT → SSE 完整链路 | ✅ 主力 |
| `real_ai_conversation/` | 真实 AI 多轮对话测试 | 🔧 实验 |
| `real_user_ai_conversation/` | 真实用户 AI 对话链路 | 🔧 实验 |
| `prompt_protocol_tuner/` | Prompt 协议调优测试 | 🔧 实验 |

## 快速开始

### 1. 环境准备

```bash
# 安装 Python 依赖（在项目根目录）
pip install -r e2e/anon_jwt_sse/requirements.txt

# 安装 Node.js 依赖（可选，用于 Newman）
cd e2e/anon_jwt_sse && pnpm install
```

### 2. 配置环境变量

```bash
# 复制示例配置
cp e2e/anon_jwt_sse/.env.local.example e2e/anon_jwt_sse/.env.local

# 编辑配置（必需项）
# - SUPABASE_URL
# - SUPABASE_ANON_KEY
# - API_BASE (本地: http://localhost:9999)
```

### 3. 运行测试

```bash
# 匿名用户 E2E（推荐入口）
cd e2e/anon_jwt_sse && pnpm run e2e

# 真实用户 E2E
bash scripts/dev/run_local_real_user_e2e.sh

# 环境体检
python e2e/anon_jwt_sse/scripts/verify_setup.py
```

## 目录结构

```
e2e/
├── README.md                    # 本文档（入口大纲）
├── CLAUDE.md                    # AI 辅助开发指令
│
├── anon_jwt_sse/                # 匿名 JWT + SSE 测试套件
│   ├── scripts/                 # Python 测试脚本
│   │   ├── run_e2e_enhanced.py  # 主测试运行器
│   │   ├── verify_setup.py      # 环境体检
│   │   ├── generate_test_token.py
│   │   ├── sse_client.py
│   │   ├── sse_chaos.py         # SSE 压力测试
│   │   └── ...
│   ├── postman/                 # Postman/Newman 集合
│   ├── sql/                     # 数据库断言脚本
│   ├── edge-functions/          # Supabase Edge Functions
│   ├── artifacts/               # 测试产物（gitignore）
│   ├── .env.local               # 本地配置（勿入库）
│   ├── package.json             # npm scripts
│   └── requirements.txt         # Python 依赖
│
├── real_user_sse/               # 真实用户 SSE 测试
│   └── artifacts/               # 测试产物
│
├── real_ai_conversation/        # AI 多轮对话测试
│   └── artifacts/
│
├── real_user_ai_conversation/   # 真实用户 AI 对话
│   └── artifacts/
│
└── prompt_protocol_tuner/       # Prompt 协议调优
    └── artifacts/
```

## 测试套件详解

### anon_jwt_sse（匿名 JWT + SSE）

**核心场景**：匿名用户通过 Supabase Anonymous Sign-in 获取 JWT，调用 `/api/v1/messages` 并验证 SSE 流式响应。

**测试覆盖**：
- 🔐 匿名 JWT 获取与验证
- 🌊 SSE 流式响应完整性
- 🚫 策略门拦截（403）
- ⏱️ 限流机制（429）
- 🗄️ 数据库一致性断言

**常用命令**：
```bash
cd e2e/anon_jwt_sse

pnpm run e2e              # 完整 E2E
pnpm run e2e:quick        # 快速模式
pnpm run jwt:test         # JWT 变体测试
pnpm run sse:test         # SSE 压力测试
pnpm run newman:run       # Postman 回归测试
```

### real_user_sse（真实用户 SSE）

**核心场景**：使用真实 Supabase 用户 JWT 走完整链路：登录 → 创建消息 → SSE 拉流。

**SSOT 配置**：复用 `e2e/anon_jwt_sse/.env.local`，无需单独配置。

**运行方式**：
```bash
# 本地 Docker 启动后运行
bash scripts/dev/run_local_real_user_e2e.sh
```

### real_ai_conversation / real_user_ai_conversation

**实验性套件**：验证多轮 AI 对话的上下文保持和响应质量。

产物存放在 `artifacts/` 目录，按 `{status}_{model}_run{n}_turn{n}_{uuid}.json` 命名。

### prompt_protocol_tuner

**实验性套件**：测试不同 Prompt 模式（server/passthrough）和输出格式（xml/auto）的组合效果。

产物汇总见 `artifacts/SUMMARY.json`。

## 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `SUPABASE_URL` | ✅ | Supabase 项目 URL |
| `SUPABASE_ANON_KEY` | ✅ | Supabase 匿名密钥 |
| `API_BASE` | ✅ | 后端 API 地址（本地: `http://localhost:9999`）|
| `SUPABASE_SERVICE_ROLE_KEY` | 🔸 | 自动创建用户时需要 |
| `MAIL_API_KEY` | 🔸 | 真实邮箱验证流需要 |
| `TEST_SKIP_PROMPT` | 🔸 | 跳过 System Prompt 注入 |

## CI/CD 集成

- **每日自动验证**：`.github/workflows/daily-real-user-e2e.yml`
- **本地 Cron**：`bash scripts/dev/install_daily_real_user_e2e_cron.sh`

## 相关文档

- [JWT 硬化指南](../docs/JWT_HARDENING_GUIDE.md)
- [Supabase 配置](../docs/SUPABASE_JWT_SETUP.md)
- [Mail API 文档](../docs/mail-api.md)
- [脚本索引](../docs/SCRIPTS_INDEX.md)

## 故障排除

### 匿名登录失败
- 检查 Supabase 项目是否启用 Anonymous Sign-ins
- 确认 `SUPABASE_ANON_KEY` 配置正确

### SSE 连接失败
- 确认后端服务运行中：`curl http://localhost:9999/api/v1/healthz`
- 检查 JWT 令牌有效性

### 数据库断言失败
- 确认数据库表已创建
- 检查迁移是否最新：`make upgrade`

## 维护准则

1. **SSOT**：所有套件复用 `anon_jwt_sse/.env.local` 配置
2. **产物隔离**：每个套件的 `artifacts/` 目录独立，已加入 `.gitignore`
3. **脚本更新**：新增脚本需同步更新本 README 和 `docs/SCRIPTS_INDEX.md`
4. **实验性套件**：标记为 🔧 的套件处于开发中，可能不稳定
