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

      <n-button text :loading="loading" @click="loadMetrics">
        <template #icon>
          <HeroIcon name="arrow-path" :size="16" />
        </template>
        刷新
      </n-button>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getSystemMetrics, parsePrometheusMetrics } from '@/api/dashboard'
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

let refreshTimer = null

async function loadMetrics() {
  loading.value = true
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
  } finally {
    loading.value = false
  }
}

function calculateErrorRate(parsed) {
  const total = parsed['auth_requests_total'] || 0
  const errors = parsed['jwt_validation_errors_total'] || 0
  return total > 0 ? parseFloat(((errors / total) * 100).toFixed(2)) : 0
}

onMounted(() => {
  loadMetrics()
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
</script>

<style scoped>
.n-card {
  height: 100%;
}
</style>
