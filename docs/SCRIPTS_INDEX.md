# GymBro 脚本索引

**更新时间**：2025-10-08  
**总计**：24 个 Python 脚本（scripts/ 目录 16 个，e2e/ 匿名链路 8 个）

---

## 目录结构

```
vue-fastapi-admin/
├── scripts/                      # 核心运维与诊断脚本
└── e2e/anon_jwt_sse/scripts/     # 匿名 JWT SSE 专用 E2E 脚本
```

---

## scripts/ 目录（16 个）

### 1. JWT 工具（5 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `verify_jwks_cache.py` | ✅ 综合校验 JWKS 缓存与 JWT 验证链路 | `python scripts/verify_jwks_cache.py` |
| `verify_jwt_config.py` | 检查 Supabase JWT 配置并尝试初始化验证器 | `python scripts/verify_jwt_config.py` |
| `create_jwk.py` | 生成 HS256 对应的 JWK | `python scripts/create_jwk.py` |
| `decode_jwt.py` | 解码 JWT 观察 Claims | `python scripts/decode_jwt.py <token>` |
| `find_jwt_secret.py` | 辅助定位正确的 JWT Secret | `python scripts/find_jwt_secret.py` |

### 2. Supabase 体检（4 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `verify_supabase_config.py` | ✅ 异步验证配置 / API / 表权限 | `python scripts/verify_supabase_config.py` |
| `diagnose_supabase.py` | Supabase 健康检查 | `python scripts/diagnose_supabase.py` |
| `detect_table_schema.py` | 探测聊天表结构，给出字段建议 | `python scripts/detect_table_schema.py` |
| `create_supabase_tables.sql` | 建表 SQL（通过 Supabase CLI 或控制台执行） | `supabase db push < scripts/create_supabase_tables.sql` |

### 3. 回归运维（6 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `k5_build_and_test.py` | ✅ K5 CI 管线（双构建 + Newman 测试） | `python scripts/k5_build_and_test.py` |
| `k5_rollback_drill.py` | K5 回滚演练 | `python scripts/k5_rollback_drill.py` |
| `k5_security_scanner.py` | K5 安全扫描与报告 | `python scripts/k5_security_scanner.py` |
| `smoke_test.py` | API 冒烟：注册、JWT、SSE、持久化 | `python scripts/smoke_test.py` |
| `verify_docker_deployment.py` | Docker 部署探测 | `python scripts/verify_docker_deployment.py` |
| `verify_gw_auth.py` | 网关认证通路验证 | `python scripts/verify_gw_auth.py` |

### 4. 平台部署与巡检（4 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `deploy-edge-function.sh` | 部署 Supabase Edge Function | `./scripts/deploy-edge-function.sh` |
| `docker_build_and_run.ps1` | Windows 下一键构建 / 启动 Docker | `pwsh ./scripts/docker_build_and_run.ps1` |
| `quick_verify.sh` | Linux / macOS 快速巡检 | `./scripts/quick_verify.sh` |
| `quick_verify.ps1` | Windows 快速巡检 | `pwsh ./scripts/quick_verify.ps1` |

### 5. 辅助工具（2 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `analyze_scripts.py` | 输出脚本清单与分类统计 | `python scripts/analyze_scripts.py` |
| `test_web_frontend.py` | 校验本地前端与 API 反向代理 | `python scripts/test_web_frontend.py` |

---

## e2e/anon_jwt_sse/scripts/ 目录（8 个）

### 1. E2E 执行（5 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `verify_setup.py` | ✅ 检查依赖、网络与配置 | `python e2e/anon_jwt_sse/scripts/verify_setup.py` |
| `run_e2e_enhanced.py` | 注册 → 登录 → AI 消息 → SSE → JSON 记录 | `python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py` |
| `anon_signin_enhanced.py` | 逐步调试匿名登录与 SSE | `python e2e/anon_jwt_sse/scripts/anon_signin_enhanced.py` |
| `sse_client.py` | 轻量 SSE 客户端调试 | `python e2e/anon_jwt_sse/scripts/sse_client.py` |
| `sse_chaos.py` | SSE 混沌/压力测试 | `python e2e/anon_jwt_sse/scripts/sse_chaos.py` |

### 2. Token & 验证（3 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `generate_test_token.py` | ✅ 生成匿名 Token（`--method {auto|edge|native}` / `--verify`） | `python e2e/anon_jwt_sse/scripts/generate_test_token.py` |
| `jwt_mutation_tests.py` | JWT 变体安全测试 | `python e2e/anon_jwt_sse/scripts/jwt_mutation_tests.py` |
| `validate_anon_integration.py` | 快速校验匿名 JWT API | `python e2e/anon_jwt_sse/scripts/validate_anon_integration.py` |

---

## 最近清理摘要

- 删除历史脚本：`create_test_jwt.py`、`manual_jwt_test.py` 及旧版测试脚本，改由 `generate_test_token.py` 和 `run_e2e_enhanced.py` 提供统一能力。
- `generate_test_token.py`、`run_e2e_enhanced.py`、`anon_signin_enhanced.py`、`sse_*` 等脚本统一由 Ruff 校验通过，并输出 JSON 级联记录。
- 文档与 README 均同步更新，确保目录统计和使用说明准确。

---

## 快速上手

```bash
# 1. 校验 Supabase 配置与 JWKS
python scripts/verify_supabase_config.py
python scripts/verify_jwks_cache.py

# 2. 生成 Token 并执行匿名 E2E
python e2e/anon_jwt_sse/scripts/generate_test_token.py --method auto --verify
python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py

# 3. 运行冒烟 / CI 套件
python scripts/smoke_test.py
python scripts/k5_build_and_test.py
```

---

## 维护准则

1. 新增脚本前优先评估是否能扩展现有脚本，避免再出现平行版本。
2. 必须同步更新本文件与所属目录 README，注明用途、运行方式与主要输出。
3. 对外部系统有写操作的脚本应提供 dry-run 或确认提示。
4. 定期执行 `python scripts/analyze_scripts.py` 复核脚本分类与数量。
