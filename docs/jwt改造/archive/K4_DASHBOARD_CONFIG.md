# K4 仪表盘与告警配置草案

## 🎛️ Grafana 仪表盘配置

### 应用层仪表盘 (gymbro-api-app.json)
```json
{
  "dashboard": {
    "title": "GymBro API - Application Metrics",
    "tags": ["gymbro", "api", "application"],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s",
    "panels": [
      {
        "title": "请求概览",
        "type": "stat",
        "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
        "targets": [
          {
            "expr": "sum(rate(http_requests_total[5m]))",
            "legendFormat": "QPS"
          },
          {
            "expr": "sum(rate(http_requests_total{status_code!~\"5..\"}[5m])) / sum(rate(http_requests_total[5m])) * 100",
            "legendFormat": "成功率 (%)"
          },
          {
            "expr": "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) * 1000",
            "legendFormat": "P95延迟 (ms)"
          }
        ]
      },
      {
        "title": "业务指标",
        "type": "graph",
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
        "targets": [
          {
            "expr": "count(count by (user_id) (rate(http_requests_total{path=~\"/api/v1/messages.*\"}[5m])))",
            "legendFormat": "活跃用户数"
          },
          {
            "expr": "sum(rate(http_requests_total{path=\"/api/v1/messages\", method=\"POST\"}[5m]))",
            "legendFormat": "消息创建率"
          },
          {
            "expr": "gymbro_sse_active_connections",
            "legendFormat": "SSE连接数"
          }
        ]
      },
      {
        "title": "限流状态",
        "type": "singlestat",
        "gridPos": {"h": 4, "w": 6, "x": 0, "y": 8},
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{status_code=\"429\"}[5m])) / sum(rate(http_requests_total[5m])) * 100",
            "legendFormat": "限流命中率 (%)"
          }
        ],
        "thresholds": "10,20",
        "colorBackground": true
      },
      {
        "title": "认证状态",
        "type": "singlestat",
        "gridPos": {"h": 4, "w": 6, "x": 6, "y": 8},
        "targets": [
          {
            "expr": "sum(rate(http_requests_total{status_code=\"401\"}[5m])) / sum(rate(http_requests_total[5m])) * 100",
            "legendFormat": "401错误率 (%)"
          }
        ],
        "thresholds": "1,5",
        "colorBackground": true
      }
    ]
  }
}
```

### 基础设施仪表盘 (gymbro-api-infra.json)
```json
{
  "dashboard": {
    "title": "GymBro API - Infrastructure Metrics",
    "tags": ["gymbro", "api", "infrastructure"],
    "panels": [
      {
        "title": "系统资源",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(process_cpu_seconds_total[5m]) * 100",
            "legendFormat": "CPU使用率 (%)"
          },
          {
            "expr": "process_resident_memory_bytes / 1024 / 1024",
            "legendFormat": "内存使用 (MB)"
          }
        ]
      },
      {
        "title": "外部依赖延迟",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, sum(rate(external_request_duration_seconds_bucket{service=\"openai\"}[5m])) by (le)) * 1000",
            "legendFormat": "OpenAI API P95 (ms)"
          },
          {
            "expr": "histogram_quantile(0.95, sum(rate(external_request_duration_seconds_bucket{service=\"supabase\"}[5m])) by (le)) * 1000",
            "legendFormat": "Supabase P95 (ms)"
          }
        ]
      }
    ]
  }
}
```

## 🚨 Prometheus 告警规则

### 关键告警规则 (alerts-critical.yml)
```yaml
groups:
  - name: gymbro-api-critical
    rules:
      - alert: APIServiceDown
        expr: up{job="gymbro-api"} == 0
        for: 1m
        labels:
          severity: critical
          service: gymbro-api
        annotations:
          summary: "GymBro API服务不可用"
          description: "API服务已下线超过1分钟"
          runbook_url: "https://wiki.company.com/runbooks/api-down"

      - alert: HighErrorRate
        expr: sum(rate(http_requests_total{status_code=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100 > 5
        for: 3m
        labels:
          severity: critical
          service: gymbro-api
        annotations:
          summary: "5xx错误率过高"
          description: "5xx错误率 {{ $value }}% 超过阈值5%"
          runbook_url: "https://wiki.company.com/runbooks/high-error-rate"

      - alert: HighLatency
        expr: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) * 1000 > 5000
        for: 5m
        labels:
          severity: critical
          service: gymbro-api
        annotations:
          summary: "API延迟过高"
          description: "P95延迟 {{ $value }}ms 超过阈值5000ms"
          runbook_url: "https://wiki.company.com/runbooks/high-latency"

      - alert: LowSuccessRate
        expr: sum(rate(http_requests_total{status_code!~"5.."}[5m])) / sum(rate(http_requests_total[5m])) * 100 < 95
        for: 2m
        labels:
          severity: critical
          service: gymbro-api
        annotations:
          summary: "API成功率过低"
          description: "成功率 {{ $value }}% 低于阈值95%"
          runbook_url: "https://wiki.company.com/runbooks/low-success-rate"
```

