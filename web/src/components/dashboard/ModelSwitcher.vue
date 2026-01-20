<template>
  <NCard :title="compact ? undefined : 'AI 供应商 / 映射模型'" size="small">
    <NSpace vertical :size="12">
      <NSelect
        v-model:value="selectedEndpointId"
        :options="endpointOptions"
        :loading="loading"
        placeholder="选择 API（端点）"
        filterable
        @update:value="handleEndpointChange"
      />

      <NSelect
        v-model:value="selectedMappedModel"
        :options="mappedModelOptions"
        :loading="loading"
        placeholder="选择映射模型名（推荐）"
        filterable
        clearable
        @update:value="handleMappedModelChange"
      />

      <NSpace align="center" justify="space-between">
        <NText depth="3">App 转发模式</NText>
        <NSpace align="center" :size="6">
          <NTag v-if="llmAppDefaultResultModeLegacyAuto" size="small" type="warning">legacy:auto</NTag>
          <NSelect
            v-model:value="llmAppDefaultResultMode"
            :options="llmAppResultModeOptions"
            :loading="llmAppConfigLoading"
            :disabled="loading || llmAppConfigLoading || llmAppConfigSaving"
            placeholder="选择转发模式"
            size="small"
            style="min-width: 180px"
            @update:value="handleSaveLlmAppConfig"
          />
          <NButton tertiary size="small" :loading="probeRunning" @click="handleRunSseProbe">
            SSE 探针
          </NButton>
          <NTag v-if="probeEvents.length" size="small" :type="probeSummary.ok ? 'success' : 'warning'">
            {{ probeSummary.ok ? 'PASS' : 'SUSPECT' }}
          </NTag>
        </NSpace>
      </NSpace>

      <NSpace align="center" justify="space-between">
        <NText depth="3">App 输出协议</NText>
        <NSpace align="center" :size="6">
          <NSelect
            v-model:value="llmAppOutputProtocol"
            :options="llmAppOutputProtocolOptions"
            :loading="llmAppConfigLoading"
            :disabled="loading || llmAppConfigLoading || llmAppOutputProtocolSaving"
            placeholder="选择输出协议"
            size="small"
            style="min-width: 180px"
            @update:value="handleSaveLlmAppOutputProtocol"
          />
          <NTag
            size="small"
            :type="llmAppOutputProtocol === 'jsonseq_v1' ? 'success' : 'default'"
          >
            {{ llmAppOutputProtocol }}
          </NTag>
        </NSpace>
      </NSpace>

      <div v-if="!compact && currentEndpoint" class="model-info">
        <NText depth="3" style="font-size: 12px">
          {{ currentEndpoint.base_url }}
        </NText>
        <NSpace :size="4" style="margin-top: 4px">
          <NTag v-if="currentEndpoint.is_active" type="success" size="small">启用</NTag>
          <NTag v-if="currentEndpoint.is_default" type="info" size="small">默认</NTag>
          <NTag :type="statusType[currentEndpoint.status] || 'default'" size="small">
            {{ statusLabel[currentEndpoint.status] || '未知' }}
          </NTag>
        </NSpace>
      </div>
    </NSpace>
  </NCard>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { NButton, NCard, NSelect, NSpace, NText, NTag, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'
import api from '@/api'
import { getToken } from '@/utils'

defineOptions({ name: 'ModelSwitcher' })

defineProps({
  compact: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['change'])

const store = useAiModelSuiteStore()
const { models, modelsLoading, mappings, mappingsLoading } = storeToRefs(store)
const message = useMessage()

const ENDPOINT_ID_KEY = 'dashboard_default_endpoint_id'
const MAPPED_MODEL_KEY = 'dashboard_default_mapped_model'

const selectedEndpointId = ref(null)
const selectedMappedModel = ref('')
const actionLoading = ref(false)
const loading = computed(() => modelsLoading.value || actionLoading.value || mappingsLoading.value)

// LLM App config（App 默认转发模式；持久化 SSOT：llm_app_settings.default_result_mode）
const llmAppConfigLoading = ref(false)
const llmAppConfigSaving = ref(false)
const llmAppDefaultResultMode = ref('raw_passthrough') // xml_plaintext | raw_passthrough（仅两项）
const llmAppDefaultResultModeLegacyAuto = ref(false)
const llmAppResultModeOptions = [
  { label: '透明转发（SSE content_delta）', value: 'raw_passthrough' },
  { label: 'XML 文本转发（SSE content_delta）', value: 'xml_plaintext' },
]
const llmAppOutputProtocolSaving = ref(false)
const llmAppOutputProtocol = ref('thinkingml_v45')
const llmAppOutputProtocolOptions = [
  { label: 'ThinkingML v4.5', value: 'thinkingml_v45' },
  { label: 'JSONSeq v1', value: 'jsonseq_v1' },
]

// SSE 探针：用于定位网关缓冲导致的“假流式 / 大 chunk”
const probeRunning = ref(false)
const probeEvents = ref([])

const probeSummary = computed(() => {
  const items = Array.isArray(probeEvents.value) ? probeEvents.value : []
  if (!items.length) return { ok: false, note: 'no_data', gaps: [] }
  const gaps = []
  for (let i = 1; i < items.length; i += 1) gaps.push(items[i] - items[i - 1])
  const maxGapMs = gaps.length ? Math.max(...gaps) : 0
  return { ok: maxGapMs < 1500, note: maxGapMs ? `max_gap_ms=${maxGapMs}` : 'ok', gaps }
})

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
  if (probeRunning.value) return
  const token = getToken()
  if (!token) {
    message.warning('请先登录（JWT）')
    return
  }

  probeRunning.value = true
  probeEvents.value = []

  try {
    const baseURL = import.meta.env.VITE_BASE_API || '/api/v1'
    const normalizedBase = String(baseURL).replace(/\/+$/, '')
    const url = `${normalizedBase}/base/sse_probe`

    const requestId = `dash-probe-${Date.now()}`
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
          probeEvents.value.push(receivedAtMs)
          if (probeEvents.value.length > 50) probeEvents.value.splice(0, probeEvents.value.length - 50)
        }
        if (ev.event === 'completed') return true
        return false
      },
    })

    message.success(probeSummary.value.ok ? 'SSE 探针：通过（无明显缓冲）' : 'SSE 探针：疑似缓冲/压缩')
  } catch (error) {
    message.error(error?.message || 'SSE 探针失败')
  } finally {
    probeRunning.value = false
  }
}

