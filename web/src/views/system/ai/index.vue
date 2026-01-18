<script setup>
import { computed, h, onBeforeUnmount, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { useRouter } from 'vue-router'
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NDropdown,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  NTooltip,
  useMessage,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

	import { getToken, renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'

defineOptions({ name: 'AIConfigModels' })

const vPermission = resolveDirective('permission')
const $table = ref(null)
const router = useRouter()
const message = useMessage()

const supabaseStatus = ref(null)
const supabaseLoading = ref(false)
const bulkSyncing = ref(null)
const bulkChecking = ref(false)
const syncingRowId = ref(null)
const checkingRowId = ref(null)

// LLM App config（App 默认转发模式）
const llmAppConfigLoading = ref(false)
const llmAppConfigSaving = ref(false)
const llmAppDefaultResultMode = ref('raw_passthrough')
const llmAppDefaultResultModeLegacyAuto = ref(false)
const llmAppResultModeOptions = [
  { label: '透明转发（SSE content_delta）', value: 'raw_passthrough' },
  { label: 'XML 文本转发（SSE content_delta）', value: 'xml_plaintext' },
]

// SSE 探针：用于定位网关缓冲导致的“假流式 / 大 chunk”
const sseProbeRunning = ref(false)
const sseProbeEvents = ref([])

const sseProbeSummary = computed(() => {
  const items = Array.isArray(sseProbeEvents.value) ? sseProbeEvents.value : []
  if (!items.length) return { ok: false, note: 'no_data', gaps: [] }
  const gaps = []
  for (let i = 1; i < items.length; i += 1) gaps.push(items[i] - items[i - 1])
  const maxGapMs = gaps.length ? Math.max(...gaps) : 0
  return { ok: maxGapMs < 1500, note: maxGapMs ? `max_gap_ms=${maxGapMs}` : 'ok', gaps }
})

// Web 搜索（Exa）配置（写入到 /api/v1/llm/app/config；后端仅返回 masked）
const webSearchConfigSaving = ref(false)
const webSearchEnabled = ref(false)
const webSearchProvider = ref('exa')
const webSearchExaApiKeyMasked = ref('')
const webSearchExaApiKeySource = ref('none')
const webSearchExaApiKeyInput = ref('')

async function loadLlmAppConfig() {
  llmAppConfigLoading.value = true
  try {
    const res = await api.getLlmAppConfig()
    const data = res?.data?.data || res?.data || {}
    const mode = String(data?.default_result_mode || '').trim()
    if (mode === 'auto') {
      llmAppDefaultResultModeLegacyAuto.value = true
      llmAppDefaultResultMode.value = null
    } else {
      llmAppDefaultResultModeLegacyAuto.value = false
      llmAppDefaultResultMode.value = ['xml_plaintext', 'raw_passthrough'].includes(mode) ? mode : 'raw_passthrough'
    }

    webSearchEnabled.value = Boolean(data?.web_search_enabled)
    webSearchProvider.value = String(data?.web_search_provider || 'exa').trim().toLowerCase() || 'exa'
    webSearchExaApiKeyMasked.value = String(data?.web_search_exa_api_key_masked || '').trim()
    webSearchExaApiKeySource.value = String(data?.web_search_exa_api_key_source || 'none').trim()
  } catch (error) {
    message.error(error?.message || '加载 App 转发模式配置失败')
  } finally {
    llmAppConfigLoading.value = false
  }
}

async function handleSaveLlmAppConfig() {
  llmAppConfigSaving.value = true
  try {
    const mode = String(llmAppDefaultResultMode.value || '').trim()
    if (!['xml_plaintext', 'raw_passthrough'].includes(mode)) {
      message.warning('请选择转发模式（透明转发 / XML 文本转发）')
      return
    }
    const res = await api.upsertLlmAppConfig({ default_result_mode: mode })
    const data = res?.data?.data || res?.data || {}
    const saved = String(data?.default_result_mode || '').trim()
    if (saved === 'auto') {
      llmAppDefaultResultModeLegacyAuto.value = true
      llmAppDefaultResultMode.value = null
      message.warning('后端返回 legacy:auto，请选择一种并保存')
      return
    }
    llmAppDefaultResultModeLegacyAuto.value = false
    llmAppDefaultResultMode.value = ['xml_plaintext', 'raw_passthrough'].includes(saved) ? saved : mode
    message.success('已更新 App 默认转发模式')
  } catch (error) {
    message.error(error?.message || '保存 App 转发模式配置失败')
  } finally {
    llmAppConfigSaving.value = false
  }
}

async function consumeSseReader(reader, { onEvent } = {}) {
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = 'message'
  let dataLines = []

  const flushEvent = () => {
    if (!dataLines.length) return null
    const rawData = dataLines.join('\n')
    dataLines = []
    let parsed = rawData
    try {
      parsed = JSON.parse(rawData)
    } catch {
      // ignore
    }
    return { event: currentEvent || 'message', data: parsed }
  }

  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    for (;;) {
      const idx = buffer.indexOf('\n')
      if (idx === -1) break
      const line = buffer.slice(0, idx).replace(/\r$/, '')
      buffer = buffer.slice(idx + 1)

      if (!line) {
        const ev = flushEvent()
        if (ev) {
          const receivedAtMs = Date.now()
          const stop = await onEvent?.(ev, receivedAtMs)
          if (stop) return
        }
        currentEvent = 'message'
        continue
      }

      if (line.startsWith('event:')) {
        currentEvent = line.slice('event:'.length).trim() || 'message'
        continue
      }
      if (line.startsWith('data:')) {
        dataLines.push(line.slice('data:'.length).trim())
      }
    }
  }
}

async function handleRunSseProbe() {
  if (sseProbeRunning.value) return
  const token = getToken()
  if (!token) {
    message.warning('请先登录（JWT）')
    return
  }

  sseProbeRunning.value = true
  sseProbeEvents.value = []

  try {
    const baseURL = import.meta.env.VITE_BASE_API || '/api/v1'
    const normalizedBase = String(baseURL).replace(/\/+$/, '')
    const url = `${normalizedBase}/base/sse_probe`

    const requestId = `system-probe-${Date.now()}`
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'text/event-stream',
        'X-Request-Id': requestId,
      },
    })
    if (!response.ok) {
      const text = await response.text().catch(() => '')
      throw new Error(`SSE 探针失败：${response.status} ${text}`)
    }
    const reader = response.body?.getReader()
    if (!reader) throw new Error('SSE 探针响应不支持流式读取')

    await consumeSseReader(reader, {
      onEvent: async (ev, receivedAtMs) => {
        if (ev.event === 'probe') {
          sseProbeEvents.value.push(receivedAtMs)
          if (sseProbeEvents.value.length > 50) sseProbeEvents.value.splice(0, sseProbeEvents.value.length - 50)
        }
        if (ev.event === 'completed') return true
        return false
      },
    })

    message.success(sseProbeSummary.value.ok ? 'SSE 探针：通过（无明显缓冲）' : 'SSE 探针：疑似缓冲/压缩')
  } catch (error) {
    message.error(error?.message || 'SSE 探针失败')
  } finally {
    sseProbeRunning.value = false
  }
}

