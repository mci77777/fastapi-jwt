# Scripts 目录说明

本目录存放 GymBro FastAPI + Vue3 项目的运维脚本、验证工具与自动化套件。

**最后更新**: 2025-11-03
**重组状态**: ✅ 已完成（删除 21 个重复脚本，减少 35% 冗余）

## 📁 目录结构

```
scripts/
├── testing/                    # 测试脚本（13 个文件）
│   ├── jwt/                   # JWT 相关测试（3 个脚本）
│   │   ├── test_complete.py           # JWT 完整测试（SSOT）
│   │   ├── test_token_refresh.py      # Token 刷新测试
│   │   └── test_token_simple.py       # 简单 Token 测试
│   ├── api/                   # API 测试（2 个脚本）
│   │   ├── test_api.py                # 基础 API 测试
│   │   └── test_menu.py               # 菜单 API 测试
│   ├── supabase/              # Supabase 测试（1 个脚本）
│   │   └── test_keepalive.py          # Supabase 保活测试
│   └── frontend/              # 前端测试（5 个文件）
│       ├── browser_test_ws.html       # WebSocket 浏览器测试
│       ├── diagnose_token.html        # Token 诊断页面
│       ├── inject_token_to_browser.html  # Token 注入工具
│       ├── test_root_redirect.html    # 根路径重定向测试
│       └── test_web_frontend.py       # 前端自动化测试
│
├── deployment/                 # 部署脚本（11 个文件）
│   ├── deploy_edge_function.sh        # Edge Function 部署
│   ├── docker_build_and_run.ps1       # Docker 构建和运行
│   ├── downgrade_frp_v052.ps1         # FRP 降级脚本
│   ├── k5_build_and_test.py           # K5 CI/CD 构建和测试
│   ├── k5_rollback_drill.py           # K5 回滚演练
│   ├── k5_security_scanner.py         # K5 安全扫描
│   └── sql/                   # SQL 脚本（5 个文件）
│       ├── create_ai_config_tables.sql      # 创建 AI 配置表
│       ├── create_supabase_tables.sql       # 创建 Supabase 表
│       ├── optimize_rls_performance.sql     # RLS 性能优化
│       ├── rollback_rls_optimization.sql    # 回滚 RLS 优化
│       └── verify_rls_optimization.sql      # 验证 RLS 优化
│
├── verification/               # 验证脚本（8 个脚本）
│   ├── quick_verify.ps1               # 快速验证（PowerShell）
│   ├── quick_verify.sh                # 快速验证（Shell）
│   ├── verify_gw_auth.py              # 网关认证验证
│   ├── verify_docker_deployment.py    # Docker 部署验证
│   ├── verify_jwks_cache.py           # JWKS 缓存验证（SSOT）
│   ├── verify_supabase_config.py      # Supabase 配置验证（SSOT）
│   ├── verify_phase4_ui.py            # Phase 4 UI 验证
│   └── visual_verification_phase4.py  # Phase 4 可视化验证
│
├── monitoring/                 # 监控脚本（2 个脚本）
│   ├── smoke_test.py                  # 冒烟测试（SSOT）
│   └── test_api_monitor.py            # API 监控测试
│
├── utils/                      # 工具脚本（4 个脚本）
│   ├── analyze_jwt.py                 # JWT 分析工具
│   ├── analyze_scripts.py             # 脚本分析工具
│   ├── debug_frontend.py              # 前端调试工具（308 行）
│   └── detect_table_schema.py         # 表结构检测工具
│
├── docs/                       # 文档（3 个文档）
│   ├── JWT_COMPLETE_GUIDE.md          # JWT 完整指南（463 行）
│   ├── LOGIN_GUIDE.md                 # 登录指南（291 行）
│   └── DIAGNOSIS_REPORT.md            # 诊断报告（252 行）
│
├── README.md                   # 本文件
└── REORGANIZATION_PLAN.md      # 重组计划文档
```

**标注说明**：
- **(SSOT)**: Single Source of Truth - 该功能的权威脚本
- **行数**: 重要文档/脚本的代码行数

## 🚀 快速使用示例

### 日常验证（推荐）

```bash
# 1. 快速验证（一键检查所有关键服务）
.\scripts\verification\quick_verify.ps1  # Windows
# 或
bash scripts/verification/quick_verify.sh  # Linux/Mac

# 2. 校验 Supabase 配置与 JWKS
python scripts/verification/verify_supabase_config.py
python scripts/verification/verify_jwks_cache.py

# 3. 运行端到端冒烟测试
python scripts/monitoring/smoke_test.py
```

### 开发测试

```bash
# JWT 完整测试
python scripts/testing/jwt/test_complete.py

# API 测试
python scripts/testing/api/test_api.py
python scripts/testing/api/test_menu.py

# Supabase 保活测试
python scripts/testing/supabase/test_keepalive.py
```

### 部署与 CI/CD

