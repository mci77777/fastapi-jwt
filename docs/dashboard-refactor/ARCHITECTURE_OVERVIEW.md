# Dashboard 重构 - 顶层架构设计

**文档版本**: v2.0
**最后更新**: 2025-01-12 | **变更**: 基于核心功能缺失诊断重写
**状态**: 待实施

---

## 📋 文档目的

本文档基于 **Dashboard 核心功能缺失诊断报告**，重新定义 Dashboard 的架构设计。

**核心发现**：Dashboard 不是数据展示问题，而是**缺少核心控制功能**。

**新架构目标**：
1. **导航枢纽**：提供跳转入口到所有主要配置页面
2. **模型切换控制**：在 Dashboard 上直接切换 AI 模型
3. **Prompt/Tools 管理**：支持 Prompt 切换和 Tools 启用/禁用
4. **API 供应商监控**：显示详细的 API 供应商状态和映射关系
5. **系统状态监控**：Supabase 连接状态 + 服务器负载

---

## 🏗️ 系统架构图

### 整体架构（Mermaid 图）

```mermaid
graph TB
    subgraph "前端 Dashboard 页面"
        A[统计横幅] --> B[5个核心指标]
        C[导航卡片组] --> D[快速访问入口]
        E[当前配置面板] --> F[模型切换器]
        E --> G[Prompt选择器]
        E --> H[API状态详情]
        I[Log小窗] --> J[日志收集API]
        K[用户活跃度图表] --> L[统计数据API]
    end

    subgraph "新增核心组件"
        M[QuickAccessCard] --> N[路由跳转]
        O[ModelSwitcher] --> P[模型切换API]
        Q[PromptSelector] --> R[Prompt切换API]
        S[ApiConnectivityModal] --> T[监控状态API]
        U[SupabaseStatusCard] --> V[Supabase健康检查]
        W[ServerLoadCard] --> X[Prometheus指标]
    end

    subgraph "后端 API 层"
        P --> Y[/api/v1/llm/models]
        R --> Z[/api/v1/llm/prompts]
        T --> AA[/api/v1/llm/monitor/status]
        V --> AB[/api/v1/llm/status/supabase]
        X --> AC[/api/v1/metrics]
        J --> AD[/api/v1/logs/recent]
        L --> AE[/api/v1/stats/dashboard]
    end

    subgraph "服务层"
        Y --> AF[AIConfigService]
        Z --> AF
        AA --> AG[EndpointMonitor]
        AB --> AF
        AC --> AH[Prometheus Metrics]
        AD --> AI[LogCollector]
        AE --> AJ[MetricsCollector]
    end

    subgraph "数据层"
        AF --> AK[(SQLite<br/>ai_endpoints)]
        AF --> AL[(SQLite<br/>ai_prompts)]
        AG --> AK
        AJ --> AM[(SQLite<br/>user_activity_stats)]
        AJ --> AN[(SQLite<br/>ai_request_stats)]
    end
```

### 核心控制链路设计

#### 1. 导航枢纽链路
```
用户点击快速访问卡片
  ↓
QuickAccessCard 组件触发路由跳转
  ↓
Vue Router 导航到目标页面
  ↓
目标页面加载（模型目录/Prompt管理/API配置等）
```

#### 2. 模型切换控制链路
```
用户在 Dashboard 选择模型
  ↓
ModelSwitcher 组件调用 API
  ↓
PUT /api/v1/llm/models (设置 is_default=true)
  ↓
AIConfigService 更新 SQLite ai_endpoints 表
  ↓
（可选）同步到 Supabase
  ↓
Dashboard 实时更新显示当前模型
```

#### 3. Prompt/Tools 管理链路
```
用户在 Dashboard 选择 Prompt
  ↓
PromptSelector 组件调用 API
  ↓
PUT /api/v1/llm/prompts (设置 is_active=true)
  ↓
AIConfigService 更新 SQLite ai_prompts 表
  ↓
用户切换 Tools 开关
  ↓
更新 ai_prompts.tools_json 字段
  ↓
Dashboard 实时更新显示当前 Prompt 和 Tools 状态
```