async function handleSaveWebSearchConfig() {
  webSearchConfigSaving.value = true
  try {
    const payload = {
      web_search_enabled: !!webSearchEnabled.value,
      web_search_provider: 'exa',
    }

    const key = String(webSearchExaApiKeyInput.value || '').trim()
    if (key) payload.web_search_exa_api_key = key

    const res = await api.upsertLlmAppConfig(payload)
    const data = res?.data?.data || res?.data || {}
    webSearchEnabled.value = Boolean(data?.web_search_enabled)
    webSearchProvider.value = String(data?.web_search_provider || 'exa').trim().toLowerCase() || 'exa'
    webSearchExaApiKeyMasked.value = String(data?.web_search_exa_api_key_masked || '').trim()
    webSearchExaApiKeySource.value = String(data?.web_search_exa_api_key_source || 'none').trim()
    webSearchExaApiKeyInput.value = ''
    message.success('已更新 Web 搜索配置')
  } catch (error) {
    message.error(error?.message || '保存 Web 搜索配置失败')
  } finally {
    webSearchConfigSaving.value = false
  }
}

async function handleClearWebSearchConfig() {
  webSearchConfigSaving.value = true
  try {
    const res = await api.upsertLlmAppConfig({
      web_search_enabled: false,
      web_search_provider: 'exa',
      web_search_exa_api_key: '',
    })
    const data = res?.data?.data || res?.data || {}
    webSearchEnabled.value = Boolean(data?.web_search_enabled)
    webSearchProvider.value = String(data?.web_search_provider || 'exa').trim().toLowerCase() || 'exa'
    webSearchExaApiKeyMasked.value = String(data?.web_search_exa_api_key_masked || '').trim()
    webSearchExaApiKeySource.value = String(data?.web_search_exa_api_key_source || 'none').trim()
    webSearchExaApiKeyInput.value = ''
    message.success('已清空 Web 搜索密钥并禁用')
  } catch (error) {
    message.error(error?.message || '清空 Web 搜索配置失败')
  } finally {
    webSearchConfigSaving.value = false
  }
}

