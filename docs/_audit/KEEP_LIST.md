# 保留文件清单

> ⚠️ 说明：该清单为历史审计产物（2025-10）。2026-01 起已移除 `JWTTestService` 与 `tests/test_jwt_test_service.py`；最新以 `docs/features/model_management/testing.md` 与 `tests/` 实际文件为准。

**生成日期**: 2025-10-17  
**保留原则**: 核心功能、活跃使用、无重复  
**总计**: 测试 8 个 + 脚本 26 个 + E2E 8 个 = 42 个核心文件

---

## 📋 测试文件保留清单 (8 个)

| 文件 | 用途 | 测试覆盖 | 保留理由 |
|------|------|----------|----------|
| `conftest.py` | pytest 配置 | N/A | 必需的测试基础设施 |
| `test_jwt_complete.py` | JWT 完整测试 | 认证、安全、集成 | **新建** - 合并 3 个文件 |
| `test_ai_config_service_push.py` | AI 配置服务 | Supabase 推送、备份轮转 | 核心业务逻辑 |
| `test_ai_conversation_e2e.py` | E2E 对话测试 | 完整对话流程 | 端到端验证 |
| `test_ai_conversation_logs.py` | 对话日志 | 日志记录与查询 | 可观测性验证 |
| `test_api_contracts.py` | API 契约 | 响应格式、Trace ID | API 稳定性保障 |
| `test_e2e_integration.py` | E2E 集成 | 消息创建、SSE 流 | 核心功能验证 |
| `test_model_mapping_service.py` | 模型映射 | Prompt/Fallback 映射 | 核心业务逻辑 |

**运行方式**:
```bash
# 运行所有测试
pytest tests/ -v

# 运行特定测试
pytest tests/test_jwt_complete.py -v
pytest tests/test_ai_config_service_push.py -v
```

---

## 📋 脚本文件保留清单 (26 个)

### JWT 工具 (3 个)

| 文件 | 功能 | 运行方式 |
|------|------|----------|
| `test_jwt_complete.py` | JWT 完整测试：获取、验证、失效时间 | `python scripts/test_jwt_complete.py` |
| `verify_jwks_cache.py` | JWKS 缓存验证（合并 verify_jwt_config） | `python scripts/verify_jwks_cache.py` |
| `decode_jwt.py` | JWT 解码工具 | `python scripts/decode_jwt.py <token>` |

### Supabase 体检 (3 个)

| 文件 | 功能 | 运行方式 |
|------|------|----------|
| `verify_supabase_config.py` | 异步验证配置 / API / 表权限 | `python scripts/verify_supabase_config.py` |
| `diagnose_supabase.py` | Supabase 健康检查 | `python scripts/diagnose_supabase.py` |
| `create_supabase_tables.sql` | 建表 SQL | `supabase db push < scripts/create_supabase_tables.sql` |

### 回归运维 (6 个)

| 文件 | 功能 | 运行方式 |
|------|------|----------|
| `k5_build_and_test.py` | K5 CI 管线（双构建 + Newman 测试） | `python scripts/k5_build_and_test.py` |
| `k5_rollback_drill.py` | K5 回滚演练 | `python scripts/k5_rollback_drill.py` |
| `k5_security_scanner.py` | K5 安全扫描与报告 | `python scripts/k5_security_scanner.py` |
| `smoke_test.py` | API 冒烟：注册、JWT、SSE、持久化（合并 verify_e2e_conversation） | `python scripts/smoke_test.py` |
| `verify_docker_deployment.py` | Docker 部署探测 | `python scripts/verify_docker_deployment.py` |
| `verify_gw_auth.py` | 网关认证通路验证 | `python scripts/verify_gw_auth.py` |

### 部署巡检 (4 个)

| 文件 | 功能 | 运行方式 |
|------|------|----------|
| `deploy-edge-function.sh` | 部署 Supabase Edge Function | `./scripts/deploy-edge-function.sh` |
| `docker_build_and_run.ps1` | Windows 下一键构建 / 启动 Docker | `pwsh ./scripts/docker_build_and_run.ps1` |
| `quick_verify.sh` | Linux / macOS 快速巡检（合并 verify_dashboard） | `./scripts/quick_verify.sh` |
| `quick_verify.ps1` | Windows 快速巡检（合并 verify_dashboard） | `pwsh ./scripts/quick_verify.ps1` |

### 测试脚本 (5 个)

| 文件 | 功能 | 运行方式 |
|------|------|----------|
| `test_ai_endpoints.py` | AI 端点测试（**新建** - 合并 3 个文件） | `python scripts/test_ai_endpoints.py` |
| `test_api_monitor.py` | API 监控测试 | `python scripts/test_api_monitor.py` |
| `test_jwt_complete.py` | JWT 完整测试 | `python scripts/test_jwt_complete.py` |
| `test_monitoring_pipeline.py` | 监控管线测试（合并 verify_prometheus_metrics） | `python scripts/test_monitoring_pipeline.py` |
| `test_web_frontend.py` | 校验本地前端与 API 反向代理 | `python scripts/test_web_frontend.py` |

