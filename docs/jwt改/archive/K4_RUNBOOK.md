# K4 Runbook - 故障排查与恢复指南

## 🚨 告警响应流程

### 通用响应步骤
1. **确认告警** - 检查告警详情和影响范围
2. **快速诊断** - 使用本Runbook进行初步定位
3. **缓解措施** - 实施临时解决方案
4. **根因分析** - 深入调查问题原因
5. **永久修复** - 实施长期解决方案
6. **文档更新** - 更新Runbook和监控

## 🔥 常见故障场景

### 1. API服务不可用 (APIServiceDown)

#### 症状
- 健康检查失败
- 所有API请求返回连接错误
- 负载均衡器显示后端不健康

#### 快速诊断
```bash
# 检查服务状态
kubectl get pods -l app=gymbro-api
docker ps | grep gymbro-api

# 检查服务日志
kubectl logs -l app=gymbro-api --tail=100
docker logs gymbro-api --tail=100

# 检查资源使用
kubectl top pods -l app=gymbro-api
docker stats gymbro-api
```

#### 缓解措施
```bash
# 重启服务
kubectl rollout restart deployment/gymbro-api
docker restart gymbro-api

# 扩容实例
kubectl scale deployment gymbro-api --replicas=3

# 检查配置
kubectl get configmap gymbro-api-config -o yaml
```

#### 常见原因与解决方案
| 原因 | 症状 | 解决方案 |
|------|------|----------|
| 内存不足 | OOMKilled | 增加内存限制，检查内存泄漏 |
| 配置错误 | 启动失败 | 检查环境变量和配置文件 |
| 依赖服务不可用 | 连接超时 | 检查Supabase、AI API连接 |
| 端口冲突 | 绑定失败 | 检查端口占用，修改配置 |

---

### 2. Supabase 连接故障

#### 症状
- JWT验证失败
- 数据库查询超时
- 认证相关API返回5xx错误

#### 快速诊断
```bash
# 测试Supabase连接
curl -H "apikey: $SUPABASE_SERVICE_KEY" \
     "$SUPABASE_URL/rest/v1/"

# 检查JWKS端点
curl "$SUPABASE_JWKS_URL"

# 验证环境变量
echo $SUPABASE_PROJECT_ID
echo $SUPABASE_SERVICE_ROLE_KEY | head -c 20
```

#### 缓解措施
```bash
# 切换到备用配置
export SUPABASE_PROJECT_ID="backup-project-id"
kubectl set env deployment/gymbro-api SUPABASE_PROJECT_ID="backup-project-id"

# 增加超时时间
export HTTP_TIMEOUT_SECONDS=30

# 启用降级模式
export AUTH_FALLBACK_MODE=true
```

#### 恢复步骤
1. **确认Supabase状态** - 检查Supabase状态页面
2. **验证配置** - 确认项目ID、密钥正确
3. **测试连接** - 使用curl验证各个端点
4. **重启服务** - 重新加载配置
5. **监控恢复** - 观察错误率下降

---

### 3. JWKS 获取失效

#### 症状
- JWT验证失败，错误信息包含"JWKS"
- 401错误率突然上升
- 日志显示"Failed to fetch JWKS"

#### 快速诊断
```bash
# 测试JWKS端点
curl -v "$SUPABASE_JWKS_URL"

# 检查DNS解析
nslookup $(echo $SUPABASE_JWKS_URL | cut -d'/' -f3)

# 检查缓存状态
grep "JWKS" /var/log/gymbro-api.log | tail -10
```

#### 缓解措施
```bash
# 使用静态JWK配置
export SUPABASE_JWK='{"kty":"RSA","kid":"...","use":"sig",...}'

# 增加缓存时间
export JWKS_CACHE_TTL_SECONDS=3600

# 重启服务刷新缓存
kubectl rollout restart deployment/gymbro-api
```

#### 预防措施
- 配置多个JWKS端点
- 实施本地JWK缓存
- 设置合理的缓存TTL

---

### 4. AI模型服务限流

#### 症状
- AI消息完成时长异常增长
- 大量429错误从AI API返回
- 用户反馈AI响应缓慢

#### 快速诊断
```bash
# 检查AI API调用日志
grep "AI API" /var/log/gymbro-api.log | grep -E "(429|timeout)" | tail -20

# 查看当前QPS
grep "AI API" /var/log/gymbro-api.log | grep "$(date '+%Y-%m-%d %H:%M')" | wc -l

# 检查API密钥配额
curl -H "Authorization: Bearer $AI_API_KEY" \
     "https://api.openai.com/v1/usage"
```