const queryItems = ref({ keyword: null, only_active: null })

const statusOptions = [
  { label: '全部', value: null },
  { label: '启用', value: true },
  { label: '停用', value: false },
]

const syncOptions = [
  { label: '推送到 Supabase', key: 'push' },
  { label: '从 Supabase 拉取', key: 'pull' },
  { label: '推送后拉取', key: 'both' },
]

const statusTypeMap = {
  online: 'success',
  offline: 'error',
  checking: 'warning',
  unknown: 'default',
}

const statusLabelMap = {
  online: '在线',
  offline: '离线',
  checking: '检测中',
  unknown: '未知',
}

const protocolOptions = [
  { label: 'OpenAI（/v1/chat/completions）', value: 'openai' },
  { label: 'Claude（/v1/messages）', value: 'claude' },
]

const supabaseTagType = computed(() => {
  const status = supabaseStatus.value?.status
  if (status === 'online') return 'success'
  if (status === 'offline') return 'error'
  if (status === 'disabled') return 'default'
  return 'warning'
})

const supabaseLabel = computed(() => {
  const status = supabaseStatus.value?.status
  if (status === 'online') return '已连接'
  if (status === 'offline') return '连接失败'
  if (status === 'disabled') return '未配置'
  return '检测中'
})

const monitorStatus = ref({
  is_running: false,
  interval_seconds: 60,
  last_run_at: null,
  last_error: null,
})
const monitorIntervalSeconds = ref(60)
const monitorLoading = ref(false)
const monitorIntervalOptions = [
  { label: '10s', value: 10 },
  { label: '30s', value: 30 },
  { label: '60s', value: 60 },
  { label: '120s', value: 120 },
  { label: '300s', value: 300 },
  { label: '600s', value: 600 },
]
let monitorStatusTimer = null

const checkLogs = ref([])
const checkLogText = computed(() => checkLogs.value.join('\n'))

function nowText() {
  try {
    const d = new Date()
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  } catch {
    return String(Date.now())
  }
}

function appendCheckLog(line) {
  const text = String(line || '').trim()
  if (!text) return
  checkLogs.value.unshift(text)
  if (checkLogs.value.length > 200) {
    checkLogs.value.length = 200
  }
}

function clearCheckLogs() {
  checkLogs.value = []
}

function formatEndpointCheckLog(endpoint) {
  const name = endpoint?.name || `#${endpoint?.id || '?'}`
  const status = endpoint?.status || 'unknown'
  const ok = status === 'online'
  const models = Array.isArray(endpoint?.model_list) ? endpoint.model_list.length : 0
  const latency = endpoint?.latency_ms !== null && endpoint?.latency_ms !== undefined
    ? `${Number(endpoint.latency_ms).toFixed(0)}ms`
    : '--'
  const error = String(endpoint?.last_error || '').trim().replace(/\s+/g, ' ')
  const base = `[${nowText()}] ${ok ? 'SUCCESS' : 'FAIL'} endpoint=${name} status=${status} models=${models} latency=${latency}`
  return error ? `${base} error=${error.slice(0, 220)}` : base
}

function handleGoMapping() {
  router.push('/ai')
}

const initForm = {
  id: null,
  name: '',
  model: '',
  base_url: '',
  provider_protocol: 'openai',
  api_key: '',
  description: '',
  timeout: 60,
  is_active: true,
  is_default: false,
  auto_sync: false,
  api_key_masked: '',
}

function normalizePayload(form, isUpdate = false) {
  const payload = {
    name: form.name?.trim(),
    model: form.model?.trim() || null,
    base_url: form.base_url?.trim(),
    provider_protocol: form.provider_protocol || 'openai',
    api_key: form.api_key?.trim() || undefined,
    description: form.description?.trim() || undefined,
    timeout: form.timeout,
    is_active: form.is_active,
    is_default: form.is_default,
    auto_sync: form.auto_sync,
  }
  if (!payload.base_url) delete payload.base_url
  if (!payload.model) delete payload.model
  if (!payload.description) delete payload.description
  if (!payload.api_key) delete payload.api_key
  if (isUpdate) payload.id = form.id
  return payload
}

