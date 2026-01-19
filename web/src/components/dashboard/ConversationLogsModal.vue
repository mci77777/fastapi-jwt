<template>
  <NModal v-model:show="visible" preset="card" title="对话日志" style="width: 1000px">
    <NSpace vertical :size="12">
      <NSpace justify="space-between" align="center" wrap>
        <NSpace align="center" :size="8" wrap>
          <NTag :bordered="false" type="info">显示: {{ filteredLogs.length }} / {{ logs.length }}</NTag>
          <NSelect v-model:value="kindFilter" size="small" :options="kindOptions" style="width: 120px" @update:value="load" />
          <NSelect v-model:value="statusFilter" size="small" :options="statusOptions" style="width: 120px" />
          <NSelect v-model:value="resultModeFilter" size="small" :options="resultModeOptions" style="width: 160px" />
          <NSelect v-model:value="dialectFilter" size="small" :options="dialectOptions" style="width: 200px" />
          <NInput
            v-model:value="keyword"
            size="small"
            clearable
            placeholder="搜索 conversation_id / request_id"
            style="width: 260px"
          />
        </NSpace>
        <NButton secondary size="small" :loading="loading" @click="load">刷新</NButton>
      </NSpace>

      <NDataTable
        size="small"
        :columns="columns"
        :data="filteredLogs"
        :loading="loading"
        :pagination="paginationProps"
        :max-height="600"
      />
    </NSpace>
  </NModal>
</template>

<script setup>
import { computed, h, ref, watch } from 'vue'
import { NModal, NSpace, NButton, NDataTable, NTag, NText, NCollapse, NCollapseItem, NCode, NSelect, NInput, useMessage } from 'naive-ui'
import { getConversationLogs } from '@/api/dashboard'

defineOptions({ name: 'ConversationLogsModal' })

const props = defineProps({
  show: { type: Boolean, required: true },
})

const emit = defineEmits(['update:show'])

const message = useMessage()

const visible = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val),
})

const loading = ref(false)
const logs = ref([])
const kindFilter = ref('trace')
const statusFilter = ref('all')
const resultModeFilter = ref('all')
const dialectFilter = ref('all')
const keyword = ref('')

function formatTime(timestamp) {
  if (!timestamp) return '--'
  try {
    const date = new Date(timestamp)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return timestamp
  }
}

function formatLatency(ms) {
  const n = Number(ms)
  if (!Number.isFinite(n) || n <= 0) return '--'
  return `${Math.round(n)}ms`
}

function parseMaybeJson(detail) {
  if (!detail) return null
  try {
    return typeof detail === 'string' ? JSON.parse(detail) : detail
  } catch {
    return null
  }
}

function extractAppRequest(row) {
  const req = parseMaybeJson(row?.request_detail_json)
  const app = req?.app_request
  return app && typeof app === 'object' ? app : null
}

function extractResultMode(row) {
  const app = extractAppRequest(row)
  const v = app?.result_mode
  return v ? String(v) : ''
}

function extractDialect(row) {
  const app = extractAppRequest(row)
  const v = app?.dialect
  return v ? String(v) : ''
}

function extractIncludeReply(row) {
  const app = extractAppRequest(row)
  if (!app) return null
  return null
}

function renderDetail(detail) {
  if (!detail) return '--'
  try {
    const obj = typeof detail === 'string' ? JSON.parse(detail) : detail
    return h(
      NCollapse,
      { defaultExpandedNames: [] },
      {
        default: () =>
          h(
            NCollapseItem,
            { title: '查看详情', name: '1' },
            {
              default: () =>
                h(
                  NCode,
                  { code: JSON.stringify(obj, null, 2), language: 'json' },
                ),
            },
          ),
      },
    )
  } catch {
    return h(NText, { depth: 3 }, { default: () => String(detail).slice(0, 100) })
  }
}

function renderKind(kind) {
  const k = String(kind || '').trim() || '--'
  const tone = k === 'trace' ? 'success' : k === 'summary' ? 'info' : 'default'
  return h(
    NTag,
    { size: 'small', bordered: false, type: tone },
    { default: () => k },
  )
}

function renderSseBrief(detail) {
  if (!detail) return '--'
  try {
    const obj = typeof detail === 'string' ? JSON.parse(detail) : detail
    const sse = obj?.sse
    if (!sse || typeof sse !== 'object') return '--'
    const stats = sse.stats || {}
    const deltaCount = Number(stats.delta_count || 0)
    const maxDelta = Number(stats.delta_max_len || 0)
    const rawCount = Number(stats.raw_count || 0)
    const dropped = Number(sse.dropped_frames || 0)
    const parts = []
    if (deltaCount) parts.push(`Δ${deltaCount}`)
    if (maxDelta) parts.push(`maxΔ${maxDelta}`)
    if (rawCount) parts.push(`raw${rawCount}`)
    if (dropped) parts.push(`drop${dropped}`)
    return parts.length ? h(NText, { depth: 3 }, { default: () => parts.join(' ') }) : '--'
  } catch {
    return '--'
  }
}