#### 4. API 供应商监控链路
```
用户点击 "API 连通性" 卡片
  ↓
ApiConnectivityModal 弹窗打开
  ↓
调用 GET /api/v1/llm/monitor/status
  ↓
EndpointMonitor 返回所有端点状态
  ↓
显示详细列表（在线/离线、延迟、最近检测时间）
  ↓
用户点击 "启动监控" / "停止监控"
  ↓
POST /api/v1/llm/monitor/start 或 stop
  ↓
EndpointMonitor 启动/停止定时任务
```

#### 5. 系统状态监控链路
```
Dashboard 加载时自动调用
  ↓
GET /api/v1/llm/status/supabase
  ↓
AIConfigService.supabase_status() 检查连接
  ↓
SupabaseStatusCard 显示状态（在线/离线、延迟）
  ↓
GET /api/v1/metrics
  ↓
Prometheus 指标解析（auth_requests_total、active_connections 等）
  ↓
ServerLoadCard 显示服务器负载（请求数、错误率、连接数）
```

---

## 🔑 关键技术决策

### 1. 导航枢纽设计

**决策**：使用卡片组 + 路由跳转，而非嵌入式子页面

**理由**：
- **YAGNI**：用户需要"快速访问"，不需要在 Dashboard 内嵌完整功能
- **SSOT**：复用现有页面（模型目录、Prompt 管理等），避免重复实现
- **KISS**：简单的路由跳转，无需复杂的状态同步

**实现**：
```vue
<!-- QuickAccessCard.vue -->
<template>
  <n-card hoverable @click="handleNavigate">
    <div class="quick-access-card">
      <hero-icon :name="icon" :size="32" />
      <h3>{{ title }}</h3>
      <p>{{ description }}</p>
    </div>
  </n-card>
</template>

<script setup>
const router = useRouter()
const props = defineProps(['path', 'icon', 'title', 'description'])

function handleNavigate() {
  router.push(props.path)
}
</script>
```

---

### 2. 模型切换控制

**决策**：提取独立组件 `ModelSwitcher.vue`，复用现有 API

**理由**：
- **SSOT**：复用 `/api/v1/llm/models` API 和 `useAiModelSuiteStore`
- **KISS**：不重复实现模型列表获取逻辑
- **可复用**：组件可在 Dashboard 和模型目录页面共用

**实现**：
```vue
<!-- ModelSwitcher.vue -->
<template>
  <n-card title="当前模型">
    <n-select
      v-model:value="selectedModel"
      :options="modelOptions"
      @update:value="handleModelChange"
    />
  </n-card>
</template>

<script setup>
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'

const store = useAiModelSuiteStore()
const selectedModel = ref(null)

const modelOptions = computed(() =>
  store.models.map(m => ({ label: m.name, value: m.id }))
)

async function handleModelChange(modelId) {
  const model = store.models.find(m => m.id === modelId)
  await store.setDefaultModel(model)
  window.$message.success('模型已切换')
}

onMounted(() => {
  store.loadModels()
  const defaultModel = store.models.find(m => m.is_default)
  if (defaultModel) selectedModel.value = defaultModel.id
})
</script>
```

---

### 3. API 供应商详情面板

**决策**：使用 Modal 弹窗展示详细信息，而非内嵌表格

**理由**：
- **YAGNI**：Dashboard 主页面不需要显示完整的 API 列表
- **KISS**：点击统计卡片弹出详情，保持主页面简洁
- **复用**：复用 `EndpointMonitor` 的状态快照数据

**实现**：
```vue
<!-- ApiConnectivityModal.vue -->
<template>
  <n-modal v-model:show="visible" preset="card" title="API 供应商详情">
    <n-table :data="endpoints">
      <n-table-column prop="name" label="名称" />
      <n-table-column prop="status" label="状态">
        <template #default="{ row }">
          <n-tag :type="row.status === 'online' ? 'success' : 'error'">
            {{ row.status }}
          </n-tag>
        </template>
      </n-table-column>
      <n-table-column prop="latency_ms" label="延迟 (ms)" />
      <n-table-column prop="last_checked_at" label="最近检测" />
    </n-table>

    <template #footer>
      <n-space justify="end">
        <n-button @click="handleStartMonitor">启动监控</n-button>
        <n-button @click="handleStopMonitor">停止监控</n-button>
      </n-space>
    </template>
  </n-modal>
</template>
```