function ensureDefaultActive(value) {
  if (value) {
    modalForm.value.is_active = true
  }
}

const {
  modalVisible,
  modalTitle,
  modalLoading,
  modalForm,
  modalFormRef,
  modalAction,
  handleAdd,
  handleSave,
  handleEdit: innerHandleEdit,
} = useCRUD({
  name: '端点',
  initForm,
  doCreate: (form) => api.createAIModel(normalizePayload(form, false)),
  doUpdate: (form) => api.updateAIModel(normalizePayload(form, true)),
  refresh: () => {
    loadSupabaseStatus()
    $table.value?.handleSearch()
  },
})

function openEdit(row) {
  const sanitized = {
    ...row,
    api_key: '',
    api_key_masked: row.api_key_masked ?? '',
    auto_sync: false,
  }
  delete sanitized.created_at
  delete sanitized.updated_at
  delete sanitized.model_list
  delete sanitized.resolved_endpoints
  delete sanitized.last_checked_at
  delete sanitized.last_synced_at
  delete sanitized.status
  delete sanitized.latency_ms
  delete sanitized.sync_status
  innerHandleEdit(sanitized)
}

const formRules = {
  name: [
    {
      required: true,
      message: '请输入端点名称',
      trigger: ['input', 'blur'],
    },
  ],
  base_url: [
    {
      required: true,
      message: '请输入 Base URL',
      trigger: ['input', 'blur'],
    },
  ],
  timeout: [
    {
      required: true,
      type: 'number',
      message: '请输入超时时间',
      trigger: ['blur', 'change'],
    },
  ],
}

function renderStatusTag(row) {
  const status = row.status || 'unknown'
  const type = statusTypeMap[status] || 'default'
  return h(
    NTag,
    { type, round: true, bordered: false },
    { default: () => statusLabelMap[status] || status }
  )
}

function renderModelList(row) {
  const models = row.model_list || []
  if (!models.length) return h('span', { class: 'text-gray-400' }, '--')
  return h(
    NTooltip,
    {},
    {
      trigger: () =>
        h(
          NTag,
          { type: 'info', bordered: false, size: 'small' },
          { default: () => `${models.length} 个模型` }
        ),
      default: () => models.map((model) => h('div', { key: model }, model)),
    }
  )
}

function renderEndpoints(row) {
  const endpoints = row.resolved_endpoints || {}
  const items = Object.entries(endpoints)
  if (!items.length) return h('span', { class: 'text-gray-400' }, '--')
  return h(
    NTooltip,
    {},
    {
      trigger: () =>
        h(NTag, { type: 'default', bordered: false, size: 'small' }, { default: () => '查看路径' }),
      default: () => items.map(([key, value]) => h('div', { key }, `${key}: ${value}`)),
    }
  )
}

function formatLatency(value) {
  if (value === null || value === undefined) return '--'
  return `${value.toFixed(0)} ms`
}

async function loadSupabaseStatus() {
  try {
    supabaseLoading.value = true
    const response = await api.getSupabaseStatus()
    supabaseStatus.value = response.data || null
  } catch (error) {
    supabaseStatus.value = { status: 'offline', detail: error.message }
  } finally {
    supabaseLoading.value = false
  }
}

function clearMonitorTimer() {
  if (monitorStatusTimer) {
    clearInterval(monitorStatusTimer)
    monitorStatusTimer = null
  }
}
function setupMonitorTimer() {
  clearMonitorTimer()
  if (!monitorStatus.value.is_running) {
    return
  }
  const interval = Math.min(
    Math.max((monitorStatus.value.interval_seconds || 60) * 1000, 5000),
    600000
  )
  monitorStatusTimer = setInterval(() => {
    loadMonitorStatus(true)
  }, interval)
}

async function loadMonitorStatus(triggerTableRefresh = false) {
  try {
    const response = await api.getMonitorStatus()
    const data = response.data || {}
    monitorStatus.value = {
      is_running: !!data.is_running,
      interval_seconds: data.interval_seconds ?? monitorStatus.value.interval_seconds,
      last_run_at: data.last_run_at ?? null,
      last_error: data.last_error ?? null,
    }
    monitorIntervalSeconds.value = Number(
      monitorStatus.value.interval_seconds || monitorIntervalSeconds.value
    )
    if (triggerTableRefresh && monitorStatus.value.is_running) {
      $table.value?.handleSearch()
    }
    setupMonitorTimer()
  } catch (error) {
    monitorStatus.value = {
      is_running: false,
      interval_seconds: Number(monitorIntervalSeconds.value),
      last_run_at: null,
      last_error: error.message,
    }
    clearMonitorTimer()
  }
}

