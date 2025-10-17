# 项目重组执行计划

**计划日期**: 2025-10-17  
**预计工时**: 9 小时  
**执行原则**: YAGNI → SSOT → KISS  
**Git 策略**: 每 5-15 个文件改动一次 commit

---

## 📋 执行清单

### 阶段 1: 测试文件整合 (2 小时)

#### Task 1.1: 合并 JWT 测试文件 ✅
**预计时间**: 1.5 小时

**步骤**:
1. 创建 `tests/test_jwt_complete.py`
2. 从 `test_jwt_auth.py` 提取基础验证测试
3. 从 `test_jwt_hardening.py` 提取安全强化测试
4. 从 `test_jwt_integration_hardening.py` 提取集成测试
5. 统一测试结构和命名
6. 运行测试验证: `pytest tests/test_jwt_complete.py -v`
7. 删除旧文件
8. Git commit

**验收标准**:
- [ ] 所有测试通过
- [ ] 测试覆盖率不降低
- [ ] 代码格式符合规范

**Git Commit**:
```bash
git add tests/test_jwt_complete.py
git rm tests/test_jwt_auth.py tests/test_jwt_hardening.py tests/test_jwt_integration_hardening.py
git commit -m "test: 合并 JWT 测试文件到 test_jwt_complete.py

- 整合 3 个 JWT 测试文件为单一入口
- 保留所有测试用例 (基础验证 + 安全强化 + 集成测试)
- 统一测试结构和命名规范
- 测试覆盖率保持不变

BREAKING CHANGE: 删除 test_jwt_auth.py, test_jwt_hardening.py, test_jwt_integration_hardening.py
"
```

#### Task 1.2: 创建测试文档 ✅
**预计时间**: 0.5 小时

**步骤**:
1. 创建 `tests/README.md`
2. 添加测试文件说明
3. 添加运行方式
4. 添加覆盖范围说明
5. Git commit

**内容大纲**:
```markdown
# 测试文件说明

## 测试文件清单
- conftest.py - pytest 配置
- test_jwt_complete.py - JWT 完整测试
- test_ai_config_service_push.py - AI 配置服务测试
- ...

## 运行方式
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_jwt_complete.py -v

## 覆盖范围
- JWT 认证: 基础验证、安全强化、集成测试
- AI 服务: 配置推送、对话流程、日志记录
- API 契约: 响应格式、Trace ID、错误处理
- E2E 集成: 消息创建、SSE 流、完整对话
```

**Git Commit**:
```bash
git add tests/README.md
git commit -m "docs: 添加测试文件说明文档

- 测试文件清单
- 运行方式
- 覆盖范围说明
"
```

---

### 阶段 2: 脚本文件整合 (4 小时)

#### Task 2.1: 删除过时脚本 - 第一批 (登录和路由) ✅
**预计时间**: 0.5 小时

**删除清单** (10 个):
```bash
scripts/auto_login.py              # 登录问题已修复
scripts/check_app_routes.py        # 路由问题已修复
scripts/check_database.py          # 数据库结构已稳定
scripts/check_routes.py             # 与 check_app_routes.py 重复
scripts/check_services.py           # 功能已集成到 quick_verify
scripts/configure-env.ps1           # 环境配置已完成
scripts/final_verification.py      # 一次性验证脚本
scripts/test_login_redirect.py     # 登录跳转问题已修复
scripts/test_websocket_connection.py # WebSocket 功能已废弃
scripts/verify_route_ssot.py       # 路由问题已修复
```

**执行**:
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

git commit -m "scripts: 删除过时脚本 - 登录和路由相关 (10 个)

删除理由：
- 登录问题已修复 (auto_login, test_login_redirect)
- 路由问题已修复 (check_app_routes, check_routes, verify_route_ssot)
- 功能已集成 (check_services → quick_verify)
- 数据库结构已稳定 (check_database)
- 一次性脚本 (final_verification, configure-env)
- 功能已废弃 (test_websocket_connection)
"
```

#### Task 2.2: 删除过时脚本 - 第二批 (FRP 和部署) ✅
**预计时间**: 0.5 小时

**删除清单** (10 个):
```bash
scripts/diagnose-frp.ps1            # FRP 配置已稳定
scripts/fix-frp-docker.sh           # FRP 问题已修复
scripts/remove_leaked_key.ps1       # 密钥泄露已处理
scripts/restart_backend.ps1         # 使用 start-dev.ps1 替代
scripts/start-frp-client.ps1        # FRP 启动已标准化
scripts/start-frp-docker.sh         # FRP 启动已标准化
scripts/start-frp-ini.ps1           # FRP 启动已标准化
scripts/start-frp-native.sh         # FRP 启动已标准化
scripts/start-frp-wsl.sh            # FRP 启动已标准化
scripts/verify-frp-connection.ps1   # FRP 连接已稳定
```

**执行**:
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

git commit -m "scripts: 删除过时脚本 - FRP 和部署相关 (10 个)

删除理由：
- FRP 配置已稳定 (diagnose-frp, verify-frp-connection)
- FRP 问题已修复 (fix-frp-docker)
- FRP 启动已标准化 (5 个 start-frp-* 脚本)
- 密钥泄露已处理 (remove_leaked_key)
- 使用统一启动脚本 (restart_backend → start-dev.ps1)
"
```

