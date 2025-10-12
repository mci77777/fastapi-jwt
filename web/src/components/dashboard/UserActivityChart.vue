<template>
  <NCard title="用户活跃度" :bordered="true" class="user-activity-chart">
    <template #header-extra>
      <NSelect
        v-model:value="currentTimeRange"
        :options="timeRangeOptions"
        size="small"
        style="width: 120px"
        @update:value="handleTimeRangeChange"
      />
    </template>

    <div ref="chartRef" class="chart-container" :class="{ 'chart-loading': loading }"></div>
  </NCard>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { NCard, NSelect } from 'naive-ui'
import * as echarts from 'echarts'

defineOptions({ name: 'UserActivityChart' })

const props = defineProps({
  timeRange: {
    type: String,
    default: '24h',
    validator: (value) => ['1h', '24h', '7d'].includes(value)
  },
  loading: {
    type: Boolean,
    default: false
  },
  data: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['time-range-change'])

// 响应式引用
const chartRef = ref(null)
const currentTimeRange = ref(props.timeRange)

// ECharts 实例
let chartInstance = null
let resizeObserver = null

// 时间范围选项
const timeRangeOptions = [
  { label: '最近 1 小时', value: '1h' },
  { label: '最近 24 小时', value: '24h' },
  { label: '最近 7 天', value: '7d' }
]

/**
 * 初始化图表
 */
function initChart() {
  if (!chartRef.value) return

  // 销毁旧实例
  if (chartInstance) {
    chartInstance.dispose()
  }

  // 创建新实例
  chartInstance = echarts.init(chartRef.value)

  // 设置初始配置
  updateChart()

  // 监听窗口大小变化
  setupResizeObserver()
}

/**
 * 更新图表数据
 */
function updateChart() {
  if (!chartInstance) return

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross',
        label: {
          backgroundColor: '#6a7985'
        }
      }
    },
    legend: {
      data: ['活跃用户数'],
      top: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: generateXAxisData()
    },
    yAxis: {
      type: 'value',
      name: '用户数',
      minInterval: 1
    },
    series: [
      {
        name: '活跃用户数',
        type: 'line',
        smooth: true,
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(24, 160, 88, 0.3)' },
            { offset: 1, color: 'rgba(24, 160, 88, 0.05)' }
          ])
        },
        lineStyle: {
          color: '#18a058',
          width: 2
        },
        itemStyle: {
          color: '#18a058'
        },
        data: generateYAxisData()
      }
    ]
  }

  chartInstance.setOption(option, true)
}

/**
 * 生成 X 轴数据（时间标签）
 */
function generateXAxisData() {
  const now = new Date()
  const labels = []

  if (currentTimeRange.value === '1h') {
    // 最近 1 小时，每 5 分钟一个点
    for (let i = 12; i >= 0; i--) {
      const time = new Date(now.getTime() - i * 5 * 60 * 1000)
      labels.push(time.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }))
    }
  } else if (currentTimeRange.value === '24h') {
    // 最近 24 小时，每 2 小时一个点
    for (let i = 12; i >= 0; i--) {
      const time = new Date(now.getTime() - i * 2 * 60 * 60 * 1000)
      labels.push(time.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }))
    }
  } else if (currentTimeRange.value === '7d') {
    // 最近 7 天，每天一个点
    for (let i = 7; i >= 0; i--) {
      const time = new Date(now.getTime() - i * 24 * 60 * 60 * 1000)
      labels.push(time.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }))
    }
  }

  return labels
}

/**
 * 生成 Y 轴数据（用户数）
 */
function generateYAxisData() {
  // 如果有真实数据，使用真实数据
  if (props.data && props.data.length > 0) {
    return props.data
  }

  // 否则生成模拟数据
  const count = currentTimeRange.value === '7d' ? 8 : 13
  const baseValue = currentTimeRange.value === '7d' ? 500 : 100
  const variance = currentTimeRange.value === '7d' ? 200 : 50

  return Array.from({ length: count }, () => {
    return Math.floor(baseValue + Math.random() * variance)
  })
}

/**
 * 设置 ResizeObserver 监听容器大小变化
 */
function setupResizeObserver() {
  if (!chartRef.value || !chartInstance) return

  resizeObserver = new ResizeObserver(() => {
    chartInstance.resize()
  })

  resizeObserver.observe(chartRef.value)
}

/**
 * 切换时间范围
 */
function handleTimeRangeChange(value) {
  emit('time-range-change', value)
  nextTick(() => {
    updateChart()
  })
}

// 监听 props 变化
watch(
  () => props.data,
  () => {
    updateChart()
  },
  { deep: true }
)

watch(
  () => props.timeRange,
  (newValue) => {
    currentTimeRange.value = newValue
    updateChart()
  }
)

// 生命周期钩子
onMounted(() => {
  nextTick(() => {
    initChart()
  })
})

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }

  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.user-activity-chart {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.user-activity-chart :deep(.n-card__content) {
  flex: 1;
  overflow: hidden;
  padding: 12px;
}

.chart-container {
  width: 100%;
  height: 100%;
  min-height: 300px;
}

.chart-loading {
  opacity: 0.6;
  pointer-events: none;
}
</style>

