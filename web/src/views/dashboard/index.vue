<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue'
import {
  NButton,
  NCard,
  NDivider,
  NEmpty,
  NGrid,
  NGridItem,
  NSpace,
  NTable,
  NTag,
  NTooltip,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useAiModelSuiteStore, useUserStore } from '@/store'
import api from '@/api'

defineOptions({ name: 'GlobalWorkbench' })

const store = useAiModelSuiteStore()
const userStore = useUserStore()
const { models, mappings, modelsLoading, mappingsLoading } = storeToRefs(store)
const { userInfo } = storeToRefs(userStore)
const router = useRouter()

const totalEndpoints = computed(() => models.value.length)
const defaultEndpoint = computed(() => models.value.find((item) => item.is_default))
const activeEndpoints = computed(() => models.value.filter((item) => item.is_active).length)
const syncedEndpoints = computed(
  () => models.value.filter((item) => item.sync_status === 'synced').length
)
const monitoredEndpoints = computed(
  () => models.value.filter((item) => item.status === 'online').length
)
const aggregatedModels = computed(() => store.modelCandidates.length)
const mappingScopeStats = computed(() => {
  const stats = new Map()
  mappings.value.forEach((item) => {
    const current = stats.get(item.scope_type) || 0
    stats.set(item.scope_type, current + 1)
  })
  return Array.from(stats.entries()).map(([scope, count]) => ({ scope, count }))
})

function goToCatalog() {
  router.push('/ai/catalog')
}

function goToMapping() {
  router.push('/ai/mapping')
}

function goToJwt() {
  router.push('/ai/jwt')
}

// 系统模块快捷入口
const systemModules = [
  {
    name: '用户管理',
    path: '/system/user',
    icon: '👥',
    desc: '管理系统用户账户',
    color: '#18a058',
  },
  {
    name: '角色管理',
    path: '/system/role',
    icon: '🎭',
    desc: '配置角色权限',
    color: '#2080f0',
  },
  {
    name: '菜单管理',
    path: '/system/menu',
    icon: '📋',
    desc: '维护系统菜单',
    color: '#f0a020',
  },
  {
    name: 'API权限',
    path: '/system/api',
    icon: '🔌',
    desc: '管理API访问权限',
    color: '#d03050',
  },
  {
    name: '审计日志',
    path: '/system/auditlog',
    icon: '📝',
    desc: '查看系统操作日志',
    color: '#8a2be2',
  },
  {
    name: 'AI配置',
    path: '/system/ai',
    icon: '⚙️',
    desc: 'AI服务配置管理',
    color: '#00bcd4',
  },
]

function navigateToModule(path) {
  router.push(path)
}

// 系统健康状态
const systemHealth = ref({
  status: 'unknown',
  service: 'GymBro',
  loading: false,
})

// 系统统计数据（从 Prometheus 指标解析）
const systemStats = ref({
  totalRequests: 0,
  errorRate: 0,
  activeConnections: 0,
  rateLimitBlocks: 0,
})

// Supabase 状态
const supabaseStatus = ref(null)

// 监控状态
const monitorStatus = ref({
  is_running: false,
  interval_seconds: 60,
  last_run_at: null,
})

let pollingTimer = null

const endpointRows = computed(() =>
  models.value.map((item) => ({
    ...item,
    candidateCount: Array.isArray(item.model_list) ? item.model_list.length : 0,
  }))
)

const mappingRows = computed(() =>
  mappings.value.map((item) => ({
    ...item,
    candidateCount: Array.isArray(item.candidates) ? item.candidates.length : 0,
  }))
)

async function loadHealthStatus() {
  try {
    systemHealth.value.loading = true
    const response = await api.getHealthStatus()
    systemHealth.value.status = response.data?.status || 'unknown'
    systemHealth.value.service = response.data?.service || 'GymBro'
  } catch (error) {
    systemHealth.value.status = 'error'
  } finally {
    systemHealth.value.loading = false
  }
}

