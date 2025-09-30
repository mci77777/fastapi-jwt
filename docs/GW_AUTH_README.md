# GW-Auth 网关最小改造

> **版本**: v1.0  
> **完成时间**: 2025-09-30  
> **目标**: 确保 App 首接入稳定、探活明确、可观测可回滚

## 📚 快速导航

- [安装指南](GW_AUTH_INSTALLATION.md) - 如何安装和配置
- [交付报告](GW_AUTH_DELIVERY_REPORT.md) - 完整的功能说明
- [回滚预案](runbooks/GW_AUTH_ROLLBACK.md) - 紧急回滚步骤

## 🎯 核心功能

### 1. 健康探针端点

为K8s和负载均衡器提供探活端点：

```bash
# 基础健康检查
curl http://localhost:9999/api/v1/healthz
# 响应: {"status": "ok", "service": "GymBro API"}

# 存活探针（K8s liveness）
curl http://localhost:9999/api/v1/livez

# 就绪探针（K8s readiness）
curl http://localhost:9999/api/v1/readyz
```

### 2. Prometheus指标导出

提供6类核心指标供Grafana监控：

```bash
# 获取所有指标
curl http://localhost:9999/api/v1/metrics
```

**指标列表**:
- `auth_requests_total{status, user_type}` - 认证请求总数
- `auth_request_duration_seconds{endpoint}` - 认证请求持续时间
- `jwt_validation_errors_total{code}` - JWT验证错误总数
- `jwks_cache_hits_total{result}` - JWKS缓存命中总数
- `active_connections` - 活跃连接数
- `rate_limit_blocks_total{reason, user_type}` - 限流阻止总数

### 3. 公共路由白名单

以下路径免限流，确保监控和文档可用：

- `/api/v1/healthz`, `/api/v1/livez`, `/api/v1/readyz` - 健康探针
- `/api/v1/metrics` - Prometheus指标
- `/docs`, `/redoc`, `/openapi.json` - API文档

### 4. 回滚预案

支持3种回滚方案，可在15-30分钟内完成：

```bash
# 方案1: 配置开关回滚（15分钟）
export RATE_LIMIT_ENABLED=false
export POLICY_GATE_ENABLED=false
docker-compose restart api

# 方案2: JWT验证宽松化（20分钟）
export JWT_CLOCK_SKEW_SECONDS=300
docker-compose restart api

# 方案3: 代码回滚（30分钟）
git revert <commit_hash>
docker-compose build api
docker-compose up -d api
```

## 🚀 快速开始

### 1. 安装依赖

```bash
# 使用 uv（推荐）
uv add prometheus_client

# 或使用 pip
pip install prometheus_client
```

### 2. 配置环境变量

```bash
# 复制示例配置
cp .env.example .env

# 确保包含以下配置
AUTH_FALLBACK_ENABLED=false
RATE_LIMIT_ENABLED=true
POLICY_GATE_ENABLED=true
```

### 3. 启动服务

```bash
# 开发环境
python run.py

# 生产环境（Docker）
docker-compose up -d api
```

### 4. 验证安装

```bash
# Linux/Mac
bash scripts/quick_verify.sh

# Windows (PowerShell)
.\scripts\quick_verify.ps1

# Python验证脚本
python scripts/verify_gw_auth.py
```

## 📊 监控配置

### Grafana面板推荐查询

**认证成功率**:
```promql
rate(auth_requests_total{status="200"}[5m]) / rate(auth_requests_total[5m]) * 100
```

**JWT验证错误率**:
```promql
rate(jwt_validation_errors_total[5m])
```

**限流阻止率**:
```promql
rate(rate_limit_blocks_total[5m])
```

**JWKS缓存命中率**:
```promql
rate(jwks_cache_hits_total{result="hit"}[5m]) / rate(jwks_cache_hits_total[5m]) * 100
```

### 告警规则

**认证失败率过高**:
```yaml
alert: HighAuthFailureRate
expr: rate(auth_requests_total{status!="200"}[5m]) > 0.05
for: 5m
annotations:
  summary: "认证失败率超过5%"
```