---

## 📊 新增组件清单

### 核心组件（P0 优先级）

#### 1. QuickAccessCard.vue - 快速访问卡片
**路径**: `web/src/components/dashboard/QuickAccessCard.vue`

**Props**:
```typescript
interface Props {
  icon: string        // Heroicons 图标名称
  title: string       // 卡片标题
  description: string // 卡片描述
  path: string        // 跳转路由路径
  badge?: number      // 可选徽章数字
}
```

**功能**:
- 显示图标、标题、描述
- 点击跳转到目标路由
- 支持徽章显示（如"3 个在线端点"）

---

#### 2. ModelSwitcher.vue - 模型切换器
**路径**: `web/src/components/dashboard/ModelSwitcher.vue`

**Props**:
```typescript
interface Props {
  compact?: boolean  // 紧凑模式（仅显示下拉框）
}
```

**功能**:
- 显示当前激活模型
- 下拉选择其他模型
- 调用 `PUT /api/v1/llm/models` 切换默认模型
- 切换后实时更新显示

**复用**:
- 复用 `useAiModelSuiteStore` 状态管理
- 复用 `fetchModels()` 和 `updateModel()` API

---

#### 3. ApiConnectivityModal.vue - API 连通性详情弹窗
**路径**: `web/src/components/dashboard/ApiConnectivityModal.vue`

**Props**:
```typescript
interface Props {
  show: boolean  // 控制弹窗显示
}
```

**功能**:
- 显示所有 API 供应商列表
- 显示每个端点的状态（在线/离线）、延迟、最近检测时间
- 提供"启动监控"/"停止监控"按钮
- 调用 `POST /api/v1/llm/monitor/start` 和 `stop`

**数据来源**:
- `GET /api/v1/llm/monitor/status` - 监控状态
- `GET /api/v1/llm/models` - 端点列表

---

### 增强组件（P1 优先级）

#### 4. PromptSelector.vue - Prompt 选择器
**路径**: `web/src/components/dashboard/PromptSelector.vue`

**Props**:
```typescript
interface Props {
  compact?: boolean  // 紧凑模式
}
```

**功能**:
- 显示当前激活 Prompt
- 下拉选择其他 Prompt
- 调用 `PUT /api/v1/llm/prompts` 切换激活状态
- 显示 Tools 启用/禁用开关
- 更新 `ai_prompts.tools_json` 字段

**复用**:
- 复用 `web/src/views/system/ai/prompt/index.vue` 的 Prompt 列表逻辑

---

#### 5. SupabaseStatusCard.vue - Supabase 连接状态卡片
**路径**: `web/src/components/dashboard/SupabaseStatusCard.vue`

**功能**:
- 显示 Supabase 连接状态（在线/离线）
- 显示延迟（ms）
- 显示最近同步时间
- 调用 `GET /api/v1/llm/status/supabase`

**复用**:
- 复用 `web/src/views/system/ai/index.vue` 的 Supabase 状态逻辑

---

#### 6. ServerLoadCard.vue - 服务器负载卡片
**路径**: `web/src/components/dashboard/ServerLoadCard.vue`

**功能**:
- 解析 Prometheus 指标（`GET /api/v1/metrics`）
- 显示关键指标：
  - 总请求数（`auth_requests_total`）
  - 错误率（`jwt_validation_errors_total / auth_requests_total`）
  - 活跃连接数（`active_connections`）
  - 限流阻止数（`rate_limit_blocks_total`）
- 使用 ECharts 或 Naive UI 的 NStatistic 组件展示

**新增 API 封装**:
```javascript
// web/src/api/dashboard.js
export function getSystemMetrics() {
  return request.get('/metrics', { responseType: 'text' })
}

// 解析 Prometheus 文本格式
function parsePrometheusMetrics(text) {
  const lines = text.split('\n')
  const metrics = {}

  lines.forEach(line => {
    if (line.startsWith('#') || !line.trim()) return
    const [key, value] = line.split(' ')
    metrics[key] = parseFloat(value)
  })

  return metrics
}
```

