# Dashboard 重构 - 实施规格说明

**文档版本**: v2.0
**最后更新**: 2025-01-12 | **变更**: 基于核心功能缺失诊断重写
**状态**: 待实施

---

## 📋 文档目的

本文档提供 Dashboard 重构的详细技术规格，包括 6 个新增组件的完整接口定义和使用示例。

---

## 🎨 前端组件规格

### 1. QuickAccessCard.vue - 快速访问卡片

**文件路径**: `web/src/components/dashboard/QuickAccessCard.vue`

**功能**: 提供快速跳转到配置页面的卡片组件

#### Props 定义

```typescript
interface Props {
  icon: string        // 图标名称（如 'mdi:robot'）
  title: string       // 卡片标题
  description: string // 卡片描述
  path: string        // 跳转路由路径
  badge?: number      // 可选徽章数字
}
```

#### Events 定义

```typescript
interface Emits {
  (e: 'click', path: string): void  // 点击卡片时触发
}
```

#### 完整实现示例

```vue
<template>
  <n-card
    class="quick-access-card"
    hoverable
    @click="handleClick"
  >
    <div class="card-content">
      <div class="icon-wrapper">
        <TheIcon :icon="icon" :size="32" />
        <n-badge v-if="badge" :value="badge" class="badge" />
      </div>
      <div class="text-content">
        <h3 class="title">{{ title }}</h3>
        <p class="description">{{ description }}</p>
      </div>
    </div>
  </n-card>
</template>

<script setup>
import { useRouter } from 'vue-router'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({
  icon: { type: String, required: true },
  title: { type: String, required: true },
  description: { type: String, required: true },
  path: { type: String, required: true },
  badge: { type: Number, default: undefined }
})

const emit = defineEmits(['click'])
const router = useRouter()

function handleClick() {
  emit('click', props.path)
  router.push(props.path)
}
</script>

<style scoped>
.quick-access-card {
  cursor: pointer;
  transition: all 0.3s ease;
}

.quick-access-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.card-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.icon-wrapper {
  position: relative;
}

.badge {
  position: absolute;
  top: -8px;
  right: -8px;
}

.text-content {
  flex: 1;
}

.title {
  margin: 0 0 4px 0;
  font-size: 16px;
  font-weight: 600;
}

.description {
  margin: 0;
  font-size: 14px;
  color: var(--n-text-color-2);
}
</style>
```

#### 使用示例

```vue
<template>
  <div class="quick-access-section">
    <QuickAccessCard
      icon="mdi:robot"
      title="模型目录"
      description="查看和管理 AI 模型"
      path="/ai/catalog"
      :badge="5"
      @click="handleCardClick"
    />
  </div>
</template>

<script setup>
import QuickAccessCard from '@/components/dashboard/QuickAccessCard.vue'

function handleCardClick(path) {
  console.log('Navigating to:', path)
}
</script>
```

---

### 2. ModelSwitcher.vue - 模型切换器

**文件路径**: `web/src/components/dashboard/ModelSwitcher.vue`

**功能**: 显示当前激活模型并支持快速切换

#### Props 定义

```typescript
interface Props {
  compact?: boolean  // 紧凑模式（仅显示下拉框）
}
```

#### Events 定义

```typescript
interface Emits {
  (e: 'change', modelId: number): void  // 模型切换时触发
}
```

#### 完整实现示例

```vue
<template>
  <n-card :title="compact ? undefined : '当前模型'">
    <n-space vertical>
      <n-select
        v-model:value="selectedModelId"
        :options="modelOptions"
        :loading="loading"
        placeholder="选择模型"
        @update:value="handleModelChange"
      />
      <n-text v-if="!compact && currentModel" depth="3">
        {{ currentModel.base_url }}
      </n-text>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'

const props = defineProps({
  compact: { type: Boolean, default: false }
})

const emit = defineEmits(['change'])
const store = useAiModelSuiteStore()

const selectedModelId = ref(null)
const loading = ref(false)

const modelOptions = computed(() => {
  return store.models.map(model => ({
    label: `${model.model} (${model.provider})`,
    value: model.id
  }))
})

const currentModel = computed(() => {
  return store.models.find(m => m.id === selectedModelId.value)
})

async function handleModelChange(modelId) {
  loading.value = true
  try {
    await store.setDefaultModel({ id: modelId, is_default: true })
    emit('change', modelId)
    window.$message?.success('模型已切换')
  } catch (error) {
    window.$message?.error('模型切换失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await store.loadModels()
    const defaultModel = store.models.find(m => m.is_default)
    if (defaultModel) {
      selectedModelId.value = defaultModel.id
    }
  } finally {
    loading.value = false
  }
})
</script>
```

