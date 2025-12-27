<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useMessage, NModal, NCard, NSpace, NText } from 'naive-ui'
import { getToken } from '@/utils'

// Dashboard Components
import StatsBanner from '@/components/dashboard/StatsBanner.vue'
import MonitorPanel from '@/components/dashboard/MonitorPanel.vue'
import ControlCenter from '@/components/dashboard/ControlCenter.vue'
import WebSocketClient from '@/components/dashboard/WebSocketClient.vue'
import PollingConfig from '@/components/dashboard/PollingConfig.vue'
import StatDetailModal from '@/components/dashboard/StatDetailModal.vue'
import ApiConnectivityModal from '@/components/dashboard/ApiConnectivityModal.vue'
import SupabaseStatusCard from '@/components/dashboard/SupabaseStatusCard.vue'

// Dashboard API
import {
  getDashboardStats,
  getRecentLogs,
  getStatsConfig,
  updateStatsConfig,
  createWebSocketUrl,
  getDailyActiveUsers,
} from '@/api/dashboard'

defineOptions({ name: 'DashboardIndex' })

const message = useMessage()

// 响应式状态
const connectionStatus = ref('disconnected') // 'connected' | 'disconnected' | 'connecting' | 'error' | 'polling'
const statsLoading = ref(false)
const logsLoading = ref(false)
const showConfigModal = ref(false)
const showStatDetailModal = ref(false)
const showApiModal = ref(false)
const showSupabaseModal = ref(false)
const selectedStat = ref(null)

// 统计数据
const stats = ref([
  {
    id: 1,
    icon: 'user-group',
    label: '日活用户数',
    value: 0,
    trend: 0,
    color: '#18a058',
    detail: '今日活跃用户数量',
  },
  {
    id: 2,
    icon: 'cpu-chip',
    label: 'AI 请求数',
    value: 0,
    trend: 0,
    color: '#2080f0',
    detail: '今日 AI API 调用总次数',
  },
  {
    id: 3,
    icon: 'currency-dollar',
    label: 'Token 使用量',
    value: '--',
    trend: 0,
    color: '#f0a020',
    detail: 'Token 消耗总量（后续追加）',
  },
  {
    id: 4,
    icon: 'signal',
    label: 'API 连通性',
    value: '0/0',
    trend: 0,
    color: '#00bcd4',
    detail: 'API 供应商在线状态',
  },
  {
    id: 5,
    icon: 'key',
    label: 'JWT 连通性',
    value: '0%',
    trend: 0,
    color: '#8a2be2',
    detail: 'JWT 验证成功率',
  },
])

// 日志数据
const logs = ref([])

// 图表数据
const chartTimeRange = ref('24h')
const chartData = ref([])

// 默认快速访问卡片配置
const defaultQuickAccessCards = [
  {
    icon: 'wrench-screwdriver',
    title: 'AI 供应商',
    description: '配置 AI 供应商',
    path: '/system/ai',
    iconColor: '#d03050',
  },
  {
    icon: 'document-text',
    title: '提示词',
    description: '管理 Prompt 模板',
    path: '/system/ai/prompt',
    iconColor: '#18a058',
  },
  {
    icon: 'rectangle-stack',
    title: '模型目录',
    description: '查看和管理 AI 模型',
    path: '/ai/catalog',
    iconColor: '#667eea',
  },
  {
    icon: 'map',
    title: '模型映射',
    description: '配置模型映射关系',
    path: '/ai/mapping',
    iconColor: '#2080f0',
  },
  {
    icon: 'chart-line',
    title: 'API 监控',
    description: '监控后端 API 端点健康状态',
    path: '/dashboard/api-monitor',
    iconColor: '#f0a020',
  },
  {
    icon: 'folder',
    title: '目录管理',
    description: '管理内容分类和标签',
    path: '/catalog',
    iconColor: '#da7756',
  },
  {
    icon: 'key',
    title: 'JWT 测试',
    description: '测试 JWT 认证',
    path: '/ai/jwt',
    iconColor: '#999',
  },
]

// 从 localStorage 加载保存的卡片顺序
const loadSavedCardOrder = () => {
  try {
    const saved = localStorage.getItem('dashboard_card_order')
    if (saved) {
      const savedOrder = JSON.parse(saved)
      if (Array.isArray(savedOrder) && savedOrder.length === defaultQuickAccessCards.length) {
        return savedOrder
      }
    }
  } catch (error) {
    console.error('加载卡片顺序失败:', error)
  }
  return defaultQuickAccessCards
}

const quickAccessCards = ref(loadSavedCardOrder())