---

## 🗄️ 数据库现状（无需变更）

### 现有 SQLite 表（已实现）

#### 1. `dashboard_stats` - Dashboard 统计数据缓存表 ✅
**状态**: 已存在（`app/db/sqlite_manager.py` 第80-92行）

**用途**: 缓存聚合后的统计数据

---

#### 2. `user_activity_stats` - 用户活跃度统计表 ✅
**状态**: 已存在（`app/db/sqlite_manager.py` 第94-107行）

**用途**: 记录每日用户活跃度，支持日活统计

---

#### 3. `ai_request_stats` - AI 请求统计表 ✅
**状态**: 已存在（`app/db/sqlite_manager.py` 第109-125行）

**用途**: 记录 AI 请求统计，支持请求量、成功率、延迟分析

---

#### 4. `ai_endpoints` - AI 端点配置表 ✅
**状态**: 已存在

**用途**: 存储 API 供应商配置（base_url、api_key、model、status 等）

**关键字段**:
- `is_default`: 标记默认模型
- `status`: 端点状态（online/offline/checking）
- `latency_ms`: 延迟（毫秒）
- `last_checked_at`: 最近检测时间

---

#### 5. `ai_prompts` - Prompt 配置表 ✅
**状态**: 已存在

**用途**: 存储 Prompt 模板和 Tools 配置

**关键字段**:
- `is_active`: 标记激活状态
- `content`: Prompt 内容
- `tools_json`: Tools 定义（JSON 格式）

---

### 数据库变更结论

**✅ 无需新增表**：所有必要的数据库表已存在。

**✅ 无需迁移脚本**：现有表结构满足需求。

**⚠️ 需要确认的字段**:
1. `ai_endpoints.is_default` - 用于标记默认模型（需验证是否已实现）
2. `ai_prompts.is_active` - 用于标记激活 Prompt（需验证是否已实现）

**建议操作**:
```sql
-- 验证 is_default 字段是否存在
SELECT is_default FROM ai_endpoints LIMIT 1;

-- 验证 is_active 字段是否存在
SELECT is_active FROM ai_prompts LIMIT 1;

-- 如果缺失，添加字段
ALTER TABLE ai_endpoints ADD COLUMN is_default INTEGER DEFAULT 0;
ALTER TABLE ai_prompts ADD COLUMN is_active INTEGER DEFAULT 0;
```

---

## 📡 API 现状与新增需求

### 现有 API 端点（已实现，可直接复用）

| 端点 | 方法 | 功能 | 状态 | 文件位置 |
|------|------|------|------|---------|
| `/api/v1/llm/models` | GET | 获取模型列表 | ✅ 已实现 | `app/api/v1/llm_models.py` |
| `/api/v1/llm/models` | PUT | 更新模型（设置默认） | ✅ 已实现 | `app/api/v1/llm_models.py` |
| `/api/v1/llm/prompts` | GET | 获取 Prompt 列表 | ✅ 已实现 | `app/api/v1/llm_prompts.py` |
| `/api/v1/llm/prompts` | PUT | 更新 Prompt（设置激活） | ✅ 已实现 | `app/api/v1/llm_prompts.py` |
| `/api/v1/llm/monitor/status` | GET | 监控状态 | ✅ 已实现 | `app/api/v1/llm_models.py` |
| `/api/v1/llm/monitor/start` | POST | 启动监控 | ✅ 已实现 | `app/api/v1/llm_models.py` |
| `/api/v1/llm/monitor/stop` | POST | 停止监控 | ✅ 已实现 | `app/api/v1/llm_models.py` |
| `/api/v1/llm/status/supabase` | GET | Supabase 连接状态 | ✅ 已实现 | `app/api/v1/llm_models.py` |
| `/api/v1/metrics` | GET | Prometheus 指标 | ✅ 已实现 | `app/api/v1/metrics.py` |
| `/api/v1/stats/dashboard` | GET | Dashboard 聚合统计 | ✅ 已实现 | `app/api/v1/dashboard.py` |
| `/api/v1/logs/recent` | GET | 最近日志 | ✅ 已实现 | `app/api/v1/dashboard.py` |
| `/ws/dashboard` | WebSocket | 实时数据推送 | ✅ 已实现 | `app/api/v1/dashboard.py` |

