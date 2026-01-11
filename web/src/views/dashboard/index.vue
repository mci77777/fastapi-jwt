<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useMessage, NButton, NSpace, NModal } from 'naive-ui'
import { getToken } from '@/utils'

// Dashboard Components
import StatsBanner from '@/components/dashboard/StatsBanner.vue'
import MonitorPanel from '@/components/dashboard/MonitorPanel.vue'
import ControlCenter from '@/components/dashboard/ControlCenter.vue'
import WebSocketClient from '@/components/dashboard/WebSocketClient.vue'
import PollingConfig from '@/components/dashboard/PollingConfig.vue'
import StatDetailModal from '@/components/dashboard/StatDetailModal.vue'
import MappedModelsModal from '@/components/dashboard/MappedModelsModal.vue'
import SupabaseStatusCard from '@/components/dashboard/SupabaseStatusCard.vue'
import ModelObservabilityCard from '@/components/dashboard/ModelObservabilityCard.vue'
import ModelSwitcher from '@/components/dashboard/ModelSwitcher.vue'
import PromptSelector from '@/components/dashboard/PromptSelector.vue'

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
const showMappedModelsModal = ref(false)
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
    detail: 'Token 消耗总量（从对话响应 usage 汇总）',
  },
  {
    id: 4,
    icon: 'signal',
    label: '映射模型可用性',
    value: '0/0',
    trend: 0,
    color: '#00bcd4',
    detail: '映射模型是否可路由（resolve_model_key）+ 调用聚合',
  },
  {
    id: 5,
    icon: 'key',
    label: 'JWT 连通性',
    value: '0%',
    trend: 0,
    color: '#8a2be2',
    detail: 'JWKS 连通性（辅以验证统计）',
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
    icon: 'map',
    title: '模型映射',
    description: '配置模型映射关系',
    path: '/ai',
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

const connectionBadge = computed(() => {
  const status = String(connectionStatus.value || 'disconnected')
  if (status === 'connected') {
    return { label: '实时', tone: 'good' }
  }
  if (status === 'polling') {
    return { label: '轮询', tone: 'warn' }
  }
  if (status === 'connecting') {
    return { label: '连接中', tone: 'neutral' }
  }
  if (status === 'error') {
    return { label: '异常', tone: 'bad' }
  }
  return { label: '断开', tone: 'neutral' }
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
    stats.value[2].value = data.token_usage ?? '--'
    stats.value[3].value = `${data.mapped_models?.available || 0}/${data.mapped_models?.total || 0}`
    stats.value[4].value = `${data.jwt_availability?.success_rate?.toFixed(1) || 0}%`

    if (data.mapped_models) {
      const rate = data.mapped_models.availability_rate || 0
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

    const payload = response?.data && typeof response.data === 'object' ? response.data : response
    const series = Array.isArray(payload?.series) ? payload.series : []
    chartData.value = series
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
    stats.value[2].value = statsData.token_usage ?? '--'
    stats.value[3].value = `${statsData.mapped_models?.available || 0}/${statsData.mapped_models?.total || 0}`
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
    showMappedModelsModal.value = true
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

function refreshDashboard() {
  loadDashboardStats()
  loadRecentLogs()
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

    <!-- Header -->
    <div class="dash-header">
      <div class="dash-title">
        <div class="dash-title-text">Dashboard</div>
        <div class="dash-subtitle">系统概览 · 观测 · 操作</div>
      </div>
      <div class="dash-actions">
        <div class="dash-connection" :data-tone="connectionBadge.tone">
          <span class="dash-connection-dot" />
          <span class="dash-connection-text">{{ connectionBadge.label }}</span>
        </div>
        <NSpace :size="8">
          <NButton size="small" secondary :loading="statsLoading || logsLoading" @click="refreshDashboard">
            刷新
          </NButton>
          <NButton size="small" secondary @click="showConfigModal = true">设置</NButton>
        </NSpace>
      </div>
    </div>

    <!-- Overview -->
    <div class="dash-section">
      <div class="dash-section-head">
        <div class="dash-section-title">概览</div>
      </div>
      <StatsBanner :stats="stats" :loading="statsLoading" @stat-click="handleStatClick" />
    </div>

    <!-- Main Grid Layout -->
    <div class="main-grid">
      <!-- Left: Observability -->
      <div class="monitor-area">
        <div class="dash-section-head">
          <div class="dash-section-title">观测</div>
        </div>
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

      <!-- Right: Actions -->
      <div class="control-area">
        <div class="dash-section-head">
          <div class="dash-section-title">操作</div>
        </div>

        <div class="glass-panel main-controls">
          <div class="controls-header">
            <div class="controls-title">核心配置</div>
            <div class="controls-subtitle">AI 供应商 / 映射模型 / Prompt</div>
          </div>
          <div class="controls-grid">
            <ModelSwitcher :compact="false" />
            <PromptSelector :compact="false" />
          </div>
        </div>

        <ControlCenter
          :quick-access-cards="quickAccessCards"
          @update:quick-access-cards="saveCardOrder"
          @reset-layout="resetCardOrder"
          @show-supabase-modal="showSupabaseModal = true"
        />
      </div>
    </div>

    <div class="dash-section">
      <div class="dash-section-head">
        <div class="dash-section-title">模型与映射</div>
      </div>
      <ModelObservabilityCard />
    </div>

    <!-- Dialogs -->
    <PollingConfig
      v-model:show="showConfigModal"
      :config="dashboardConfig"
      @save="handleConfigSave"
    />
    <StatDetailModal v-model:show="showStatDetailModal" :stat="selectedStat" />
    <MappedModelsModal v-model:show="showMappedModelsModal" />
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

<style scoped lang="scss">
@use './dashboard-tokens.scss';

.dashboard-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 24px;
  min-height: 100vh;
  background: var(--dash-bg);
}

.dash-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.dash-title-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--dash-text);
  line-height: 1.2;
}

.dash-subtitle {
  margin-top: 6px;
  font-size: 12px;
  color: var(--dash-text-secondary);
}

.dash-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dash-connection {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--dash-border);
  background: var(--dash-surface);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  color: var(--dash-text);
  font-size: 12px;
}

.dash-connection-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--dash-text-secondary);
}

.dash-connection[data-tone='good'] .dash-connection-dot {
  background: var(--dash-good);
}

.dash-connection[data-tone='warn'] .dash-connection-dot {
  background: var(--dash-warn);
}

.dash-connection[data-tone='bad'] .dash-connection-dot {
  background: var(--dash-bad);
}

.dash-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dash-section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.dash-section-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--dash-text-secondary);
}

.glass-panel {
  background: var(--dash-surface);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-radius: var(--dash-radius);
  border: 1px solid var(--dash-border);
  box-shadow: var(--dash-shadow);
  overflow: hidden;
}

.main-controls {
  padding: 16px;
}

.controls-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}

.controls-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--dash-text);
}

.controls-subtitle {
  font-size: 12px;
  color: var(--dash-text-secondary);
}

.controls-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
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
  .dash-header {
    flex-direction: column;
    align-items: stretch;
  }
  .dash-actions {
    justify-content: space-between;
  }
  .controls-grid {
    grid-template-columns: 1fr;
  }
}
</style>
