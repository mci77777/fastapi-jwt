<template>
  <NModal v-model:show="visible" preset="card" title="对话日志" style="width: 1000px">
    <NSpace vertical :size="12">
      <NSpace justify="space-between" align="center">
        <NTag :bordered="false" type="info">总计: {{ logs.length }} 条</NTag>
        <NButton secondary size="small" :loading="loading" @click="load">刷新</NButton>
      </NSpace>

      <NDataTable
        size="small"
        :columns="columns"
        :data="logs"
        :loading="loading"
        :pagination="paginationProps"
        :max-height="600"
      />
    </NSpace>
  </NModal>
</template>

<script setup>
import { computed, h, ref, watch } from 'vue'
import { NModal, NSpace, NButton, NDataTable, NTag, NText, NCollapse, NCollapseItem, NCode, useMessage } from 'naive-ui'
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

const columns = computed(() => [
  {
    title: '时间',
    key: 'created_at',
    width: 160,
    render: (row) => formatTime(row.created_at),
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
])

const paginationProps = computed(() => ({
  pageSize: 20,
  showSizePicker: false,
}))

async function load() {
  try {
    loading.value = true
    const res = await getConversationLogs({ limit: 50 })
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
