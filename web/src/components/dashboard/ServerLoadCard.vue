<template>
  <n-card title="服务器负载 & API 监控">
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
          API 端点健康
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
            <n-statistic label="平均响应" :value="apiMetrics.avgLatency" suffix="ms" />
          </n-grid-item>
          <n-grid-item>
            <n-button text type="primary" @click="navigateToApiMonitor">
              <template #icon>
                <HeroIcon name="chart-bar" :size="16" />
              </template>
              查看详情
            </n-button>
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
import { useRouter } from 'vue-router'
import { getSystemMetrics, parsePrometheusMetrics } from '@/api/dashboard'
import { getCheckableEndpoints } from '@/config/apiEndpoints'
import { request } from '@/utils/http'
import HeroIcon from '@/components/common/HeroIcon.vue'

const router = useRouter()

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
  avgLatency: 0,
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
    const endpoints = getCheckableEndpoints()
    apiMetrics.value.totalEndpoints = endpoints.length

    let onlineCount = 0
    let offlineCount = 0
    let totalLatency = 0
    let latencyCount = 0

    // 快速检测前 5 个端点（避免阻塞）
    const checkPromises = endpoints.slice(0, 5).map(async (endpoint) => {
      const startTime = Date.now()
      try {
        await request({
          url: endpoint.path,
          method: endpoint.method,
          timeout: 3000,
        })
        const latency = Date.now() - startTime
        onlineCount++
        totalLatency += latency
        latencyCount++
      } catch {
        offlineCount++
      }
    })

    await Promise.all(checkPromises)

    apiMetrics.value.onlineEndpoints = onlineCount
    apiMetrics.value.offlineEndpoints = offlineCount
    apiMetrics.value.avgLatency = latencyCount > 0 ? Math.round(totalLatency / latencyCount) : 0
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

function navigateToApiMonitor() {
  router.push('/dashboard/api-monitor')
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