async function handleStartMonitor() {
  if (monitorLoading.value) return
  try {
    monitorLoading.value = true
    await api.startMonitor(monitorIntervalSeconds.value)
    await loadMonitorStatus()
    window.$message?.success(`Monitor started (${monitorIntervalSeconds.value}s/round)`)
  } catch (error) {
    window.$message?.error(error.message || 'Failed to start monitor')
  } finally {
    monitorLoading.value = false
  }
}

async function handleStopMonitor() {
  if (monitorLoading.value) return
  try {
    monitorLoading.value = true
    await api.stopMonitor()
    await loadMonitorStatus()
    window.$message?.success('Monitor stopped')
  } catch (error) {
    window.$message?.error(error.message || 'Failed to stop monitor')
  } finally {
    monitorLoading.value = false
  }
}

async function handleCheckAll() {
  try {
    bulkChecking.value = true
    const result = await api.checkAllAIModels()
    appendCheckLog(`[${nowText()}] INFO batch_check_triggered msg=${String(result?.msg || '已触发批量检测')}`)
    window.$message?.success(result?.msg || '已触发批量检测')
    $table.value?.handleSearch()
  } catch (error) {
    window.$message?.error(error.message || '批量检测失败')
  } finally {
    bulkChecking.value = false
  }
}

async function handleSyncAll(direction) {
  try {
    bulkSyncing.value = direction
    const result = await api.syncAllAIModels(direction)
    // 使用返回的数据立即更新表格
    if (result?.data && Array.isArray(result.data)) {
      // 刷新表格会自动加载最新数据
      await loadSupabaseStatus()
      $table.value?.handleSearch()
    }
    window.$message?.success('批量同步已完成')
  } catch (error) {
    window.$message?.error(error.message || '批量同步失败')
  } finally {
    bulkSyncing.value = null
  }
}

async function handleCheckRow(row) {
  try {
    checkingRowId.value = row.id
    const result = await api.checkAIModel(row.id)
    const refreshed = result?.data || row
    appendCheckLog(formatEndpointCheckLog(refreshed))
    if (refreshed?.status === 'online') {
      window.$message?.success('检测成功')
    } else {
      window.$message?.error('检测失败')
    }
    $table.value?.handleSearch()
  } catch (error) {
    window.$message?.error(error.message || '检测失败')
  } finally {
    checkingRowId.value = null
  }
}

async function handleSyncRow(row, direction) {
  try {
    syncingRowId.value = row.id
    const result = await api.syncAIModel(row.id, direction)
    // 使用返回的数据立即更新
    if (result?.data) {
      await loadSupabaseStatus()
      $table.value?.handleSearch()
    }
    window.$message?.success(`端点「${row.name}」同步完成`)
  } catch (error) {
    window.$message?.error(error.message || '同步失败')
  } finally {
    syncingRowId.value = null
  }
}