#### Task 2.3: 删除过时脚本 - 第三批 (其他) ✅
**预计时间**: 0.5 小时

**删除清单** (5+ 个):
```bash
scripts/verify_restoration.ps1      # 仓库恢复已完成
scripts/check-vue-syntax.ps1        # 代码检查已集成到 CI
scripts/check-vue-syntax.sh         # 代码检查已集成到 CI
# ... 其他过时脚本
```

**执行**:
```bash
git rm scripts/verify_restoration.ps1 \
       scripts/check-vue-syntax.ps1 \
       scripts/check-vue-syntax.sh

git commit -m "scripts: 删除过时脚本 - 其他 (5+ 个)

删除理由：
- 仓库恢复已完成 (verify_restoration)
- 代码检查已集成到 CI (check-vue-syntax)
"
```

#### Task 2.4: 合并 JWT 验证脚本 ✅
**预计时间**: 1 小时

**合并方案**:
```
verify_jwt_config.py → verify_jwks_cache.py
```

**步骤**:
1. 打开 `verify_jwks_cache.py`
2. 添加 `verify_jwt_config.py` 的配置检查功能
3. 测试合并后的脚本
4. 删除 `verify_jwt_config.py`
5. 删除 `create_jwk.py`, `find_jwt_secret.py`
6. Git commit

**Git Commit**:
```bash
git add scripts/verify_jwks_cache.py
git rm scripts/verify_jwt_config.py scripts/create_jwk.py scripts/find_jwt_secret.py
git commit -m "scripts: 合并 JWT 验证脚本

- 合并 verify_jwt_config.py 到 verify_jwks_cache.py
- 删除 create_jwk.py (仅用于初始化，已完成)
- 删除 find_jwt_secret.py (密钥配置已确定)
- 统一 JWT 验证入口
"
```

#### Task 2.5: 合并 AI 测试脚本 ✅
**预计时间**: 1 hour

**合并方案**:
```
test_ai_request_direct.py + test_ai_request_recording.py + test_dashboard_api.py
→ test_ai_endpoints.py
```

**步骤**:
1. 创建 `scripts/test_ai_endpoints.py`
2. 合并 AI 请求测试逻辑
3. 合并 Dashboard API 测试逻辑
4. 统一测试结构
5. 运行测试验证
6. 删除旧文件
7. Git commit

**Git Commit**:
```bash
git add scripts/test_ai_endpoints.py
git rm scripts/test_ai_request_direct.py \
       scripts/test_ai_request_recording.py \
       scripts/test_dashboard_api.py
git commit -m "scripts: 合并 AI 测试脚本 (3→1)

- 创建 test_ai_endpoints.py 统一入口
- 合并 AI 请求测试 (direct + recording)
- 合并 Dashboard API 测试
- 统一测试结构和输出格式
"
```

#### Task 2.6: 合并部署验证脚本 ✅
**预计时间**: 0.5 小时

**合并方案**:
```
verify_dashboard.py → quick_verify.sh/ps1
verify_e2e_conversation.py → smoke_test.py
verify_prometheus_metrics.py → test_monitoring_pipeline.py
```

**步骤**:
1. 将 `verify_dashboard.py` 功能合并到 `quick_verify.sh` 和 `quick_verify.ps1`
2. 将 `verify_e2e_conversation.py` 功能合并到 `smoke_test.py`
3. 将 `verify_prometheus_metrics.py` 功能合并到 `test_monitoring_pipeline.py`
4. 测试合并后的脚本
5. 删除旧文件
6. Git commit

**Git Commit**:
```bash
git add scripts/quick_verify.sh scripts/quick_verify.ps1 \
        scripts/smoke_test.py scripts/test_monitoring_pipeline.py
git rm scripts/verify_dashboard.py \
       scripts/verify_e2e_conversation.py \
       scripts/verify_prometheus_metrics.py
git commit -m "scripts: 合并部署验证脚本 (3→0)

- verify_dashboard → quick_verify.sh/ps1
- verify_e2e_conversation → smoke_test.py
- verify_prometheus_metrics → test_monitoring_pipeline.py
- 减少脚本数量，统一验证入口
"
```

