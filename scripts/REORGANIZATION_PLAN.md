# Scripts 目录重组计划

## 📊 当前状态
- **总脚本数**: 60 个文件
- **问题**: 扁平结构，重复脚本多，命名混乱

## 🎯 重组目标
1. 按功能划分子目录
2. 删除重复脚本，保留 SSOT
3. 删除临时脚本（`tmp_*`）
4. 统一命名规范

## 📁 目录结构设计

```
scripts/
├── testing/          # 测试脚本
│   ├── jwt/         # JWT 相关测试
│   ├── api/         # API 测试
│   ├── supabase/    # Supabase 测试
│   └── frontend/    # 前端测试
├── deployment/       # 部署脚本
├── verification/     # 验证脚本
├── monitoring/       # 监控脚本
├── utils/           # 工具脚本
└── docs/            # 文档和指南
```

## 🔄 脚本分类和去重

### 1. JWT 测试脚本（12 个 → 3 个）

**保留（SSOT）**:
- `test_jwt_complete.py` → `testing/jwt/test_complete.py` ✅ 最全面
- `verify_jwks_cache.py` → `verification/verify_jwks_cache.py` ✅ 专门验证 JWKS
- `analyze_jwt.py` → `utils/analyze_jwt.py` ✅ 分析工具

**删除（重复/临时）**:
- `test_jwt_with_models.py` ❌ 功能被 test_jwt_complete.py 覆盖
- `test_jwks_keys.py` ❌ 功能被 verify_jwks_cache.py 覆盖
- `quick_test_jwt.py` ❌ 简化版，功能重复
- `tmp_verify_es256_jwt.py` ❌ 临时脚本
- `tmp_verify_hs256.py` ❌ 临时脚本
- `decode_jwt.py` ❌ 功能被 analyze_jwt.py 覆盖
- `decode_test_jwt.py` ❌ 功能被 analyze_jwt.py 覆盖
- `create_test_jwt.py` ❌ 功能被 test_jwt_complete.py 覆盖
- `generate_test_token.py` ❌ 功能被 test_jwt_complete.py 覆盖

### 2. Supabase 测试脚本（6 个 → 2 个）

**保留（SSOT）**:
- `verify_supabase_config.py` → `verification/verify_supabase_config.py` ✅ 配置验证
- `test_supabase_keepalive.py` → `testing/supabase/test_keepalive.py` ✅ 保活测试

**删除（重复）**:
- `test_supabase_status.py` ❌ 功能被 verify_supabase_config.py 覆盖
- `test_supabase_user_123.py` ❌ 临时测试脚本
- `test_supabase_user_api.py` ❌ 功能被 verify_supabase_config.py 覆盖
- `diagnose_supabase.py` ❌ 功能被 verify_supabase_config.py 覆盖
- `diagnose_supabase_endpoint.py` ❌ 功能被 verify_supabase_config.py 覆盖

### 3. API 测试脚本（4 个 → 2 个）

**保留（SSOT）**:
- `test_api.py` → `testing/api/test_api.py` ✅ 基础 API 测试
- `test_menu.py` → `testing/api/test_menu.py` ✅ 菜单 API 测试

**删除（重复）**:
- `test_phase1.py` ❌ 阶段性测试，已过时
- `test_phase2_api.py` ❌ 阶段性测试，已过时

### 4. 监控脚本（3 个 → 2 个）

**保留（SSOT）**:
- `smoke_test.py` → `monitoring/smoke_test.py` ✅ 冒烟测试
- `test_api_monitor.py` → `monitoring/test_api_monitor.py` ✅ API 监控

**删除（重复）**:
- `test_monitoring_pipeline.py` ❌ 功能被 test_api_monitor.py 覆盖

### 5. 验证脚本（保留）

**保留（SSOT）**:
- `quick_verify.ps1` → `verification/quick_verify.ps1` ✅
- `quick_verify.sh` → `verification/quick_verify.sh` ✅
- `verify_gw_auth.py` → `verification/verify_gw_auth.py` ✅
- `verify_docker_deployment.py` → `verification/verify_docker_deployment.py` ✅
- `verify_phase4_ui.py` → `verification/verify_phase4_ui.py` ✅
- `visual_verification_phase4.py` → `verification/visual_verification_phase4.py` ✅

### 6. 部署脚本（保留）

**保留（SSOT）**:
- `deploy-edge-function.sh` → `deployment/deploy_edge_function.sh` ✅
- `docker_build_and_run.ps1` → `deployment/docker_build_and_run.ps1` ✅
- `downgrade-frp-v052.ps1` → `deployment/downgrade_frp_v052.ps1` ✅

### 7. K5 CI/CD 脚本（保留）

**保留（SSOT）**:
- `k5_build_and_test.py` → `deployment/k5_build_and_test.py` ✅
- `k5_rollback_drill.py` → `deployment/k5_rollback_drill.py` ✅
- `k5_security_scanner.py` → `deployment/k5_security_scanner.py` ✅

### 8. 工具脚本（保留）

**保留（SSOT）**:
- `analyze_scripts.py` → `utils/analyze_scripts.py` ✅
- `debug_frontend.py` → `utils/debug_frontend.py` ✅
- `detect_table_schema.py` → `utils/detect_table_schema.py` ✅

**删除（临时）**:
- `tmp_decode_supabase_keys.py` ❌ 临时脚本
- `tmp_find_correct_secret.py` ❌ 临时脚本
- `tmp_verify_service_role_key.py` ❌ 临时脚本

### 9. SQL 脚本（保留）

**保留（SSOT）**:
- `create_ai_config_tables.sql` → `deployment/sql/create_ai_config_tables.sql` ✅
- `create_supabase_tables.sql` → `deployment/sql/create_supabase_tables.sql` ✅
- `optimize_rls_performance.sql` → `deployment/sql/optimize_rls_performance.sql` ✅
- `rollback_rls_optimization.sql` → `deployment/sql/rollback_rls_optimization.sql` ✅
- `verify_rls_optimization.sql` → `deployment/sql/verify_rls_optimization.sql` ✅

### 10. HTML 测试页面（保留）

**保留（SSOT）**:
- `browser_test_ws.html` → `testing/frontend/browser_test_ws.html` ✅
- `diagnose_token.html` → `testing/frontend/diagnose_token.html` ✅
- `inject_token_to_browser.html` → `testing/frontend/inject_token_to_browser.html` ✅
- `test_root_redirect.html` → `testing/frontend/test_root_redirect.html` ✅

### 11. 文档（保留）

**保留（SSOT）**:
- `JWT_COMPLETE_GUIDE.md` → `docs/JWT_COMPLETE_GUIDE.md` ✅
- `LOGIN_GUIDE.md` → `docs/LOGIN_GUIDE.md` ✅
- `DIAGNOSIS_REPORT.md` → `docs/DIAGNOSIS_REPORT.md` ✅
- `README.md` → `README.md` ✅（根目录）

### 12. 其他文件

**保留**:
- `.last_token.txt` → 删除（临时文件）❌
- `test_token_refresh.py` → `testing/jwt/test_token_refresh.py` ✅
- `test_token_simple.py` → `testing/jwt/test_token_simple.py` ✅
- `test_web_frontend.py` → `testing/frontend/test_web_frontend.py` ✅

## 📊 统计

- **原始脚本数**: 60 个
- **删除脚本数**: 18 个（重复 + 临时）
- **保留脚本数**: 42 个
- **减少比例**: 30%

## ✅ 执行步骤

1. 创建子目录结构
2. 移动保留脚本到对应目录
3. 删除重复和临时脚本
4. 更新文档引用
5. Git 提交
