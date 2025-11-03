<template>
  <n-card title="AI 对话端点监控">
    <n-space vertical :size="16">
      <!-- Status Badge -->
      <n-space align="center">
        <n-tag :type="statusType" size="small">
          {{ statusText }}
        </n-tag>
        <n-button text :loading="loading" @click="loadMetrics">
          <template #icon>
            <HeroIcon name="arrow-path" :size="16" />
          </template>
        </n-button>
        <n-text v-if="lastUpdate" depth="3" style="font-size: 12px">
          最后更新: {{ formatTime(lastUpdate) }}
        </n-text>
      </n-space>

      <!-- Metrics Grid -->
      <n-grid :cols="3" :x-gap="12" :y-gap="12">
        <n-grid-item>
          <n-statistic label="P50 延迟" :value="metrics.p50" suffix="ms">
            <template #prefix>
              <HeroIcon name="clock" :size="16" />
            </template>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="P95 延迟" :value="metrics.p95" suffix="ms">
            <template #prefix>
              <HeroIcon name="clock" :size="16" />
            </template>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="P99 延迟" :value="metrics.p99" suffix="ms">
            <template #prefix>
              <HeroIcon name="clock" :size="16" />
            </template>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="成功率" :value="metrics.successRate" suffix="%">
            <template #prefix>
              <HeroIcon name="check-circle" :size="16" />
            </template>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="总请求数" :value="metrics.totalRequests">
            <template #prefix>
              <HeroIcon name="chart-bar" :size="16" />
            </template>
          </n-statistic>
        </n-grid-item>
        <n-grid-item>
          <n-statistic label="平均延迟" :value="metrics.avgLatency" suffix="ms">
            <template #prefix>
              <HeroIcon name="clock" :size="16" />
            </template>
          </n-statistic>
        </n-grid-item>
      </n-grid>

      <!-- Model Breakdown -->
      <n-collapse v-if="modelBreakdown.length > 0">
        <n-collapse-item title="按模型分组" name="models">
          <n-data-table :columns="modelColumns" :data="modelBreakdown" size="small" />
        </n-collapse-item>
      </n-collapse>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getSystemMetrics, parsePrometheusMetrics } from '@/api/dashboard'
import HeroIcon from '@/components/common/HeroIcon.vue'

const props = defineProps({
  autoRefresh: { type: Boolean, default: true },
  refreshInterval: { type: Number, default: 30 },
})

const emit = defineEmits(['metrics-update'])

const loading = ref(false)
const lastUpdate = ref(null)
const metrics = ref({
  p50: 0,
  p95: 0,
  p99: 0,
  successRate: 100,
  totalRequests: 0,
  avgLatency: 0,
})
const modelBreakdown = ref([])

const statusType = computed(() => {
  if (metrics.value.successRate >= 99) return 'success'
  if (metrics.value.successRate >= 95) return 'warning'
  return 'error'
})

const statusText = computed(() => {
  if (metrics.value.successRate >= 99) return '健康'
  if (metrics.value.successRate >= 95) return '警告'
  return '异常'
})

const modelColumns = [
  { title: '模型', key: 'model' },
  { title: 'P50 (ms)', key: 'p50', render: (row) => row.p50.toFixed(0) },
  { title: 'P95 (ms)', key: 'p95', render: (row) => row.p95.toFixed(0) },
  { title: '请求数', key: 'count' },
  { title: '成功率', key: 'successRate', render: (row) => `${row.successRate.toFixed(1)}%` },
]

async function loadMetrics() {
  loading.value = true
  try {
    const res = await getSystemMetrics()
    const text = typeof res === 'string' ? res : res?.data
    if (!text) {
      throw new Error('指标响应格式异常')
    }

    const parsed = parsePrometheusMetrics(text)

    // Parse histogram data
    const histogram = parseHistogram(parsed, 'ai_conversation_latency_seconds')

    if (histogram.totalCount === 0) {
      // No data yet
      metrics.value = {
        p50: 0,
        p95: 0,
        p99: 0,
        successRate: 100,
        totalRequests: 0,
        avgLatency: 0,
      }
      modelBreakdown.value = []
    } else {
      metrics.value = {
        p50: Math.round(calculatePercentile(histogram.allBuckets, 0.5) * 1000),
        p95: Math.round(calculatePercentile(histogram.allBuckets, 0.95) * 1000),
        p99: Math.round(calculatePercentile(histogram.allBuckets, 0.99) * 1000),
        successRate: calculateSuccessRate(histogram),
        totalRequests: histogram.totalCount,
        avgLatency:
          histogram.totalCount > 0
            ? Math.round((histogram.totalSum / histogram.totalCount) * 1000)
            : 0,
      }

      // Group by model
      modelBreakdown.value = groupByModel(histogram)
    }

    lastUpdate.value = new Date()
    emit('metrics-update', metrics.value)
  } catch (error) {
    console.error('获取 AI 对话指标失败:', error)
    window.$message?.error('获取 AI 对话指标失败')
  } finally {
    loading.value = false
  }
}