### 重要告警规则 (alerts-warning.yml)
```yaml
groups:
  - name: gymbro-api-warning
    rules:
      - alert: JWTRefreshFailure
        expr: sum(rate(jwt_refresh_failures_total[5m])) / sum(rate(jwt_refresh_attempts_total[5m])) * 100 > 5
        for: 10m
        labels:
          severity: warning
          service: gymbro-api
        annotations:
          summary: "JWT刷新失败率过高"
          description: "JWT刷新失败率 {{ $value }}% 超过阈值5%"

      - alert: HighRateLimitHitRate
        expr: sum(rate(http_requests_total{status_code="429"}[5m])) / sum(rate(http_requests_total[5m])) * 100 > 20
        for: 15m
        labels:
          severity: warning
          service: gymbro-api
        annotations:
          summary: "限流命中率异常"
          description: "限流命中率 {{ $value }}% 超过阈值20%"

      - alert: SlowMessageCompletion
        expr: histogram_quantile(0.95, sum(rate(ai_message_duration_seconds_bucket[5m])) by (le)) * 1000 > 45000
        for: 10m
        labels:
          severity: warning
          service: gymbro-api
        annotations:
          summary: "AI消息完成时长过长"
          description: "消息P95完成时长 {{ $value }}ms 超过阈值45000ms"

      - alert: HighSSERejectionRate
        expr: sum(rate(sse_connections_rejected_total[5m])) / sum(rate(sse_connections_attempted_total[5m])) * 100 > 10
        for: 10m
        labels:
          severity: warning
          service: gymbro-api
        annotations:
          summary: "SSE连接拒绝率过高"
          description: "SSE拒绝率 {{ $value }}% 超过阈值10%"
```

### 信息告警规则 (alerts-info.yml)
```yaml
groups:
  - name: gymbro-api-info
    rules:
      - alert: HighSSEConnections
        expr: gymbro_sse_active_connections > 1000
        for: 30m
        labels:
          severity: info
          service: gymbro-api
        annotations:
          summary: "SSE连接数异常"
          description: "活跃SSE连接数 {{ $value }} 超过阈值1000"

      - alert: SuspiciousTraffic
        expr: sum(rate(http_requests_total{user_agent=~".*bot.*|.*crawler.*|.*spider.*"}[1h])) > 100
        for: 1h
        labels:
          severity: info
          service: gymbro-api
        annotations:
          summary: "检测到可疑流量"
          description: "可疑UA请求数 {{ $value }}/hour 超过阈值100"

      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes / 1024 / 1024 > 1000
        for: 30m
        labels:
          severity: info
          service: gymbro-api
        annotations:
          summary: "内存使用率过高"
          description: "内存使用 {{ $value }}MB 超过阈值1000MB"
```

## 📞 AlertManager 配置

### 通知路由 (alertmanager.yml)
```yaml
global:
  smtp_smarthost: 'smtp.company.com:587'
  smtp_from: 'alerts@company.com'

route:
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: 'default'
  routes:
    - match:
        severity: critical
      receiver: 'pagerduty-critical'
      group_wait: 10s
      repeat_interval: 5m

    - match:
        severity: warning
      receiver: 'slack-dev'
      group_wait: 2m
      repeat_interval: 2h

    - match:
        severity: info
      receiver: 'slack-monitoring'
      group_wait: 5m
      repeat_interval: 24h

receivers:
  - name: 'default'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx'
        channel: '#gymbro-alerts'

  - name: 'pagerduty-critical'
    pagerduty_configs:
      - routing_key: 'xxx'
        description: '{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx'
        channel: '#gymbro-oncall'
        color: 'danger'
        title: '🚨 CRITICAL: {{ .GroupLabels.alertname }}'

  - name: 'slack-dev'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx'
        channel: '#gymbro-dev'
        color: 'warning'
        title: '⚠️ WARNING: {{ .GroupLabels.alertname }}'

  - name: 'slack-monitoring'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/xxx'
        channel: '#gymbro-monitoring'
        color: 'good'
        title: 'ℹ️ INFO: {{ .GroupLabels.alertname }}'

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'service']
```