async function loadSystemMetrics() {
  try {
    const response = await api.getSystemMetrics()
    let metricsText = ''

    if (typeof response === 'string') {
      metricsText = response
    } else if (response.data) {
      metricsText = response.data
    } else if (response.error) {
      metricsText = response.error
    }

    const authTotal = parseMetric(metricsText, 'auth_requests_total')
    const authErrors = parseMetric(metricsText, 'jwt_validation_errors_total')
    const activeConns = parseMetric(metricsText, 'active_connections')
    const rateLimitBlocks = parseMetric(metricsText, 'rate_limit_blocks_total')

    systemStats.value = {
      totalRequests: authTotal,
      errorRate: authTotal > 0 ? ((authErrors / authTotal) * 100).toFixed(2) : 0,
      activeConnections: activeConns,
      rateLimitBlocks: rateLimitBlocks,
    }
  } catch (error) {
    if (error.error && typeof error.error === 'string') {
      const metricsText = error.error
      const authTotal = parseMetric(metricsText, 'auth_requests_total')
      const authErrors = parseMetric(metricsText, 'jwt_validation_errors_total')
      const activeConns = parseMetric(metricsText, 'active_connections')
      const rateLimitBlocks = parseMetric(metricsText, 'rate_limit_blocks_total')

      systemStats.value = {
        totalRequests: authTotal,
        errorRate: authTotal > 0 ? ((authErrors / authTotal) * 100).toFixed(2) : 0,
        activeConnections: activeConns,
        rateLimitBlocks: rateLimitBlocks,
      }
    }
  }
}

function parseMetric(metricsText, metricName) {
  const regex = new RegExp(`${metricName}(?:{[^}]*})?\\s+(\\d+(?:\\.\\d+)?)`, 'g')
  let total = 0
  let match
  while ((match = regex.exec(metricsText)) !== null) {
    total += parseFloat(match[1])
  }
  return total
}

async function loadSupabaseStatus() {
  try {
    const response = await api.getSupabaseStatus()
    supabaseStatus.value = response.data || null
  } catch (error) {
    supabaseStatus.value = { status: 'offline', detail: error.message }
  }
}

async function loadMonitorStatus() {
  try {
    const response = await api.getMonitorStatus()
    const data = response.data || {}
    monitorStatus.value = {
      is_running: !!data.is_running,
      interval_seconds: data.interval_seconds ?? 60,
      last_run_at: data.last_run_at ?? null,
    }
  } catch (error) {
    monitorStatus.value.is_running = false
  }
}

async function loadAllStatus() {
  await Promise.all([
    loadHealthStatus(),
    loadSystemMetrics(),
    loadSupabaseStatus(),
    loadMonitorStatus(),
  ])
}

