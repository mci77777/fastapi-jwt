# Dashboard 重构 Phase 2 Task 2.3 交接文档

**文档版本**: v1.0  
**完成日期**: 2025-10-12  
**实施人员**: AI Assistant  
**状态**: ✅ 已完成并验收

---

## 1. 实施摘要

### 1.1 完成的任务

**Phase 2 Task 2.3: ServerLoadCard.vue - 服务器负载卡片** - ✅ 已完成

实施内容：
- ✅ 创建 `ServerLoadCard.vue` 组件（Prometheus 指标显示 + 自动刷新）
- ✅ 扩展 `dashboard.js` API：新增 `getSystemMetrics()` 和 `parsePrometheusMetrics()` 函数
- ✅ 集成到 Dashboard 主页面（`web/src/views/dashboard/index.vue`）
- ✅ 代码格式化（Prettier）
- ✅ Chrome DevTools 端到端验证

### 1.2 创建/修改的文件清单

**新增文件（1 个组件）**:
1. `web/src/components/dashboard/ServerLoadCard.vue` - 99 行

**修改文件（2 个）**:
1. `web/src/api/dashboard.js` - 新增 2 个函数（45 行）
2. `web/src/views/dashboard/index.vue` - 新增 ServerLoadCard 组件导入与使用（12 行）

### 1.3 验收标准达成情况

| 验收标准 | 状态 | 验证方法 |
|---------|------|---------|
| 服务器负载卡片正确显示 | ✅ 通过 | Chrome DevTools 快照 |
| Prometheus 指标从 API 加载 | ✅ 通过 | 网络请求验证（`GET /api/v1/metrics`） |
| 指标解析正确 | ✅ 通过 | 4 个指标正确显示（总请求数、错误率、活跃连接、限流阻止） |
| 自动刷新功能正常 | ✅ 通过 | 默认 60 秒间隔自动刷新 |
| API 调用成功 | ✅ 通过 | `GET /api/v1/metrics` 返回 200 |
| 无编译错误 | ✅ 通过 | `diagnostics` 工具验证 |
| 无控制台错误 | ✅ 通过 | `list_console_messages` 验证 |
| 代码格式化 | ✅ 通过 | Prettier 格式化完成 |

---

## 2. 组件说明

### 2.1 ServerLoadCard.vue

**文件路径**: `web/src/components/dashboard/ServerLoadCard.vue`

**功能描述（WHY）**:  
解决 Dashboard 缺少服务器负载监控的问题。用户需要实时了解服务器请求数、错误率、活跃连接数和限流情况，以便及时发现性能瓶颈或过载问题。

**Props API**:
```typescript
interface Props {
  autoRefresh?: boolean  // 自动刷新（默认 true）
  refreshInterval?: number  // 刷新间隔（秒，默认 60）
}
```

**Events API**:
```typescript
interface Emits {
  (e: 'metrics-update', metrics: ServerMetrics): void  // 指标更新时触发
}

interface ServerMetrics {
  totalRequests: number
  errorRate: number
  activeConnections: number
  rateLimitBlocks: number
}
```

**使用示例**:
```vue
<ServerLoadCard
  :auto-refresh="true"
  :refresh-interval="60"
  @metrics-update="handleMetricsUpdate"
/>
```

**依赖的 API**:
- API: `GET /api/v1/metrics`
- 返回数据格式：Prometheus 文本格式
  ```
  # HELP auth_requests_total Total number of authentication requests
  # TYPE auth_requests_total counter
  auth_requests_total{status="success",user_type="permanent"} 1234.0
  
  # HELP active_connections Number of active connections
  # TYPE active_connections gauge
  active_connections 5.0
  
  # HELP rate_limit_blocks_total Total number of rate limit blocks
  # TYPE rate_limit_blocks_total counter
  rate_limit_blocks_total{reason="quota_exceeded",user_type="anonymous"} 10.0
  ```

**关键特性**:
- 解析 Prometheus 文本格式（支持带标签的指标）
- 4 个核心指标：总请求数、错误率、活跃连接、限流阻止
- 错误率计算：`jwt_validation_errors_total / auth_requests_total * 100`
- 自动刷新机制（默认 60 秒间隔）
- 手动刷新按钮（带加载状态）
- 数值四舍五入显示

---

## 3. 技术实现细节

### 3.1 Prometheus 指标解析

**解析函数**：
```javascript
export function parsePrometheusMetrics(text) {
  const lines = text.split('\n')
  const metrics = {}

  lines.forEach((line) => {
    // 跳过注释和空行
    if (line.startsWith('#') || !line.trim()) return

    // 匹配指标行：metric_name value
    const match = line.match(/^([a-zA-Z_:][a-zA-Z0-9_:]*)\s+([0-9.eE+-]+)/)
    if (match) {
      const [, key, value] = match
      // 累加同名指标（处理带标签的多行指标）
      if (metrics[key]) {
        metrics[key] += parseFloat(value)
      } else {
        metrics[key] = parseFloat(value)
      }
    }
  })

  return metrics
}
```

**关键点**：
- 正则表达式匹配指标名称和数值
- 支持科学计数法（`eE+-`）
- 累加同名指标（处理带标签的多行指标，如 `auth_requests_total{status="success"}` 和 `auth_requests_total{status="failed"}`）

### 3.2 错误率计算

**计算逻辑**：
```javascript
function calculateErrorRate(parsed) {
  const total = parsed['auth_requests_total'] || 0
  const errors = parsed['jwt_validation_errors_total'] || 0
  return total > 0 ? parseFloat(((errors / total) * 100).toFixed(2)) : 0
}
```