### 新增 API 需求（仅前端封装）

**无需新增后端 API**，只需在前端 `web/src/api/dashboard.js` 中封装现有端点：

```javascript
// web/src/api/dashboard.js

// 模型管理（复用现有 API）
export function getModels(params) {
  return request.get('/llm/models', { params })
}

export function setDefaultModel(modelId) {
  return request.put('/llm/models', { id: modelId, is_default: true })
}

// Prompt 管理（复用现有 API）
export function getPrompts(params) {
  return request.get('/llm/prompts', { params })
}

export function setActivePrompt(promptId) {
  return request.put('/llm/prompts', { id: promptId, is_active: true })
}

// API 监控（复用现有 API）
export function getMonitorStatus() {
  return request.get('/llm/monitor/status')
}

export function startMonitor(intervalSeconds = 60) {
  return request.post('/llm/monitor/start', { interval_seconds: intervalSeconds })
}

export function stopMonitor() {
  return request.post('/llm/monitor/stop')
}

// Supabase 状态（复用现有 API）
export function getSupabaseStatus() {
  return request.get('/llm/status/supabase')
}

// Prometheus 指标（复用现有 API）
export function getSystemMetrics() {
  return request.get('/metrics', { responseType: 'text' })
}

// 解析 Prometheus 文本格式
export function parsePrometheusMetrics(text) {
  const lines = text.split('\n')
  const metrics = {}

  lines.forEach(line => {
    if (line.startsWith('#') || !line.trim()) return
    const match = line.match(/^([a-zA-Z_:]+)(?:\{[^}]*\})?\s+([0-9.]+)/)
    if (match) {
      const [, key, value] = match
      metrics[key] = parseFloat(value)
    }
  })

  return metrics
}
```

### API 调用示例

#### 1. 模型切换
```javascript
// ModelSwitcher.vue
import { getModels, setDefaultModel } from '@/api/dashboard'

async function handleModelChange(modelId) {
  await setDefaultModel(modelId)
  window.$message.success('模型已切换')
  // 刷新 Dashboard 显示
  await loadDashboardData()
}
```

#### 2. API 监控控制
```javascript
// ApiConnectivityModal.vue
import { getMonitorStatus, startMonitor, stopMonitor } from '@/api/dashboard'

async function handleStartMonitor() {
  await startMonitor(60)  // 60 秒间隔
  window.$message.success('监控已启动')
  await loadMonitorStatus()
}
```

#### 3. Prometheus 指标解析
```javascript
// ServerLoadCard.vue
import { getSystemMetrics, parsePrometheusMetrics } from '@/api/dashboard'

async function loadServerLoad() {
  const text = await getSystemMetrics()
  const metrics = parsePrometheusMetrics(text)

  serverLoad.value = {
    totalRequests: metrics['auth_requests_total'] || 0,
    errorRate: calculateErrorRate(metrics),
    activeConnections: metrics['active_connections'] || 0,
    rateLimitBlocks: metrics['rate_limit_blocks_total'] || 0
  }
}

function calculateErrorRate(metrics) {
  const total = metrics['auth_requests_total'] || 0
  const errors = metrics['jwt_validation_errors_total'] || 0
  return total > 0 ? (errors / total * 100).toFixed(2) : 0
}
```

---

## 🎨 组件变更清单

### 现有组件（已实现，保持不变）

| 组件路径 | 功能 | 状态 |
|---------|------|------|
| `web/src/components/dashboard/StatsBanner.vue` | 统计横幅（5 个指标） | ✅ 已实现 |
| `web/src/components/dashboard/LogWindow.vue` | Log 小窗 | ✅ 已实现 |
| `web/src/components/dashboard/UserActivityChart.vue` | 用户活跃度图表 | ✅ 已实现 |
| `web/src/components/dashboard/WebSocketClient.vue` | WebSocket 客户端封装 | ✅ 已实现 |
| `web/src/components/dashboard/PollingConfig.vue` | 轮询间隔配置 | ✅ 已实现 |
| `web/src/components/dashboard/RealTimeIndicator.vue` | 实时状态指示器 | ✅ 已实现 |
| `web/src/components/dashboard/StatDetailModal.vue` | 统计详情弹窗 | ✅ 已实现 |