// 保存卡片顺序到 localStorage
const saveCardOrder = (newOrder) => {
  try {
     quickAccessCards.value = newOrder // update local state
    localStorage.setItem('dashboard_card_order', JSON.stringify(quickAccessCards.value))
    message.success('布局已保存')
  } catch (error) {
    console.error('保存卡片顺序失败:', error)
    message.error('保存布局失败')
  }
}

// 重置卡片顺序
const resetCardOrder = () => {
  quickAccessCards.value = [...defaultQuickAccessCards]
  localStorage.removeItem('dashboard_card_order')
  message.success('布局已重置')
}


// Dashboard 配置
const dashboardConfig = ref({
  websocket_push_interval: 10,
  http_poll_interval: 30,
  log_retention_size: 100,
})

// WebSocket URL
const wsUrl = computed(() => {
  const token = getToken()
  if (!token) return ''
  return createWebSocketUrl(token)
})

// HTTP 轮询定时器
let pollingTimer = null

/**
 * 加载 Dashboard 统计数据
 */
async function loadDashboardStats() {
  try {
    statsLoading.value = true
    const response = await getDashboardStats({ time_window: '24h' })

    let data = response
    if (response.data && typeof response.data === 'object') {
      data = response.data
    }

    stats.value[0].value = data.daily_active_users || 0
    stats.value[1].value = data.ai_requests?.total || 0
    stats.value[2].value = data.token_usage || '--'
    stats.value[3].value = `${data.api_connectivity?.healthy_endpoints || 0}/${
      data.api_connectivity?.total_endpoints || 0
    }`
    stats.value[4].value = `${data.jwt_availability?.success_rate?.toFixed(1) || 0}%`

    if (data.api_connectivity) {
      const rate = data.api_connectivity.connectivity_rate || 0
      stats.value[3].trend = rate - 100
    }
  } catch (error) {
    console.error('加载统计数据失败:', error)
    message.error('加载统计数据失败')
  } finally {
    statsLoading.value = false
  }
}

/**
 * 加载最近日志
 */
async function loadRecentLogs() {
  try {
    logsLoading.value = true
    const response = await getRecentLogs({ level: 'WARNING', limit: 100 })

    let data = response
    if (response.data && typeof response.data === 'object') {
      data = response.data
    }

    if (Array.isArray(data.logs)) {
      logs.value = data.logs.map((log, index) => ({
        id: index,
        ...log,
      }))
    } else if (Array.isArray(data)) {
      logs.value = data.map((log, index) => ({
        id: index,
        ...log,
      }))
    }
  } catch (error) {
    console.error('加载日志失败:', error)
  } finally {
    logsLoading.value = false
  }
}

/**
 * 加载图表数据
 */
async function loadChartData() {
  try {
    const response = await getDailyActiveUsers({ time_window: chartTimeRange.value })
    // Check if response has data property (standard response format) or is direct array
    let data = response
    if (response.data && Array.isArray(response.data)) {
        data = response.data
    } else if (response.data && typeof response.data === 'object' && response.data.data) {
        // Handle cases where might be nested like { code: 200, data: [...] }
        data = response.data
    }
    
    // Ensure data is array of numbers as expected by chart
    if (Array.isArray(data)) {
         chartData.value = data
    } else {
         chartData.value = []
    }
    
  } catch (error) {
    console.error('Failed to load chart data:', error)
    chartData.value = []
  }
}

/**
 * 加载 Dashboard 配置
 */
async function loadDashboardConfig() {
  try {
    const response = await getStatsConfig()

    let data = response
    if (response.data && typeof response.data === 'object') {
      data = response.data
    }

    if (data.config) {
      dashboardConfig.value = { ...data.config }
    }
  } catch (error) {
    console.error('加载配置失败:', error)
  }
}

/**
 * WebSocket 消息处理
 */
function handleWebSocketMessage(data) {
  if (data.type === 'stats_update' && data.data) {
    const statsData = data.data

    stats.value[0].value = statsData.daily_active_users || 0
    stats.value[1].value = statsData.ai_requests?.total || 0
    stats.value[2].value = statsData.token_usage || '--'
    stats.value[3].value = `${statsData.api_connectivity?.healthy_endpoints || 0}/${
      statsData.api_connectivity?.total_endpoints || 0
    }`
    stats.value[4].value = `${statsData.jwt_availability?.success_rate?.toFixed(1) || 0}%`
  }
}

/**
 * WebSocket 连接成功
 */
function handleWebSocketConnected() {
  connectionStatus.value = 'connected'
  message.success('实时连接已建立')
  stopPolling()
}

/**
 * WebSocket 断开连接
 */
function handleWebSocketDisconnected() {
  connectionStatus.value = 'disconnected'
  startPolling()
}

/**
 * WebSocket 错误
 */
function handleWebSocketError(error) {
  console.error('WebSocket 错误:', error)
  connectionStatus.value = 'error'
  startPolling()
}