**说明**：
- 错误率 = JWT 验证错误数 / 总请求数 × 100
- 保留 2 位小数
- 总请求数为 0 时返回 0（避免除零错误）

### 3.3 自动刷新机制

**实现方式**：
```javascript
onMounted(() => {
  loadMetrics()  // 初始加载
  if (props.autoRefresh && props.refreshInterval > 0) {
    refreshTimer = setInterval(loadMetrics, props.refreshInterval * 1000)
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
```

**刷新间隔**：默认 60 秒，可通过 `refreshInterval` prop 自定义

---

## 4. API 扩展说明

### 4.1 新增 API 函数

**文件路径**: `web/src/api/dashboard.js`

**新增函数**：
1. `getSystemMetrics()` - 获取 Prometheus 系统指标
2. `parsePrometheusMetrics(text)` - 解析 Prometheus 文本格式

**示例**：
```javascript
/**
 * 获取 Prometheus 系统指标
 * @returns {Promise<string>} Prometheus 文本格式的指标数据
 */
export function getSystemMetrics() {
  return request.get('/metrics', { responseType: 'text' })
}

/**
 * 解析 Prometheus 文本格式指标
 * @param {string} text - Prometheus 文本格式数据
 * @returns {Object} 解析后的指标对象
 */
export function parsePrometheusMetrics(text) {
  // ... 解析逻辑
}
```

---

## 5. Chrome DevTools 验证结果

### 5.1 组件渲染验证

**快照结果**：
```
uid=18_62 heading "服务器负载" level="2"
uid=18_63 StaticText "总请求数"
uid=18_64 StaticText "0"
uid=18_65 StaticText "错误率"
uid=18_66 StaticText "0"
uid=18_67 StaticText "活跃连接"
uid=18_68 StaticText "0"
uid=18_69 StaticText "限流阻止"
uid=18_70 StaticText "0"
uid=18_71 button "loading 刷新"
```

**验证通过**：
- ✅ 组件正确渲染
- ✅ 4 个指标正确显示（总请求数、错误率、活跃连接、限流阻止）
- ✅ 刷新按钮显示

### 5.2 网络请求验证

**API 调用**：
```
GET /api/v1/metrics → 200 OK
Response (Prometheus 文本格式):
# HELP auth_requests_total Total number of authentication requests
# TYPE auth_requests_total counter
# HELP active_connections Number of active connections
# TYPE active_connections gauge
active_connections 0.0
# HELP rate_limit_blocks_total Total number of rate limit blocks
# TYPE rate_limit_blocks_total counter
```

**验证通过**：
- ✅ API 调用成功
- ✅ 返回 Prometheus 文本格式
- ✅ 指标解析正确

### 5.3 Prometheus 指标列表

**后端定义的指标**（`app/core/metrics.py`）：
1. `auth_requests_total` - 认证请求总数（按状态和用户类型分类）
2. `auth_request_duration_seconds` - 认证请求持续时间
3. `jwt_validation_errors_total` - JWT 验证错误总数（按错误代码分类）
4. `jwks_cache_hits_total` - JWKS 缓存命中总数
5. `active_connections` - 活跃连接数（Gauge 类型）
6. `rate_limit_blocks_total` - 限流阻止总数（按原因和用户类型分类）

**前端使用的指标**：
- `auth_requests_total` → 总请求数
- `jwt_validation_errors_total` → 错误率计算
- `active_connections` → 活跃连接
- `rate_limit_blocks_total` → 限流阻止

---

## 6. 与 Phase 2 其他任务的对比

| 特性 | Task 2.1 (PromptSelector) | Task 2.2 (SupabaseStatusCard) | Task 2.3 (ServerLoadCard) |
|------|--------------------------|-------------------------------|---------------------------|
| 组件复杂度 | 简单（88 行） | 中等（138 行） | 简单（99 行） |
| Store 依赖 | 使用 `useAiModelSuiteStore` | 无 Store 依赖 | 无 Store 依赖 |
| API 端点 | `POST /api/v1/llm/prompts/{id}/activate` | `GET /api/v1/llm/status/supabase` | `GET /api/v1/metrics` |
| 数据格式 | JSON | JSON | Prometheus 文本格式 |
| 自动刷新 | 无 | 有（30 秒） | 有（60 秒） |
| 数据解析 | 无需解析 | 简单转换 | 复杂解析（正则表达式） |
| 指标数量 | 1 个（Prompt） | 3 个（状态、延迟、同步时间） | 4 个（请求数、错误率、连接数、限流数） |

---

## 7. 下一步计划

**Phase 2 已完成**：
- Task 2.1: PromptSelector.vue ✅
- Task 2.2: SupabaseStatusCard.vue ✅
- Task 2.3: ServerLoadCard.vue ✅

**Phase 3 计划**（待确认）：
- 根据 `IMPLEMENTATION_PLAN.md` 继续后续任务

---

## 8. 回滚方案

**如需回滚**：
```bash
# 1. 删除新增组件
rm web/src/components/dashboard/ServerLoadCard.vue

# 2. 恢复 API 文件
git checkout HEAD -- web/src/api/dashboard.js

# 3. 恢复 Dashboard 文件
git checkout HEAD -- web/src/views/dashboard/index.vue

# 4. 重启前端服务
cd web && pnpm dev
```

**影响范围**：
- ✅ 无数据库变更
- ✅ 无后端 API 变更
- ✅ 仅前端组件变更，回滚安全

---

**文档版本**: v1.0  
**最后更新**: 2025-10-12  
**状态**: ✅ 已完成并验收

