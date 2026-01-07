# 删除文件清单

**生成日期**: 2025-10-17  
**删除原则**: 问题已修复、功能已废弃、内容已合并  
**安全措施**: Git 历史保留，可随时恢复

---

## 📋 脚本文件删除清单 (25+ 个)

### 登录和路由相关 (10 个)

| 文件 | 删除理由 | 最后使用时间 |
|------|----------|--------------|
| `scripts/auto_login.py` | 登录问题已修复，不再需要自动登录 | 2024-10-14 |
| `scripts/check_app_routes.py` | 路由问题已修复 | 2024-10-14 |
| `scripts/check_database.py` | 数据库结构已稳定 | 2024-10-13 |
| `scripts/check_routes.py` | 与 check_app_routes.py 重复 | 2024-10-13 |
| `scripts/check_services.py` | 功能已集成到 quick_verify | 2024-10-14 |
| `scripts/configure-env.ps1` | 环境配置已完成 | 2024-10-12 |
| `scripts/final_verification.py` | 一次性验证脚本 | 2024-10-14 |
| `scripts/test_login_redirect.py` | 登录跳转问题已修复 | 2024-10-14 |
| `scripts/test_websocket_connection.py` | WebSocket 功能已废弃 | 2024-10-10 |
| `scripts/verify_route_ssot.py` | 路由问题已修复 | 2024-10-14 |

**批量删除命令**:
```bash
git rm scripts/auto_login.py \
       scripts/check_app_routes.py \
       scripts/check_database.py \
       scripts/check_routes.py \
       scripts/check_services.py \
       scripts/configure-env.ps1 \
       scripts/final_verification.py \
       scripts/test_login_redirect.py \
       scripts/test_websocket_connection.py \
       scripts/verify_route_ssot.py
```

### FRP 和部署相关 (10 个)

| 文件 | 删除理由 | 最后使用时间 |
|------|----------|--------------|
| `scripts/diagnose-frp.ps1` | FRP 配置已稳定 | 2024-10-12 |
| `scripts/fix-frp-docker.sh` | FRP 问题已修复 | 2024-10-11 |
| `scripts/remove_leaked_key.ps1` | 密钥泄露已处理 | 2024-10-14 |
| `scripts/restart_backend.ps1` | 使用 start-dev.ps1 替代 | 2024-10-14 |
| `scripts/start-frp-client.ps1` | FRP 启动已标准化 | 2024-10-12 |
| `scripts/start-frp-docker.sh` | FRP 启动已标准化 | 2024-10-12 |
| `scripts/start-frp-ini.ps1` | FRP 启动已标准化 | 2024-10-12 |
| `scripts/start-frp-native.sh` | FRP 启动已标准化 | 2024-10-12 |
| `scripts/start-frp-wsl.sh` | FRP 启动已标准化 | 2024-10-12 |
| `scripts/verify-frp-connection.ps1` | FRP 连接已稳定 | 2024-10-12 |

**批量删除命令**:
```bash
git rm scripts/diagnose-frp.ps1 \
       scripts/fix-frp-docker.sh \
       scripts/remove_leaked_key.ps1 \
       scripts/restart_backend.ps1 \
       scripts/start-frp-client.ps1 \
       scripts/start-frp-docker.sh \
       scripts/start-frp-ini.ps1 \
       scripts/start-frp-native.sh \
       scripts/start-frp-wsl.sh \
       scripts/verify-frp-connection.ps1
```

### 其他过时脚本 (5+ 个)

| 文件 | 删除理由 | 最后使用时间 |
|------|----------|--------------|
| `scripts/verify_restoration.ps1` | 仓库恢复已完成 | 2024-10-14 |
| `scripts/check-vue-syntax.ps1` | 代码检查已集成到 CI | 2024-10-13 |
| `scripts/check-vue-syntax.sh` | 代码检查已集成到 CI | 2024-10-13 |

**批量删除命令**:
```bash
git rm scripts/verify_restoration.ps1 \
       scripts/check-vue-syntax.ps1 \
       scripts/check-vue-syntax.sh
```

---

## 📋 文档文件删除清单 (1 个)

### 过时文档

| 文件 | 删除理由 | 最后更新时间 |
|------|----------|--------------|
| `docs/DOCUMENTATION_UPDATE_HANDOVER.md` | 内容已过时，端口配置已更新 | 2024-10-13 |

**删除命令**:
```bash
git rm docs/DOCUMENTATION_UPDATE_HANDOVER.md
```

---

## 🔄 合并后删除清单

### 测试文件 (3 个)

| 文件 | 合并到 | 删除时间 |
|------|--------|----------|
| `tests/test_jwt_auth.py` | `tests/test_jwt_complete.py` | 阶段 1 |
| `tests/test_jwt_hardening.py` | `tests/test_jwt_complete.py` | 阶段 1 |
| `tests/test_jwt_integration_hardening.py` | `tests/test_jwt_complete.py` | 阶段 1 |