function startPolling() {
  loadAllStatus()
  pollingTimer = setInterval(() => {
    loadAllStatus()
  }, 10000)
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

onMounted(() => {
  if (!models.value.length) {
    store.loadModels()
  }
  if (!mappings.value.length) {
    store.loadMappings()
  }
  store.loadPrompts()

  startPolling()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <div class="workbench-container">
    <div class="hero-header">
      <div class="hero-content">
        <div class="hero-main">
          <h1 class="hero-title">
            <span class="wave-emoji">👋</span>
            {{ userInfo?.username || '管理员' }}，欢迎回来
          </h1>
          <p class="hero-subtitle">GymBro 管理控制台 - 全局工作台</p>
        </div>
        <div class="hero-stats">
          <div class="hero-stat-item">
            <div class="stat-value">
              <span
                :style="{
                  color: systemHealth.status === 'ok' ? '#18a058' : '#d03050',
                }"
              >
                {{ systemHealth.status === 'ok' ? '✓' : '✗' }}
              </span>
            </div>
            <div class="stat-label">系统状态</div>
          </div>
          <div class="hero-stat-divider"></div>
          <div class="hero-stat-item">
            <div class="stat-value">{{ systemStats.totalRequests }}</div>
            <div class="stat-label">总请求数</div>
          </div>
          <div class="hero-stat-divider"></div>
          <div class="hero-stat-item">
            <div class="stat-value">{{ systemStats.errorRate }}%</div>
            <div class="stat-label">错误率</div>
          </div>
          <div class="hero-stat-divider"></div>
          <div class="hero-stat-item">
            <div class="stat-value">{{ systemStats.activeConnections }}</div>
            <div class="stat-label">活跃连接</div>
          </div>
        </div>
      </div>
    </div>

    <NCard title="🚀 快捷入口" size="small" class="modules-card">
      <div class="modules-grid">
        <div
          v-for="module in systemModules"
          :key="module.path"
          class="module-card"
          @click="navigateToModule(module.path)"
        >
          <div class="module-icon" :style="{ backgroundColor: module.color }">
            {{ module.icon }}
          </div>
          <div class="module-info">
            <div class="module-name">{{ module.name }}</div>
            <div class="module-desc">{{ module.desc }}</div>
          </div>
        </div>
      </div>
    </NCard>

    <NCard title="📊 系统监控" size="small" class="monitoring-card">
      <NGrid cols="2 640:4" responsive="screen" x-gap="16" y-gap="16">
        <NGridItem>
          <div class="mini-stat-card">
            <div class="mini-stat-icon">🔐</div>
            <div class="mini-stat-content">
              <div class="mini-stat-value">{{ systemStats.totalRequests }}</div>
              <div class="mini-stat-label">认证请求</div>
            </div>
          </div>
        </NGridItem>
        <NGridItem>
          <div class="mini-stat-card">
            <div class="mini-stat-icon">⚠️</div>
            <div class="mini-stat-content">
              <div class="mini-stat-value">{{ systemStats.errorRate }}%</div>
              <div class="mini-stat-label">错误率</div>
            </div>
          </div>
        </NGridItem>
        <NGridItem>
          <div class="mini-stat-card">
            <div class="mini-stat-icon">🔗</div>
            <div class="mini-stat-content">
              <div class="mini-stat-value">{{ systemStats.activeConnections }}</div>
              <div class="mini-stat-label">活跃连接</div>
            </div>
          </div>
        </NGridItem>
        <NGridItem>
          <div class="mini-stat-card">
            <div class="mini-stat-icon">🛡️</div>
            <div class="mini-stat-content">
              <div class="mini-stat-value">{{ systemStats.rateLimitBlocks }}</div>
              <div class="mini-stat-label">限流拦截</div>
            </div>
          </div>
        </NGridItem>
      </NGrid>
      <NDivider style="margin: 20px 0" />
      <NSpace vertical :size="12">
        <div class="status-row">
          <span class="status-label">Supabase:</span>
          <NTag
            :type="supabaseStatus?.status === 'online' ? 'success' : 'error'"
            size="small"
            :bordered="false"
          >
            {{ supabaseStatus?.status || '未知' }}
          </NTag>
          <span v-if="supabaseStatus?.latency_ms" class="status-detail">
            {{ supabaseStatus.latency_ms.toFixed(0) }}ms
          </span>
        </div>
        <div class="status-row">
          <span class="status-label">端点监控:</span>
          <NTag
            :type="monitorStatus.is_running ? 'success' : 'default'"
            size="small"
            :bordered="false"
          >
            {{ monitorStatus.is_running ? '运行中' : '已停止' }}
          </NTag>
          <span v-if="monitorStatus.last_run_at" class="status-detail">
            最近: {{ monitorStatus.last_run_at }}
          </span>
        </div>
        <div class="status-row">
          <span class="status-label">用户类型:</span>
          <NTag
            :type="userInfo?.user_type === 'permanent' ? 'success' : 'warning'"
            size="small"
            :bordered="false"
          >
            {{ userInfo?.user_type === 'permanent' ? '永久用户' : '匿名用户' }}
          </NTag>
        </div>
      </NSpace>
    </NCard>

    <NCard title="🤖 AI模型能力" size="small" class="ai-card">
      <NGrid cols="2 640:3 960:6" responsive="screen" x-gap="16" y-gap="16">
        <NGridItem>
          <div class="mini-stat-card">
            <div class="mini-stat-icon">📊</div>
            <div class="mini-stat-content">
              <div class="mini-stat-value">{{ totalEndpoints }}</div>
              <div class="mini-stat-label">端点数量</div>
            </div>
          </div>
        </NGridItem>
        <NGridItem>
          <div class="mini-stat-card">
            <div class="mini-stat-icon">✅</div>
            <div class="mini-stat-content">
              <div class="mini-stat-value">{{ activeEndpoints }}</div>
              <div class="mini-stat-label">已启用</div>
            </div>
          </div>
        </NGridItem>
        <NGridItem>
          <div class="mini-stat-card">
            <div class="mini-stat-icon">🔄</div>
            <div class="mini-stat-content">
              <div class="mini-stat-value">{{ syncedEndpoints }}</div>
              <div class="mini-stat-label">已同步</div>
            </div>
          </div>
        </NGridItem>
        <NGridItem>
          <div class="mini-stat-card">
            <div class="mini-stat-icon">🟢</div>
            <div class="mini-stat-content">
              <div class="mini-stat-value">{{ monitoredEndpoints }}</div>
              <div class="mini-stat-label">在线</div>
            </div>
          </div>
        </NGridItem>
        <NGridItem v-if="aggregatedModels">
          <div class="mini-stat-card">
            <div class="mini-stat-icon">🤖</div>
            <div class="mini-stat-content">
              <div class="mini-stat-value">{{ aggregatedModels }}</div>
              <div class="mini-stat-label">候选模型</div>
            </div>
          </div>
        </NGridItem>
        <NGridItem v-if="defaultEndpoint">
          <div class="mini-stat-card highlight">
            <div class="mini-stat-icon">⭐</div>
            <div class="mini-stat-content">
              <div class="mini-stat-value mini-stat-text">
                {{ defaultEndpoint.name || defaultEndpoint.model }}
              </div>
              <div class="mini-stat-label">默认端点</div>
            </div>
          </div>
        </NGridItem>
      </NGrid>
      <NDivider style="margin: 20px 0" />
      <div class="action-buttons">
        <NButton type="primary" size="medium" @click="goToCatalog">
          <template #icon>
            <span>📦</span>
          </template>
          管理端点
        </NButton>
        <NButton type="info" size="medium" @click="goToMapping">
          <template #icon>
            <span>🗺️</span>
          </template>
          模型映射
        </NButton>
        <NButton type="success" size="medium" @click="goToJwt">
          <template #icon>
            <span>🔬</span>
          </template>
          JWT测试
        </NButton>
      </div>
    </NCard>

    <NCard
      title="📊 端点状态"
      size="small"
      :loading="modelsLoading"
      class="status-card modern-card"
    >
      <template v-if="endpointRows.length">
        <div class="table-wrapper">
          <NTable :single-line="false" size="small" striped>
            <thead>
              <tr>
                <th style="min-width: 180px">名称</th>
                <th style="min-width: 200px">基础地址</th>
                <th style="width: 100px; text-align: center">候选模型</th>
                <th style="width: 100px; text-align: center">状态</th>
                <th style="width: 140px">最后检测</th>
                <th style="width: 100px; text-align: center">同步</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="endpoint in endpointRows" :key="endpoint.id">
                <td>
                  <div class="endpoint-name">
                    <div class="name-row">
                      <span class="name-text">{{ endpoint.name }}</span>
                      <NSpace :size="4" style="margin-left: 8px">
                        <NTag
                          v-if="endpoint.is_default"
                          type="primary"
                          size="tiny"
                          :bordered="false"
                        >
                          默认
                        </NTag>
                        <NTag
                          v-if="endpoint.is_active"
                          type="success"
                          size="tiny"
                          :bordered="false"
                        >
                          启用
                        </NTag>
                      </NSpace>
                    </div>
                    <div class="model-text">{{ endpoint.model || '未指定模型' }}</div>
                  </div>
                </td>
                <td>
                  <NTooltip trigger="hover">
                    <template #trigger>
                      <span class="url-text">{{ endpoint.base_url }}</span>
                    </template>
                    <template #default>
                      <div
                        v-for="(url, key) in endpoint.resolved_endpoints"
                        :key="key"
                        class="tooltip-line"
                      >
                        <strong>{{ key }}</strong
                        >：{{ url }}
                      </div>
                    </template>
                  </NTooltip>
                </td>
                <td style="text-align: center">
                  <span v-if="endpoint.candidateCount" class="count-badge">
                    {{ endpoint.candidateCount }}
                  </span>
                  <span v-else class="text-gray-400">--</span>
                </td>
                <td style="text-align: center">
                  <NTag
                    :type="
                      endpoint.status === 'online'
                        ? 'success'
                        : endpoint.status === 'offline'
                        ? 'error'
                        : 'warning'
                    "
                    size="small"
                    :bordered="false"
                  >
                    {{ endpoint.status || '未知' }}
                  </NTag>
                </td>
                <td>
                  <span class="time-text">{{ endpoint.last_checked_at || '--' }}</span>
                </td>
                <td style="text-align: center">
                  <NTag
                    :type="endpoint.sync_status === 'synced' ? 'success' : 'warning'"
                    size="small"
                    :bordered="false"
                  >
                    {{ endpoint.sync_status || '未同步' }}
                  </NTag>
                </td>
              </tr>
            </tbody>
          </NTable>
        </div>
      </template>
      <NEmpty v-else description="暂无端点信息" />
    </NCard>

    <NCard
      title="🗺️ 映射覆盖"
      size="small"
      :loading="mappingsLoading"
      class="mapping-card modern-card"
    >
      <div v-if="mappingScopeStats.length" class="scope-stats">
        <span class="stats-label">按业务域统计：</span>
        <NSpace wrap :size="8">
          <NTag
            v-for="item in mappingScopeStats"
            :key="item.scope"
            type="info"
            :bordered="false"
            size="small"
          >
            {{ item.scope }}：{{ item.count }}
          </NTag>
        </NSpace>
      </div>
      <template v-if="mappingRows.length">
        <div class="table-wrapper">
          <NTable :single-line="false" size="small" striped>
            <thead>
              <tr>
                <th style="width: 120px; text-align: center">业务域</th>
                <th style="min-width: 160px">对象名称</th>
                <th style="min-width: 140px">默认模型</th>
                <th>候选模型</th>
                <th style="width: 140px">更新时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="mapping in mappingRows" :key="mapping.id">
                <td style="text-align: center">
                  <NTag type="info" size="small" :bordered="false">
                    {{ mapping.scope_type }}
                  </NTag>
                </td>
                <td>
                  <span class="name-text">{{ mapping.name || mapping.scope_key }}</span>
                </td>
                <td>
                  <span class="model-text">{{ mapping.default_model || '--' }}</span>
                </td>
                <td>
                  <NSpace wrap :size="6">
                    <NTag
                      v-for="model in mapping.candidates"
                      :key="model"
                      size="small"
                      :bordered="false"
                      type="default"
                    >
                      {{ model }}
                    </NTag>
                  </NSpace>
                </td>
                <td>
                  <span class="time-text">{{ mapping.updated_at || '--' }}</span>
                </td>
              </tr>
            </tbody>
          </NTable>
        </div>
      </template>
      <NEmpty v-else description="暂无映射记录" />
    </NCard>
  </div>
</template>

<style scoped>
.workbench-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: 4px;
}

.hero-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  padding: 40px 32px;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
  margin-bottom: 4px;
  position: relative;
  overflow: hidden;
}