async function handleDelete(row) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确认要删除端点「${row.name}」吗？`,
    positiveText: '删除',
    negativeText: '取消',
    positiveButtonProps: { type: 'error' },
    async onPositiveClick() {
      try {
        await api.deleteAIModel(row.id)
        window.$message?.success('删除成功')
        await loadSupabaseStatus()
        $table.value?.handleSearch()
      } catch (error) {
        window.$message?.error(error.message || '删除失败')
      }
    },
  })
}

const columns = [
  {
    title: '端点名称',
    key: 'name',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '默认模型',
    key: 'model',
    align: 'center',
    ellipsis: { tooltip: true },
    render: (row) => row.model || '--',
  },
  {
    title: 'Base URL',
    key: 'base_url',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '协议',
    key: 'provider_protocol',
    align: 'center',
    width: 110,
    render: (row) => {
      const protocol = row.provider_protocol || 'openai'
      const isClaude = protocol === 'claude'
      return h(
        NTag,
        { type: isClaude ? 'warning' : 'info', round: true, bordered: false },
        { default: () => (isClaude ? 'Claude' : 'OpenAI') }
      )
    },
  },
  {
    title: '状态',
    key: 'status',
    align: 'center',
    width: 100,
    render: renderStatusTag,
  },
  {
    title: '响应时间',
    key: 'latency_ms',
    align: 'center',
    width: 110,
    render: (row) => formatLatency(row.latency_ms),
  },
  {
    title: '模型列表',
    key: 'model_list',
    align: 'center',
    render: renderModelList,
  },
  {
    title: '标准路径',
    key: 'resolved_endpoints',
    align: 'center',
    render: renderEndpoints,
  },
  {
    title: '最后检测',
    key: 'last_checked_at',
    align: 'center',
    render: (row) => row.last_checked_at || '--',
  },
  {
    title: '最后同步',
    key: 'last_synced_at',
    align: 'center',
    render: (row) => row.last_synced_at || '--',
  },
  {
    title: '操作',
    key: 'actions',
    width: 240,
    align: 'center',
    render(row) {
      const buttons = [
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              loading: checkingRowId.value === row.id,
              onClick: () => handleCheckRow(row),
            },
            {
              default: () => '检测',
              icon: renderIcon('mdi:stethoscope', { size: 16 }),
            }
          ),
          [[vPermission, 'post/api/v1/llm/models']]
        ),
        withDirectives(
          h(
            NDropdown,
            {
              options: syncOptions,
              trigger: 'click',
              disabled: syncingRowId.value === row.id,
              onSelect: (key) => handleSyncRow(row, key),
            },
            {
              default: () =>
                h(
                  NButton,
                  {
                    size: 'small',
                    loading: syncingRowId.value === row.id,
                  },
                  {
                    default: () => '同步',
                    icon: renderIcon('mdi:backup-restore', { size: 16 }),
                  }
                ),
            }
          ),
          [[vPermission, 'post/api/v1/llm/models']]
        ),
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              type: 'primary',
              onClick: () => openEdit(row),
            },
            {
              default: () => '编辑',
              icon: renderIcon('material-symbols:edit-outline-rounded', { size: 16 }),
            }
          ),
          [[vPermission, 'put/api/v1/llm/models']]
        ),
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              type: 'error',
              onClick: () => handleDelete(row),
            },
            {
              default: () => '删除',
              icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
            }
          ),
          [[vPermission, 'delete/api/v1/llm/models']]
        ),
      ]
      return h(NSpace, { justify: 'center' }, buttons)
    },
  },
]

onMounted(async () => {
  await loadLlmAppConfig()
  await loadSupabaseStatus()
  await loadMonitorStatus()
  $table.value?.handleSearch()
})

onBeforeUnmount(() => {
  clearMonitorTimer()
})
</script>

<template>
  <CommonPage show-footer title="AI 供应商（Endpoints）">
    <template #action>
      <NSpace justify="end">
        <NButton tertiary @click="handleGoMapping">
          <TheIcon icon="mdi:graph-outline" :size="18" class="mr-5" />去模型映射
        </NButton>
        <NDropdown
          :options="syncOptions"
          trigger="click"
          :loading="!!bulkSyncing"
          @select="handleSyncAll"
        >
          <NButton
            v-permission="'post/api/v1/llm/models'"
            :loading="!!bulkSyncing"
            type="primary"
            class="mr-10"
          >
            <TheIcon icon="mdi:database-sync" :size="18" class="mr-5" />同步所有端点
          </NButton>
        </NDropdown>
        <NButton
          v-permission="'post/api/v1/llm/models'"
          :loading="bulkChecking"
          secondary
          @click="handleCheckAll"
        >
          <TheIcon icon="mdi:waveform" :size="18" class="mr-5" />检测所有端点
        </NButton>
        <NButton
          v-permission="'post/api/v1/llm/models'"
          type="primary"
          class="float-right"
          @click="handleAdd"
        >
          <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建端点
        </NButton>
      </NSpace>
    </template>

    <NSpace vertical size="large">
      <NAlert type="info" :bordered="false">
        <div class="flex flex-wrap items-center gap-2">
          <span>
            此页仅用于维护供应商 endpoints（Base URL / API Key / 连通性）。App/JWT 只消费「模型映射」输出的
            <code>model</code>（<code>/api/v1/llm/models</code> 的 <code>data[].name</code>）。
          </span>
          <NButton text type="primary" @click="handleGoMapping">去模型映射</NButton>
        </div>
      </NAlert>

      <NCard :loading="llmAppConfigLoading" title="App 转发模式（默认）" size="small">
        <NSpace align="center" wrap>
          <NSelect
            v-model:value="llmAppDefaultResultMode"
            :options="llmAppResultModeOptions"
            placeholder="选择转发模式（透明转发 / XML 文本转发）"
            style="min-width: 280px"
          />
          <NButton type="primary" :loading="llmAppConfigSaving" @click="handleSaveLlmAppConfig">
            保存
          </NButton>
          <NButton secondary :loading="sseProbeRunning" @click="handleRunSseProbe">
            SSE 探针
          </NButton>
          <NTag v-if="sseProbeEvents.length" round :bordered="false" :type="sseProbeSummary.ok ? 'success' : 'warning'">
            {{ sseProbeSummary.ok ? 'PASS' : 'SUSPECT' }}
          </NTag>
          <NTag
            v-if="llmAppDefaultResultModeLegacyAuto"
            round
            :bordered="false"
            type="warning"
          >
            legacy:auto
          </NTag>
          <NTag
            v-else
            round
            :bordered="false"
            :type="llmAppDefaultResultMode === 'raw_passthrough' ? 'warning' : 'success'"
          >
            {{ llmAppDefaultResultMode }}
          </NTag>
        </NSpace>
        <NAlert type="warning" :bordered="false" class="mt-2">
          App 侧若不传 <code>result_mode</code>，后端将按此默认值输出：
          <code>raw_passthrough</code>（透明转发）或 <code>xml_plaintext</code>（XML 文本转发）。
          两者都通过 <code>event: content_delta</code> 以 SSE 流式下发。
        </NAlert>
        <NAlert v-if="llmAppDefaultResultModeLegacyAuto" type="warning" :bordered="false" class="mt-2">
          检测到历史值 <code>auto</code>：为避免歧义，请在上方选择一种并保存（接口保持兼容不变）。
        </NAlert>
      </NCard>

      <NCard :loading="llmAppConfigLoading" title="Web 搜索（Exa）" size="small">
        <NSpace vertical size="small">
          <div class="flex flex-wrap items-center gap-3">
            <NSwitch v-model:value="webSearchEnabled" :disabled="llmAppConfigLoading || webSearchConfigSaving" />
            <NTag round :bordered="false" type="info">
              {{ webSearchProvider || 'exa' }}
            </NTag>
            <NTag
              v-if="webSearchExaApiKeyMasked"
              round
              :bordered="false"
              :type="webSearchExaApiKeySource === 'env' ? 'warning' : 'success'"
            >
              Key: {{ webSearchExaApiKeyMasked }} ({{ webSearchExaApiKeySource }})
            </NTag>
            <NTag v-else round :bordered="false" type="default">
              Key: 未配置
            </NTag>
          </div>

          <NForm label-placement="left" label-width="120">
            <NFormItem label="Exa API Key">
              <NInput
                v-model:value="webSearchExaApiKeyInput"
                type="password"
                placeholder="填写后保存；后端只回显 masked"
                :disabled="llmAppConfigLoading || webSearchConfigSaving"
              />
            </NFormItem>
          </NForm>

          <NSpace wrap>
            <NButton type="primary" :loading="webSearchConfigSaving" @click="handleSaveWebSearchConfig">
              保存
            </NButton>
            <NButton type="error" secondary :loading="webSearchConfigSaving" @click="handleClearWebSearchConfig">
              清空并禁用
            </NButton>
          </NSpace>

          <NAlert type="info" :bordered="false">
            Web 搜索默认关闭。开启后将由后端调用 Exa；建议先保存 Key 再开启，避免 run 过程中因缺少 Key 直接失败。
          </NAlert>
        </NSpace>
      </NCard>

      <NCard :loading="supabaseLoading" title="Supabase 状态" size="small">
        <template #header-extra>
          <NButton text size="small" @click="loadSupabaseStatus">
            <TheIcon icon="mdi:refresh" :size="16" class="mr-4" />Refresh
          </NButton>
        </template>
        <NSpace vertical size="small">
          <div class="flex items-center gap-3">
            <NTag :type="supabaseTagType" round :bordered="false">
              {{ supabaseLabel }}
            </NTag>
            <span v-if="supabaseStatus?.latency_ms">
              Latency: {{ `${supabaseStatus.latency_ms.toFixed(0)} ms` }}
            </span>
            <span v-if="supabaseStatus?.last_synced_at">
              Last sync: {{ supabaseStatus.last_synced_at }}
            </span>
          </div>
          <NAlert v-if="supabaseStatus?.detail" type="info" :bordered="false">
            {{ supabaseStatus.detail }}
          </NAlert>
        </NSpace>
      </NCard>
      <NCard :loading="monitorLoading" size="small" title="端点巡检（Monitor）">
        <NSpace vertical size="small">
          <div class="flex flex-wrap items-center gap-3">
            <NSelect
              v-model:value="monitorIntervalSeconds"
              style="width: 180px"
              :disabled="monitorStatus.is_running || monitorLoading"
              :options="monitorIntervalOptions"
              placeholder="Select interval"
            />
            <NButton
              type="primary"
              :loading="monitorLoading"
              :disabled="monitorStatus.is_running"
              @click="handleStartMonitor"
            >
              <TheIcon icon="mdi:play" :size="16" class="mr-5" />开始
            </NButton>
            <NButton
              type="default"
              tertiary
              :loading="monitorLoading"
              :disabled="!monitorStatus.is_running"
              @click="handleStopMonitor"
            >
              <TheIcon icon="mdi:stop" :size="16" class="mr-5" />停止
            </NButton>
          </div>
          <div class="text-sm text-gray-500">
            <span>状态：{{ monitorStatus.is_running ? '运行中' : '已停止' }}</span>
            <span class="ml-4">最近一次：{{ monitorStatus.last_run_at || '--' }}</span>
            <span class="ml-4">间隔（秒）：{{ monitorStatus.interval_seconds }}</span>
            <span v-if="monitorStatus.last_error" class="ml-4 text-error"
              >Error: {{ monitorStatus.last_error }}</span
            >
          </div>
        </NSpace>
      </NCard>

      <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :columns="columns"
        :get-data="api.getAIModels"
      >
        <template #queryBar>
          <QueryBarItem label="关键字" :label-width="60">
            <NInput
              v-model:value="queryItems.keyword"
              clearable
              placeholder="搜索名称或模型"
              @keypress.enter="$table?.handleSearch()"
            />
          </QueryBarItem>
          <QueryBarItem label="状态" :label-width="50">
            <NSelect
              v-model:value="queryItems.only_active"
              :options="statusOptions"
              clearable
              @update:value="$table?.handleSearch()"
            />
          </QueryBarItem>
        </template>
      </CrudTable>

      <NCard size="small" title="检测日志">
        <template #header-extra>
          <NButton text size="small" @click="clearCheckLogs">
            <TheIcon icon="mdi:delete-sweep" :size="16" class="mr-4" />清空
          </NButton>
        </template>
        <NInput
          :value="checkLogText"
          type="textarea"
          :rows="8"
          readonly
          placeholder="点击『检测』或『检测所有端点』后，这里会显示 success/fail、模型数量、耗时、错误信息等。"
        />
      </NCard>
    </NSpace>

    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :loading="modalLoading"
      @save="handleSave"
    >
      <NForm
        ref="modalFormRef"
        :model="modalForm"
        :rules="formRules"
        label-placement="left"
        label-align="left"
        :label-width="110"
      >
        <NFormItem label="端点名称" path="name">
          <NInput v-model:value="modalForm.name" placeholder="请输入端点名称" />
        </NFormItem>
        <NFormItem label="默认模型" path="model">
          <NInput v-model:value="modalForm.model" placeholder="例如 gpt-4o-mini" />
        </NFormItem>
        <NFormItem label="Base URL" path="base_url">
          <NInput v-model:value="modalForm.base_url" placeholder="例如 https://api.openai.com/v1" />
        </NFormItem>
        <NFormItem label="协议" path="provider_protocol">
          <NSelect v-model:value="modalForm.provider_protocol" :options="protocolOptions" />
        </NFormItem>
        <NFormItem v-if="modalForm.api_key_masked && modalAction === 'edit'" label="当前密钥">
          <NInput :value="modalForm.api_key_masked" disabled />
        </NFormItem>
        <NFormItem label="API Key" path="api_key">
          <NInput
            v-model:value="modalForm.api_key"
            type="password"
            placeholder="留空则保留原值"
            show-password-on="click"
          />
        </NFormItem>
        <NFormItem label="超时时间(秒)" path="timeout">
          <NInputNumber v-model:value="modalForm.timeout" :min="1" :max="600" />
        </NFormItem>
        <NFormItem label="启用">
          <NSwitch v-model:value="modalForm.is_active" />
        </NFormItem>
        <NFormItem label="设为默认">
          <NSwitch v-model:value="modalForm.is_default" @update:value="ensureDefaultActive" />
        </NFormItem>
        <NFormItem label="描述">
          <NInput v-model:value="modalForm.description" type="textarea" placeholder="可选" />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