### 辅助工具 (3 个)

| 文件 | 功能 | 运行方式 |
|------|------|----------|
| `analyze_scripts.py` | 输出脚本清单与分类统计 | `python scripts/analyze_scripts.py` |
| `debug_frontend.py` | 前端调试工具 | `python scripts/debug_frontend.py` |
| `create_test_jwt.py` | 生成测试 JWT token | `python scripts/create_test_jwt.py` |

### 数据库脚本 (2 个)

| 文件 | 功能 | 运行方式 |
|------|------|----------|
| `create_ai_config_tables.sql` | AI 配置表 | 通过 Supabase CLI 或控制台执行 |
| `optimize_rls_performance.sql` | RLS 性能优化 | 通过 Supabase CLI 或控制台执行 |

---

## 📋 E2E 测试保留清单 (8 个)

### E2E 执行脚本 (5 个)

| 文件 | 功能 | 运行方式 |
|------|------|----------|
| `verify_setup.py` | 检查依赖、网络与配置 | `python e2e/anon_jwt_sse/scripts/verify_setup.py` |
| `run_e2e_enhanced.py` | 注册 → 登录 → AI 消息 → SSE → JSON 记录 | `python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py` |
| `anon_signin_enhanced.py` | 逐步调试匿名登录与 SSE | `python e2e/anon_jwt_sse/scripts/anon_signin_enhanced.py` |
| `sse_client.py` | 轻量 SSE 客户端调试 | `python e2e/anon_jwt_sse/scripts/sse_client.py` |
| `sse_chaos.py` | SSE 混沌/压力测试 | `python e2e/anon_jwt_sse/scripts/sse_chaos.py` |

### Token & 验证脚本 (3 个)

| 文件 | 功能 | 运行方式 |
|------|------|----------|
| `generate_test_token.py` | 生成匿名访问测试 Token | `python e2e/anon_jwt_sse/scripts/generate_test_token.py` |
| `validate_anon_integration.py` | 快速校验匿名 JWT API | `python e2e/anon_jwt_sse/scripts/validate_anon_integration.py` |
| `jwt_mutation_tests.py` | Token 变体与安全测试 | `python e2e/anon_jwt_sse/scripts/jwt_mutation_tests.py` |

---

## 📋 核心文档保留清单 (7 个)

### 顶层文档 (5 个)

| 文件 | 用途 | 状态 |
|------|------|------|
| `docs/README.md` | 文档索引 | ✅ 需更新 |
| `docs/PROJECT_OVERVIEW.md` | 项目概览 | ✅ 保留 |
| `docs/JWT_HARDENING_GUIDE.md` | JWT 安全指南 | ✅ 保留 |
| `docs/GW_AUTH_README.md` | 网关认证 | ✅ 保留 |
| `docs/SCRIPTS_INDEX.md` | 脚本索引 | ✅ 需更新 |

### 新建文档 (2 个)

| 文件 | 用途 | 来源 |
|------|------|------|
| `tests/README.md` | 测试文件说明 | **新建** |
| `scripts/README.md` | 脚本使用指南 | **需更新** |

---

## 📊 保留统计

| 类别 | 数量 | 说明 |
|------|------|------|
| **测试文件** | 8 | 包含 1 个新建（合并 3 个） |
| **脚本文件** | 26 | 包含 1 个新建（合并 3 个） |
| **E2E 测试** | 8 | 全部保留 |
| **核心文档** | 7 | 包含 1 个新建 |
| **总计** | **49** | 核心文件 |

---

## 🔍 保留理由分类

### 核心业务逻辑 (15 个)
- JWT 认证测试
- AI 配置服务测试
- 模型映射服务测试
- E2E 对话测试
- API 契约测试

### 运维与监控 (12 个)
- K5 CI 管线
- 冒烟测试
- Docker 部署验证
- 网关认证验证
- 监控管线测试
- Prometheus 指标验证

### 开发工具 (10 个)
- JWT 解码工具
- 前端调试工具
- 脚本分析工具
- 测试 token 生成
- Supabase 健康检查

### 部署脚本 (4 个)
- Edge Function 部署
- Docker 构建
- 快速巡检（Linux/Windows）

### E2E 测试 (8 个)
- 匿名 JWT SSE 完整测试套件

---

## ✅ 质量标准

所有保留的文件必须满足以下标准：

1. **功能明确**: 有清晰的用途和使用场景
2. **无重复**: 不与其他文件功能重叠
3. **活跃使用**: 近期有使用记录或未来有使用计划
4. **文档完整**: 有使用说明和示例
5. **测试通过**: 可正常运行且输出符合预期

---

**保留清单维护人**: AI Assistant + 人工复核  
**复核标准**: "这个文件是解决真实问题的吗？有更简单的替代方案吗？"