.hero-header::before {
  content: '';
  position: absolute;
  top: -50%;
  right: -20%;
  width: 500px;
  height: 500px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.1) 0%, transparent 70%);
  border-radius: 50%;
}

.hero-content {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 24px;
}

.hero-main {
  flex: 1;
  min-width: 300px;
}

.hero-title {
  margin: 0;
  font-size: 36px;
  font-weight: 700;
  color: white;
  letter-spacing: -0.5px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.wave-emoji {
  display: inline-block;
  animation: wave 2s infinite;
  transform-origin: 70% 70%;
}

@keyframes wave {
  0%,
  100% {
    transform: rotate(0deg);
  }
  10%,
  30% {
    transform: rotate(14deg);
  }
  20% {
    transform: rotate(-8deg);
  }
  40% {
    transform: rotate(14deg);
  }
  50% {
    transform: rotate(10deg);
  }
  60% {
    transform: rotate(0deg);
  }
}

.hero-subtitle {
  margin: 8px 0 0 0;
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 400;
}

.hero-stats {
  display: flex;
  gap: 24px;
  align-items: center;
}

.hero-stat-item {
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: white;
  line-height: 1;
  margin-bottom: 6px;
}

.stat-label {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.8);
  font-weight: 500;
}

.hero-stat-divider {
  width: 1px;
  height: 40px;
  background: rgba(255, 255, 255, 0.3);
}

