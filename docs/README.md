# GymBro 文档索引

> 项目文档导航 - 快速查找所需文档

---

## 📚 核心文档

| 文档 | 描述 |
|------|------|
| [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md) | 整体架构与技术栈概览 |
| [GW_AUTH_README.md](./GW_AUTH_README.md) | 网关改造与运行须知 |
| [SCRIPTS_INDEX.md](./SCRIPTS_INDEX.md) | 脚本与工具索引 |

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
| [auth/migrations](./auth/migrations/) | 阶段总结与 Supabase 配置速览 |
| [deployment/](./deployment/) | Supabase 匿名 JWT 部署摘要 |
| [jwt改/](./jwt改/) | JWT 改造阶段归档摘要 |
| [jwt改造/](./jwt改造/) | JWT 改造阶段归档摘要 |
| [runbooks/](./runbooks/) | 运行手册速查 |
| [task/](./task/) | 匿名 E2E 任务摘要 |
| [_audit/](./\_audit/) | 项目审计报告（测试/脚本/文档整合） |

---

## 📅 最近更新

- **2025-10-17**: 完成项目审计与重组（测试/脚本/文档整合，文件减少 52%）
- **2025-01-11**: Dashboard 作为系统首页实现完成，修复登录后动态路由加载时序问题

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
