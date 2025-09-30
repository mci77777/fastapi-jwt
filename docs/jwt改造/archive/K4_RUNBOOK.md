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
| 原因           | 症状      | 解决方案                   |
| -------------- | --------- | -------------------------- |
| 内存不足       | OOMKilled | 增加内存限制，检查内存泄漏 |
| 配置错误       | 启动失败  | 检查环境变量和配置文件     |
| 依赖服务不可用 | 连接超时  | 检查Supabase、AI API连接   |
| 端口冲突       | 绑定失败  | 检查端口占用，修改配置     |

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
| 情况              | 升级时间 | 升级对象         |
| ----------------- | -------- | ---------------- |
| 服务完全不可用    | 立即     | Secondary Oncall |
| 错误率>20%        | 15分钟   | Secondary Oncall |
| 无法在1小时内解决 | 1小时    | 技术经理         |
| 影响核心业务      | 30分钟   | CTO              |

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

## 🔍 逐步排障流程

### 故障排查决策树

```
告警触发
    ↓
检查服务状态 (kubectl/docker)
    ↓
服务运行中？
    ├─ 否 → 重启服务 → 检查启动日志 → 修复配置问题
    └─ 是 → 检查资源使用
              ↓
          资源正常？
              ├─ 否 → 扩容/优化 → 监控恢复
              └─ 是 → 检查依赖服务
                        ↓
                    依赖正常？
                        ├─ 否 → 修复依赖 → 验证恢复
                        └─ 是 → 深度分析日志
```

### 详细排障步骤

#### 第一阶段：快速评估 (0-5分钟)

```bash
# 1. 检查告警详情
curl http://alertmanager:9093/api/v1/alerts | \
  jq '.data[] | select(.state=="firing") | {alert: .labels.alertname, severity: .labels.severity}'

# 2. 验证服务基础状态
curl -s -o /dev/null -w "%{http_code}" http://localhost:9999/api/v1/health
# 预期输出: 200 (正常) 或 非200 (异常)

# 3. 检查进程状态
ps aux | grep -E "(python.*run\.py|gunicorn.*gymbro)" | grep -v grep
# 预期输出: 显示运行中的进程

# 4. 快速日志扫描
tail -50 /var/log/gymbro-api.log | grep -E "(ERROR|CRITICAL|Exception)"
# 预期输出: 最近的错误信息
```

#### 第二阶段：系统诊断 (5-15分钟)

```bash
# 1. 资源使用检查
echo "=== CPU使用率 ==="
top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1
# 预期输出: < 80% (正常)

echo "=== 内存使用率 ==="
free -m | awk 'NR==2{printf "%.1f%%\n", $3*100/$2}'
# 预期输出: < 85% (正常)

echo "=== 磁盘使用率 ==="
df -h | grep -E "/$|/var" | awk '{print $5}'
# 预期输出: < 90% (正常)

# 2. 网络连接检查
echo "=== 端口监听状态 ==="
netstat -tlnp | grep :9999
# 预期输出: LISTEN状态

echo "=== 活跃连接数 ==="
netstat -an | grep :9999 | grep ESTABLISHED | wc -l
# 预期输出: 合理范围内的连接数

# 3. 依赖服务检查
echo "=== Supabase连接测试 ==="
curl -s -H "apikey: $SUPABASE_SERVICE_KEY" "$SUPABASE_URL/rest/v1/" | \
  jq -r '.message // "连接正常"'
# 预期输出: "连接正常" 或错误信息

echo "=== AI API连接测试 ==="
curl -s -H "Authorization: Bearer $AI_API_KEY" \
  "https://api.openai.com/v1/models" | \
  jq -r '.data[0].id // "连接失败"'
# 预期输出: 模型名称或"连接失败"
```

#### 第三阶段：深度分析 (15-30分钟)

```bash
# 1. 详细日志分析
echo "=== 错误日志统计 ==="
grep -E "(ERROR|CRITICAL)" /var/log/gymbro-api.log | \
  tail -100 | \
  awk '{print $4}' | sort | uniq -c | sort -nr
# 预期输出: 错误类型分布

echo "=== 性能指标分析 ==="
grep "duration_ms" /var/log/gymbro-api.log | \
  tail -100 | \
  grep -o 'duration_ms":[0-9]*' | \
  cut -d':' -f2 | \
  awk '{sum+=$1; count++} END {print "平均响应时间:", sum/count "ms"}'
# 预期输出: 平均响应时间

# 2. 数据库连接分析
echo "=== 数据库连接池状态 ==="
curl -s http://localhost:9999/api/v1/admin/db-stats | jq '.'
# 预期输出: 连接池统计信息

# 3. 限流状态检查
echo "=== 限流统计 ==="
grep "rate_limit" /var/log/gymbro-api.log | \
  tail -100 | \
  grep -o '"action":"[^"]*"' | \
  sort | uniq -c
# 预期输出: 限流动作统计

# 4. SSE连接状态
echo "=== SSE连接统计 ==="
grep "sse_" /var/log/gymbro-api.log | \
  tail -50 | \
  grep -o '"event_type":"[^"]*"' | \
  sort | uniq -c
# 预期输出: SSE事件统计
```