---

### 新增组件（P0 优先级）

| 组件路径 | 功能 | 依赖 | 复用来源 |
|---------|------|------|---------|
| `web/src/components/dashboard/QuickAccessCard.vue` | 快速访问卡片 | Naive UI | 新建 |
| `web/src/components/dashboard/ModelSwitcher.vue` | 模型切换器 | Naive UI | 提取自 `catalog/index.vue` |
| `web/src/components/dashboard/ApiConnectivityModal.vue` | API 连通性详情弹窗 | Naive UI | 提取自 `system/ai/index.vue` |

---

### 新增组件（P1 优先级）

| 组件路径 | 功能 | 依赖 | 复用来源 |
|---------|------|------|---------|
| `web/src/components/dashboard/PromptSelector.vue` | Prompt 选择器 | Naive UI | 提取自 `mapping/index.vue` |
| `web/src/components/dashboard/SupabaseStatusCard.vue` | Supabase 连接状态卡片 | Naive UI | 提取自 `system/ai/index.vue` |
| `web/src/components/dashboard/ServerLoadCard.vue` | 服务器负载卡片 | Naive UI | 新建 |

---

### 修改组件（1 个）

| 组件路径 | 修改内容 | 优先级 |
|---------|---------|--------|
| `web/src/views/dashboard/index.vue` | 添加导航卡片组、模型切换器、API 详情弹窗 | P0 |

---

### 删除组件（0 个）

**无需删除任何组件**，所有现有组件均保留。

---

## 🛣️ 路由与菜单现状（无需变更）

### 现有路由（已实现）

**Dashboard 路由**：
- 路径：`/dashboard`
- 组件：`web/src/views/dashboard/index.vue`
- 状态：✅ 已实现（通过后端 `/api/v1/base/usermenu` 动态注入）

**配置页面路由**：
- `/ai/catalog` - 模型目录 ✅
- `/ai/mapping` - 模型映射 ✅
- `/ai/jwt` - JWT 测试 ✅
- `/system/ai` - API 配置 ✅
- `/system/ai/prompt` - Prompt 管理 ✅

---

### 现有菜单结构（已实现）

**后端菜单配置**：`app/api/v1/base.py` (第183-278行)

```javascript
// 实际返回的菜单结构
[
  {
    "name": "Dashboard",
    "path": "/dashboard",
    "component": "/dashboard",
    "icon": "mdi:view-dashboard-outline",
    "order": 0
  },
  {
    "name": "AI模型管理",
    "path": "/ai",
    "icon": "mdi:robot-outline",
    "order": 5,
    "children": [
      { "name": "模型目录", "path": "catalog", "component": "/ai/model-suite/catalog" },
      { "name": "模型映射", "path": "mapping", "component": "/ai/model-suite/mapping" },
      { "name": "JWT测试", "path": "jwt", "component": "/ai/model-suite/jwt" }
    ]
  },
  {
    "name": "系统管理",
    "path": "/system",
    "icon": "carbon:settings-adjust",
    "order": 100,
    "children": [
      { "name": "AI 配置", "path": "ai", "component": "/system/ai" },
      { "name": "Prompt 管理", "path": "ai/prompt", "component": "/system/ai/prompt" }
    ]
  }
]
```

---

### 路由变更结论

**✅ 无需新增路由**：所有必要的路由已存在。

**✅ 无需修改菜单结构**：现有菜单已包含所有配置页面入口。

**⚠️ Dashboard 内部导航**：
- 现有菜单提供了**左侧边栏导航**
- Dashboard 需要添加**快速访问卡片**，提供更直观的跳转入口
- 两者互补，不冲突

---

## 📋 实施优先级与验收标准

### P0 优先级（核心功能，必须实现）

