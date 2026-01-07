# GW-Auth 安装与验证（Installation）

本页用于快速把 **网关认证/限流/策略门** 在本项目中跑通，并给出可复制的验证步骤。

## 1) 前置条件

- 后端可启动：`python run.py` 或 `./start-dev.ps1`
- 已准备 `.env`（模板：`.env.example`）

## 2) 最小配置（推荐）

```bash
AUTH_FALLBACK_ENABLED=false
RATE_LIMIT_ENABLED=true
POLICY_GATE_ENABLED=true
```

> 说明：JWT 相关配置以 `.env.example` 与 `app/settings/config.py` 为准。

## 3) 启动与探活

```bash
curl http://localhost:9999/api/v1/healthz
curl http://localhost:9999/api/v1/livez
curl http://localhost:9999/api/v1/readyz
curl http://localhost:9999/api/v1/metrics
```

## 4) 一键验证脚本（推荐）

```bash
# Linux/Mac
bash scripts/verification/quick_verify.sh

# Windows (PowerShell)
pwsh scripts/verification/quick_verify.ps1

# 认证通路验证（Python）
python scripts/verification/verify_gw_auth.py
```

## 5) 相关文档

- 设计与总览：`docs/GW_AUTH_README.md`
- 回滚预案：`docs/runbooks/GW_AUTH_ROLLBACK.md`

