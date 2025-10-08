# GymBro 项目脚本索引

**更新时间**：2025-10-08  
**�ܼ�**��30 ���ű� / �ű����ʲ�

---

## 目录结构总览

```
vue-fastapi-admin/
������ scripts/                      # ���Ĺ�����ع�ű���21 ����
└── e2e/anon_jwt_sse/scripts/     # 匿名 JWT SSE 专用 E2E 脚本（9 个）
```

---

## scripts/ Ŀ¼��21 ����

### 1. JWT ����֤���ߣ�5 ����

| 脚本 | 作用 | 运行方式 |
|------|------|----------|
| `verify_jwks_cache.py` | ✅ 推荐：综合校验 JWKS 缓存与 JWT 验证链路 | `python scripts/verify_jwks_cache.py` |
| `verify_jwt_config.py` | 核对 Supabase JWT 配置并尝试加载验证器 | `python scripts/verify_jwt_config.py` |
| `decode_jwt.py` | 解码任意 JWT 查看 Claims | `python scripts/decode_jwt.py <token>` |
| `create_jwk.py` | 生成 HS256 对应的 JWK | `python scripts/create_jwk.py` |
| `find_jwt_secret.py` | 辅助定位正确的 JWT Secret | `python scripts/find_jwt_secret.py` |

### 2. Supabase 与环境体检（4 个）

| 脚本 | 作用 | 运行方式 |
|------|------|----------|
| `verify_supabase_config.py` | ✅ 推荐：异步校验 Supabase 配置 / API / 表权限 | `python scripts/verify_supabase_config.py` |
| `diagnose_supabase.py` | 分析 Supabase 服务健康度 | `python scripts/diagnose_supabase.py` |
| `detect_table_schema.py` | 探测聊天表结构并给出字段补全建议 | `python scripts/detect_table_schema.py` |
| `create_supabase_tables.sql` | 建表 SQL（通过 Supabase CLI 或控制台执行） | `supabase db push < scripts/create_supabase_tables.sql` |

### 3. �ع���׼�����ά�ű���6 ����

| 脚本 | 作用 | 运行方式 |
|------|------|----------|
| `k5_build_and_test.py` | ✅ 推荐：K5 CI 总控（双构建 + Newman 测试） | `python scripts/k5_build_and_test.py` |
| `k5_rollback_drill.py` | K5 回滚演练与基线对比 | `python scripts/k5_rollback_drill.py` |
| `k5_security_scanner.py` | K5 安全扫描与报告生成 | `python scripts/k5_security_scanner.py` |
| `smoke_test.py` | API 冒烟：注册、JWT 获取、SSE、持久化 | `python scripts/smoke_test.py` |
| `verify_docker_deployment.py` | Docker 部署探测 | `python scripts/verify_docker_deployment.py` |
| `verify_gw_auth.py` | 网关认证通路验证 | `python scripts/verify_gw_auth.py` |

### 4. 平台部署与快速验证（4 个）

| 脚本 | 作用 | 运行方式 |
|------|------|----------|
| `deploy-edge-function.sh` | 部署 Supabase Edge Function | `./scripts/deploy-edge-function.sh` |
| `docker_build_and_run.ps1` | Windows 下一键构建并启动 Docker | `pwsh ./scripts/docker_build_and_run.ps1` |
| `quick_verify.sh` | Shell 快速巡检（Linux / macOS） | `./scripts/quick_verify.sh` |
| `quick_verify.ps1` | PowerShell 快速巡检（Windows） | `pwsh ./scripts/quick_verify.ps1` |

### 5. 辅助工具（2 个）

| 脚本 | 作用 | 运行方式 |
|------|------|----------|
| `analyze_scripts.py` | 输出脚本清单与分类统计 | `python scripts/analyze_scripts.py` |
| `test_web_frontend.py` | 校验本地前端与 API 反向代理是否可用 | `python scripts/test_web_frontend.py` |

---

## e2e/anon_jwt_sse/scripts/ 目录（9 个）

### 1. E2E 执行与联调（6 个）

| 脚本 | 作用 | 运行方式 |
|------|------|----------|
| `verify_setup.py` | ✅ 推荐：E2E 环境体检入口 | `python e2e/anon_jwt_sse/scripts/verify_setup.py` |
| `run_e2e_enhanced.py` | 加强版匿名用户端到端流程 | `python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py` |
| `anon_signin_enhanced.py` | 增强匿名登录 + SSE 观察 | `python e2e/anon_jwt_sse/scripts/anon_signin_enhanced.py` |
| `sse_client.py` | 轻量 SSE 客户端调试器 | `python e2e/anon_jwt_sse/scripts/sse_client.py` |
| `sse_chaos.py` | SSE 混沌测试（并发 / 断连模拟） | `python e2e/anon_jwt_sse/scripts/sse_chaos.py` |
| `validate_anon_integration.py` | 匿名 JWT API 验证 | `python e2e/anon_jwt_sse/scripts/validate_anon_integration.py` |

### 2. Token 工具与集成辅助（3 个）

| 脚本 | 作用 | 运行方式 |
|------|------|----------|
| `generate_test_token.py` | ✅ 生成匿名 Token（支持 --method / --verify） | `python e2e/anon_jwt_sse/scripts/generate_test_token.py` |
| `jwt_mutation_tests.py` | JWT 变体安全测试 | `python e2e/anon_jwt_sse/scripts/jwt_mutation_tests.py` |
| `patch_postman_env.mjs` | Postman 环境变量批量更新 | `node e2e/anon_jwt_sse/scripts/patch_postman_env.mjs` |

---

## 本次脚本清理摘要

- 移除根目录早期测试脚本：`test_api_call.py`、`test_e2e_simple.py`、`test_jwt_verifier.py`、`test_jwt_verify.py`、`test_settings.py`  
  → 功能由 `scripts/smoke_test.py`、`scripts/verify_jwks_cache.py` 等脚本覆盖。
- 合并配置 / 表结构检查：删除 `scripts/check_config.py`、`scripts/check_table_structure.py`，统一使用 `scripts/verify_supabase_config.py` 与 `scripts/detect_table_schema.py`。
- 删除旧版 API / Service Key 迭代脚本：`test_jwt_api.py`、`test_with_service_key.py`、`test_without_jwt.py`。
- K 系列仅保留最终 K5 套件，移除 `k3_smoke_test.py`、`k4_demo_generator.py`。
- E2E 目录保留增强版流程，移除 `run_simple_e2e.py`。

---

## 快速上手路径

```bash
# 1. 校验配置与 JWKS
python scripts/verify_supabase_config.py
python scripts/verify_jwks_cache.py

# 2. 生成测试 Token 并执行匿名 E2E
python e2e/anon_jwt_sse/scripts/generate_test_token.py
python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py

# 3. 运行冒烟 / CI 套件
python scripts/smoke_test.py
python scripts/k5_build_and_test.py
```

---

## 维护建议

1. 避免再新增平行迭代脚本，所有增量统一并入现有脚本或添加参数开关。
2. 新脚本必须在所属目录 README 中登记用途与运行方法。
3. 高风险脚本（写操作、回滚、部署）请附带 dry-run 说明或确认提示。
4. 定期运行 `python scripts/analyze_scripts.py` 校验目录状况。

---

## 参考文档

- `docs/PROJECT_OVERVIEW.md`
- `docs/E2E_ANON_JWT_SSE_DELIVERY_REPORT.md`
- `docs/JWT_HARDENING_GUIDE.md`
- `docs/DELIVERY_REPORT_2025-10-08.md`