#### 使用示例

```vue
<template>
  <ModelSwitcher :compact="false" @change="handleModelChange" />
</template>

<script setup>
import ModelSwitcher from '@/components/dashboard/ModelSwitcher.vue'

function handleModelChange(modelId) {
  console.log('Model changed to:', modelId)
}
</script>
```

---

### 3. PromptSelector.vue - Prompt 选择器

**文件路径**: `web/src/components/dashboard/PromptSelector.vue`

**功能**: 显示当前激活 Prompt 并支持快速切换

#### Props 定义

```typescript
interface Props {
  compact?: boolean  // 紧凑模式
}
```

#### Events 定义

```typescript
interface Emits {
  (e: 'change', promptId: number): void  // Prompt 切换时触发
}
```


#### 完整实现示例

```vue
<template>
  <n-card :title="compact ? undefined : '当前 Prompt'">
    <n-space vertical>
      <n-select
        v-model:value="selectedPromptId"
        :options="promptOptions"
        :loading="loading"
        placeholder="选择 Prompt"
        @update:value="handlePromptChange"
      />
      <n-switch
        v-if="!compact && currentPrompt"
        v-model:value="toolsEnabled"
        @update:value="handleToolsToggle"
      >
        <template #checked>Tools 已启用</template>
        <template #unchecked>Tools 已禁用</template>
      </n-switch>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getPrompts, setActivePrompt } from '@/api/dashboard'

const props = defineProps({
  compact: { type: Boolean, default: false }
})

const emit = defineEmits(['change'])

const selectedPromptId = ref(null)
const toolsEnabled = ref(false)
const loading = ref(false)
const prompts = ref([])

const promptOptions = computed(() => {
  return prompts.value.map(prompt => ({
    label: prompt.name,
    value: prompt.id
  }))
})

const currentPrompt = computed(() => {
  return prompts.value.find(p => p.id === selectedPromptId.value)
})

async function loadPrompts() {
  loading.value = true
  try {
    const res = await getPrompts()
    prompts.value = res.data
    const activePrompt = prompts.value.find(p => p.is_active)
    if (activePrompt) {
      selectedPromptId.value = activePrompt.id
      toolsEnabled.value = !!activePrompt.tools_json
    }
  } finally {
    loading.value = false
  }
}

async function handlePromptChange(promptId) {
  loading.value = true
  try {
    await setActivePrompt(promptId)
    emit('change', promptId)
    window.$message?.success('Prompt 已切换')
    await loadPrompts()
  } catch (error) {
    window.$message?.error('Prompt 切换失败')
  } finally {
    loading.value = false
  }
}

async function handleToolsToggle(enabled) {
  // TODO: 实现 Tools 启用/禁用逻辑
  console.log('Tools enabled:', enabled)
}

onMounted(() => {
  loadPrompts()
})
</script>
```

#### 使用示例

```vue
<template>
  <PromptSelector :compact="false" @change="handlePromptChange" />
</template>

<script setup>
import PromptSelector from '@/components/dashboard/PromptSelector.vue'

function handlePromptChange(promptId) {
  console.log('Prompt changed to:', promptId)
}
</script>
```

---

### 4. ApiConnectivityModal.vue - API 连通性详情弹窗

**文件路径**: `web/src/components/dashboard/ApiConnectivityModal.vue`

**功能**: 显示所有 API 供应商的详细状态和监控控制

#### Props 定义

```typescript
interface Props {
  show: boolean  // 控制弹窗显示
}
```

#### Events 定义

```typescript
interface Emits {
  (e: 'update:show', value: boolean): void  // 更新显示状态
}
```

#### 完整实现示例