**限流误杀过高**:
```yaml
alert: HighRateLimitBlocks
expr: rate(rate_limit_blocks_total[5m]) > 0.1
for: 5m
annotations:
  summary: "限流阻止率超过10%"
```

## 🔧 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `AUTH_FALLBACK_ENABLED` | `false` | 认证回滚开关 |
| `RATE_LIMIT_ENABLED` | `true` | 限流开关 |
| `POLICY_GATE_ENABLED` | `true` | 策略门开关 |
| `JWT_CLOCK_SKEW_SECONDS` | `120` | JWT时钟偏移容忍度 |
| `RATE_LIMIT_ANONYMOUS_QPS` | `5` | 匿名用户QPS限制 |
| `SSE_MAX_CONCURRENT_PER_ANONYMOUS_USER` | `2` | 匿名用户并发流限制 |

### 白名单路径配置

在 `app/core/rate_limiter.py` 中修改：

```python
WHITELIST_PATHS = {
    "/api/v1/healthz",
    "/api/v1/livez",
    "/api/v1/readyz",
    "/api/v1/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
}
```

## 📁 文件结构

```
.
├── app/
│   ├── api/v1/
│   │   ├── health.py          # 健康探针端点（新增）
│   │   ├── metrics.py         # Prometheus指标端点（新增）
│   │   └── __init__.py        # 路由注册（修改）
│   ├── core/
│   │   ├── rate_limiter.py    # 限流中间件（修改：添加白名单）
│   │   └── metrics.py         # 指标收集器（修改：添加Prometheus指标）
│   └── settings/
│       └── config.py          # 配置管理（修改：添加回滚开关）
├── docs/
│   ├── GW_AUTH_README.md      # 本文档
│   ├── GW_AUTH_INSTALLATION.md # 安装指南
│   ├── GW_AUTH_DELIVERY_REPORT.md # 交付报告
│   └── runbooks/
│       └── GW_AUTH_ROLLBACK.md # 回滚预案
├── scripts/
│   ├── verify_gw_auth.py      # Python验证脚本
│   ├── quick_verify.sh        # Bash验证脚本
│   └── quick_verify.ps1       # PowerShell验证脚本
└── .env.example               # 环境变量示例（修改）
```

## 🔍 故障排查

### 问题1: 健康探针返回404

**原因**: 路由未正确注册

**解决**:
```bash
grep -r "health_router" app/api/v1/__init__.py
# 应该看到: from .health import router as health_router
```

### 问题2: Prometheus指标为空

**原因**: prometheus_client未安装

**解决**:
```bash
pip install prometheus_client
```

### 问题3: 限流白名单不生效

**原因**: 路径不匹配

**解决**: 检查 `app/core/rate_limiter.py` 中的 `WHITELIST_PATHS` 配置

## 📞 支持

- **技术文档**: [docs/](.)
- **问题反馈**: GitHub Issues
- **紧急联系**: 参考 [回滚预案](runbooks/GW_AUTH_ROLLBACK.md)

## 📝 更新日志

### v1.0 (2025-09-30)

- ✅ 新增健康探针端点（/healthz, /livez, /readyz）
- ✅ 新增Prometheus指标导出（/metrics）
- ✅ 新增公共路由白名单（免限流）
- ✅ 新增回滚预案配置开关
- ✅ 新增完整的回滚文档和验证脚本

## 🎯 设计原则

- **KISS**: 保持简单，健康探针只返回200 OK
- **YAGNI**: 不过度设计，不实现暂时不需要的功能
- **DRY**: 复用现有组件，避免重复代码

## 📚 相关文档

- [JWT认证系统实现总结](jwt改造/archive/IMPLEMENTATION_SUMMARY.md)
- [匿名用户功能实现报告](jwt改造/ANON_IMPLEMENTATION_FINAL_REPORT.md)
- [K1-K5基础设施文档](jwt改造/)

---

**维护者**: GymBro DevOps Team  
**最后更新**: 2025-09-30