/**
 * Parse Prometheus histogram from metrics text
 */
function parseHistogram(metrics, baseName) {
  const buckets = {}
  const modelBuckets = {}
  let totalCount = 0
  let totalSum = 0

  // Parse bucket metrics
  for (const [key, value] of Object.entries(metrics)) {
    if (key.startsWith(baseName + '_bucket')) {
      // Extract labels: model, user_type, status, le
      const labelMatch = key.match(/\{([^}]+)\}/)
      if (labelMatch) {
        const labels = parseLabelString(labelMatch[1])
        const le = parseFloat(labels.le)
        const model = labels.model || 'unknown'

        if (!isNaN(le)) {
          // Aggregate all buckets
          if (!buckets[le]) buckets[le] = 0
          buckets[le] += value

          // Track by model
          if (!modelBuckets[model]) {
            modelBuckets[model] = { buckets: {}, count: 0, sum: 0, successCount: 0, errorCount: 0 }
          }
          if (!modelBuckets[model].buckets[le]) modelBuckets[model].buckets[le] = 0
          modelBuckets[model].buckets[le] += value
        }
      }
    } else if (key.startsWith(baseName + '_count')) {
      const labelMatch = key.match(/\{([^}]+)\}/)
      if (labelMatch) {
        const labels = parseLabelString(labelMatch[1])
        const model = labels.model || 'unknown'
        const status = labels.status || 'unknown'

        totalCount += value

        if (!modelBuckets[model]) {
          modelBuckets[model] = { buckets: {}, count: 0, sum: 0, successCount: 0, errorCount: 0 }
        }
        modelBuckets[model].count += value

        if (status === 'success') {
          modelBuckets[model].successCount += value
        } else {
          modelBuckets[model].errorCount += value
        }
      }
    } else if (key.startsWith(baseName + '_sum')) {
      const labelMatch = key.match(/\{([^}]+)\}/)
      if (labelMatch) {
        const labels = parseLabelString(labelMatch[1])
        const model = labels.model || 'unknown'

        totalSum += value

        if (!modelBuckets[model]) {
          modelBuckets[model] = { buckets: {}, count: 0, sum: 0, successCount: 0, errorCount: 0 }
        }
        modelBuckets[model].sum += value
      }
    }
  }

  // Convert buckets object to sorted array
  const allBuckets = Object.entries(buckets)
    .map(([le, count]) => ({ le: parseFloat(le), count }))
    .sort((a, b) => a.le - b.le)

  return {
    allBuckets,
    modelBuckets,
    totalCount,
    totalSum,
  }
}

/**
 * Parse label string like "model="gpt-4o-mini",status="success",le="1.0""
 */
function parseLabelString(labelStr) {
  const labels = {}
  const pairs = labelStr.match(/(\w+)="([^"]+)"/g) || []
  pairs.forEach((pair) => {
    const [key, value] = pair.split('=')
    labels[key] = value.replace(/"/g, '')
  })
  return labels
}

/**
 * Calculate percentile from histogram buckets
 */
function calculatePercentile(buckets, percentile) {
  if (buckets.length === 0) return 0

  const totalCount = buckets[buckets.length - 1].count
  const targetCount = totalCount * percentile

  for (let i = 0; i < buckets.length; i++) {
    if (buckets[i].count >= targetCount) {
      return buckets[i].le
    }
  }

  return buckets[buckets.length - 1].le
}

/**
 * Calculate success rate from histogram
 */
function calculateSuccessRate(histogram) {
  const { modelBuckets } = histogram
  let totalSuccess = 0
  let totalError = 0

  for (const model of Object.values(modelBuckets)) {
    totalSuccess += model.successCount
    totalError += model.errorCount
  }

  const total = totalSuccess + totalError
  return total > 0 ? (totalSuccess / total) * 100 : 100
}

/**
 * Group metrics by model
 */
function groupByModel(histogram) {
  const { modelBuckets } = histogram
  const result = []

  for (const [model, data] of Object.entries(modelBuckets)) {
    if (data.count === 0) continue

    const bucketArray = Object.entries(data.buckets)
      .map(([le, count]) => ({ le: parseFloat(le), count }))
      .sort((a, b) => a.le - b.le)

    result.push({
      model,
      p50: calculatePercentile(bucketArray, 0.5) * 1000,
      p95: calculatePercentile(bucketArray, 0.95) * 1000,
      count: data.count,
      successRate: data.count > 0 ? (data.successCount / data.count) * 100 : 100,
    })
  }

  return result.sort((a, b) => b.count - a.count)
}

function formatTime(date) {
  if (!date) return ''
  const now = new Date()
  const diff = Math.floor((now - date) / 1000)

  if (diff < 60) return `${diff}秒前`
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  return date.toLocaleTimeString('zh-CN')
}

let refreshTimer = null

onMounted(() => {
  loadMetrics()
  if (props.autoRefresh) {
    refreshTimer = setInterval(loadMetrics, props.refreshInterval * 1000)
  }
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>
