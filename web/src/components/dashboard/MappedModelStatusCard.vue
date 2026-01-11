<template>
  <n-card title="映射模型可用性 & 调用" size="small" :bordered="true">
    <n-space vertical :size="12">
      <n-space justify="space-between" align="center" wrap>
        <n-space align="center" :size="8" wrap>
          <n-tag :bordered="false" type="success">可用: {{ summary.available }}</n-tag>
          <n-tag :bordered="false" type="error">不可用: {{ summary.unavailable }}</n-tag>
          <n-tag :bordered="false">总计: {{ summary.total }}</n-tag>
        </n-space>
        <n-space align="center" :size="8" wrap>
          <n-select
            v-model:value="timeWindow"
            size="small"
            style="width: 120px"
            :options="timeWindowOptions"
            :disabled="loading"
            @update:value="handleTimeWindowChange"
          />
          <n-button secondary size="small" :loading="loading" @click="load">
            <template #icon>
              <HeroIcon name="arrow-path" :size="16" />
            </template>
            刷新
          </n-button>
        </n-space>
      </n-space>

      <n-data-table
        size="small"
        :columns="columns"
        :data="rows"
        :loading="loading"
        :pagination="false"
        :max-height="420"
      />
    </n-space>
  </n-card>
</template>

<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { NTag, useMessage } from 'naive-ui'
import { getMappedModelsStats } from '@/api/dashboard'
import HeroIcon from '@/components/common/HeroIcon.vue'

defineOptions({ name: 'MappedModelStatusCard' })

const message = useMessage()

const timeWindow = ref('24h')
const timeWindowOptions = [
  { label: '近 24 小时', value: '24h' },
  { label: '近 7 天', value: '7d' },
]

const loading = ref(false)
const payload = ref({ total: 0, available: 0, unavailable: 0, rows: [] })

const summary = computed(() => ({
  total: Number(payload.value?.total || 0),
  available: Number(payload.value?.available || 0),
  unavailable: Number(payload.value?.unavailable || 0),
}))

const rows = computed(() => (Array.isArray(payload.value?.rows) ? payload.value.rows : []))

function formatPercent(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0%'
  return `${n.toFixed(1)}%`
}

function formatLatency(value) {
  const n = Number(value)
  if (!Number.isFinite(n) || n <= 0) return '--'
  return `${Math.round(n)}ms`
}

const columns = computed(() => [
  {
    title: '映射模型 key',
    key: 'model_key',
    width: 220,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'font-mono' }, String(row.model_key || '')),
  },
  {
    title: 'scope',
    key: 'scope_type',
    width: 90,
    render: (row) =>
      h(
        NTag,
        { size: 'small', bordered: false, type: String(row.scope_type) === 'mapping' ? 'info' : 'default' },
        { default: () => String(row.scope_type || '--') }
      ),
  },
  {
    title: '可用性',
    key: 'availability',
    width: 220,
    render: (row) => {
      const ok = Boolean(row.availability)
      const reason = String(row.availability_reason || '')
      const label = ok ? '可用' : '不可用'
      const type = ok ? 'success' : 'error'
      const reasonText = reason && reason !== 'ok' ? reason : ''
      return h(
        'div',
        { style: 'display:flex; align-items:center; gap:8px; min-width:0;' },
        [
          h(NTag, { bordered: false, size: 'small', type }, { default: () => label }),
          reasonText
            ? h(
                'span',
                { title: reasonText, style: 'font-size:12px; color: rgba(0,0,0,0.55); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;' },
                reasonText
              )
            : null,
        ].filter(Boolean)
      )
    },
  },
  {
    title: '调用次数',
    key: 'calls_total',
    width: 90,
    render: (row) => String(row.calls_total ?? 0),
  },
  {
    title: '用户数',
    key: 'unique_users',
    width: 80,
    render: (row) => String(row.unique_users ?? 0),
  },
  {
    title: '成功率',
    key: 'success_rate',
    width: 90,
    render: (row) => formatPercent(row.success_rate),
  },
  {
    title: '平均延迟',
    key: 'avg_latency_ms',
    width: 90,
    render: (row) => formatLatency(row.avg_latency_ms),
  },
])

async function load() {
  loading.value = true
  try {
    const res = await getMappedModelsStats({ time_window: timeWindow.value })
    payload.value = res && typeof res === 'object' ? res : { total: 0, available: 0, unavailable: 0, rows: [] }
  } catch (error) {
    message.error(error?.message || '加载映射模型统计失败')
  } finally {
    loading.value = false
  }
}

function handleTimeWindowChange() {
  load()
}

onMounted(() => {
  load()
})
</script>

<style scoped>
/* 使用 Naive UI 默认样式 */
</style>