#### Task 2.7: 更新脚本索引 ✅
**预计时间**: 0.5 小时

**步骤**:
1. 更新 `docs/SCRIPTS_INDEX.md`
2. 更新 `scripts/README.md`
3. 反映新的脚本结构
4. 更新分类统计
5. 添加删除说明
6. Git commit

**Git Commit**:
```bash
git add docs/SCRIPTS_INDEX.md scripts/README.md
git commit -m "docs: 更新脚本索引

- 反映新的脚本结构 (60+ → 26)
- 更新分类统计
- 添加删除说明
- 更新运行示例
"
```

---

### 阶段 3: 文档重组 (3 小时)

#### Task 3.1: 创建新目录结构 ✅
**预计时间**: 0.5 小时

**步骤**:
```bash
mkdir -p docs/guides/debugging
mkdir -p docs/architecture
mkdir -p docs/features
mkdir -p docs/fixes
mkdir -p docs/incidents

# 创建索引文件
touch docs/guides/debugging/README.md
touch docs/fixes/README.md
touch docs/incidents/README.md

git add docs/guides docs/architecture docs/features docs/fixes docs/incidents
git commit -m "docs: 创建新目录结构

- guides/debugging/ - 调试指南
- architecture/ - 架构文档
- features/ - 功能文档
- fixes/ - 修复记录（归档）
- incidents/ - 事件响应（归档）
"
```

#### Task 3.2: 移动调试文档 ✅
**预计时间**: 0.5 小时

**步骤**:
```bash
# 移动文件
git mv docs/CHROME_DEVTOOLS_DEBUG_GUIDE.md docs/guides/debugging/chrome-devtools.md
git mv docs/DEBUG_QUICK_REFERENCE.md docs/guides/debugging/quick-reference.md

# 创建 README (合并 DEBUG_TOOLS_SUMMARY)
# 手动创建 docs/guides/debugging/README.md

git add docs/guides/debugging/README.md
git rm docs/DEBUG_TOOLS_SUMMARY.md
git commit -m "docs: 重组调试指南到 guides/debugging/

- 移动 Chrome DevTools 指南
- 移动快速参考
- 创建 README (合并 DEBUG_TOOLS_SUMMARY)
- 统一调试文档入口
"
```

#### Task 3.3: 创建架构文档 ✅
**预计时间**: 0.5 小时

**步骤**:
```bash
# 创建 docs/architecture/token-auth.md
# 合并 TOKEN_REFRESH_HANDOVER.md + TOKEN_REFRESH_IMPLEMENTATION.md

git add docs/architecture/token-auth.md
git rm docs/TOKEN_REFRESH_HANDOVER.md docs/TOKEN_REFRESH_IMPLEMENTATION.md
git commit -m "docs: 创建 Token 认证架构文档

- 合并 TOKEN_REFRESH_HANDOVER + TOKEN_REFRESH_IMPLEMENTATION
- 统一 Token 认证文档
- 包含：问题背景、解决方案、实现细节、测试验证
"
```

#### Task 3.4: 创建功能文档 ✅
**预计时间**: 0.5 小时

**步骤**:
```bash
# 创建 docs/features/api-monitor.md (来自 API_MONITOR_HANDOVER)
# 创建 docs/features/dashboard.md (来自 DASHBOARD_ENHANCEMENTS_SUMMARY)

git add docs/features/api-monitor.md docs/features/dashboard.md
git rm docs/API_MONITOR_HANDOVER.md docs/DASHBOARD_ENHANCEMENTS_SUMMARY.md
git commit -m "docs: 创建功能文档

- API 监控功能 (来自 API_MONITOR_HANDOVER)
- Dashboard 增强功能 (来自 DASHBOARD_ENHANCEMENTS_SUMMARY)
- 统一功能文档入口
"
```

#### Task 3.5: 归档修复记录 ✅
**预计时间**: 0.5 小时

**步骤**:
```bash
# 移动文件
git mv docs/LOGIN_REDIRECT_FIX.md docs/fixes/2024-10-login-redirect.md
git mv docs/ROOT_REDIRECT_FIX.md docs/fixes/2024-10-root-redirect.md
git mv docs/SUPABASE_STATUS_FIX_HANDOVER.md docs/fixes/2024-10-supabase-status.md

# 创建索引
# 手动创建 docs/fixes/README.md

git add docs/fixes/README.md
git commit -m "docs: 归档修复记录到 fixes/

- 登录跳转修复 (2024-10)
- 根路径跳转修复 (2024-10)
- Supabase 状态修复 (2024-10)
- 创建修复索引
"
```