.modules-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 16px;
}

.module-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.module-card:hover {
  transform: translateY(-6px);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.12);
  border-color: transparent;
}

.module-icon {
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 26px;
  border-radius: 12px;
  color: white;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  flex-shrink: 0;
}

.module-info {
  flex: 1;
  min-width: 0;
}

.module-name {
  font-size: 16px;
  font-weight: 600;
  color: #333;
  margin-bottom: 4px;
}

.module-desc {
  font-size: 12px;
  color: #6b7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mini-stat-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  transition: all 0.3s ease;
  height: 100%;
}

.mini-stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
  border-color: #2080f0;
}

.mini-stat-card.highlight {
  background: linear-gradient(135deg, #fff5e6 0%, #ffffff 100%);
  border-color: #f0a020;
}

.mini-stat-icon {
  font-size: 28px;
  flex-shrink: 0;
}

.mini-stat-content {
  flex: 1;
  min-width: 0;
}

.mini-stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #333;
  line-height: 1.2;
}

.mini-stat-value.mini-stat-text {
  font-size: 14px;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mini-stat-label {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
}

.action-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.table-wrapper {
  overflow-x: auto;
}

.endpoint-name {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.name-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.name-text {
  font-weight: 500;
  color: #333;
}

.model-text {
  font-size: 12px;
  color: #6b7280;
}

.url-text {
  color: #2080f0;
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
}

.url-text:hover {
  color: #4098fc;
}

.count-badge {
  display: inline-block;
  padding: 2px 8px;
  background-color: #f0f0f0;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
}

.time-text {
  font-size: 12px;
  color: #666;
}

.tooltip-line {
  padding: 2px 0;
  line-height: 1.6;
}

.tooltip-line strong {
  color: #2080f0;
}

.scope-stats {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  padding: 12px;
  background-color: #fafafa;
  border-radius: 6px;
}

.stats-label {
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
}

.text-gray-400 {
  color: #9ca3af;
}
.text-gray-500 {
  color: #6b7280;
}
.text-primary {
  color: #2080f0;
}
.cursor-pointer {
  cursor: pointer;
}
.mt-1 {
  margin-top: 4px;
}
.mr-2 {
  margin-right: 8px;
}
.flex {
  display: flex;
}
.items-center {
  align-items: center;
}
.gap-2 {
  gap: 8px;
}

.monitoring-card {
  margin-bottom: 24px;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background-color: #fafafa;
  border-radius: 6px;
}

.status-label {
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
  min-width: 80px;
}

.status-detail {
  font-size: 12px;
  color: #9ca3af;
  margin-left: auto;
}
</style>
