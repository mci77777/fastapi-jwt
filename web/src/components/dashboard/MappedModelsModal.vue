<template>
  <NModal v-model:show="visible" preset="card" title="映射模型详情" style="width: 900px">
    <NSpace vertical :size="12">
      <NSpace justify="space-between" align="center" wrap>
        <NSpace align="center" :size="8" wrap>
          <NTag :bordered="false" type="success">可用: {{ summary.available }}</NTag>
          <NTag :bordered="false" type="error">不可用: {{ summary.unavailable }}</NTag>
          <NTag :bordered="false">总计: {{ summary.total }}</NTag>
        </NSpace>
        <NSpace align="center" :size="8" wrap>
          <NSelect
            v-model:value="timeWindow"
            size="small"
            style="width: 120px"
            :options="timeWindowOptions"
            :disabled="loading"
            @update:value="load"
          />
          <NButton secondary size="small" :loading="loading" @click="load">刷新</NButton>
        </NSpace>
      </NSpace>

      <NDataTable
        size="small"
        :columns="columns"
        :data="rows"
        :loading="loading"
        :pagination="false"
        :max-height="520"
      />
    </NSpace>
  </NModal>
</template>

<script setup>
import { computed, h, ref, watch } from 'vue'
import { NModal, NSpace, NButton, NDataTable, NTag, NSelect, useMessage } from 'naive-ui'
import { getMappedModelsStats } from '@/api/dashboard'

defineOptions({ name: 'MappedModelsModal' })

const props = defineProps({
  show: {
    type: Boolean,
    required: true,
  },
})

const emit = defineEmits(['update:show'])

const message = useMessage()

const visible = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val),
})

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
    title: 'resolved_model',
    key: 'resolved_model',
    width: 220,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'font-mono' }, String(row.resolved_model || '--')),
  },
  {
    title: 'endpoint',
    key: 'endpoint_name',
    width: 180,
    ellipsis: { tooltip: true },
    render: (row) => String(row.endpoint_name || '--'),
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

watch(
  () => props.show,
  (next) => {
    if (next) load()
  }
)
</script>
