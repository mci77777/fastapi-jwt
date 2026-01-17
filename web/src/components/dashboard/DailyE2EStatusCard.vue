<template>
  <n-card title="每日 E2E · 映射模型" size="small" :bordered="true">
    <n-space vertical :size="12">
      <n-space justify="space-between" align="center" wrap>
        <n-space align="center" :size="8" wrap>
          <n-tag v-if="currentRun" :bordered="false" type="success">成功: {{ currentRun.models_success }}</n-tag>
          <n-tag v-if="currentRun" :bordered="false" type="error">失败: {{ currentRun.models_failed }}</n-tag>
          <n-tag v-if="currentRun" :bordered="false">总计: {{ currentRun.models_total }}</n-tag>
          <n-tag v-if="scheduleLabel" :bordered="false" type="info">{{ scheduleLabel }}</n-tag>
        </n-space>
        <n-space align="center" :size="8" wrap>
          <n-select
            v-model:value="activeUserType"
            size="small"
            style="width: 140px"
            :options="userTypeOptions"
            :disabled="loading"
          />
          <n-button secondary size="small" :loading="loading" @click="load">
            <template #icon>
              <HeroIcon name="arrow-path" :size="16" />
            </template>
            刷新
          </n-button>
        </n-space>
      </n-space>

      <n-alert v-if="!currentRun" type="warning" :bordered="false" show-icon>
        暂无 E2E 记录
      </n-alert>

      <template v-else>
        <div class="text-xs text-gray-500 flex flex-wrap gap-4">
          <span>最近运行：{{ formatTime(currentRun.started_at) }}</span>
          <span>状态：{{ currentRun.status || '--' }}</span>
          <span v-if="currentRun.prompt_mode">prompt_mode：{{ currentRun.prompt_mode }}</span>
          <span v-if="currentRun.result_mode">result_mode：{{ currentRun.result_mode }}</span>
        </div>
        <div v-if="currentRun.prompt_text" class="text-xs text-gray-500">
          请求语句：{{ currentRun.prompt_text }}
        </div>

        <n-data-table
          size="small"
          :columns="columns"
          :data="rows"
          :loading="loading"
          :pagination="false"
          :max-height="360"
        />
      </template>
    </n-space>
  </n-card>
</template>

<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { NTag, useMessage } from 'naive-ui'
import HeroIcon from '@/components/common/HeroIcon.vue'
import { getE2EMappedModelsStats } from '@/api/dashboard'

defineOptions({ name: 'DailyE2EStatusCard' })

const props = defineProps({
  dashboardConfig: {
    type: Object,
    default: () => ({}),
  },
})

const message = useMessage()
const loading = ref(false)
const payload = ref({ latest: {}, summary: {} })

const activeUserType = ref('permanent')
const userTypeOptions = [
  { label: '普通用户', value: 'permanent' },
  { label: '匿名用户', value: 'anonymous' },
]

const currentRun = computed(() => {
  const latest = payload.value?.latest || {}
  return latest[activeUserType.value] || null
})

const rows = computed(() => (Array.isArray(currentRun.value?.results) ? currentRun.value.results : []))

const scheduleLabel = computed(() => {
  const interval = props.dashboardConfig?.e2e_interval_hours
  const hours = Number(interval)
  if (Number.isFinite(hours) && hours >= 3 && hours <= 24) {
    return `每隔 ${hours} 小时`
  }
  const daily = String(props.dashboardConfig?.e2e_daily_time || '').trim()
  return daily ? `每日 ${daily}` : ''
})

function formatTime(value) {
  if (!value) return '--'
  try {
    return new Date(value).toLocaleString()
  } catch (e) {
    return String(value)
  }
}

function formatLatency(value) {
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return '--'
  return `${Math.round(n)}ms`
}

const columns = computed(() => [
  {
    title: '模型 key',
    key: 'model_key',
    width: 220,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'font-mono' }, String(row.model_key || '')),
  },
  {
    title: '状态',
    key: 'success',
    width: 120,
    render: (row) => {
      const ok = Boolean(row.success)
      return h(NTag, { bordered: false, size: 'small', type: ok ? 'success' : 'error' }, { default: () => (ok ? '成功' : '失败') })
    },
  },
  {
    title: 'XML结构',
    key: 'thinkingml_ok',
    width: 120,
    render: (row) => {
      if (row.thinkingml_ok === true) {
        return h(NTag, { bordered: false, size: 'small', type: 'success' }, { default: () => 'OK' })
      }
      if (row.thinkingml_ok === false) {
        const reason = String(row.thinkingml_reason || '').trim()
        return h(
          NTag,
          { bordered: false, size: 'small', type: 'error', title: reason || undefined },
          { default: () => 'FAIL' }
        )
      }
      return h('span', { class: 'text-gray-400' }, '--')
    },
  },
  {
    title: '延迟',
    key: 'latency_ms',
    width: 90,
    render: (row) => formatLatency(row.latency_ms),
  },
  {
    title: '错误',
    key: 'error',
    ellipsis: { tooltip: true },
    render: (row) => String(row.error || '--'),
  },
])

async function load() {
  loading.value = true
  try {
    const res = await getE2EMappedModelsStats()
    const data = res?.data && typeof res.data === 'object' ? res.data : res
    payload.value = data && typeof data === 'object' ? data : { latest: {}, summary: {} }
  } catch (error) {
    message.error(error?.message || '加载 E2E 结果失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
})
</script>

<style scoped>
/* 使用 Naive UI 默认样式 */
</style>
