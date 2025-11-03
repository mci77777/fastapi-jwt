# Scripts 目录说明

本目录存放 GymBro 后端的常用运维脚本、验证工具与自动化套件。

## 📁 目录结构

```
scripts/
├── testing/          # 测试脚本
│   ├── jwt/         # JWT 相关测试（5 个脚本）
│   ├── api/         # API 测试（2 个脚本）
│   ├── supabase/    # Supabase 测试（1 个脚本）
│   └── frontend/    # 前端测试（5 个脚本）
├── deployment/       # 部署脚本（6 个脚本 + 5 个 SQL）
│   └── sql/         # SQL 脚本
├── verification/     # 验证脚本（8 个脚本）
├── monitoring/       # 监控脚本（2 个脚本）
├── utils/           # 工具脚本（4 个脚本）
└── docs/            # 文档（3 个文档）
```

## 🚀 快速使用示例

```bash
# 1. 校验 Supabase 配置与 JWKS
python scripts/verification/verify_supabase_config.py
python scripts/verification/verify_jwks_cache.py

# 2. 运行端到端冒烟测试
python scripts/monitoring/smoke_test.py

# 3. 执行 K5 CI 套件
python scripts/deployment/k5_build_and_test.py

# 4. JWT 完整测试
python scripts/testing/jwt/test_complete.py

# 5. API 测试
python scripts/testing/api/test_api.py
```

## 📋 脚本分类详情

### 测试脚本 (testing/)

#### JWT 测试 (testing/jwt/)
- `test_complete.py` - JWT 完整测试（获取、验证、失效时间）
- `test_token_refresh.py` - Token 刷新测试
- `test_token_simple.py` - 简单 Token 测试

#### API 测试 (testing/api/)
- `test_api.py` - 基础 API 测试
- `test_menu.py` - 菜单 API 测试

#### Supabase 测试 (testing/supabase/)
- `test_keepalive.py` - Supabase 保活测试

#### 前端测试 (testing/frontend/)
- `browser_test_ws.html` - WebSocket 浏览器测试
- `diagnose_token.html` - Token 诊断页面
- `inject_token_to_browser.html` - Token 注入工具
- `test_root_redirect.html` - 根路径重定向测试
- `test_web_frontend.py` - 前端自动化测试

### 部署脚本 (deployment/)
- `deploy_edge_function.sh` - Edge Function 部署
- `docker_build_and_run.ps1` - Docker 构建和运行
- `downgrade_frp_v052.ps1` - FRP 降级脚本
- `k5_build_and_test.py` - K5 CI/CD 构建和测试
- `k5_rollback_drill.py` - K5 回滚演练
- `k5_security_scanner.py` - K5 安全扫描

#### SQL 脚本 (deployment/sql/)
- `create_ai_config_tables.sql` - 创建 AI 配置表
- `create_supabase_tables.sql` - 创建 Supabase 表
- `optimize_rls_performance.sql` - RLS 性能优化
- `rollback_rls_optimization.sql` - 回滚 RLS 优化
- `verify_rls_optimization.sql` - 验证 RLS 优化

### 验证脚本 (verification/)
- `quick_verify.ps1` / `quick_verify.sh` - 快速验证
- `verify_gw_auth.py` - 网关认证验证
- `verify_docker_deployment.py` - Docker 部署验证
- `verify_jwks_cache.py` - JWKS 缓存验证
- `verify_supabase_config.py` - Supabase 配置验证
- `verify_phase4_ui.py` - Phase 4 UI 验证
- `visual_verification_phase4.py` - Phase 4 可视化验证

### 监控脚本 (monitoring/)
- `smoke_test.py` - 冒烟测试
- `test_api_monitor.py` - API 监控测试

### 工具脚本 (utils/)
- `analyze_jwt.py` - JWT 分析工具
- `analyze_scripts.py` - 脚本分析工具
- `debug_frontend.py` - 前端调试工具
- `detect_table_schema.py` - 表结构检测工具

### 文档 (docs/)
- `JWT_COMPLETE_GUIDE.md` - JWT 完整指南
- `LOGIN_GUIDE.md` - 登录指南
- `DIAGNOSIS_REPORT.md` - 诊断报告

## 📊 重组统计

- **原始脚本数**: 60 个
- **删除重复/临时脚本**: 21 个
- **保留脚本数**: 39 个
- **减少比例**: 35%

## ✅ 维护准则

- **SSOT 原则**: 每个功能只保留一个权威脚本，避免重复
- **YAGNI 原则**: 只保留当前需要的脚本，删除过时和临时脚本
- **KISS 原则**: 保持脚本简单，避免过度抽象
- 新增脚本前请确认是否可以复用现有工具
- 新脚本必须放入对应子目录，并更新本 README
- 对外部系统有写操作的脚本须提供 dry-run 或确认提示

## 📝 相关文档

- 详细脚本索引：`docs/SCRIPTS_INDEX.md`
- 重组计划：`scripts/REORGANIZATION_PLAN.md`