#### Task 3.6: 归档事件响应 ✅
**预计时间**: 0.5 小时

**步骤**:
```bash
# 移动文件
git mv docs/KEY_LEAK_RESPONSE.md docs/incidents/2024-10-key-leak.md
git mv docs/MIGRATION_TO_NEW_REPO.md docs/incidents/2024-10-repo-migration.md

# 创建合并文档
# 手动创建 docs/incidents/2024-10-repo-restoration.md
# 合并 REPO_RESTORATION_SUMMARY + REPO_RESTORATION_REPORT

git add docs/incidents/2024-10-repo-restoration.md docs/incidents/README.md
git rm docs/REPO_RESTORATION_SUMMARY.md docs/REPO_RESTORATION_REPORT.md
git commit -m "docs: 归档事件响应到 incidents/

- 密钥泄露处理 (2024-10)
- 仓库迁移 (2024-10)
- 仓库恢复 (2024-10, 合并 2 个文档)
- 创建事件索引
"
```

#### Task 3.7: 删除过时文档 ✅
**预计时间**: 0.5 小时

**步骤**:
```bash
git rm docs/DOCUMENTATION_UPDATE_HANDOVER.md

git commit -m "docs: 删除过时文档

- DOCUMENTATION_UPDATE_HANDOVER.md (内容已过时)
"
```

#### Task 3.8: 更新核心文档 ✅
**预计时间**: 0.5 小时

**步骤**:
1. 更新 `docs/README.md`
2. 更新根目录 `README.md`
3. 反映新的文档结构
4. 添加归档说明
5. 更新索引链接
6. Git commit

**Git Commit**:
```bash
git add docs/README.md README.md
git commit -m "docs: 更新核心文档

- 更新 docs/README.md 反映新结构
- 更新根目录 README.md
- 添加归档说明
- 更新索引链接
"
```

---

## ✅ 最终验收

### 验收清单

#### 测试文件
- [ ] 所有测试通过: `pytest tests/ -v`
- [ ] 测试覆盖率不降低
- [ ] `tests/README.md` 创建完成

#### 脚本文件
- [ ] 核心脚本可正常运行
- [ ] `docs/SCRIPTS_INDEX.md` 更新完成
- [ ] `scripts/README.md` 更新完成

#### 文档文件
- [ ] 新目录结构创建完成
- [ ] 所有文档链接有效
- [ ] `docs/README.md` 更新完成
- [ ] 根目录 `README.md` 更新完成

#### Git 历史
- [ ] 所有变更已提交
- [ ] Commit 消息清晰
- [ ] 无破坏性变更

---

## 📊 执行进度跟踪

| 阶段 | 任务 | 状态 | 预计时间 | 实际时间 |
|------|------|------|----------|----------|
| 1 | 合并 JWT 测试文件 | ⏳ | 1.5h | - |
| 1 | 创建测试文档 | ⏳ | 0.5h | - |
| 2 | 删除过时脚本 - 第一批 | ⏳ | 0.5h | - |
| 2 | 删除过时脚本 - 第二批 | ⏳ | 0.5h | - |
| 2 | 删除过时脚本 - 第三批 | ⏳ | 0.5h | - |
| 2 | 合并 JWT 验证脚本 | ⏳ | 1h | - |
| 2 | 合并 AI 测试脚本 | ⏳ | 1h | - |
| 2 | 合并部署验证脚本 | ⏳ | 0.5h | - |
| 2 | 更新脚本索引 | ⏳ | 0.5h | - |
| 3 | 创建新目录结构 | ⏳ | 0.5h | - |
| 3 | 移动调试文档 | ⏳ | 0.5h | - |
| 3 | 创建架构文档 | ⏳ | 0.5h | - |
| 3 | 创建功能文档 | ⏳ | 0.5h | - |
| 3 | 归档修复记录 | ⏳ | 0.5h | - |
| 3 | 归档事件响应 | ⏳ | 0.5h | - |
| 3 | 删除过时文档 | ⏳ | 0.5h | - |
| 3 | 更新核心文档 | ⏳ | 0.5h | - |

**总计**: 17 个任务，预计 9 小时

---

**执行人员**: AI Assistant + 人工复核  
**复核标准**: Linus 风格 - "这是真问题还是臆想的？有更简单的方法吗？会破坏什么吗？"