// 状态映射
const statusType = {
  online: 'success',
  offline: 'error',
  checking: 'warning',
  unknown: 'default',
}

const statusLabel = {
  online: '在线',
  offline: '离线',
  checking: '检测中',
  unknown: '未知',
}

const endpointOptions = computed(() => {
  return (models.value || []).map((endpoint) => ({
    label: endpoint.name || endpoint.base_url || String(endpoint.id),
    value: endpoint.id,
    disabled: !endpoint.is_active,
  }))
})

const currentEndpoint = computed(() => {
  return (models.value || []).find((m) => m.id === selectedEndpointId.value)
})

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

    const protocol = String(data?.app_output_protocol || '').trim().toLowerCase()
    llmAppOutputProtocol.value = ['thinkingml_v45', 'jsonseq_v1'].includes(protocol) ? protocol : 'thinkingml_v45'
  } catch (error) {
    message.error(error?.message || '加载 App 转发模式失败')
  } finally {
    llmAppConfigLoading.value = false
  }
}

async function handleSaveLlmAppOutputProtocol(protocol) {
  const next = String(protocol || '').trim().toLowerCase()
  if (!['thinkingml_v45', 'jsonseq_v1'].includes(next)) return

  const prev = llmAppOutputProtocol.value
  llmAppOutputProtocol.value = next

  llmAppOutputProtocolSaving.value = true
  try {
    const res = await api.upsertLlmAppConfig({ app_output_protocol: next })
    const data = res?.data?.data || res?.data || {}
    const saved = String(data?.app_output_protocol || '').trim().toLowerCase()
    llmAppOutputProtocol.value = ['thinkingml_v45', 'jsonseq_v1'].includes(saved) ? saved : next
    message.success('已更新 App 输出协议')
  } catch (error) {
    llmAppOutputProtocol.value = prev
    message.error(error?.message || '保存 App 输出协议失败')
  } finally {
    llmAppOutputProtocolSaving.value = false
  }
}

async function handleSaveLlmAppConfig(mode) {
  const next = String(mode || '').trim()
  if (!['xml_plaintext', 'raw_passthrough'].includes(next)) return

  const prev = llmAppDefaultResultMode.value
  llmAppDefaultResultMode.value = next

  llmAppConfigSaving.value = true
  try {
    const res = await api.upsertLlmAppConfig({ default_result_mode: next })
    const data = res?.data?.data || res?.data || {}
    const saved = String(data?.default_result_mode || '').trim()
    if (saved === 'auto') {
      llmAppDefaultResultModeLegacyAuto.value = true
      llmAppDefaultResultMode.value = next
    } else {
      llmAppDefaultResultModeLegacyAuto.value = false
      llmAppDefaultResultMode.value = ['xml_plaintext', 'raw_passthrough'].includes(saved) ? saved : next
    }
    message.success('已更新 App 默认转发模式')
  } catch (error) {
    llmAppDefaultResultMode.value = prev
    message.error(error?.message || '保存 App 转发模式失败')
  } finally {
    llmAppConfigSaving.value = false
  }
}

