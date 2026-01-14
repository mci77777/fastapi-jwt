# GymBro 脚本索引

**更新时间**：2025-12-24
**总计**：32 个 Python 脚本（`scripts/` 目录 24 个，`e2e/anon_jwt_sse/scripts/` 目录 8 个）

---

## 目录结构

```
vue-fastapi-admin/
├── scripts/                      # 运维 / 验证 / 测试脚本（已按子目录重组）
└── e2e/anon_jwt_sse/scripts/     # 匿名 JWT SSE 专用 E2E 脚本
```

---

## scripts/ 目录（24 个）

### 1. JWT 工具（4 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `scripts/testing/jwt/test_complete.py` | ✅ **JWT 完整测试（SSOT）**：获取/解析/验证/失效 | `python scripts/testing/jwt/test_complete.py` |
| `scripts/testing/jwt/test_token_refresh.py` | Token 刷新测试 | `python scripts/testing/jwt/test_token_refresh.py` |
| `scripts/testing/jwt/test_token_simple.py` | 简单 Token 测试 | `python scripts/testing/jwt/test_token_simple.py` |
| `scripts/utils/analyze_jwt.py` | JWT 分析工具 | `python scripts/utils/analyze_jwt.py` |

### 2. Supabase 体检（3 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `scripts/verification/verify_supabase_config.py` | ✅ 异步验证配置 / API / 表权限（SSOT） | `python scripts/verification/verify_supabase_config.py` |
| `scripts/testing/supabase/test_keepalive.py` | Supabase 保活测试 | `python scripts/testing/supabase/test_keepalive.py` |
| `scripts/utils/detect_table_schema.py` | 探测聊天表结构，给出字段建议 | `python scripts/utils/detect_table_schema.py` |

### 3. 回归运维（8 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `scripts/monitoring/smoke_test.py` | API 冒烟：注册、JWT、SSE、持久化 | `python scripts/monitoring/smoke_test.py` |
| `scripts/monitoring/test_api_monitor.py` | API 监控测试 | `python scripts/monitoring/test_api_monitor.py` |
| `scripts/monitoring/daily_mapped_model_jwt_e2e.py` | ✅ 每日 E2E：匿名/普通 JWT + 映射模型 message 可用性，结果写入 SQLite | `python scripts/monitoring/daily_mapped_model_jwt_e2e.py` |
| `scripts/monitoring/daily_mapped_model_schedule_check.py` | ✅ 调度守门：读取 Dashboard 配置，判断是否应触发每日 E2E | `python scripts/monitoring/daily_mapped_model_schedule_check.py` |
| `scripts/deployment/k5_build_and_test.py` | ✅ K5 CI 管线（双构建 + Newman 测试） | `python scripts/deployment/k5_build_and_test.py` |
| `scripts/deployment/k5_rollback_drill.py` | K5 回滚演练 | `python scripts/deployment/k5_rollback_drill.py` |
| `scripts/deployment/k5_security_scanner.py` | K5 安全扫描与报告 | `python scripts/deployment/k5_security_scanner.py` |
| `scripts/verification/verify_docker_deployment.py` | Docker 部署探测 | `python scripts/verification/verify_docker_deployment.py` |
| `scripts/verification/verify_gw_auth.py` | 网关认证通路验证 | `python scripts/verification/verify_gw_auth.py` |

### 4. UI / Docker / 其他验证（4 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `scripts/verification/verify_jwks_cache.py` | ✅ 综合校验 JWKS 缓存与 JWT 验证链路 | `python scripts/verification/verify_jwks_cache.py` |
| `scripts/verification/verify_phase4_ui.py` | Phase 4 UI 验证 | `python scripts/verification/verify_phase4_ui.py` |
| `scripts/verification/visual_verification_phase4.py` | Phase 4 可视化验证 | `python scripts/verification/visual_verification_phase4.py` |
| `scripts/verification/audit_supabase_naming.py` | Supabase 命名/引用审计（输出到 report/audit） | `python scripts/verification/audit_supabase_naming.py` |

### 5. API / 前端测试（3 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `scripts/testing/api/test_api.py` | 基础 API 测试 | `python scripts/testing/api/test_api.py` |
| `scripts/testing/api/test_menu.py` | 菜单 API 测试 | `python scripts/testing/api/test_menu.py` |
| `scripts/testing/frontend/test_web_frontend.py` | 校验本地前端与 API 反向代理 | `python scripts/testing/frontend/test_web_frontend.py` |

---

## e2e/anon_jwt_sse/scripts/ 目录（8 个）

### 1. E2E 执行（5 个）

| 脚本 | 功能 | 运行方式 |
|------|------|----------|
| `verify_setup.py` | ✅ 检查依赖、网络与配置 | `python e2e/anon_jwt_sse/scripts/verify_setup.py` |
| `run_e2e_enhanced.py` | 注册 → 登录 → AI 消息 → SSE → **TXT（默认，含 <> 标签原样）** + JSON 记录 | `python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py` |
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
python scripts/verification/verify_supabase_config.py
python scripts/verification/verify_jwks_cache.py

# 2. 生成 Token 并执行匿名 E2E
python e2e/anon_jwt_sse/scripts/generate_test_token.py --method auto --verify
python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py
# 产物：默认输出到 e2e/anon_jwt_sse/artifacts/anon_e2e_trace.json + anon_e2e_trace.txt（TXT 含 completed.reply 原文，便于人工核对尖括号标签）
#
# 可选：prompt 模式（server / passthrough）与 TXT 内容（text / raw / both）
# python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py --prompt-mode passthrough --extra-system-prompt "<text>" --result-mode both
# python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py --prompt-mode server --result-mode raw
#
# 可选：多模型并发（model key 来自 /api/v1/llm/app/models；并发过高可能触发 SSE 并发守卫/限流，失败会在报告中汇总）
# python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py --models "xai,deepseek" --concurrency 2
# python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py --models auto --concurrency 2

# 3. 运行冒烟 / CI 套件
python scripts/monitoring/smoke_test.py
python scripts/deployment/k5_build_and_test.py
```

---

## 维护准则

1. 新增脚本前优先评估是否能扩展现有脚本，避免再出现平行版本。
2. 必须同步更新本文件与所属目录 README，注明用途、运行方式与主要输出。
3. 对外部系统有写操作的脚本应提供 dry-run 或确认提示。
4. 定期执行 `python scripts/utils/analyze_scripts.py` 复核脚本分类与数量。
