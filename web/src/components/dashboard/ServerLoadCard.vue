<template>
  <n-card title="服务器负载 & 供应商监控" :bordered="false" style="background: transparent;">
    <n-space vertical :size="16">
      <!-- 服务器负载指标 -->
      <div>
        <n-text depth="3" style="font-size: 12px; margin-bottom: 8px; display: block">
          服务器指标
        </n-text>
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
      </div>

      <!-- API 端点监控指标 -->
      <div>
        <n-text depth="3" style="font-size: 12px; margin-bottom: 8px; display: block">
          AI 供应商端点健康
        </n-text>
        <n-grid :cols="2" :x-gap="12" :y-gap="12">
          <n-grid-item>
            <n-statistic label="在线端点" :value="apiMetrics.onlineEndpoints">
              <template #suffix>
                <n-text depth="3" style="font-size: 12px">
                  / {{ apiMetrics.totalEndpoints }}
                </n-text>
              </template>
            </n-statistic>
          </n-grid-item>
          <n-grid-item>
            <n-statistic label="离线端点" :value="apiMetrics.offlineEndpoints">
              <template #suffix>
                <n-tag
                  v-if="apiMetrics.offlineEndpoints > 0"
                  type="error"
                  size="small"
                  style="margin-left: 8px"
                >
                  异常
                </n-tag>
              </template>
            </n-statistic>
          </n-grid-item>
          <n-grid-item>
            <n-statistic label="连通率" :value="apiMetrics.connectivityRate" suffix="%" />
          </n-grid-item>
          <n-grid-item>
            <n-statistic label="监控状态" :value="apiMetrics.isRunning ? '运行中' : '已停止'">
              <template #suffix>
                <n-text
                  v-if="apiMetrics.lastCheck"
                  depth="3"
                  style="font-size: 12px; margin-left: 8px"
                >
                  最近检测: {{ formatTime(apiMetrics.lastCheck) }}
                </n-text>
              </template>
            </n-statistic>
          </n-grid-item>
        </n-grid>
      </div>

      <!-- 刷新按钮 -->
      <n-button text :loading="loading" @click="loadAllMetrics">
        <template #icon>
          <HeroIcon name="arrow-path" :size="16" />
        </template>
        刷新所有指标
      </n-button>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getApiConnectivity, getSystemMetrics, parsePrometheusMetrics } from '@/api/dashboard'
import HeroIcon from '@/components/common/HeroIcon.vue'

const props = defineProps({
  autoRefresh: { type: Boolean, default: true },
  refreshInterval: { type: Number, default: 60 },
})

const emit = defineEmits(['metrics-update'])

const loading = ref(false)
const metrics = ref({
  totalRequests: 0,
  errorRate: 0,
  activeConnections: 0,
  rateLimitBlocks: 0,
})

const apiMetrics = ref({
  totalEndpoints: 0,
  onlineEndpoints: 0,
  offlineEndpoints: 0,
  connectivityRate: 0,
  isRunning: false,
  lastCheck: null,
})

let refreshTimer = null

async function loadMetrics() {
  try {
    const res = await getSystemMetrics()
    let text = ''
    if (typeof res === 'string') {
      text = res
    } else if (res && typeof res === 'object' && typeof res.data === 'string') {
      text = res.data
    }
    if (!text) {
      throw new Error('指标响应格式异常')
    }
    const parsed = parsePrometheusMetrics(text)

    metrics.value = {
      totalRequests: Math.round(parsed['auth_requests_total'] || 0),
      errorRate: calculateErrorRate(parsed),
      activeConnections: Math.round(parsed['active_connections'] || 0),
      rateLimitBlocks: Math.round(parsed['rate_limit_blocks_total'] || 0),
    }

    emit('metrics-update', metrics.value)
  } catch (error) {
    window.$message?.error('获取服务器指标失败')
  }
}

async function loadApiMetrics() {
  try {
    const res = await getApiConnectivity()
    const data = res?.data && typeof res.data === 'object' ? res.data : res

    const total = Number(data?.total_endpoints || 0)
    const online = Number(data?.healthy_endpoints || 0)
    const connectivityRate = Number(data?.connectivity_rate || 0)

    apiMetrics.value = {
      totalEndpoints: Number.isFinite(total) ? total : 0,
      onlineEndpoints: Number.isFinite(online) ? online : 0,
      offlineEndpoints:
        Number.isFinite(total) && Number.isFinite(online) ? Math.max(0, total - online) : 0,
      connectivityRate: Number.isFinite(connectivityRate) ? connectivityRate : 0,
      isRunning: Boolean(data?.is_running),
      lastCheck: data?.last_check || null,
    }
  } catch (error) {
    console.error('加载 API 指标失败:', error)
  }
}

async function loadAllMetrics() {
  loading.value = true
  try {
    await Promise.all([loadMetrics(), loadApiMetrics()])
  } finally {
    loading.value = false
  }
}

function calculateErrorRate(parsed) {
  const total = parsed['auth_requests_total'] || 0
  const errors = parsed['jwt_validation_errors_total'] || 0
  return total > 0 ? parseFloat(((errors / total) * 100).toFixed(2)) : 0
}

function formatTime(value) {
  try {
    const d = new Date(value)
    if (Number.isNaN(d.getTime())) return String(value || '')
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return String(value || '')
  }
}

onMounted(() => {
  loadAllMetrics()
  if (props.autoRefresh && props.refreshInterval > 0) {
    refreshTimer = setInterval(loadAllMetrics, props.refreshInterval * 1000)
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.n-card {
  height: 100%;
}
</style>