/**
 * 启动 HTTP 轮询
 */
function startPolling() {
  if (pollingTimer) return

  connectionStatus.value = 'polling'
  message.warning('WebSocket 不可用，已降级为轮询模式')

  loadDashboardStats()
  loadRecentLogs()
  loadChartData()

  pollingTimer = setInterval(() => {
    loadDashboardStats()
    loadRecentLogs()
    loadChartData()
  }, dashboardConfig.value.http_poll_interval * 1000)
}

/**
 * 停止 HTTP 轮询
 */
function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

/**
 * 点击统计卡片（打开详情弹窗）
 */
function handleStatClick(stat) {
  if (stat.id === 4) {
    showApiModal.value = true
  } else {
    selectedStat.value = stat
    showStatDetailModal.value = true
  }
}

/**
 * 切换日志级别
 */
function handleLogFilterChange() {
  loadRecentLogs()
}

/**
 * 刷新日志
 */
function handleLogRefresh() {
  loadRecentLogs()
}

/**
 * 切换图表时间范围
 */
function handleTimeRangeChange(range) {
  chartTimeRange.value = range
  loadChartData()
}

/**
 * 保存配置
 */
async function handleConfigSave(config) {
  try {
    await updateStatsConfig(config)
    dashboardConfig.value = { ...config }
    message.success('配置已保存')

    if (connectionStatus.value === 'polling') {
      stopPolling()
      startPolling()
    }
  } catch (error) {
    console.error('保存配置失败:', error)
    message.error('保存配置失败')
  }
}

/**
 * 处理服务器指标更新
 */
function handleMetricsUpdate(metrics) {
  console.log('[Dashboard] 服务器指标更新:', metrics)
}


// 生命周期钩子
onMounted(() => {
  nextTick(() => {
    loadDashboardStats()
    loadRecentLogs()
    loadDashboardConfig()
    loadChartData()
  })
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <div class="dashboard-container">
    <WebSocketClient
      v-if="wsUrl"
      :url="wsUrl"
      :token="getToken()"
      @message="handleWebSocketMessage"
      @connected="handleWebSocketConnected"
      @disconnected="handleWebSocketDisconnected"
      @error="handleWebSocketError"
    />

    <!-- Header Stats -->
    <StatsBanner 
      :stats="stats" 
      :loading="statsLoading" 
      @stat-click="handleStatClick" 
    />

    <!-- Main Grid Layout -->
    <div class="main-grid">
       <!-- Left: Monitoring Panel (75%) -->
       <div class="monitor-area">
          <MonitorPanel 
            :chart-data="chartData"
            :chart-time-range="chartTimeRange"
            :stats-loading="statsLoading"
            :logs="logs"
            :logs-loading="logsLoading"
            :dashboard-config="dashboardConfig"
            @time-range-change="handleTimeRangeChange"
            @log-click="() => {}"
            @log-filter-change="handleLogFilterChange"
            @log-refresh="handleLogRefresh"
            @metrics-update="handleMetricsUpdate"
          />
       </div>

       <!-- Right: Control Center (25%) -->
       <div class="control-area">
          <ControlCenter 
            :quick-access-cards="quickAccessCards"
            @update:quick-access-cards="saveCardOrder"
            @reset-layout="resetCardOrder"
            @show-supabase-modal="showSupabaseModal = true"
          />
       </div>
    </div>


    <!-- Dialogs -->
    <PollingConfig
      v-model:show="showConfigModal"
      :config="dashboardConfig"
      @save="handleConfigSave"
    />
    <StatDetailModal v-model:show="showStatDetailModal" :stat="selectedStat" />
    <ApiConnectivityModal v-model:show="showApiModal" />
    <NModal
      v-model:show="showSupabaseModal"
      preset="card"
      title="Supabase 连接状态"
      style="width: 600px"
    >
      <SupabaseStatusCard
        :auto-refresh="true"
        :refresh-interval="30"
        @status-change="() => {}"
      />
    </NModal>
  </div>
</template>

<style scoped>
.dashboard-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px;
  min-height: 100vh;
  background: var(--claude-bg-warm);
  /* Optional: mesh gradient background for premium feel */
  background-image: 
      radial-gradient(at 0% 0%, rgba(200, 220, 255, 0.3) 0px, transparent 50%),
      radial-gradient(at 100% 0%, rgba(255, 220, 200, 0.3) 0px, transparent 50%);
}

.main-grid {
  display: grid;
  grid-template-columns: 3fr 1fr;
  gap: 24px;
  flex: 1;
}

/* Response Layout */
@media (max-width: 1200px) {
  .main-grid {
    grid-template-columns: 1fr;
  }
}
</style>
