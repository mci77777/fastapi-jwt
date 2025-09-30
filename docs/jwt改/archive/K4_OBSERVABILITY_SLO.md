# K4 观测与告警基线 - SLO/SLI 指标体系

## 📊 核心指标四件套

### 1. 首字延迟 P95 (Time to First Byte)
**定义**: 从请求发起到收到第一个字节的时间
**SLI**: P95 < 2000ms
**SLO**: 99.5% 的请求在2秒内返回首字节

```sql
-- 日志查询示例 (假设使用 Grafana + Loki)
{app="gymbro-api"} 
| json 
| line_format "{{.timestamp}} {{.level}} {{.message}}"
| regexp "请求处理完成.*duration=(?P<duration>[0-9.]+)ms"
| unwrap duration 
| quantile_over_time(0.95, [5m])
```

### 2. 请求成功率
**定义**: 非5xx状态码请求占总请求的比例
**SLI**: 成功率 > 99.0%
**SLO**: 99.5% 的时间窗口内成功率不低于99%

```sql
-- 成功率计算
sum(rate({app="gymbro-api"} |~ "HTTP.*[2-4][0-9][0-9]"[5m])) 
/ 
sum(rate({app="gymbro-api"} |~ "HTTP.*[0-9][0-9][0-9]"[5m])) * 100
```

### 3. 401→刷新成功率
**定义**: 401错误后JWT刷新成功的比例
**SLI**: 刷新成功率 > 95%
**SLO**: 95% 的401错误能在30秒内通过刷新恢复

```sql
-- JWT刷新成功率
sum(rate({app="gymbro-api"} |~ "JWT刷新成功"[5m]))
/
sum(rate({app="gymbro-api"} |~ "JWT.*401"[5m])) * 100
```

### 4. 消息完成时长
**定义**: AI消息从创建到完成的端到端时长
**SLI**: P95 < 30000ms
**SLO**: 95% 的消息在30秒内完成

```sql
-- 消息完成时长
{app="gymbro-api"} 
| json 
| regexp "AI会话处理.*message_id=(?P<msg_id>[a-f0-9]+).*duration=(?P<duration>[0-9.]+)ms"
| unwrap duration
| quantile_over_time(0.95, [5m])
```

## 🎛️ 面板布局设计

### App 面板 (应用层监控)
```yaml
dashboard: "GymBro API - Application Metrics"
panels:
  - title: "请求概览"
    metrics:
      - 总QPS (requests/sec)
      - 成功率 (%)
      - P95延迟 (ms)
      - 错误率分布 (4xx/5xx)
    
  - title: "业务指标"
    metrics:
      - 活跃用户数
      - 消息创建率
      - SSE连接数
      - AI完成率
    
  - title: "限流状态"
    metrics:
      - 限流命中率 (%)
      - 冷静期触发次数
      - SSE拒绝率 (%)
      - 可疑UA检测数
    
  - title: "认证状态"
    metrics:
      - JWT验证成功率 (%)
      - 401错误率 (%)
      - 刷新成功率 (%)
      - JWKS缓存命中率 (%)

dimensions:
  - provider: [openai, anthropic, local]
  - channel: [web, mobile, api]
  - build_type: [dev, staging, prod]
  - user_type: [authenticated, anonymous]
```

### 网关面板 (基础设施监控)
```yaml
dashboard: "GymBro API - Infrastructure Metrics"
panels:
  - title: "系统资源"
    metrics:
      - CPU使用率 (%)
      - 内存使用率 (%)
      - 磁盘IO (MB/s)
      - 网络IO (MB/s)
    
  - title: "数据库连接"
    metrics:
      - Supabase连接数
      - 查询延迟 P95 (ms)
      - 连接池使用率 (%)
      - 慢查询数量
    
  - title: "外部依赖"
    metrics:
      - AI API延迟 (ms)
      - JWKS获取延迟 (ms)
      - 第三方服务可用性 (%)
      - 网络错误率 (%)
    
  - title: "容器状态"
    metrics:
      - 容器重启次数
      - 健康检查状态
      - 日志错误率 (%)
      - 内存泄漏检测
```

## 🚨 告警门槛与规则

