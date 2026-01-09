# GymBro Docs（Wiki）

> 项目文档导航（SSOT）。建议从 `docs/SUMMARY.md` 进入做全局浏览；历史材料统一从 `docs/archive/` 入口访问。

---

## 📚 核心文档

| 文档 | 描述 |
|------|------|
| [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) | 整体架构与技术栈概览 |
| [GW_AUTH_README.md](./GW_AUTH_README.md) | 网关改造与运行须知 |
| [SCRIPTS_INDEX.md](./SCRIPTS_INDEX.md) | 脚本与工具索引 |

---

## 🔌 API / SSE / E2E（对接必读）

| 文档 | 描述 |
|------|------|
| [api-contracts/](./api-contracts/) | Cloud API 最小契约（App/Web） |
| [sse/](./sse/) | SSE 对话链路 + 统一事件（GymBro SSE） |
| [ai预期响应结构.md](./ai预期响应结构.md) | AI 输出结构 SSOT（ThinkingML v4.5） |
| [app_ai_sse_raw_结构体与样本.md](./sse/app_ai_sse_raw_结构体与样本.md) | App 端 SSE RAW 结构体 + 近期 E2E 样本（含映射字段对账） |
| [e2e-ai-conversation/](./e2e-ai-conversation/) | E2E 对话验收（含 mock 上游） |

---

## 🏗️ 架构文档 (`architecture/`)

| 文档 | 描述 |
|------|------|
| [TOKEN_AUTHENTICATION.md](./architecture/TOKEN_AUTHENTICATION.md) | Token 认证架构（JWT 硬化 + Token 刷新 + Supabase 集成） |

---

## 🎯 功能文档 (`features/`)

| 文档 | 描述 |
|------|------|
| [DASHBOARD_FEATURES.md](./features/DASHBOARD_FEATURES.md) | Dashboard 功能（API 监控 + Supabase 状态 + 快速访问卡片） |
| [ai_endpoint/](./features/ai_endpoint/) | AI Endpoint 规划及测试摘要 |
| [model_management/](./features/model_management/) | AI 模型管理功能文档（2025-01） |

---

## 📖 指南文档 (`guides/`)

| 文档 | 描述 |
|------|------|
| [debugging/DEBUGGING_GUIDE.md](./guides/debugging/DEBUGGING_GUIDE.md) | 前端调试完整指南（Chrome DevTools + 实战场景 + 自动化工具） |
| [mail-api.md](./mail-api.md) | 真实邮箱流测试（Mail API：临时邮箱 + 拉取邮件） |

---

## 🧭 规则与约定（Meta）

| 文档 | 描述 |
|------|------|
| [WIKI_RULES.md](./meta/WIKI_RULES.md) | 文档/Wiki 维护规则 |
| [DOCS_MTIME_INDEX.md](./archive/_audit/DOCS_MTIME_INDEX.md) | 文档写入时间索引（用于归档/保留判定） |

---

## 🔧 修复记录 (`fixes/`)

| 文档 | 描述 |
|------|------|
| [README.md](./fixes/README.md) | 修复记录索引 |
| [2024-10-login-redirect.md](./fixes/2024-10-login-redirect.md) | 登录后跳转到 404 页面修复 |
| [2024-10-root-redirect.md](./fixes/2024-10-root-redirect.md) | 根路径 `/` 跳转到 404 页面修复 |
| [2024-10-documentation-update.md](./fixes/2024-10-documentation-update.md) | 文档更新交接 |

---

## 🚨 事件响应 (`incidents/`)

| 文档 | 描述 |
|------|------|
| [README.md](./incidents/README.md) | 事件响应索引 |
| [2024-10-key-leak.md](./incidents/2024-10-key-leak.md) | 密钥泄露事件响应 |
| [2024-10-repo-migration.md](./incidents/2024-10-repo-migration.md) | 仓库迁移记录 |
| [2024-10-repo-restoration-report.md](./incidents/2024-10-repo-restoration-report.md) | 仓库恢复详细报告 |
| [2024-10-repo-restoration-summary.md](./incidents/2024-10-repo-restoration-summary.md) | 仓库恢复摘要 |

---

## 📦 其他目录

| 目录 | 描述 |
|------|------|
| [auth/migration-history](./auth/migration-history/) | 历史迁移入口（详细材料已归档至 `archive/auth/migration-history/`） |
| [deployment/](./deployment/) | Supabase 匿名 JWT 部署摘要 |
| [runbooks/](./runbooks/) | 运行手册速查 |
| [archive/](./archive/) | 历史归档入口（阶段交付/审计/旧任务） |

---

## 📅 最近更新

> 约定：超过 30 天未更新的文档已归档到 `docs/archive/`；本节只展示最近 7 天的部分条目（按写入时间倒序）。

- **2026-01-09**: [README.md](./README.md)、[SUMMARY.md](./SUMMARY.md)、[runbooks/](./runbooks/)、[api-contracts/](./api-contracts/)、[ai预期响应结构.md](./ai预期响应结构.md)
- **2026-01-08**: [reports/](./reports/)、[sse/2026-01-07/](./sse/2026-01-07/)、[guides/dev/START_DEV_OPTIMIZATION.md](./guides/dev/START_DEV_OPTIMIZATION.md)
- **2026-01-07**: [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)、[GW_AUTH_README.md](./GW_AUTH_README.md)、[deployment/](./deployment/)、[incidents/](./incidents/)

---

## 🔍 快速查找

### 按主题查找

- **认证与安全**: [TOKEN_AUTHENTICATION.md](./architecture/TOKEN_AUTHENTICATION.md), [GW_AUTH_README.md](./GW_AUTH_README.md)
- **Dashboard**: [DASHBOARD_FEATURES.md](./features/DASHBOARD_FEATURES.md), [model_management/](./features/model_management/)
- **调试**: [DEBUGGING_GUIDE.md](./guides/debugging/DEBUGGING_GUIDE.md)
- **部署**: [deployment/](./deployment/), [GW_AUTH_README.md](./GW_AUTH_README.md)
- **脚本工具**: [SCRIPTS_INDEX.md](./SCRIPTS_INDEX.md)

### 按时间查找

- **2025-10**: 项目审计、文档重组、Token 认证、Dashboard 功能
- **2025-01**: AI 模型管理、Dashboard 首页
- **2024-10**: 修复记录、事件响应

---

**文档维护**: 详细记录已在各摘要下注明，可通过 git 历史或备份目录追溯原始文档。
