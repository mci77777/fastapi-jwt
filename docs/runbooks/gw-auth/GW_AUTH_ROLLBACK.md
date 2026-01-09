# GW-Auth 回滚预案（Runbook）

目标：在出现认证/策略门/限流引发的 **大面积误杀** 或 **服务不可用** 时，快速回滚到可用状态，并保留排障所需的最小证据。

## 0) 触发条件（任一满足即可）

- `/api/v1/healthz` 非 200 或持续超时
- 认证失败率突增（`auth_requests_total{status!="success"}` 上升）且与发布强相关
- 限流误杀（正常用户 429/403 激增）
- SSE 连接大面积断连/并发被拒（`SSE_CONCURRENCY_LIMIT_EXCEEDED` 激增）

## 1) 回滚优先级（KISS）

### 方案 A：配置开关（最快）

```bash
export RATE_LIMIT_ENABLED=false
export POLICY_GATE_ENABLED=false
```

重启服务后验证：

```bash
curl http://localhost:9999/api/v1/healthz
curl http://localhost:9999/api/v1/readyz
```

### 方案 B：JWT 宽松化（降低误杀）

```bash
export JWT_CLOCK_SKEW_SECONDS=300
```

> 说明：仅作为短期止血；恢复后需要回收该变更并补齐根因修复。

### 方案 C：代码回滚（最彻底）

使用 `git revert <sha>` 回滚到上一可用版本，然后重新构建并发布。

## 2) 回滚后必做验证

- 探活：`/api/v1/healthz`、`/api/v1/livez`、`/api/v1/readyz`
- 指标：`/api/v1/metrics` 可访问
- 关键链路：登录拿 JWT → 调用一个受保护接口（如 `/api/v1/base/userinfo`）

推荐使用脚本：

```bash
bash scripts/verification/quick_verify.sh
python scripts/verification/verify_gw_auth.py
```

## 3) 回滚后记录（最小）

- 发布版本/sha、回滚方案（A/B/C）
- 触发指标截图（或 PromQL）
- 典型请求的 `X-Request-Id`（用于后续对账排查）

