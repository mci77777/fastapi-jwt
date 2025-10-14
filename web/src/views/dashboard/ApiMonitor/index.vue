<template>
  <div class="api-monitor-container">
    <!-- 顶部控制面板 -->
    <div class="control-panel">
      <div class="panel-left">
        <h2 class="page-title">API 端点健康监控</h2>
        <NText depth="3" class="page-subtitle">
          实时监控后端 API 端点的连通性和响应时间
        </NText>
      </div>
      <div class="panel-right">
        <NSpace :size="12">
          <NButton type="primary" :loading="loading" @click="checkAllEndpoints">
            <template #icon>
              <TheIcon icon="mdi:refresh" />
            </template>
            手动检测
          </NButton>
          <NSelect
            v-model:value="selectedInterval"
            :options="intervalOptions"
            style="width: 150px"
            placeholder="轮询间隔"
          />
          <NButton
            v-if="!isPolling"
            type="success"
            :disabled="loading"
            @click="startPolling"
          >
            <template #icon>
              <TheIcon icon="mdi:play" />
            </template>
            启动轮询
          </NButton>
          <NButton v-else type="error" @click="stopPolling">
            <template #icon>
              <TheIcon icon="mdi:stop" />
            </template>
            停止轮询
          </NButton>
        </NSpace>
      </div>
    </div>

    <!-- 统计摘要 -->
    <div class="stats-summary">
      <div class="stat-card">
        <div class="stat-label">总端点数</div>
        <div class="stat-value">{{ totalEndpoints }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">正常</div>
        <div class="stat-value stat-success">{{ onlineCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">异常</div>
        <div class="stat-value stat-error">{{ offlineCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">未知</div>
        <div class="stat-value stat-unknown">{{ unknownCount }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">平均响应时间</div>
        <div class="stat-value">{{ avgLatency }} ms</div>
      </div>
    </div>

    <!-- 端点列表表格 -->
    <NDataTable
      :columns="columns"
      :data="endpoints"
      :loading="loading"
      :pagination="pagination"
      :row-key="(row) => row.path"
      class="endpoints-table"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, h } from 'vue'
import { NDataTable, NButton, NSelect, NSpace, NText, NTag, useMessage } from 'naive-ui'
import { getToken } from '@/utils'
import { API_ENDPOINTS, getCheckableEndpoints, CATEGORY_LABELS, CATEGORY_COLORS } from '@/config/apiEndpoints'
import TheIcon from '@/components/icon/TheIcon.vue'

defineOptions({ name: 'ApiMonitor' })

const message = useMessage()

// 状态管理
const endpoints = ref([])
const loading = ref(false)
const isPolling = ref(false)
const pollingTimer = ref(null)
const selectedInterval = ref(60) // 默认 60 秒

// 轮询间隔选项
const intervalOptions = [
  { label: '30 秒', value: 30 },
  { label: '1 分钟', value: 60 },
  { label: '5 分钟', value: 300 },
  { label: '10 分钟', value: 600 },
]

// 分页配置
const pagination = {
  pageSize: 20,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
}

// 表格列定义
const columns = [
  {
    title: '路径',
    key: 'path',
    width: 250,
    ellipsis: {
      tooltip: true,
    },
  },
  {
    title: '方法',
    key: 'method',
    width: 100,
    render: (row) => {
      const typeMap = {
        GET: 'success',
        POST: 'info',
        PUT: 'warning',
        DELETE: 'error',
        WebSocket: 'primary',
      }
      return h(
        NTag,
        { type: typeMap[row.method] || 'default', size: 'small' },
        { default: () => row.method }
      )
    },
  },
  {
    title: '分类',
    key: 'category',
    width: 120,
    render: (row) => {
      return h(
        NTag,
        { type: CATEGORY_COLORS[row.category] || 'default', size: 'small' },
        { default: () => CATEGORY_LABELS[row.category] || row.category }
      )
    },
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => {
      const typeMap = {
        online: 'success',
        offline: 'error',
        checking: 'warning',
        unknown: 'default',
      }
      const labelMap = {
        online: '正常',
        offline: '异常',
        checking: '检测中',
        unknown: '未知',
      }
      return h(
        NTag,
        { type: typeMap[row.status] || 'default', size: 'small' },
        { default: () => labelMap[row.status] || row.status }
      )
    },
  },
  {
    title: '状态码',
    key: 'statusCode',
    width: 100,
    render: (row) => {
      return row.statusCode !== null && row.statusCode !== undefined ? row.statusCode : '-'
    },
  },
  {
    title: '响应时间 (ms)',
    key: 'latency',
    width: 130,
    render: (row) => {
      if (row.latency === null || row.latency === undefined) return '-'
      const latency = row.latency
      let color = '#18a058' // 绿色
      if (latency > 1000) color = '#d03050' // 红色
      else if (latency > 500) color = '#f0a020' // 橙色
      return h('span', { style: { color } }, latency.toFixed(0))
    },
  },
  {
    title: '描述',
    key: 'description',
    ellipsis: {
      tooltip: true,
    },
  },
  {
    title: '最后检测',
    key: 'lastChecked',
    width: 160,
    render: (row) => {
      if (!row.lastChecked) return '-'
      return new Date(row.lastChecked).toLocaleString('zh-CN')
    },
  },
]

// 统计数据
const totalEndpoints = computed(() => endpoints.value.length)
const onlineCount = computed(() => endpoints.value.filter((e) => e.status === 'online').length)
const offlineCount = computed(() => endpoints.value.filter((e) => e.status === 'offline').length)
const unknownCount = computed(() => endpoints.value.filter((e) => e.status === 'unknown').length)
const avgLatency = computed(() => {
  const validLatencies = endpoints.value.filter((e) => e.latency !== null && e.latency !== undefined)
  if (validLatencies.length === 0) return '-'
  const sum = validLatencies.reduce((acc, e) => acc + e.latency, 0)
  return (sum / validLatencies.length).toFixed(0)
})

/**
 * 检测所有端点
 */
async function checkAllEndpoints() {
  loading.value = true
  try {
    const checkableEndpoints = endpoints.value.filter((e) => !e.skipCheck)
    for (const endpoint of checkableEndpoints) {
      await checkEndpoint(endpoint)
    }
    message.success('检测完成')
  } catch (error) {
    console.error('检测失败:', error)
    message.error('检测失败')
  } finally {
    loading.value = false
  }
}

/**
 * 检测单个端点
 */
async function checkEndpoint(endpoint) {
  endpoint.status = 'checking'
  const startTime = Date.now()

  try {
    if (endpoint.type === 'http') {
      // HTTP 端点检测
      const token = getToken()
      const headers = {}
      if (endpoint.requiresAuth && token) {
        headers.Authorization = `Bearer ${token}`
      }

      const response = await fetch(endpoint.path, {
        method: endpoint.method,
        headers,
      })

      endpoint.statusCode = response.status
      endpoint.status = response.status >= 200 && response.status < 300 ? 'online' : 'offline'
      endpoint.error = null
    } else if (endpoint.type === 'websocket') {
      // WebSocket 端点检测（简化实现：标记为未知）
      endpoint.status = 'unknown'
      endpoint.statusCode = null
      endpoint.error = 'WebSocket 端点暂不支持自动检测'
    } else {
      endpoint.status = 'unknown'
      endpoint.statusCode = null
      endpoint.error = '未知端点类型'
    }
  } catch (error) {
    endpoint.status = 'offline'
    endpoint.statusCode = null
    endpoint.error = error.message
  }

  endpoint.latency = Date.now() - startTime
  endpoint.lastChecked = new Date().toISOString()
}

/**
 * 启动定时轮询
 */
function startPolling() {
  if (isPolling.value) return

  isPolling.value = true
  message.success(`已启动定时轮询（间隔 ${selectedInterval.value} 秒）`)

  // 立即执行一次
  checkAllEndpoints()

  // 启动定时器
  pollingTimer.value = setInterval(() => {
    checkAllEndpoints()
  }, selectedInterval.value * 1000)
}

/**
 * 停止定时轮询
 */
function stopPolling() {
  if (!isPolling.value) return

  isPolling.value = false
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
  message.info('已停止定时轮询')
}

// 生命周期
onMounted(() => {
  // 初始化端点列表
  endpoints.value = getCheckableEndpoints().map((ep) => ({
    ...ep,
    status: 'unknown',
    statusCode: null,
    latency: null,
    lastChecked: null,
    error: null,
  }))

  // 立即执行一次检测
  checkAllEndpoints()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.api-monitor-container {
  padding: var(--spacing-xl);
  background: var(--bg-color);
  min-height: 100vh;
}

/* 控制面板 */
.control-panel {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
  padding: var(--spacing-lg);
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.panel-left {
  flex: 1;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  color: #000;
  margin: 0 0 var(--spacing-xs) 0;
}

.page-subtitle {
  font-size: 14px;
  color: #666;
}

.panel-right {
  flex-shrink: 0;
}

/* 统计摘要 */
.stats-summary {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-lg);
}

.stat-card {
  padding: var(--spacing-lg);
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  text-align: center;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-bottom: var(--spacing-sm);
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #000;
}

.stat-success {
  color: #18a058;
}

.stat-error {
  color: #d03050;
}

.stat-unknown {
  color: #999;
}

/* 表格 */
.endpoints-table {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

/* 响应式 */
@media (max-width: 1400px) {
  .stats-summary {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 768px) {
  .control-panel {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-md);
  }

  .panel-right {
    width: 100%;
  }

  .stats-summary {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