```vue
<template>
  <n-modal
    v-model:show="visible"
    preset="card"
    title="API 连通性详情"
    style="width: 800px"
  >
    <n-space vertical>
      <n-space>
        <n-button
          type="primary"
          :loading="monitorLoading"
          @click="handleStartMonitor"
        >
          启动监控
        </n-button>
        <n-button
          :loading="monitorLoading"
          @click="handleStopMonitor"
        >
          停止监控
        </n-button>
        <n-text v-if="monitorStatus.is_running" type="success">
          监控运行中（间隔: {{ monitorStatus.interval_seconds }}s）
        </n-text>
      </n-space>

      <n-data-table
        :columns="columns"
        :data="endpoints"
        :loading="loading"
      />
    </n-space>
  </n-modal>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { NTag } from 'naive-ui'
import { getMonitorStatus, startMonitor, stopMonitor } from '@/api/dashboard'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'

const props = defineProps({
  show: { type: Boolean, required: true }
})

const emit = defineEmits(['update:show'])

const store = useAiModelSuiteStore()
const visible = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val)
})

const loading = ref(false)
const monitorLoading = ref(false)
const monitorStatus = ref({ is_running: false, interval_seconds: 60 })
const endpoints = ref([])

const columns = [
  { title: '名称', key: 'model' },
  { title: '供应商', key: 'provider' },
  {
    title: '状态',
    key: 'status',
    render: (row) => {
      const type = row.status === 'online' ? 'success' : 'error'
      return h(NTag, { type }, { default: () => row.status })
    }
  },
  { title: '延迟 (ms)', key: 'latency_ms' },
  { title: '最近检测', key: 'last_checked_at' }
]

async function loadMonitorStatus() {
  loading.value = true
  try {
    const res = await getMonitorStatus()
    monitorStatus.value = res.data
    await store.loadModels()
    endpoints.value = store.models
  } finally {
    loading.value = false
  }
}

async function handleStartMonitor() {
  monitorLoading.value = true
  try {
    await startMonitor(60)
    window.$message?.success('监控已启动')
    await loadMonitorStatus()
  } catch (error) {
    window.$message?.error('启动监控失败')
  } finally {
    monitorLoading.value = false
  }
}

async function handleStopMonitor() {
  monitorLoading.value = true
  try {
    await stopMonitor()
    window.$message?.success('监控已停止')
    await loadMonitorStatus()
  } catch (error) {
    window.$message?.error('停止监控失败')
  } finally {
    monitorLoading.value = false
  }
}

watch(() => props.show, (newVal) => {
  if (newVal) {
    loadMonitorStatus()
  }
})

onMounted(() => {
  if (props.show) {
    loadMonitorStatus()
  }
})
</script>
```

#### 使用示例

```vue
<template>
  <div>
    <n-button @click="showModal = true">查看 API 详情</n-button>
    <ApiConnectivityModal v-model:show="showModal" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import ApiConnectivityModal from '@/components/dashboard/ApiConnectivityModal.vue'

const showModal = ref(false)
</script>
```
---

### 5. SupabaseStatusCard.vue - Supabase 状态卡片

**文件路径**: `web/src/components/dashboard/SupabaseStatusCard.vue`

**功能**: 显示 Supabase 连接状态和健康度

#### Props 定义

```typescript
interface Props {
  autoRefresh?: boolean  // 是否自动刷新（默认 true）
  refreshInterval?: number  // 刷新间隔（秒，默认 30）
}
```

#### Events 定义

```typescript
interface Emits {
  (e: 'status-change', status: SupabaseStatus): void  // 状态变化时触发
}

interface SupabaseStatus {
  connected: boolean
  latency_ms: number
  last_sync_at: string
}
```

#### 完整实现示例

```vue
<template>
  <n-card title="Supabase 连接状态">
    <n-space vertical>
      <n-space align="center">
        <n-tag :type="status.connected ? 'success' : 'error'">
          {{ status.connected ? '在线' : '离线' }}
        </n-tag>
        <n-button
          text
          :loading="loading"
          @click="loadStatus"
        >
          <template #icon>
            <TheIcon icon="mdi:refresh" />
          </template>
        </n-button>
      </n-space>

      <n-descriptions :column="1" size="small">
        <n-descriptions-item label="延迟">
          {{ status.latency_ms }} ms
        </n-descriptions-item>
        <n-descriptions-item label="最近同步">
          {{ formatTime(status.last_sync_at) }}
        </n-descriptions-item>
      </n-descriptions>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getSupabaseStatus } from '@/api/dashboard'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({
  autoRefresh: { type: Boolean, default: true },
  refreshInterval: { type: Number, default: 30 }
})

const emit = defineEmits(['status-change'])

const loading = ref(false)
const status = ref({
  connected: false,
  latency_ms: 0,
  last_sync_at: null
})

let refreshTimer = null

async function loadStatus() {
  loading.value = true
  try {
    const res = await getSupabaseStatus()
    status.value = res.data
    emit('status-change', res.data)
  } catch (error) {
    status.value.connected = false
    window.$message?.error('获取 Supabase 状态失败')
  } finally {
    loading.value = false
  }
}

function formatTime(time) {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

onMounted(() => {
  loadStatus()
  if (props.autoRefresh) {
    refreshTimer = setInterval(loadStatus, props.refreshInterval * 1000)
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>
```

#### 使用示例