#### 1. 导航枢纽
**组件**：`QuickAccessCard.vue`
**验收标准**：
- ✅ 显示 6 个快速访问卡片（模型目录、模型映射、Prompt 管理、JWT 测试、API 配置、审计日志）
- ✅ 点击卡片跳转到对应页面
- ✅ 卡片显示图标、标题、描述

#### 2. 模型切换
**组件**：`ModelSwitcher.vue`
**验收标准**：
- ✅ 显示当前激活模型
- ✅ 下拉选择其他模型
- ✅ 调用 `PUT /api/v1/llm/models` 切换默认模型
- ✅ 切换后 Dashboard 实时更新显示

#### 3. API 连通性详情
**组件**：`ApiConnectivityModal.vue`
**验收标准**：
- ✅ 点击统计卡片弹出详情弹窗
- ✅ 显示所有 API 供应商列表（在线/离线、延迟、最近检测时间）
- ✅ 提供"启动监控"/"停止监控"按钮
- ✅ 调用 `POST /api/v1/llm/monitor/start` 和 `stop`

---

### P1 优先级（增强功能，建议实现）

#### 4. Prompt 管理
**组件**：`PromptSelector.vue`
**验收标准**：
- ✅ 显示当前激活 Prompt
- ✅ 下拉选择其他 Prompt
- ✅ 调用 `PUT /api/v1/llm/prompts` 切换激活状态
- ✅ 显示 Tools 启用/禁用开关

#### 5. Supabase 连接状态
**组件**：`SupabaseStatusCard.vue`
**验收标准**：
- ✅ 显示 Supabase 连接状态（在线/离线）
- ✅ 显示延迟（ms）
- ✅ 显示最近同步时间
- ✅ 调用 `GET /api/v1/llm/status/supabase`

#### 6. 服务器负载监控
**组件**：`ServerLoadCard.vue`
**验收标准**：
- ✅ 解析 Prometheus 指标（`GET /api/v1/metrics`）
- ✅ 显示总请求数、错误率、活跃连接数、限流阻止数
- ✅ 使用 NStatistic 或 ECharts 展示

---

### 端到端验证清单

#### 导航枢纽链路
```
用户点击"模型目录"卡片
  ↓
QuickAccessCard 触发 router.push('/ai/catalog')
  ↓
Vue Router 导航到模型目录页面
  ↓
模型目录页面加载并显示模型列表
```

#### 模型切换链路
```
用户在 Dashboard 选择 gpt-4o-mini
  ↓
ModelSwitcher 调用 setDefaultModel(modelId)
  ↓
PUT /api/v1/llm/models { id: 123, is_default: true }
  ↓
AIConfigService 更新 SQLite ai_endpoints 表
  ↓
Dashboard 刷新，显示"当前模型: gpt-4o-mini"
```

#### API 监控链路
```
用户点击 "API 连通性: 3/5" 卡片
  ↓
ApiConnectivityModal 弹窗打开
  ↓
调用 GET /api/v1/llm/monitor/status
  ↓
显示 5 个端点详情（3 个在线，2 个离线）
  ↓
用户点击"启动监控"
  ↓
POST /api/v1/llm/monitor/start { interval_seconds: 60 }
  ↓
EndpointMonitor 启动定时任务
  ↓
弹窗显示"监控已启动"
```

---

## 📋 架构设计总结

### 核心发现

**问题本质**：Dashboard 不是数据展示问题，而是**缺少核心控制功能**。

**现有实现**：
- ✅ 统计数据采集（日活、AI 请求、API 连通性、JWT 可获取性）
- ✅ WebSocket 实时推送
- ✅ Log 小窗
- ✅ 用户活跃度图表
- ✅ 后端 API 端点（模型、Prompt、监控、Supabase 状态、Prometheus 指标）

**缺失功能**：
- ❌ 导航枢纽（快速访问卡片）
- ❌ 模型切换控制
- ❌ Prompt/Tools 管理
- ❌ API 供应商详情面板
- ❌ Supabase 连接状态显示
- ❌ 服务器负载监控

---

### 架构设计原则

