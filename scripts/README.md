# scripts 目录说明

本目录存放 GymBro 后端的常用运维脚本、验证工具与自动化套件。脚本划分为以下几类：

| 分类 | 脚本 |
|------|------|
| JWT 工具 | `verify_jwks_cache.py`、`verify_jwt_config.py`、`create_jwk.py`、`decode_jwt.py`、`find_jwt_secret.py` |
| 环境体检 | `verify_supabase_config.py`、`diagnose_supabase.py`、`detect_table_schema.py`、`create_supabase_tables.sql` |
| 回归运维 | `k5_build_and_test.py`、`k5_rollback_drill.py`、`k5_security_scanner.py`、`smoke_test.py`、`verify_docker_deployment.py`、`verify_gw_auth.py` |
| 部署与巡检 | `deploy-edge-function.sh`、`docker_build_and_run.ps1`、`quick_verify.sh`、`quick_verify.ps1` |
| 辅助工具 | `analyze_scripts.py`、`test_web_frontend.py` |

> 详细说明及运行示例可参考 `docs/SCRIPTS_INDEX.md`。

## 快速使用示例

```bash
# 1. 校验 Supabase 配置与 JWKS
python scripts/verify_supabase_config.py
python scripts/verify_jwks_cache.py

# 2. 运行端到端冒烟
python scripts/smoke_test.py

# 3. 执行 K5 CI 套件
python scripts/k5_build_and_test.py
```

## 维护准则

- 新增脚本前请确认是否可以复用现有工具，避免再次产生平行迭代版本。
- 新脚本必须更新 `docs/SCRIPTS_INDEX.md` 与本 README，注明用途、输入输出及风险点。
- 对外部系统（Supabase、Docker、网关等）有写操作的脚本须提供 dry-run 或确认提示。
- 如需批量运行脚本，可通过 `python scripts/analyze_scripts.py` 查看分类统计结果。
