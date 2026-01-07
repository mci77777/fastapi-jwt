# GW-Auth 交付报告（Delivery Report）

> 范围：网关认证 / 策略门 / 限流 / 健康探针 / 指标导出（与 App 首接入相关的最小闭环）

## 1) 对外接口（最小集合）

- 探活：
  - `GET /api/v1/healthz`
  - `GET /api/v1/livez`
  - `GET /api/v1/readyz`
- 指标：
  - `GET /api/v1/metrics`

## 2) 中间件链路（SSOT）

以 `app/core/application.py::create_app()` 的注册顺序为准，典型为：

1) `RequestIDMiddleware`（`X-Request-Id`）
2) `PolicyGateMiddleware`（匿名白名单 + 管理端限制）
3) `RateLimitMiddleware`（QPS/日限额；SSE `/events` 豁免 QPS 计数，由 `sse_guard` 控制并发）

## 3) Prometheus 指标（最小）

以 `app/core/metrics.py` 为准，常用指标：

- `auth_requests_total{status,user_type}`
- `auth_request_duration_seconds{endpoint}`
- `jwt_validation_errors_total{code}`
- `jwks_cache_hits_total{result}`
- `rate_limit_blocks_total{reason,user_type}`

## 4) 验证（DONE）

推荐走一键脚本：

```bash
bash scripts/verification/quick_verify.sh
python scripts/verification/verify_gw_auth.py
```

## 5) 回滚

回滚步骤见：`docs/runbooks/GW_AUTH_ROLLBACK.md`

