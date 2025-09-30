# GW-Auth 网关回滚预案

**版本**: v1.0  
**更新时间**: 2025-09-30  
**目标**: 15-30分钟内完成回滚

## 🎯 回滚场景

当出现以下情况时，需要执行回滚：

1. **认证失败率 > 5%**：大量用户无法通过JWT验证
2. **限流误杀 > 10%**：正常用户被错误限流
3. **健康探针失败**：/healthz 返回非200状态
4. **Prometheus指标异常**：jwt_validation_errors_total 激增
5. **用户投诉激增**：客服反馈大量认证问题

## 📋 配置快照（当前版本）

### 环境变量配置
```bash
# JWT验证配置
JWT_CLOCK_SKEW_SECONDS=120
JWT_MAX_FUTURE_IAT_SECONDS=120
JWT_REQUIRE_NBF=false
JWT_ALLOWED_ALGORITHMS=ES256,RS256,HS256

# 匿名用户配置
ANON_ENABLED=true
RATE_LIMIT_ANONYMOUS_QPS=5
RATE_LIMIT_ANONYMOUS_DAILY=1000
SSE_MAX_CONCURRENT_PER_ANONYMOUS_USER=2

# 回滚开关（默认关闭）
AUTH_FALLBACK_ENABLED=false
RATE_LIMIT_ENABLED=true
POLICY_GATE_ENABLED=true
```

### 关键文件清单
- `app/api/v1/health.py` - 健康探针端点
- `app/api/v1/metrics.py` - Prometheus指标端点
- `app/core/rate_limiter.py` - 限流中间件（含白名单）
- `app/core/metrics.py` - 指标收集器
- `app/settings/config.py` - 配置管理

## 🚨 快速回滚步骤（15分钟）

### 方案1: 配置开关回滚（推荐）

**适用场景**: 限流或策略门导致的问题

```bash
# 1. 修改环境变量（5分钟）
export RATE_LIMIT_ENABLED=false  # 禁用限流
export POLICY_GATE_ENABLED=false # 禁用策略门
export ANON_ENABLED=false        # 禁用匿名用户支持

# 2. 重启服务（5分钟）
# 方式A: Docker
docker-compose restart api

# 方式B: 直接运行
pkill -f "python run.py"
python run.py &

# 3. 验证回滚（5分钟）
curl http://localhost:9999/api/v1/healthz
# 预期: {"status": "ok", "service": "GymBro API"}

curl http://localhost:9999/api/v1/metrics | grep auth_requests_total
# 预期: 指标正常输出
```

### 方案2: JWT验证宽松化（20分钟）

**适用场景**: JWT验证过严导致的问题

```bash
# 1. 放宽JWT验证参数（10分钟）
export JWT_CLOCK_SKEW_SECONDS=300  # 从120s增加到300s
export JWT_REQUIRE_NBF=false       # 不强制要求nbf声明

# 2. 重启服务（5分钟）
docker-compose restart api

# 3. 验证回滚（5分钟）
# 使用测试JWT验证
curl -H "Authorization: Bearer <test_jwt>" \
  http://localhost:9999/api/v1/ai/messages
```

### 方案3: 代码回滚（30分钟）

**适用场景**: 配置开关无法解决的严重问题

```bash
# 1. Git回滚到上一个稳定版本（10分钟）
git log --oneline -10  # 查看最近10次提交
git revert <commit_hash>  # 回滚到指定提交

# 2. 重新构建镜像（15分钟）
docker-compose build api

# 3. 重启服务（5分钟）
docker-compose up -d api

# 4. 验证回滚
curl http://localhost:9999/api/v1/healthz
```

## 📊 回滚验证清单

执行回滚后，必须验证以下项目：

- [ ] **健康探针**: `curl /api/v1/healthz` 返回200
- [ ] **认证成功率**: 检查日志中JWT验证成功率 > 95%
- [ ] **限流正常**: 正常用户不被误杀
- [ ] **匿名用户**: 匿名用户可以正常访问（如果ANON_ENABLED=true）
- [ ] **Prometheus指标**: `/api/v1/metrics` 正常输出
- [ ] **用户反馈**: 客服确认用户问题解决

## 🔍 故障排查

### 问题1: 健康探针返回404

**原因**: 路由未正确注册

**解决**:
```bash
# 检查路由注册
grep -r "health_router" app/api/v1/__init__.py
# 预期输出: from .health import router as health_router
```

### 问题2: Prometheus指标为空

**原因**: prometheus_client未安装

**解决**:
```bash
pip install prometheus_client
# 或
uv add prometheus_client
```

### 问题3: 限流白名单不生效

**原因**: 路径不匹配

**解决**:
```python
# 检查 app/core/rate_limiter.py
WHITELIST_PATHS = {
    "/api/v1/healthz",  # 确保路径完全匹配
    "/api/v1/livez",
    "/api/v1/readyz",
    "/api/v1/metrics",
}
```

## 📞 紧急联系

- **技术负责人**: [待填写]
- **运维值班**: [待填写]
- **Slack频道**: #incident-response

## 📝 回滚后操作

1. **记录回滚原因**: 在Incident Report中详细记录
2. **分析根因**: 使用Prometheus指标和日志分析
3. **修复问题**: 在测试环境复现并修复
4. **重新部署**: 修复后重新部署到生产环境

## 🔄 恢复正常流程

回滚后，如需恢复正常配置：

```bash
# 1. 恢复环境变量
export RATE_LIMIT_ENABLED=true
export POLICY_GATE_ENABLED=true
export ANON_ENABLED=true

# 2. 重启服务
docker-compose restart api

# 3. 灰度验证
# 先在staging环境验证，再逐步放量到生产环境
```

## 📚 相关文档

- [JWT认证系统实现总结](../jwt改造/archive/IMPLEMENTATION_SUMMARY.md)
- [匿名用户功能实现报告](../jwt改造/ANON_IMPLEMENTATION_FINAL_REPORT.md)
- [K1-K5基础设施文档](../jwt改造/)

---

**最后更新**: 2025-09-30  
**维护者**: GymBro DevOps Team

