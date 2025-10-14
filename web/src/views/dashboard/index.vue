<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useMessage, NButton } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { useUserStore } from '@/store'
import { getToken } from '@/utils'
import draggable from 'vuedraggable'

// Dashboard 组件
import StatsBanner from '@/components/dashboard/StatsBanner.vue'
import LogWindow from '@/components/dashboard/LogWindow.vue'
import UserActivityChart from '@/components/dashboard/UserActivityChart.vue'
import WebSocketClient from '@/components/dashboard/WebSocketClient.vue'
import PollingConfig from '@/components/dashboard/PollingConfig.vue'
import StatDetailModal from '@/components/dashboard/StatDetailModal.vue'
import ModelSwitcher from '@/components/dashboard/ModelSwitcher.vue'
import PromptSelector from '@/components/dashboard/PromptSelector.vue'
import SupabaseStatusCard from '@/components/dashboard/SupabaseStatusCard.vue'
import ServerLoadCard from '@/components/dashboard/ServerLoadCard.vue'
import QuickAccessCard from '@/components/dashboard/QuickAccessCard.vue'
import ApiConnectivityModal from '@/components/dashboard/ApiConnectivityModal.vue'
import HeroIcon from '@/components/common/HeroIcon.vue'

// Dashboard API
import {
  getDashboardStats,
  getRecentLogs,
  getStatsConfig,
  updateStatsConfig,
  createWebSocketUrl,
} from '@/api/dashboard'

defineOptions({ name: 'DashboardIndex' })

const userStore = useUserStore()
const { userInfo } = storeToRefs(userStore)
const message = useMessage()

// 响应式状态
const connectionStatus = ref('disconnected') // 'connected' | 'disconnected' | 'connecting' | 'error' | 'polling'
const statsLoading = ref(false)
const logsLoading = ref(false)
const showConfigModal = ref(false)
const showStatDetailModal = ref(false)
const showApiModal = ref(false)
const selectedStat = ref(null)

// 统计数据（图标已改为 Heroicons 名称）
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
    label: 'JWT 可获取性',
    value: '0%',
    trend: 0,
    color: '#8a2be2',
    detail: 'JWT 获取成功率',
  },
])

// 日志数据
const logs = ref([])

// 图表数据
const chartTimeRange = ref('24h')
const chartData = ref([])

// 默认快速访问卡片配置
const defaultQuickAccessCards = [
  // 核心 AI 管理卡片（4 个强关联）
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

  // 内容管理
  {
    icon: 'folder',
    title: '目录管理',
    description: '管理内容分类和标签',
    path: '/catalog',
    iconColor: '#da7756', // Claude Terra Cotta 主色
  },

  // 测试工具
  {
    icon: 'key',
    title: 'JWT 测试',
    description: '测试 JWT 认证',
    path: '/ai/jwt',
    iconColor: '#f0a020',
  },
]

// 从 localStorage 加载保存的卡片顺序
const loadSavedCardOrder = () => {
  try {
    const saved = localStorage.getItem('dashboard_card_order')
    if (saved) {
      const savedOrder = JSON.parse(saved)
      // 验证保存的数据是否有效
      if (Array.isArray(savedOrder) && savedOrder.length === defaultQuickAccessCards.length) {
        return savedOrder
      }
    }
  } catch (error) {
    console.error('加载卡片顺序失败:', error)
  }
  return defaultQuickAccessCards
}

// 快速访问卡片配置（响应式）
const quickAccessCards = ref(loadSavedCardOrder())