### 关键告警 (P0 - 立即响应)
```yaml
alerts:
  - name: "API服务不可用"
    condition: "成功率 < 95% for 2分钟"
    severity: "critical"
    notification: ["pagerduty", "slack-oncall"]
    
  - name: "首字延迟过高"
    condition: "P95延迟 > 5000ms for 5分钟"
    severity: "critical"
    notification: ["pagerduty", "slack-oncall"]
    
  - name: "5xx错误激增"
    condition: "5xx错误率 > 5% for 3分钟"
    severity: "critical"
    notification: ["pagerduty", "slack-oncall"]
```

### 重要告警 (P1 - 工作时间响应)
```yaml
alerts:
  - name: "JWT刷新成功率低"
    condition: "401刷新成功率 < 95% for 10分钟"
    severity: "warning"
    notification: ["slack-dev"]
    
  - name: "消息完成时长过长"
    condition: "消息P95完成时长 > 45000ms for 10分钟"
    severity: "warning"
    notification: ["slack-dev"]
    
  - name: "限流命中率异常"
    condition: "限流命中率 > 20% for 15分钟"
    severity: "warning"
    notification: ["slack-dev"]
```

### 信息告警 (P2 - 日常监控)
```yaml
alerts:
  - name: "SSE连接数异常"
    condition: "活跃SSE连接 > 1000 for 30分钟"
    severity: "info"
    notification: ["slack-monitoring"]
    
  - name: "可疑流量检测"
    condition: "可疑UA检测数 > 100/hour"
    severity: "info"
    notification: ["slack-security"]
```

## 📋 值班流程与联系人

### 值班轮换
```yaml
oncall_schedule:
  primary: 
    - week1: "张三 <zhang@company.com>"
    - week2: "李四 <li@company.com>"
    - week3: "王五 <wang@company.com>"
  
  secondary:
    - "技术经理 <manager@company.com>"
    - "架构师 <architect@company.com>"
  
  escalation:
    - 15分钟无响应 → secondary
    - 30分钟无响应 → CTO
```

### 通知渠道
```yaml
notification_channels:
  pagerduty:
    integration_key: "xxx"
    escalation_policy: "gymbro-api-critical"
  
  slack:
    oncall: "#gymbro-oncall"
    dev: "#gymbro-dev"
    monitoring: "#gymbro-monitoring"
    security: "#gymbro-security"
  
  email:
    critical: ["oncall@company.com"]
    warning: ["dev-team@company.com"]
```

## 🔍 日志萃取映射

### 结构化日志格式
```json
{
  "timestamp": "2025-09-29T13:49:03.139Z",
  "level": "INFO",
  "logger": "app.api.v1.messages",
  "message": "请求处理完成",
  "trace_id": "abc123def456",
  "user_id": "user_789",
  "request_id": "req_456",
  "method": "POST",
  "path": "/api/v1/messages",
  "status_code": 200,
  "duration_ms": 1250.5,
  "provider": "openai",
  "channel": "web",
  "build_type": "prod",
  "client_ip": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "metadata": {
    "conversation_id": "conv_123",
    "message_id": "msg_456",
    "ai_model": "gpt-4o-mini",
    "tokens_used": 150
  }
}
```

### Grafana查询示例
```promql
# QPS计算
sum(rate(http_requests_total[5m])) by (status_code)

# 延迟分布
histogram_quantile(0.95, 
  sum(rate(http_request_duration_seconds_bucket[5m])) by (le)
)

# 错误率
sum(rate(http_requests_total{status_code=~"5.."}[5m])) 
/ 
sum(rate(http_requests_total[5m])) * 100

# 按维度分组
sum(rate(http_requests_total[5m])) by (provider, channel, build_type)
```

## 📈 基线性能指标

### 正常运行基线
```yaml
baseline_metrics:
  qps: 50-200 req/s
  p95_latency: 800-1500ms
  success_rate: 99.2-99.8%
  memory_usage: 200-500MB
  cpu_usage: 10-30%
  
  ai_completion:
    p95_duration: 15000-25000ms
    success_rate: 98-99.5%
    
  jwt_auth:
    success_rate: 99.5-99.9%
    refresh_success_rate: 96-99%
    
  rate_limiting:
    hit_rate: 0.1-2%
    cooldown_triggers: 0-5/hour
```

### 容量规划
```yaml
capacity_planning:
  current_limits:
    max_qps: 500
    max_concurrent_users: 1000
    max_sse_connections: 2000
    
  scaling_triggers:
    cpu_threshold: 70%
    memory_threshold: 80%
    qps_threshold: 400
    
  growth_projections:
    monthly_user_growth: 20%
    peak_traffic_multiplier: 3x
    holiday_surge_factor: 5x
```