```vue
<template>
  <SupabaseStatusCard
    :auto-refresh="true"
    :refresh-interval="30"
    @status-change="handleStatusChange"
  />
</template>

<script setup>
import SupabaseStatusCard from '@/components/dashboard/SupabaseStatusCard.vue'

function handleStatusChange(status) {
  console.log('Supabase status:', status)
}
</script>
```

---

### 6. ServerLoadCard.vue - 服务器负载卡片

**文件路径**: `web/src/components/dashboard/ServerLoadCard.vue`

**功能**: 显示服务器负载指标（从 Prometheus 解析）

#### Props 定义

```typescript
interface Props {
  autoRefresh?: boolean  // 是否自动刷新（默认 true）
  refreshInterval?: number  // 刷新间隔（秒，默认 60）
}
```

#### Events 定义

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

#### 完整实现示例

```vue
<template>
  <n-card title="服务器负载">
    <n-space vertical>
      <n-grid :cols="2" :x-gap="12" :y-gap="12">
        <n-grid-item>
          <n-statistic label="总请求数" :value="metrics.totalRequests" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="错误率" :value="metrics.errorRate" suffix="%" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="活跃连接" :value="metrics.activeConnections" />
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="限流阻止" :value="metrics.rateLimitBlocks" />
        </n-grid-item>
      </n-grid>

      <n-button
        text
        :loading="loading"
        @click="loadMetrics"
      >
        <template #icon>
          <TheIcon icon="mdi:refresh" />
        </template>
        刷新
      </n-button>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getSystemMetrics, parsePrometheusMetrics } from '@/api/dashboard'
import TheIcon from '@/components/icon/TheIcon.vue'

const props = defineProps({
  autoRefresh: { type: Boolean, default: true },
  refreshInterval: { type: Number, default: 60 }
})

const emit = defineEmits(['metrics-update'])

const loading = ref(false)
const metrics = ref({
  totalRequests: 0,
  errorRate: 0,
  activeConnections: 0,
  rateLimitBlocks: 0
})

let refreshTimer = null

async function loadMetrics() {
  loading.value = true
  try {
    const text = await getSystemMetrics()
    const parsed = parsePrometheusMetrics(text)

    metrics.value = {
      totalRequests: parsed['auth_requests_total'] || 0,
      errorRate: calculateErrorRate(parsed),
      activeConnections: parsed['active_connections'] || 0,
      rateLimitBlocks: parsed['rate_limit_blocks_total'] || 0
    }

    emit('metrics-update', metrics.value)
  } catch (error) {
    window.$message?.error('获取服务器指标失败')
  } finally {
    loading.value = false
  }
}

function calculateErrorRate(parsed) {
  const total = parsed['auth_requests_total'] || 0
  const errors = parsed['jwt_validation_errors_total'] || 0
  return total > 0 ? parseFloat((errors / total * 100).toFixed(2)) : 0
}

onMounted(() => {
  loadMetrics()
  if (props.autoRefresh) {
    refreshTimer = setInterval(loadMetrics, props.refreshInterval * 1000)
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
  }
})
</script>
```

#### 使用示例

```vue
<template>
  <ServerLoadCard
    :auto-refresh="true"
    :refresh-interval="60"
    @metrics-update="handleMetricsUpdate"
  />
</template>

<script setup>
import ServerLoadCard from '@/components/dashboard/ServerLoadCard.vue'

function handleMetricsUpdate(metrics) {
  console.log('Server metrics:', metrics)
}
</script>
```

---

## 📡 API 封装规格

### dashboard.js - Dashboard 专用 API 封装

**文件路径**: `web/src/api/dashboard.js`

**功能**: 封装所有 Dashboard 相关的 API 调用

```javascript
import request from '@/utils/http'

// 模型管理
export function getModels(params) {
  return request.get('/llm/models', { params })
}

export function setDefaultModel(modelId) {
  return request.put('/llm/models', { id: modelId, is_default: true })
}

// Prompt 管理
export function getPrompts(params) {
  return request.get('/llm/prompts', { params })
}

export function setActivePrompt(promptId) {
  return request.put('/llm/prompts', { id: promptId, is_active: true })
}

// API 监控
export function getMonitorStatus() {
  return request.get('/llm/monitor/status')
}

export function startMonitor(intervalSeconds = 60) {
  return request.post('/llm/monitor/start', { interval_seconds: intervalSeconds })
}

export function stopMonitor() {
  return request.post('/llm/monitor/stop')
}

// Supabase 状态
export function getSupabaseStatus() {
  return request.get('/llm/status/supabase')
}

// Prometheus 指标
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

---

**文档版本**: v2.0
**最后更新**: 2025-01-12
**变更**: 基于核心功能缺失诊断重写
**状态**: 待实施