#### 1. YAGNI（You Aren't Gonna Need It）
- **只实现诊断报告中明确缺失的功能**
- **不添加额外扩展**（如配置总览面板、快速操作栏等，列为 P2 可选）
- **核心链路端到端完备**（导航、模型切换、API 监控必须全链路打通）

#### 2. SSOT（Single Source of Truth）
- **复用现有 API**：不重复实现模型列表、Prompt 列表、监控状态等接口
- **复用现有组件**：提取 `catalog/index.vue`、`mapping/index.vue`、`system/ai/index.vue` 中的逻辑
- **统一状态管理**：使用 `useAiModelSuiteStore` 管理模型数据

#### 3. KISS（Keep It Simple, Stupid）
- **简单的路由跳转**：快速访问卡片直接跳转，不嵌入子页面
- **Modal 弹窗展示详情**：API 详情、Supabase 状态等使用弹窗，保持主页面简洁
- **无需新增数据库表**：现有表结构满足需求

---

### 技术栈（无需新增依赖）

**后端**：
- FastAPI 0.111.0 ✅
- SQLite 3.x ✅
- Supabase ✅
- Prometheus ✅

**前端**：
- Vue 3.3.x ✅
- Naive UI 2.x ✅
- Pinia 2.x ✅
- ECharts 5.x ✅（可选，用于服务器负载图表）

**复用模块**：
- `AIConfigService` - 模型/Prompt 管理 ✅
- `EndpointMonitor` - API 监控 ✅
- `MetricsCollector` - 统计数据聚合 ✅
- `LogCollector` - 日志收集 ✅
- `DashboardBroker` - WebSocket 推送 ✅

---

### 实施路径

#### 阶段 1（P0）：核心控制功能
1. **QuickAccessCard.vue** - 导航枢纽
2. **ModelSwitcher.vue** - 模型切换
3. **ApiConnectivityModal.vue** - API 详情面板

**验收标准**：
- ✅ 点击卡片跳转到配置页面
- ✅ 模型切换后 Dashboard 实时更新
- ✅ API 详情弹窗显示所有端点状态

#### 阶段 2（P1）：增强功能
4. **PromptSelector.vue** - Prompt 管理
5. **SupabaseStatusCard.vue** - Supabase 状态
6. **ServerLoadCard.vue** - 服务器负载

**验收标准**：
- ✅ Prompt 切换后 Dashboard 实时更新
- ✅ Supabase 状态显示在线/离线、延迟
- ✅ 服务器负载显示请求数、错误率、连接数

#### 阶段 3（P2）：可选优化
7. **ConfigSummaryPanel.vue** - 配置总览
8. **QuickActionsBar.vue** - 快速操作栏

**验收标准**：
- ✅ 配置总览显示当前系统配置摘要
- ✅ 快速操作栏提供常用操作按钮

---

### 风险与缓释

| 风险 | 等级 | 缓释方案 |
|------|------|---------|
| 组件提取失败 | 低 | 逐步提取，先复制后重构 |
| API 调用失败 | 低 | 复用现有 API，已验证可用 |
| 状态同步问题 | 低 | 使用 Pinia store 统一管理 |
| 性能问题 | 低 | 复用现有 WebSocket 推送，无额外负载 |

---

## 📋 下一步行动

**基于本架构设计，将生成以下文档**：

1. ✅ **IMPLEMENTATION_SPEC.md** - 详细实施规格（组件 Props、Events、API 调用示例）
2. ✅ **IMPLEMENTATION_PLAN.md** - 分阶段实施计划（P0/P1/P2 优先级、时间估算）
3. ✅ **CODE_REVIEW_AND_GAP_ANALYSIS.md** - 差距分析（LSP 扫描清单、影响面扫描）
4. ✅ **DEPLOYMENT_GUIDE.md** - 部署指南（前置检查、组件部署顺序、回滚方案）
5. ✅ **UI_DESIGN_PREVIEW.html** - UI 设计预览（3 个 HTML 文件）

**请确认架构设计无误后，我将继续生成其他文档。**

---

**文档版本**: v2.0
**最后更新**: 2025-01-12
**变更**: 基于核心功能缺失诊断重写
**状态**: 待实施

