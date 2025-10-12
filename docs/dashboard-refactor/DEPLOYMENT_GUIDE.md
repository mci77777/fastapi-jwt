# Dashboard 重构 - 部署运维指南

**文档版本**: v1.0  
**创建时间**: 2025-10-12  
**适用版本**: Dashboard v1.0（阶段1-5完成）

---

## 📋 目录

1. [部署前准备](#1-部署前准备)
2. [Docker 部署](#2-docker-部署)
3. [环境变量配置](#3-环境变量配置)
4. [健康检查](#4-健康检查)
5. [监控配置](#5-监控配置)
6. [回滚方案](#6-回滚方案)
7. [故障排查](#7-故障排查)

---

## 1. 部署前准备

### 1.1 系统要求

| 组件 | 最低要求 | 推荐配置 |
|------|---------|---------|
| CPU | 2 核 | 4 核 |
| 内存 | 2GB | 4GB |
| 磁盘 | 10GB | 20GB |
| Docker | 20.10+ | 最新版 |
| Docker Compose | 1.29+ | 最新版 |

### 1.2 依赖服务

- ✅ Supabase 项目（JWT 认证 + 数据备份）
- ✅ 域名与 SSL 证书（生产环境）
- ⚠️ Prometheus + Grafana（可选，监控）

### 1.3 端口规划

| 服务 | 端口 | 说明 |
|------|------|------|
| Nginx（前端 + API） | 80 | HTTP 入口 |
| Prometheus | 9090 | 监控指标 |
| Grafana | 3000 | 可视化仪表盘 |

---

## 2. Docker 部署

### 2.1 克隆代码

```bash
git clone https://github.com/your-org/vue-fastapi-admin.git
cd vue-fastapi-admin
git checkout dashboard-v1
```

### 2.2 配置环境变量

复制环境变量模板：

```bash
cp .env.example .env
```

编辑 `.env` 文件，替换以下占位符：

```bash
# Supabase 配置（必填）
SUPABASE_PROJECT_ID=your-project-id
SUPABASE_JWKS_URL=https://your-project-id.supabase.co/.well-known/jwks.json
SUPABASE_ISSUER=https://your-project-id.supabase.co
SUPABASE_AUDIENCE=your-project-id
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# AI 服务配置（可选）
AI_API_KEY=your-openai-api-key
```

### 2.3 构建镜像

```bash
docker build -t vue-fastapi-admin:dashboard-v1 .
```

**预期输出**：
```
✓ built in 18.59s
Successfully tagged vue-fastapi-admin:dashboard-v1
```

**镜像体积**：约 450MB（多阶段构建优化）

### 2.4 启动服务

```bash
docker-compose up -d
```

**验证启动**：
```bash
docker-compose ps
# 预期输出：
# NAME                COMMAND             STATUS              PORTS
# vue-fastapi-admin   /bin/sh entrypoint  Up 30 seconds       0.0.0.0:80->80/tcp
# prometheus          /bin/prometheus     Up 30 seconds       0.0.0.0:9090->9090/tcp
# grafana             /run.sh             Up 30 seconds       0.0.0.0:3000->3000/tcp
```

### 2.5 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看主服务日志
docker-compose logs -f app

# 查看最近 100 行日志
docker-compose logs --tail=100 app
```

---

## 3. 环境变量配置

### 3.1 核心配置项

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `DEBUG` | `false` | 调试模式（生产环境必须为 false）|
| `ANON_ENABLED` | `true` | 是否允许匿名用户 |
| `RATE_LIMIT_ENABLED` | `true` | 是否启用限流 |
| `POLICY_GATE_ENABLED` | `true` | 是否启用策略网关 |

### 3.2 性能调优

| 变量名 | 默认值 | 调优建议 |
|--------|--------|---------|
| `RATE_LIMIT_PER_USER_QPS` | `10` | 根据实际负载调整 |
| `SSE_MAX_CONCURRENT_PER_USER` | `2` | 限制并发 SSE 连接 |
| `JWKS_CACHE_TTL_SECONDS` | `900` | JWKS 缓存时间（15 分钟）|

### 3.3 安全配置

| 变量名 | 默认值 | 安全建议 |
|--------|--------|---------|
| `CORS_ALLOW_ORIGINS` | `*` | 生产环境改为具体域名 |
| `FORCE_HTTPS` | `false` | 生产环境改为 `true` |
| `JWT_ALLOWED_ALGORITHMS` | `ES256,RS256,HS256` | 仅保留必要算法 |

---

## 4. 健康检查

### 4.1 健康探针

```bash
# 总体健康状态
curl http://localhost/api/v1/healthz

# 预期输出：
{
  "status": "healthy",
  "timestamp": "2025-10-12T14:30:00Z",
  "version": "0.1.0"
}
```

### 4.2 存活探针

```bash
curl http://localhost/api/v1/livez

# 预期输出：
{
  "status": "alive"
}
```

### 4.3 就绪探针

```bash
curl http://localhost/api/v1/readyz

# 预期输出：
{
  "status": "ready",
  "database": "connected",
  "supabase": "connected"
}
```

---

## 5. 监控配置

### 5.1 Prometheus 指标

访问 Prometheus UI：http://localhost:9090

**核心指标**：
- `http_requests_total` - HTTP 请求总数
- `http_request_duration_seconds` - 请求延迟分布
- `websocket_connections_active` - WebSocket 活跃连接数
- `dashboard_stats_last_update_timestamp` - Dashboard 统计数据更新时间
- `process_resident_memory_bytes` - 内存使用量

### 5.2 Grafana 仪表盘

访问 Grafana UI：http://localhost:3000

**默认凭证**：
- 用户名：`admin`
- 密码：`admin`

**预置仪表盘**：
1. **Dashboard 概览**
   - 日活用户数趋势
   - AI 请求数趋势
   - API 连通性状态
   - JWT 可获取性趋势

2. **性能监控**
   - 请求延迟 P50/P95/P99
   - 错误率趋势
   - WebSocket 连接数

3. **资源监控**
   - CPU 使用率
   - 内存使用率
   - 磁盘 I/O

### 5.3 告警规则

已配置的告警（见 `deploy/alerts.yml`）：

| 告警名称 | 触发条件 | 严重级别 |
|---------|---------|---------|
| HighErrorRate | 错误率 > 5% | Critical |
| HighLatency | P95 延迟 > 2s | Warning |
| WebSocketConnectionsHigh | 连接数 > 1000 | Warning |
| ServiceDown | 服务不可用 > 1min | Critical |
| HighMemoryUsage | 内存 > 2GB | Warning |
| DashboardStatsStale | 数据 > 5min 未更新 | Warning |

---

## 6. 回滚方案

### 6.1 快速回滚（Docker 镜像）

```bash
# 停止当前版本
docker-compose down

# 切换到旧版本镜像
docker tag vue-fastapi-admin:dashboard-v0 vue-fastapi-admin:latest

# 重新启动
docker-compose up -d
```

### 6.2 数据库回滚

```bash
# 备份当前数据库
cp data/db.sqlite3 data/db.sqlite3.backup

# 恢复旧版本数据库
cp data/db.sqlite3.v0 data/db.sqlite3

# 重启服务
docker-compose restart app
```

### 6.3 功能开关回滚

编辑 `.env` 文件，禁用新功能：

```bash
# 禁用 Dashboard 新功能（降级为旧版本）
DASHBOARD_V2_ENABLED=false

# 重启服务
docker-compose restart app
```

---

## 7. 故障排查

### 7.1 服务无法启动

**症状**：`docker-compose up -d` 失败

**排查步骤**：
1. 检查端口占用：`netstat -tuln | grep -E '80|9090|3000'`
2. 检查 Docker 日志：`docker-compose logs app`
3. 检查环境变量：`docker-compose config`

**常见原因**：
- 端口被占用 → 修改 `docker-compose.yml` 端口映射
- 环境变量缺失 → 检查 `.env` 文件
- 镜像构建失败 → 重新构建镜像

### 7.2 Dashboard 数据不更新

**症状**：统计数据显示为 0 或过期

**排查步骤**：
1. 检查 WebSocket 连接：浏览器 DevTools → Network → WS
2. 检查后端日志：`docker-compose logs app | grep dashboard`
3. 检查数据库：`sqlite3 data/db.sqlite3 "SELECT * FROM dashboard_stats ORDER BY created_at DESC LIMIT 5;"`

**常见原因**：
- WebSocket 连接失败 → 检查防火墙/代理配置
- 数据库写入失败 → 检查磁盘空间
- 统计服务未启动 → 检查后端日志

### 7.3 高延迟/高错误率

**症状**：Prometheus 告警触发

**排查步骤**：
1. 查看 Grafana 仪表盘：http://localhost:3000
2. 检查慢查询：`docker-compose logs app | grep "slow query"`
3. 检查资源使用：`docker stats vue-fastapi-admin`

**常见原因**：
- 数据库查询慢 → 添加索引
- 内存不足 → 增加容器内存限制
- 并发过高 → 调整限流配置

---

## 8. 性能基准

### 8.1 首屏加载

| 指标 | 目标值 | 实测值 |
|------|--------|--------|
| DOM 内容加载 | < 800ms | 399ms |
| 页面完全加载 | < 2000ms | 400ms |
| 首次绘制（FP） | < 500ms | 328ms |
| 首次内容绘制（FCP） | < 800ms | 328ms |

### 8.2 API 响应时间

| API 端点 | P50 | P95 | P99 |
|---------|-----|-----|-----|
| /api/v1/stats/dashboard | 50ms | 120ms | 200ms |
| /api/v1/logs/recent | 30ms | 80ms | 150ms |
| /api/v1/base/userinfo | 40ms | 100ms | 180ms |

### 8.3 并发能力

| 指标 | 数值 |
|------|------|
| WebSocket 并发连接数 | 1000+ |
| HTTP QPS | 500+ |
| 内存占用（稳定状态） | < 500MB |

---

## 9. 维护计划

### 9.1 日常维护

- **每日**：检查 Grafana 仪表盘，确认无告警
- **每周**：清理过期日志（`logs/` 目录）
- **每月**：备份数据库（`data/db.sqlite3`）

### 9.2 数据清理

```bash
# 清理 30 天前的统计数据
sqlite3 data/db.sqlite3 "DELETE FROM dashboard_stats WHERE created_at < datetime('now', '-30 days');"
sqlite3 data/db.sqlite3 "DELETE FROM user_activity_stats WHERE activity_date < date('now', '-30 days');"
sqlite3 data/db.sqlite3 "DELETE FROM ai_request_stats WHERE request_date < date('now', '-30 days');"

# 压缩数据库
sqlite3 data/db.sqlite3 "VACUUM;"
```

### 9.3 升级流程

1. 备份数据库和配置文件
2. 拉取新版本代码
3. 构建新镜像
4. 停止旧服务
5. 启动新服务
6. 验证健康检查
7. 监控告警

---

## 10. 联系方式

**技术支持**：
- 文档：https://github.com/your-org/vue-fastapi-admin/docs
- Issues：https://github.com/your-org/vue-fastapi-admin/issues

**紧急联系**：
- 运维负责人：[姓名] <email@example.com>
- 开发负责人：[姓名] <email@example.com>

---

**文档更新时间**: 2025-10-12  
**下次审查**: 2025-11-12