#### 缓解措施
```bash
# 启用请求队列
export AI_REQUEST_QUEUE_SIZE=100
export AI_MAX_CONCURRENT_REQUESTS=5

# 切换到备用模型
export AI_MODEL="gpt-3.5-turbo"

# 实施客户端限流
export RATE_LIMIT_PER_USER_QPS=5
```

#### 长期解决方案
- 实施智能重试机制
- 配置多个AI提供商
- 优化prompt减少token使用

---

### 5. 高错误率 (5xx错误激增)

#### 症状
- 5xx错误率超过5%
- 用户反馈功能异常
- 服务响应时间增长

#### 快速诊断
```bash
# 分析错误分布
grep "HTTP.*5[0-9][0-9]" /var/log/gymbro-api.log | \
  awk '{print $NF}' | sort | uniq -c | sort -nr

# 检查最近的错误
tail -100 /var/log/gymbro-api.log | grep -E "(ERROR|CRITICAL)"

# 查看资源使用情况
top -p $(pgrep -f gymbro-api)
```

#### 缓解措施
```bash
# 扩容服务
kubectl scale deployment gymbro-api --replicas=5

# 启用熔断器
export CIRCUIT_BREAKER_ENABLED=true
export CIRCUIT_BREAKER_THRESHOLD=50

# 降级非关键功能
export FEATURE_AI_ENABLED=false
export FEATURE_ANALYTICS_ENABLED=false
```

#### 根因分析
1. **代码问题** - 检查最近部署的代码变更
2. **资源不足** - 分析CPU、内存、网络使用
3. **依赖故障** - 检查外部服务状态
4. **数据问题** - 分析异常数据或查询

---

## 🛠️ 诊断工具与命令

### 日志分析
```bash
# 实时监控错误
tail -f /var/log/gymbro-api.log | grep -E "(ERROR|WARN|CRITICAL)"

# 分析请求模式
grep "HTTP" /var/log/gymbro-api.log | \
  awk '{print $1, $2, $(NF-1), $NF}' | \
  sort | uniq -c | sort -nr | head -20

# 查找慢请求
grep "duration_ms" /var/log/gymbro-api.log | \
  awk -F'duration_ms":' '{print $2}' | \
  awk -F',' '{print $1}' | \
  sort -nr | head -10
```

### 性能分析
```bash
# CPU使用分析
top -p $(pgrep -f gymbro-api) -H

# 内存使用分析
pmap -x $(pgrep -f gymbro-api)

# 网络连接分析
netstat -tulpn | grep :9999
ss -tulpn | grep :9999
```

### 数据库诊断
```bash
# 测试Supabase连接
psql "$DATABASE_URL" -c "SELECT version();"

# 检查慢查询
psql "$DATABASE_URL" -c "
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;"
```

## 📞 升级路径

### 升级决策矩阵
| 情况 | 升级时间 | 升级对象 |
|------|----------|----------|
| 服务完全不可用 | 立即 | Secondary Oncall |
| 错误率>20% | 15分钟 | Secondary Oncall |
| 无法在1小时内解决 | 1小时 | 技术经理 |
| 影响核心业务 | 30分钟 | CTO |

### 升级联系方式
```yaml
contacts:
  secondary_oncall: 
    slack: "#gymbro-oncall"
    phone: "+86-400-xxx-xxxx"
  
  tech_manager:
    slack: "@tech.manager"
    phone: "+86-138-xxxx-xxxx"
  
  cto:
    slack: "@cto"
    phone: "+86-139-xxxx-xxxx"
```

## 📝 事后处理

### 事件记录模板
```markdown
## 事件报告 - [事件标题]

**时间**: 2025-09-29 14:00 - 15:30
**影响**: 用户无法创建新消息，影响100%功能
**严重级别**: P0

### 时间线
- 14:00 - 告警触发，开始调查
- 14:15 - 确认Supabase连接问题
- 14:30 - 实施临时修复
- 15:00 - 服务恢复正常
- 15:30 - 确认稳定

### 根因
Supabase项目配额耗尽导致连接被拒绝

### 解决方案
1. 升级Supabase套餐
2. 实施连接池管理
3. 添加配额监控

### 预防措施
- 配置配额告警
- 实施降级机制
- 定期容量规划
```

### 改进行动
1. **更新监控** - 添加新的告警规则
2. **完善文档** - 更新Runbook内容
3. **优化流程** - 改进响应流程
4. **技术改进** - 实施预防措施