## 👥 值班流程配置

### PagerDuty 排班表
```yaml
schedules:
  - name: "GymBro API Primary"
    time_zone: "Asia/Shanghai"
    layers:
      - start: "2025-09-29T00:00:00"
        rotation_virtual_start: "2025-09-29T00:00:00"
        rotation_turn_length_seconds: 604800  # 1 week
        users:
          - user: "zhang@company.com"
          - user: "li@company.com"
          - user: "wang@company.com"

  - name: "GymBro API Secondary"
    time_zone: "Asia/Shanghai"
    layers:
      - start: "2025-09-29T00:00:00"
        rotation_virtual_start: "2025-09-29T00:00:00"
        rotation_turn_length_seconds: 2592000  # 1 month
        users:
          - user: "manager@company.com"
          - user: "architect@company.com"

escalation_policies:
  - name: "GymBro API Critical"
    escalation_rules:
      - escalation_delay_in_minutes: 0
        targets:
          - type: "schedule"
            id: "GymBro API Primary"
      - escalation_delay_in_minutes: 15
        targets:
          - type: "schedule"
            id: "GymBro API Secondary"
      - escalation_delay_in_minutes: 30
        targets:
          - type: "user"
            id: "cto@company.com"
```

### 联系人信息
```yaml
contacts:
  primary_oncall:
    - name: "张三"
      email: "zhang@company.com"
      phone: "+86-138-0000-0001"
      slack: "@zhang.san"

    - name: "李四"
      email: "li@company.com"
      phone: "+86-138-0000-0002"
      slack: "@li.si"

    - name: "王五"
      email: "wang@company.com"
      phone: "+86-138-0000-0003"
      slack: "@wang.wu"

  secondary_oncall:
    - name: "技术经理"
      email: "manager@company.com"
      phone: "+86-138-0000-0004"
      slack: "@tech.manager"

    - name: "架构师"
      email: "architect@company.com"
      phone: "+86-138-0000-0005"
      slack: "@system.architect"

  escalation:
    - name: "CTO"
      email: "cto@company.com"
      phone: "+86-138-0000-0006"
      slack: "@cto"
```

## 📋 值班手册

### 响应时间要求
- **Critical (P0)**: 15分钟内响应，1小时内解决或升级
- **Warning (P1)**: 2小时内响应，工作日内解决
- **Info (P2)**: 24小时内确认，按优先级排期

### 值班职责
1. **监控告警**: 及时响应PagerDuty和Slack通知
2. **初步诊断**: 使用Runbook进行故障定位
3. **沟通协调**: 及时更新事件状态，必要时拉群讨论
4. **文档记录**: 记录处理过程，更新Runbook
5. **事后复盘**: 重大事件需要进行事后分析

### 交接流程
1. **值班开始**: 检查系统状态，确认无遗留问题
2. **值班期间**: 记录所有处理的事件和变更
3. **值班结束**: 向下一班交接，说明当前状态和注意事项

## 🔧 可复制命令块

### Grafana仪表盘部署

```bash
# 1. 导入应用层仪表盘
curl -X POST \
  http://grafana:3000/api/dashboards/db \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @gymbro-api-app.json

# 2. 导入基础设施仪表盘
curl -X POST \
  http://grafana:3000/api/dashboards/db \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -H "Content-Type: application/json" \
  -d @gymbro-api-infra.json

# 3. 验证仪表盘导入
curl -H "Authorization: Bearer $GRAFANA_API_KEY" \
  http://grafana:3000/api/search?query=GymBro
```

### Prometheus告警规则部署

```bash
# 1. 验证告警规则语法
promtool check rules alerts-critical.yml alerts-warning.yml alerts-info.yml

# 2. 重载Prometheus配置
curl -X POST http://prometheus:9090/-/reload

# 3. 检查告警规则状态
curl http://prometheus:9090/api/v1/rules | jq '.data.groups[].rules[] | select(.type=="alerting")'

# 4. 查看当前活跃告警
curl http://prometheus:9090/api/v1/alerts | jq '.data[] | select(.state=="firing")'
```