function buildMappedModelOptionsForEndpoint(endpoint) {
  const items = Array.isArray(mappings.value) ? mappings.value : []
  const active = items.filter((m) => m && m.is_active !== false && (m.name || m.id || m.scope_key))

  const endpointModels = new Set()
  if (endpoint && Array.isArray(endpoint.model_list)) {
    endpoint.model_list.forEach((x) => {
      if (typeof x === 'string' && x.trim()) endpointModels.add(x.trim())
    })
  }

  const filtered =
    endpoint && endpointModels.size
      ? active.filter((m) => {
          const target = new Set()
          if (typeof m.default_model === 'string' && m.default_model.trim()) target.add(m.default_model.trim())
          if (Array.isArray(m.candidates)) {
            m.candidates.forEach((x) => {
              if (typeof x === 'string' && x.trim()) target.add(x.trim())
            })
          }
          for (const t of target) {
            if (endpointModels.has(t)) return true
          }
          return false
        })
      : active

  const list = filtered.length ? filtered : active
  return list.map((m) => {
    const name = (m.name || '').trim()
    const fallback = typeof m.id === 'string' && m.id ? m.id : `${m.scope_type}:${m.scope_key}`
    const value = fallback
    const target =
      (typeof m.default_model === 'string' && m.default_model.trim() ? m.default_model.trim() : '') ||
      (Array.isArray(m.candidates) && typeof m.candidates[0] === 'string' ? String(m.candidates[0]) : '')
    const suffix = target ? ` → ${target}` : ''
    const label = `${(name || fallback)}${suffix}`
    return { label, value }
  })
}

const mappedModelOptions = computed(() => {
  return buildMappedModelOptionsForEndpoint(currentEndpoint.value)
})

// 监听 mappings 变化，自动刷新选项
watch(
  () => mappings.value,
  () => {
    // mappings 变更时：若当前映射模型不可用则清理
    const exists = mappedModelOptions.value.some((opt) => opt.value === selectedMappedModel.value)
    if (selectedMappedModel.value && !exists) {
      selectedMappedModel.value = ''
    }
  },
  { deep: true }
)

/**
 * 处理端点切换（仍保留“设为默认端点”的语义）
 */
async function handleEndpointChange(endpointId) {
  if (!endpointId) return

  actionLoading.value = true
  try {
    const endpoint = models.value.find((m) => m.id === endpointId)
    if (!endpoint) {
      message.error('端点不存在')
      return
    }

    // 调用 store action 设置默认端点（SSOT：后端 config）
    await store.setDefaultModel(endpoint)

    selectedEndpointId.value = endpointId
    try {
      localStorage.setItem(ENDPOINT_ID_KEY, String(endpointId))
    } catch {
      // ignore
    }

    emit('change', {
      endpoint_id: endpointId,
      model_source: 'mapping',
      model: selectedMappedModel.value || null,
    })
    message.success(`已切换到端点: ${endpoint.name || endpoint.base_url}`)
  } catch (error) {
    console.error('端点切换失败:', error)
    message.error('端点切换失败，请重试')

    // 恢复到之前的选择
    const defaultEndpoint = models.value.find((m) => m.is_default)
    if (defaultEndpoint) {
      selectedEndpointId.value = defaultEndpoint.id
    }
  } finally {
    actionLoading.value = false
  }
}

function handleMappedModelChange(value) {
  const v = typeof value === 'string' ? value.trim() : ''
  selectedMappedModel.value = v
  try {
    if (v) localStorage.setItem(MAPPED_MODEL_KEY, v)
    else localStorage.removeItem(MAPPED_MODEL_KEY)
  } catch {
    // ignore
  }
  emit('change', {
    endpoint_id: selectedEndpointId.value,
    model_source: 'mapping',
    model: v || null,
  })
}

/**
 * 初始化：加载模型列表、映射数据并设置默认选中
 */
async function initializeModels() {
  actionLoading.value = true
  try {
    // 并行加载模型列表和映射数据
    await Promise.all([store.loadModels(), store.loadMappings()])

    // 1) 端点：优先 localStorage，其次后端 default，其次第一个启用
    const savedEndpointIdRaw = (() => {
      try {
        return localStorage.getItem(ENDPOINT_ID_KEY)
      } catch {
        return null
      }
    })()
    const savedEndpointId = savedEndpointIdRaw ? Number(savedEndpointIdRaw) : null
    const savedEndpoint = savedEndpointId ? models.value.find((m) => m.id === savedEndpointId) : null

    const defaultEndpoint = models.value.find((m) => m.is_default)
    const firstActive = models.value.find((m) => m.is_active)
    selectedEndpointId.value = (savedEndpoint || defaultEndpoint || firstActive || models.value[0] || {}).id ?? null

    // 2) 映射模型：只做客户端默认值（不修改后端）
    try {
      const savedMapped = localStorage.getItem(MAPPED_MODEL_KEY)
      if (savedMapped) selectedMappedModel.value = savedMapped
    } catch {
      // ignore
    }

    // 如果当前映射不在候选中，自动选择第一个
    if (!mappedModelOptions.value.some((opt) => opt.value === selectedMappedModel.value)) {
      selectedMappedModel.value = mappedModelOptions.value[0]?.value || ''
    }

    emit('change', {
      endpoint_id: selectedEndpointId.value,
      model_source: 'mapping',
      model: selectedMappedModel.value || null,
    })
  } catch (error) {
    console.error('加载模型列表失败:', error)
    message.error('加载模型列表失败')
  } finally {
    actionLoading.value = false
  }
}

onMounted(() => {
  initializeModels()
  loadLlmAppConfig()
})
</script>

<style scoped>
.model-info {
  padding: 8px 0;
  border-top: 1px solid var(--n-border-color);
}
</style>
