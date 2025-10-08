# Runbook 汇总

整合原 `e2e-anon.md` 与 `GW_AUTH_ROLLBACK.md`，集中保留告警判定、排查路径与回滚步骤。

## 🌙 E2E-ANON Nightly
- 指标：`e2e_anon_success`、`e2e_anon_latency_ms`、`sse_conns_inflight`、`auth_jwks_refresh_err_total`。
- 告警：夜跑连续失败 ≥ 2 次、SSE 并发超阈、JWT 刷新错误激增。
- 排查：基于 Actions 日志获取 `X-Trace-Id` → 追踪 API/网关/数据库 → 校正策略或限流阈值 → 复跑工作流。

## 🔁 GW-Auth 回滚
- 触发：认证失败率 >5%、正常用户误杀 >10%、`/healthz` 异常、Prometheus 指标异常或用户投诉激增。
- 快照：保留 JWT 校验开关、匿名限流、SSE 并发、回滚 Feature Flag 等环境变量。
- 操作：切换回旧版本配置→验证健康探针→观察告警回落→记录根因与补救动作。