// 保存卡片顺序到 localStorage
const saveCardOrder = () => {
  try {
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

// 拖拽结束事件
const onDragEnd = () => {
  saveCardOrder()
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

    // 处理响应格式（兼容两种格式）
    // 格式1: {code: 200, data: {...}}
    // 格式2: {...} (直接返回数据)
    let data = response
    if (response.data && typeof response.data === 'object') {
      data = response.data
    }

    // 更新统计数据
    stats.value[0].value = data.daily_active_users || 0
    stats.value[1].value = data.ai_requests?.total || 0
    stats.value[2].value = data.token_usage || '--'
    stats.value[3].value = `${data.api_connectivity?.healthy_endpoints || 0}/${
      data.api_connectivity?.total_endpoints || 0
    }`
    stats.value[4].value = `${data.jwt_availability?.success_rate?.toFixed(1) || 0}%`

    // 更新 API 连通性率
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

    // 处理响应格式（兼容两种格式）
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
 * 加载 Dashboard 配置
 */
async function loadDashboardConfig() {
  try {
    const response = await getStatsConfig()

    // 处理响应格式（兼容两种格式）
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

    // 更新统计数据
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

  // 停止 HTTP 轮询
  stopPolling()
}

/**
 * WebSocket 断开连接
 */
function handleWebSocketDisconnected() {
  connectionStatus.value = 'disconnected'

  // 降级为 HTTP 轮询
  startPolling()
}

/**
 * WebSocket 错误
 */
function handleWebSocketError(error) {
  console.error('WebSocket 错误:', error)
  connectionStatus.value = 'error'

  // 降级为 HTTP 轮询
  startPolling()
}

/**
 * 启动 HTTP 轮询
 */
function startPolling() {
  if (pollingTimer) return

  connectionStatus.value = 'polling'
  message.warning('WebSocket 不可用，已降级为轮询模式')

  // 立即加载一次
  loadDashboardStats()
  loadRecentLogs()

  // 定时轮询
  pollingTimer = setInterval(() => {
    loadDashboardStats()
    loadRecentLogs()
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
  // 如果点击的是 API 连通性卡片，打开 API 详情弹窗
  if (stat.id === 4) {
    showApiModal.value = true
  } else {
    selectedStat.value = stat
    showStatDetailModal.value = true
  }
}

/**
 * 点击日志项
 */
function handleLogClick() {
  // LogWindow 组件内部已处理复制逻辑
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
  // 这里可以加载对应时间范围的数据
}

/**
 * 保存配置
 */
async function handleConfigSave(config) {
  try {
    await updateStatsConfig(config)
    dashboardConfig.value = { ...config }
    message.success('配置已保存')

    // 如果是轮询模式，重启轮询
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
 * 处理模型切换
 */
function handleModelChange(modelId) {
  console.log('[Dashboard] 模型已切换，新模型 ID:', modelId)
  // 模型切换后可以触发相关数据刷新（如需要）
  // 当前仅记录日志，后续可扩展
}

/**
 * 处理 Prompt 切换
 */
function handlePromptChange(promptId) {
  console.log('[Dashboard] Prompt 已切换，新 Prompt ID:', promptId)
}

/**
 * 处理 Supabase 状态变化
 */
function handleSupabaseStatusChange(status) {
  console.log('[Dashboard] Supabase 状态变化:', status)
}

/**
 * 处理服务器指标更新
 */
function handleMetricsUpdate(metrics) {
  console.log('[Dashboard] 服务器指标更新:', metrics)
}

/**
 * 处理快速访问卡片点击
 */
function handleQuickAccessClick(path) {
  console.log('[Dashboard] 快速访问卡片点击，路径:', path)
}

// 生命周期钩子
onMounted(() => {
  nextTick(() => {
    // 加载初始数据
    loadDashboardStats()
    loadRecentLogs()
    loadDashboardConfig()
  })
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <div class="dashboard-container">
    <!-- WebSocket 客户端（无 UI） -->
    <WebSocketClient
      v-if="wsUrl"
      :url="wsUrl"
      :token="getToken()"
      @message="handleWebSocketMessage"
      @connected="handleWebSocketConnected"
      @disconnected="handleWebSocketDisconnected"
      @error="handleWebSocketError"
    />

    <!-- 统计横幅（包含实时指示器和操作按钮） -->
    <StatsBanner :stats="stats" :loading="statsLoading" @stat-click="handleStatClick" />

    <!-- 快速访问卡片组（支持拖拽重排） -->
    <div class="quick-access-header">
      <h2 class="section-title">快速访问</h2>
      <NButton text @click="resetCardOrder">
        <template #icon>
          <HeroIcon name="arrow-path" :size="18" color="var(--claude-terra-cotta)" />
        </template>
        重置布局
      </NButton>
    </div>
    <draggable
      v-model="quickAccessCards"
      class="quick-access-section"
      item-key="path"
      :animation="300"
      :delay="100"
      :delay-on-touch-only="true"
      ghost-class="ghost-card"
      chosen-class="chosen-card"
      drag-class="drag-card"
      @end="onDragEnd"
    >
      <template #item="{ element }">
        <QuickAccessCard
          :icon="element.icon"
          :title="element.title"
          :description="element.description"
          :path="element.path"
          :icon-color="element.iconColor"
          @click="handleQuickAccessClick"
        />
      </template>
    </draggable>

    <!-- 控制面板：模型切换器 + Prompt 选择器 + Supabase 状态 + 服务器负载 -->
    <div class="dashboard-controls">
      <ModelSwitcher :compact="false" @change="handleModelChange" />
      <PromptSelector :compact="false" @change="handlePromptChange" />
      <SupabaseStatusCard
        :auto-refresh="true"
        :refresh-interval="30"
        @status-change="handleSupabaseStatusChange"
      />
      <ServerLoadCard
        :auto-refresh="true"
        :refresh-interval="60"
        @metrics-update="handleMetricsUpdate"
      />
    </div>

    <!-- 主内容区域：Grid 两列布局 -->
    <div class="dashboard-main">
      <!-- 左侧：Log 小窗 -->
      <div class="dashboard-left">
        <LogWindow
          :logs="logs"
          :loading="logsLoading"
          @log-click="handleLogClick"
          @filter-change="handleLogFilterChange"
          @refresh="handleLogRefresh"
        />
      </div>

      <!-- 右侧：用户活跃度图表 -->
      <div class="dashboard-right">
        <UserActivityChart
          :time-range="chartTimeRange"
          :data="chartData"
          :loading="statsLoading"
          @time-range-change="handleTimeRangeChange"
        />
      </div>
    </div>

    <!-- 配置弹窗 -->
    <PollingConfig
      v-model:show="showConfigModal"
      :config="dashboardConfig"
      @save="handleConfigSave"
    />

    <!-- 统计详情弹窗 -->
    <StatDetailModal v-model:show="showStatDetailModal" :stat="selectedStat" />

    <!-- API 连通性详情弹窗 -->
    <ApiConnectivityModal v-model:show="showApiModal" />
  </div>
</template>

<style scoped>
/* ========== Claude 设计系统（Design Tokens 已在全局导入） ========== */

.dashboard-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg); /* 从 24px 减少到 16px */
  padding: var(--spacing-xl); /* 从 24px 减少到 20px */
  min-height: auto;
  /* Claude 暖白背景 */
  background: var(--claude-bg-warm);
}

/* ========== 快速访问区域标题 ========== */
.quick-access-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-md);
}

.section-title {
  font-family: var(--font-serif);
  font-size: 24px;
  font-weight: var(--font-weight-semibold);
  color: var(--claude-black);
  margin: 0;
  letter-spacing: -0.01em;
}

/* ========== 快速访问卡片组（网格布局 + 拖拽支持） ========== */
.quick-access-section {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--spacing-lg); /* 保持 16px */
}

/* ========== 拖拽状态样式 ========== */
.ghost-card {
  opacity: 0.4;
  background: var(--claude-hover-bg);
  border: 2px dashed var(--claude-terra-cotta);
  transform: rotate(2deg);
}

.chosen-card {
  cursor: move;
  box-shadow: var(--shadow-float);
  transform: scale(1.05);
  transition: all var(--duration-normal) cubic-bezier(0.4, 0, 0.2, 1);
}

.drag-card {
  opacity: 0.8;
  transform: rotate(-2deg);
  cursor: grabbing;
}

/* ========== 控制面板区域（2 列网格） ========== */
.dashboard-controls {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-lg); /* 从 20px 减少到 16px */
  margin: var(--spacing-md) 0; /* 从 16px 减少到 12px */
}

/* ========== 主内容区域（60% + 40% 网格） ========== */
.dashboard-main {
  display: grid;
  grid-template-columns: 60% 40%;
  gap: var(--spacing-lg); /* 从 24px 减少到 16px */
  min-height: 600px;
}

.dashboard-left {
  min-width: 0;
}

.dashboard-right {
  min-width: 0;
}

/* ========== 响应式布局 ========== */
@media (max-width: 1400px) {
  .dashboard-main {
    grid-template-columns: 55% 45%;
  }
}

@media (max-width: 1200px) {
  .dashboard-controls {
    grid-template-columns: 1fr;
  }

  .dashboard-main {
    grid-template-columns: 1fr;
    min-height: auto;
  }
}

@media (max-width: 768px) {
  .dashboard-container {
    padding: 16px;
    gap: 16px;
  }

  .dashboard-header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
    padding: 24px 20px;
  }

  .header-left {
    width: 100%;
  }

  .header-right {
    width: 100%;
    justify-content: flex-end;
  }

  .dashboard-title {
    font-size: 24px;
  }

  .quick-access-section {
    gap: 12px;
  }
}
</style>