function renderCategory(row) {
  const resultMode = extractResultMode(row)
  const dialect = extractDialect(row)
  const tags = []
  if (resultMode) {
    tags.push(h(NTag, { size: 'small', bordered: false, type: 'info' }, { default: () => resultMode }))
  }
  if (dialect) {
    tags.push(h(NTag, { size: 'small', bordered: false, type: 'default' }, { default: () => dialect }))
  }
  if (!tags.length) return '--'
  return h('div', { style: 'display:flex; flex-wrap:wrap; gap:6px' }, tags)
}

const statusOptions = [
  { label: '全部状态', value: 'all' },
  { label: '成功', value: 'success' },
  { label: '失败', value: 'error' },
]

const kindOptions = [
  { label: '仅 Trace', value: 'trace' },
  { label: '仅 Summary', value: 'summary' },
  { label: 'All', value: 'all' },
]

const resultModeOptions = computed(() => {
  const base = [
    { label: '全部输出', value: 'all' },
    { label: 'raw_passthrough', value: 'raw_passthrough' },
    { label: 'xml_plaintext', value: 'xml_plaintext' },
    { label: 'auto', value: 'auto' },
  ]
  const modes = new Set()
  ;(logs.value || []).forEach((row) => {
    const m = extractResultMode(row)
    if (m) modes.add(m)
  })
  modes.forEach((m) => {
    if (!base.some((x) => x.value === m)) base.push({ label: m, value: m })
  })
  return base
})

const dialectOptions = computed(() => {
  const base = [{ label: '全部方言', value: 'all' }]
  const dialects = new Set()
  ;(logs.value || []).forEach((row) => {
    const d = extractDialect(row)
    if (d) dialects.add(d)
  })
  Array.from(dialects)
    .sort()
    .forEach((d) => base.push({ label: d, value: d }))
  return base
})

const filteredLogs = computed(() => {
  const list = Array.isArray(logs.value) ? logs.value : []
  const kw = String(keyword.value || '').trim().toLowerCase()
  return list.filter((row) => {
    if (statusFilter.value !== 'all') {
      if (String(row?.status || '') !== statusFilter.value) return false
    }
    if (resultModeFilter.value !== 'all') {
      if (extractResultMode(row) !== resultModeFilter.value) return false
    }
    if (dialectFilter.value !== 'all') {
      if (extractDialect(row) !== dialectFilter.value) return false
    }
    if (kw) {
      const conv = String(row?.conversation_id || '').toLowerCase()
      const rid = String(row?.request_id || '').toLowerCase()
      if (!conv.includes(kw) && !rid.includes(kw)) return false
    }
    return true
  })
})

const columns = computed(() => [
  {
    title: '时间',
    key: 'created_at',
    width: 160,
    render: (row) => formatTime(row.created_at),
  },
  {
    title: '类型',
    key: 'kind',
    width: 80,
    render: (row) => renderKind(row.kind),
  },
  {
    title: '分类',
    key: 'category',
    width: 260,
    render: (row) => renderCategory(row),
  },
  {
    title: '会话 ID',
    key: 'conversation_id',
    width: 120,
    ellipsis: { tooltip: true },
    render: (row) => h('span', { class: 'font-mono text-xs' }, String(row.conversation_id || '--').slice(0, 12)),
  },
  {
    title: '模型',
    key: 'model_used',
    width: 120,
    ellipsis: { tooltip: true },
  },
  {
    title: '延迟',
    key: 'latency_ms',
    width: 80,
    render: (row) => formatLatency(row.latency_ms),
  },
  {
    title: '状态',
    key: 'status',
    width: 80,
    render: (row) =>
      h(
        NTag,
        {
          size: 'small',
          type: row.status === 'success' ? 'success' : 'error',
          bordered: false,
        },
        { default: () => (row.status === 'success' ? '成功' : '失败') },
      ),
  },
  {
    title: '请求详情',
    key: 'request_detail_json',
    width: 150,
    render: (row) => renderDetail(row.request_detail_json),
  },
  {
    title: '响应详情',
    key: 'response_detail_json',
    width: 150,
    render: (row) => renderDetail(row.response_detail_json),
  },
  {
    title: 'SSE',
    key: 'sse_brief',
    width: 140,
    render: (row) => renderSseBrief(row.response_detail_json),
  },
])

const paginationProps = computed(() => ({
  pageSize: 20,
  showSizePicker: false,
}))

async function load() {
  try {
    loading.value = true
    const res = await getConversationLogs({ limit: 50, kind: kindFilter.value })
    logs.value = res.logs || []
  } catch (err) {
    message.error(`加载日志失败: ${err.message || '未知错误'}`)
    logs.value = []
  } finally {
    loading.value = false
  }
}

watch(
  () => props.show,
  (newVal) => {
    if (newVal) {
      load()
    }
  },
  { immediate: true },
)

defineExpose({
  load,
})
</script>

<style scoped>
.font-mono {
  font-family: 'Courier New', monospace;
}

.text-xs {
  font-size: 12px;
}
</style>