```bash
# K5 CI 套件（构建 + 测试）
python scripts/deployment/k5_build_and_test.py

# K5 回滚演练
python scripts/deployment/k5_rollback_drill.py

# Docker 构建和运行
.\scripts\deployment\docker_build_and_run.ps1

# 部署 Edge Function
bash scripts/deployment/deploy_edge_function.sh
```

### 调试工具

```bash
# JWT 分析
python scripts/utils/analyze_jwt.py

# 前端调试（Chrome DevTools 指南）
python scripts/utils/debug_frontend.py

# 表结构检测
python scripts/utils/detect_table_schema.py
```

## 📋 脚本分类详情

### 测试脚本 (testing/)

#### JWT 测试 (testing/jwt/)
| 脚本 | 功能 | 用途 |
|------|------|------|
| `test_complete.py` | JWT 完整测试 | 获取、验证、失效时间测试（**SSOT**）|
| `test_token_refresh.py` | Token 刷新测试 | 测试 Token 刷新机制 |
| `test_token_simple.py` | 简单 Token 测试 | 快速验证 Token 基本功能 |

#### API 测试 (testing/api/)
| 脚本 | 功能 | 用途 |
|------|------|------|
| `test_api.py` | 基础 API 测试 | 测试核心 API 端点 |
| `test_menu.py` | 菜单 API 测试 | 测试菜单权限 API |

#### Supabase 测试 (testing/supabase/)
| 脚本 | 功能 | 用途 |
|------|------|------|
| `test_keepalive.py` | Supabase 保活测试 | 测试免费层保活机制 |

#### 前端测试 (testing/frontend/)
| 文件 | 功能 | 用途 |
|------|------|------|
| `browser_test_ws.html` | WebSocket 测试 | 浏览器端 WebSocket 连接测试 |
| `diagnose_token.html` | Token 诊断 | 浏览器端 Token 解析和诊断 |
| `inject_token_to_browser.html` | Token 注入 | 将 Token 注入浏览器 localStorage |
| `test_root_redirect.html` | 重定向测试 | 测试根路径重定向逻辑 |
| `test_web_frontend.py` | 前端自动化测试 | Selenium 自动化测试 |

### 部署脚本 (deployment/)

| 脚本 | 功能 | 用途 |
|------|------|------|
| `deploy_edge_function.sh` | Edge Function 部署 | 部署 Supabase Edge Functions |
| `docker_build_and_run.ps1` | Docker 构建运行 | 一键构建和运行 Docker 容器 |
| `downgrade_frp_v052.ps1` | FRP 降级 | 降级 FRP 到 v0.52.3 |
| `k5_build_and_test.py` | K5 CI/CD | 构建和测试（Newman 集成）|
| `k5_rollback_drill.py` | K5 回滚演练 | 回滚流程演练 |
| `k5_security_scanner.py` | K5 安全扫描 | 安全漏洞扫描 |

#### SQL 脚本 (deployment/sql/)
| 脚本 | 功能 | 用途 |
|------|------|------|
| `create_ai_config_tables.sql` | 创建 AI 配置表 | 初始化 AI 配置数据库 |
| `create_supabase_tables.sql` | 创建 Supabase 表 | 初始化 Supabase 数据库 |
| `optimize_rls_performance.sql` | RLS 性能优化 | 优化行级安全策略 |
| `rollback_rls_optimization.sql` | 回滚 RLS 优化 | 回滚 RLS 优化 |
| `verify_rls_optimization.sql` | 验证 RLS 优化 | 验证 RLS 优化效果 |

### 验证脚本 (verification/)

| 脚本 | 功能 | 用途 |
|------|------|------|
| `quick_verify.ps1` / `.sh` | 快速验证 | 一键检查所有关键服务 |
| `verify_gw_auth.py` | 网关认证验证 | 验证网关认证流程 |
| `verify_docker_deployment.py` | Docker 部署验证 | 验证 Docker 部署 |
| `verify_jwks_cache.py` | JWKS 缓存验证 | 验证 JWKS 缓存机制（**SSOT**）|
| `verify_supabase_config.py` | Supabase 配置验证 | 验证 Supabase 配置（**SSOT**）|
| `verify_phase4_ui.py` | Phase 4 UI 验证 | 验证 Phase 4 UI 功能 |
| `visual_verification_phase4.py` | Phase 4 可视化验证 | Phase 4 可视化验证 |

### 监控脚本 (monitoring/)

| 脚本 | 功能 | 用途 |
|------|------|------|
| `smoke_test.py` | 冒烟测试 | 端到端冒烟测试（**SSOT**）|
| `test_api_monitor.py` | API 监控测试 | API 监控和性能测试 |

### 工具脚本 (utils/)

| 脚本 | 功能 | 用途 |
|------|------|------|
| `analyze_jwt.py` | JWT 分析 | 解析和分析 JWT Token |
| `analyze_scripts.py` | 脚本分析 | 分析脚本依赖和结构 |
| `debug_frontend.py` | 前端调试 | Chrome DevTools 调试指南（308 行）|
| `detect_table_schema.py` | 表结构检测 | 检测数据库表结构 |