### AlertManager配置部署

```bash
# 1. 验证AlertManager配置
amtool config check --config.file=alertmanager.yml

# 2. 重载AlertManager配置
curl -X POST http://alertmanager:9093/-/reload

# 3. 测试告警路由
amtool config routes test --config.file=alertmanager.yml \
  --tree \
  severity=critical service=gymbro-api

# 4. 发送测试告警
curl -X POST http://alertmanager:9093/api/v1/alerts \
  -H "Content-Type: application/json" \
  -d '[{
    "labels": {
      "alertname": "TestAlert",
      "service": "gymbro-api",
      "severity": "warning"
    },
    "annotations": {
      "summary": "测试告警",
      "description": "这是一个测试告警"
    }
  }]'
```

### 监控验证命令

```bash
# 1. 检查Prometheus targets状态
curl http://prometheus:9090/api/v1/targets | \
  jq '.data.activeTargets[] | select(.labels.job=="gymbro-api") | {health: .health, lastScrape: .lastScrape}'

# 2. 验证关键指标采集
curl -G http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=up{job="gymbro-api"}' | \
  jq '.data.result[0].value[1]'

# 3. 测试告警查询
curl -G http://prometheus:9090/api/v1/query \
  --data-urlencode 'query=rate(http_requests_total{code=~"5.."}[5m]) / rate(http_requests_total[5m]) * 100 > 5'

# 4. 检查日志采集状态
curl -G http://loki:3100/loki/api/v1/query \
  --data-urlencode 'query={app="gymbro-api"}' \
  --data-urlencode 'limit=1'
```

### 故障模拟与验证

```bash
# 1. 模拟高错误率
for i in {1..100}; do
  curl -f http://localhost:9999/api/v1/nonexistent || true
  sleep 0.1
done

# 2. 模拟高延迟
curl -H "X-Simulate-Delay: 6000" http://localhost:9999/api/v1/health

# 3. 模拟内存压力
curl -X POST http://localhost:9999/api/v1/admin/simulate-load \
  -H "Content-Type: application/json" \
  -d '{"type": "memory", "duration": 300}'

# 4. 验证告警触发
curl http://alertmanager:9093/api/v1/alerts | \
  jq '.data[] | select(.labels.alertname=="HighErrorRate")'
```

### 日志查询示例

```bash
# 1. 查看最近的错误日志
curl -G http://loki:3100/loki/api/v1/query_range \
  --data-urlencode 'query={app="gymbro-api"} |= "ERROR"' \
  --data-urlencode 'start=1h' \
  --data-urlencode 'limit=100'

# 2. 分析限流事件
curl -G http://loki:3100/loki/api/v1/query_range \
  --data-urlencode 'query={app="gymbro-api"} |= "rate_limit"' \
  --data-urlencode 'start=1h' | \
  jq '.data.result[].values[][1]' | \
  grep -o '"action":"[^"]*"' | sort | uniq -c

# 3. 统计API调用分布
curl -G http://loki:3100/loki/api/v1/query_range \
  --data-urlencode 'query={app="gymbro-api"} |~ "HTTP.*[0-9]{3}"' \
  --data-urlencode 'start=1h' | \
  jq -r '.data.result[].values[][1]' | \
  grep -o 'HTTP [0-9]*' | sort | uniq -c
```

## 📊 预期输出示例

### 正常状态输出

```json
// Prometheus targets检查
{
  "health": "up",
  "lastScrape": "2025-09-29T14:30:52.123Z"
}

// 关键指标查询
{
  "data": {
    "result": [
      {
        "metric": {"job": "gymbro-api"},
        "value": [1727616652, "1"]
      }
    ]
  }
}
```

### 告警触发输出

```json
// 活跃告警示例
{
  "labels": {
    "alertname": "HighErrorRate",
    "service": "gymbro-api",
    "severity": "critical"
  },
  "state": "firing",
  "activeAt": "2025-09-29T14:25:00Z",
  "value": "12.5"
}
```

### 故障模拟结果

```bash
# 高错误率模拟输出
curl: (22) The requested URL returned error: 404 Not Found
curl: (22) The requested URL returned error: 404 Not Found
...
# 预期: 触发HighErrorRate告警

# 高延迟模拟输出
HTTP/1.1 200 OK
Content-Length: 15
# 响应时间: 6.2秒
# 预期: 触发HighLatency告警
```
