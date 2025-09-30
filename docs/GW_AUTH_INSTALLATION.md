# GW-Auth 网关改造 - 安装指南

**版本**: v1.0  
**更新时间**: 2025-09-30

## 📦 依赖安装

### 方式1: 使用 uv（推荐）

```bash
# 安装 prometheus_client
uv add prometheus_client

# 同步所有依赖
uv sync
```

### 方式2: 使用 pip

```bash
# 激活虚拟环境
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows

# 安装 prometheus_client
pip install prometheus_client

# 更新 requirements.txt
pip freeze > requirements.txt
```

## 🔧 配置更新

### 1. 环境变量配置

复制并编辑 `.env` 文件：

```bash
# 复制示例配置
cp .env.example .env

# 编辑配置（确保包含以下配置）
# 回滚预案配置
AUTH_FALLBACK_ENABLED=false
RATE_LIMIT_ENABLED=true
POLICY_GATE_ENABLED=true
```

### 2. 验证配置

```bash
# 检查配置是否正确加载
python -c "from app.settings.config import get_settings; print(get_settings().model_dump())"
```

## 🚀 启动服务

### 开发环境

```bash
# 直接运行
python run.py

# 或使用 make
make start
```

### 生产环境（Docker）

```bash
# 构建镜像
docker-compose build api

# 启动服务
docker-compose up -d api

# 查看日志
docker-compose logs -f api
```

## ✅ 验证安装

### 1. 健康检查

```bash
# 测试健康探针
curl http://localhost:9999/api/v1/healthz

# 预期输出:
# {"status":"ok","service":"GymBro API"}
```

### 2. Prometheus指标

```bash
# 测试指标端点
curl http://localhost:9999/api/v1/metrics

# 预期输出: Prometheus格式的指标数据
# 包含: auth_requests_total, jwt_validation_errors_total 等
```

### 3. 白名单验证

```bash
# 快速连续请求（测试免限流）
for i in {1..20}; do curl -s http://localhost:9999/api/v1/healthz | jq .status; done

# 预期: 所有请求都返回 "ok"，无 429 错误
```

### 4. 运行验证脚本

```bash
# 运行自动化验证
python scripts/verify_gw_auth.py

# 预期输出:
# 🚀 开始验证 GW-Auth 网关改造...
# ✅ 健康探针 /api/v1/healthz
# ✅ 健康探针 /api/v1/livez
# ✅ 健康探针 /api/v1/readyz
# ✅ Prometheus指标端点
# ✅ 白名单路径免限流
# 🎉 所有测试通过！
```

## 🔍 故障排查

### 问题1: ModuleNotFoundError: No module named 'prometheus_client'

**原因**: prometheus_client 未安装

**解决**:
```bash
pip install prometheus_client
# 或
uv add prometheus_client
```

### 问题2: 健康探针返回 404

**原因**: 路由未正确注册

**解决**:
```bash
# 检查路由注册
grep -r "health_router" app/api/v1/__init__.py

# 预期输出:
# from .health import router as health_router
# v1_router.include_router(health_router)
```

### 问题3: Prometheus指标为空

**原因**: 指标未被触发

**解决**:
```bash
# 先发送一些请求触发指标
curl http://localhost:9999/api/v1/healthz

# 再查看指标
curl http://localhost:9999/api/v1/metrics | grep auth_requests_total
```

### 问题4: 限流白名单不生效

**原因**: 路径不匹配

**解决**:
```python
# 检查 app/core/rate_limiter.py 中的白名单配置
WHITELIST_PATHS = {
    "/api/v1/healthz",  # 确保路径完全匹配
    "/api/v1/livez",
    "/api/v1/readyz",
    "/api/v1/metrics",
}
```

## 📊 Grafana 配置（可选）

### 1. 添加 Prometheus 数据源

在 Grafana 中添加 Prometheus 数据源：

- URL: `http://localhost:9090`（根据实际Prometheus地址调整）
- Access: Server (default)

### 2. 导入推荐面板

创建新的 Dashboard，添加以下 Panel：

**Panel 1: 认证成功率**
```promql
rate(auth_requests_total{status="200"}[5m]) / rate(auth_requests_total[5m]) * 100
```

**Panel 2: JWT验证错误率**
```promql
rate(jwt_validation_errors_total[5m])
```

**Panel 3: 限流阻止率**
```promql
rate(rate_limit_blocks_total[5m])
```

**Panel 4: JWKS缓存命中率**
```promql
rate(jwks_cache_hits_total{result="hit"}[5m]) / rate(jwks_cache_hits_total[5m]) * 100
```

## 🔄 回滚步骤

如需回滚，请参考：`docs/runbooks/GW_AUTH_ROLLBACK.md`

**快速回滚命令**:
```bash
# 禁用限流
export RATE_LIMIT_ENABLED=false

# 禁用策略门
export POLICY_GATE_ENABLED=false

# 重启服务
docker-compose restart api
```

## 📚 相关文档

- [完整交付报告](GW_AUTH_DELIVERY_REPORT.md)
- [回滚预案](runbooks/GW_AUTH_ROLLBACK.md)
- [JWT认证系统实现总结](jwt改造/archive/IMPLEMENTATION_SUMMARY.md)

---

**维护者**: GymBro DevOps Team  
**最后更新**: 2025-09-30