#### 第四阶段：问题定位 (30-60分钟)

```bash
# 1. 性能瓶颈分析
echo "=== 慢查询分析 ==="
grep "duration_ms" /var/log/gymbro-api.log | \
  awk -F'duration_ms":' '{print $2}' | \
  awk -F',' '{print $1}' | \
  awk '$1 > 2000 {count++} END {print "慢请求数量:", count+0}'
# 预期输出: 慢请求统计

# 2. 内存泄漏检查
echo "=== 内存使用趋势 ==="
for i in {1..5}; do
  ps -p $(pgrep -f "python.*run.py") -o pid,vsz,rss,pcpu,pmem,etime
  sleep 60
done
# 预期输出: 内存使用趋势

# 3. 线程/协程状态
echo "=== 线程状态分析 ==="
curl -s http://localhost:9999/api/v1/admin/thread-stats | jq '.'
# 预期输出: 线程池状态

# 4. 外部依赖延迟测试
echo "=== 外部服务延迟测试 ==="
time curl -s "$SUPABASE_URL/rest/v1/conversations?limit=1" \
  -H "apikey: $SUPABASE_SERVICE_KEY" > /dev/null
# 预期输出: 响应时间 < 1秒

time curl -s "https://api.openai.com/v1/models" \
  -H "Authorization: Bearer $AI_API_KEY" > /dev/null
# 预期输出: 响应时间 < 2秒
```

### 常见问题快速修复

#### 问题1: 服务启动失败

```bash
# 诊断步骤
echo "检查配置文件..."
python -c "
import os
from pathlib import Path
env_file = Path('.env')
if env_file.exists():
    print('✅ .env文件存在')
    with open(env_file) as f:
        lines = f.readlines()
    missing = []
    required = ['SUPABASE_URL', 'SUPABASE_SERVICE_KEY', 'AI_API_KEY']
    for req in required:
        if not any(req in line for line in lines):
            missing.append(req)
    if missing:
        print(f'❌ 缺失配置: {missing}')
    else:
        print('✅ 必需配置完整')
else:
    print('❌ .env文件不存在')
"

# 修复命令
cp .env.example .env
echo "请编辑 .env 文件，填入正确的配置值"
```

#### 问题2: 数据库连接失败

```bash
# 诊断步骤
echo "测试数据库连接..."
python -c "
import os
import requests
from dotenv import load_dotenv

load_dotenv()
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')

try:
    response = requests.get(f'{url}/rest/v1/', headers={'apikey': key})
    if response.status_code == 200:
        print('✅ Supabase连接正常')
    else:
        print(f'❌ Supabase连接失败: {response.status_code}')
        print(f'响应: {response.text[:200]}')
except Exception as e:
    print(f'❌ 连接异常: {e}')
"

# 修复命令
echo "1. 检查Supabase项目状态"
echo "2. 验证API密钥是否正确"
echo "3. 确认项目URL格式: https://xxx.supabase.co"
```

#### 问题3: 高内存使用

```bash
# 诊断步骤
echo "分析内存使用..."
python -c "
import psutil
import os

# 获取当前进程
pid = os.getpid()
process = psutil.Process(pid)

print(f'内存使用: {process.memory_info().rss / 1024 / 1024:.1f} MB')
print(f'CPU使用: {process.cpu_percent():.1f}%')

# 检查子进程
children = process.children(recursive=True)
print(f'子进程数量: {len(children)}')

# 系统内存
mem = psutil.virtual_memory()
print(f'系统内存使用: {mem.percent:.1f}%')
"

# 修复命令
echo "重启服务以释放内存..."
systemctl restart gymbro-api
# 或
docker restart gymbro-api
```

### 预期输出参考

#### 正常状态输出

```bash
# 健康检查
$ curl -s -o /dev/null -w "%{http_code}" http://localhost:9999/api/v1/health
200

# 进程状态
$ ps aux | grep -E "(python.*run\.py|gunicorn.*gymbro)" | grep -v grep
user     12345  0.5  2.1 123456 87654 ?        S    14:30   0:05 python run.py

# 资源使用
$ top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1
15.2

$ free -m | awk 'NR==2{printf "%.1f%%\n", $3*100/$2}'
45.3%
```

#### 异常状态输出

```bash
# 服务不可用
$ curl -s -o /dev/null -w "%{http_code}" http://localhost:9999/api/v1/health
000

# 高资源使用
$ top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1
95.8

$ free -m | awk 'NR==2{printf "%.1f%%\n", $3*100/$2}'
92.1%

# 错误日志
$ tail -10 /var/log/gymbro-api.log | grep ERROR
2025-09-29 14:30:15 ERROR Database connection failed: timeout
2025-09-29 14:30:16 ERROR Rate limit exceeded for user_123
```