### 文档 (docs/)

| 文档 | 内容 | 行数 |
|------|------|------|
| `JWT_COMPLETE_GUIDE.md` | JWT 完整指南 | 463 行 |
| `LOGIN_GUIDE.md` | 登录指南 | 291 行 |
| `DIAGNOSIS_REPORT.md` | 诊断报告 | 252 行 |

## 📊 重组统计（2025-11-03）

| 指标 | 数值 | 说明 |
|------|------|------|
| **原始脚本数** | 60 个 | 重组前的总脚本数 |
| **删除脚本数** | 21 个 | 重复/临时/过时脚本 |
| **保留脚本数** | 39 个 | 当前活跃脚本 |
| **减少比例** | 35% | 冗余消除比例 |
| **子目录数** | 9 个 | 功能分类目录 |
| **SSOT 脚本** | 5 个 | 权威脚本（标注 SSOT）|

### 删除的脚本类别

| 类别 | 删除数量 | 示例 |
|------|---------|------|
| JWT 测试 | 9 个 | `test_jwt_with_models.py`, `quick_test_jwt.py`, `tmp_verify_es256_jwt.py` |
| Supabase 测试 | 5 个 | `test_supabase_status.py`, `diagnose_supabase.py` |
| API 测试 | 2 个 | `test_phase1.py`, `test_phase2_api.py` |
| 监控 | 1 个 | `test_monitoring_pipeline.py` |
| 工具 | 3 个 | `tmp_decode_supabase_keys.py`, `tmp_find_correct_secret.py` |
| 临时文件 | 1 个 | `.last_token.txt` |

**删除理由**: 功能被 SSOT 脚本覆盖，或为临时/过时脚本。

## ✅ 维护准则

### 三大原则（严格优先级）

1. **YAGNI (You Aren't Gonna Need It)**
   - 只保留当前需要的脚本
   - 删除过时和临时脚本（`tmp_*` 前缀）
   - 拒绝"可能有用"的预留脚本

2. **SSOT (Single Source of Truth)**
   - 每个功能只保留一个权威脚本
   - 避免重复实现（如 9 个 JWT 测试 → 1 个 SSOT）
   - 标注 SSOT 脚本，便于识别

3. **KISS (Keep It Simple, Stupid)**
   - 保持脚本简单，避免过度抽象
   - 采用两层目录结构（避免过度嵌套）
   - 命名清晰直观

### 新增脚本规范

- ✅ **检查复用**: 新增前确认是否可以复用现有工具
- ✅ **放入子目录**: 必须放入对应功能子目录
- ✅ **更新 README**: 在本文件中添加脚本说明
- ✅ **写操作保护**: 对外部系统有写操作的脚本须提供 dry-run 或确认提示
- ✅ **命名规范**:
  - 测试脚本: `test_*.py`
  - 验证脚本: `verify_*.py`
  - 工具脚本: `analyze_*.py`, `debug_*.py`, `detect_*.py`
  - 禁止临时脚本: 不允许 `tmp_*` 前缀

## 📝 相关文档

| 文档 | 路径 | 说明 |
|------|------|------|
| **详细脚本索引** | `docs/SCRIPTS_INDEX.md` | 24 个脚本按用例分类 |
| **重组计划** | `scripts/REORGANIZATION_PLAN.md` | 重组策略和决策记录 |
| **项目概览** | `docs/PROJECT_OVERVIEW.md` | 系统架构和技术栈 |
| **JWT 硬化指南** | `docs/JWT_HARDENING_GUIDE.md` | JWT 安全配置 |
| **网关认证文档** | `docs/GW_AUTH_README.md` | 健康探针和指标 |

## 🔧 常见问题

### Q: 如何选择合适的脚本？

**A**: 根据用途选择：
- **日常验证**: `quick_verify.ps1` 或 `verify_supabase_config.py`
- **端到端测试**: `smoke_test.py`
- **JWT 调试**: `test_complete.py` 或 `analyze_jwt.py`
- **部署**: `k5_build_and_test.py` 或 `docker_build_and_run.ps1`

### Q: 脚本执行失败怎么办？

**A**: 检查步骤：
1. 确认 Python 环境（需要 3.11+）
2. 检查 `.env` 配置文件
3. 查看脚本内的注释说明
4. 参考 `scripts/docs/` 中的相关文档

### Q: 如何贡献新脚本？

**A**: 遵循流程：
1. 检查是否可以复用现有脚本
2. 确定功能分类（testing/deployment/verification/monitoring/utils）
3. 放入对应子目录
4. 更新本 README 和 `REORGANIZATION_PLAN.md`
5. 提交 PR 并说明用途

## 📞 支持

- **问题反馈**: 提交 GitHub Issue
- **文档更新**: 提交 PR 到 `scripts/README.md`
- **脚本贡献**: 遵循维护准则，提交 PR