**删除命令**:
```bash
git rm tests/test_jwt_auth.py \
       tests/test_jwt_hardening.py \
       tests/test_jwt_integration_hardening.py
```

### 脚本文件 (9 个)

| 文件 | 合并到 | 删除时间 |
|------|--------|----------|
| `scripts/verify_jwt_config.py` | `scripts/verify_jwks_cache.py` | 阶段 2 |
| `scripts/create_jwk.py` | 删除（功能已完成） | 阶段 2 |
| `scripts/find_jwt_secret.py` | 删除（配置已确定） | 阶段 2 |
| `scripts/test_ai_request_direct.py` | `scripts/test_ai_endpoints.py` | 阶段 2 |
| `scripts/test_ai_request_recording.py` | `scripts/test_ai_endpoints.py` | 阶段 2 |
| `scripts/test_dashboard_api.py` | `scripts/test_ai_endpoints.py` | 阶段 2 |
| `scripts/verify_dashboard.py` | `scripts/quick_verify.sh/ps1` | 阶段 2 |
| `scripts/verify_e2e_conversation.py` | `scripts/smoke_test.py` | 阶段 2 |
| `scripts/verify_prometheus_metrics.py` | `scripts/test_monitoring_pipeline.py` | 阶段 2 |

**删除命令**:
```bash
# JWT 脚本
git rm scripts/verify_jwt_config.py \
       scripts/create_jwk.py \
       scripts/find_jwt_secret.py

# AI 测试脚本
git rm scripts/test_ai_request_direct.py \
       scripts/test_ai_request_recording.py \
       scripts/test_dashboard_api.py

# 部署验证脚本
git rm scripts/verify_dashboard.py \
       scripts/verify_e2e_conversation.py \
       scripts/verify_prometheus_metrics.py
```

### 文档文件 (7 个)

| 文件 | 合并到 | 删除时间 |
|------|--------|----------|
| `docs/TOKEN_REFRESH_HANDOVER.md` | `docs/architecture/token-auth.md` | 阶段 3 |
| `docs/TOKEN_REFRESH_IMPLEMENTATION.md` | `docs/architecture/token-auth.md` | 阶段 3 |
| `docs/API_MONITOR_HANDOVER.md` | `docs/features/api-monitor.md` | 阶段 3 |
| `docs/DASHBOARD_ENHANCEMENTS_SUMMARY.md` | `docs/features/dashboard.md` | 阶段 3 |
| `docs/REPO_RESTORATION_SUMMARY.md` | `docs/incidents/2024-10-repo-restoration.md` | 阶段 3 |
| `docs/REPO_RESTORATION_REPORT.md` | `docs/incidents/2024-10-repo-restoration.md` | 阶段 3 |
| `docs/DEBUG_TOOLS_SUMMARY.md` | `docs/guides/debugging/README.md` | 阶段 3 |

**删除命令**:
```bash
git rm docs/TOKEN_REFRESH_HANDOVER.md \
       docs/TOKEN_REFRESH_IMPLEMENTATION.md \
       docs/API_MONITOR_HANDOVER.md \
       docs/DASHBOARD_ENHANCEMENTS_SUMMARY.md \
       docs/REPO_RESTORATION_SUMMARY.md \
       docs/REPO_RESTORATION_REPORT.md \
       docs/DEBUG_TOOLS_SUMMARY.md
```

---

## 📊 删除统计

| 类别 | 直接删除 | 合并后删除 | 总计 |
|------|----------|------------|------|
| **测试文件** | 0 | 3 | 3 |
| **脚本文件** | 23 | 9 | 32 |
| **文档文件** | 1 | 7 | 8 |
| **总计** | 24 | 19 | **43** |

---

## 🔄 恢复方法

如果需要恢复已删除的文件：

### 查找文件历史
```bash
# 查找文件的最后一次提交
git log --all --full-history -- "scripts/deleted_file.py"
```

### 恢复文件
```bash
# 恢复到工作区
git checkout <commit_hash> -- "scripts/deleted_file.py"

# 或创建新分支恢复
git checkout -b restore-deleted-file <commit_hash>
```

### 查看删除的文件内容
```bash
# 查看文件内容
git show <commit_hash>:"scripts/deleted_file.py"
```

---

## ⚠️ 注意事项

1. **删除前确认**: 使用 `codebase-retrieval` 确认无代码引用
2. **Git 历史保留**: 所有删除的文件在 Git 历史中仍可访问
3. **分批删除**: 按类别分批删除，每批 commit 一次
4. **测试验证**: 删除后运行测试确保无破坏性影响

---

**删除执行人**: AI Assistant + 人工复核  
**复核标准**: "这个文件真的不再需要了吗？删除会破坏什么吗？"

