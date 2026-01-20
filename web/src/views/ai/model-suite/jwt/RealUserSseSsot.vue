<script setup>
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NDivider,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NSelect,
  NSpace,
  NTabPane,
  NTabs,
  NTag,
  NText,
  useMessage,
} from 'naive-ui'

import {
  createAnonToken,
  createMailUser,
  fetchAppModels,
  listMailUsers,
  refreshMailUserToken,
  fetchActivePromptsSnapshot,
  fetchActiveAgentPromptsSnapshot,
  createMessage,
  createAgentRun,
} from '@/api/aiModelSuite'
import api from '@/api'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'
import { validateThinkingMLV45 } from '@/utils/common'
import { requestLogAppendEvent } from '@/utils/http/requestLog'

defineOptions({ name: 'RealUserSseSsot' })

const message = useMessage()
const aiStore = useAiModelSuiteStore()
const { mailApiKey } = storeToRefs(aiStore)

function handleSaveMailApiKey() {
  aiStore.setMailApiKey(mailApiKey.value)
  message.success('Mail API Key 已保存（仅本地）')
}

// ---------------- JWT ----------------
const jwtToken = computed({
  get: () => aiStore.jwtToken,
  set: (value) => aiStore.setJwtTokenManual(value),
})
const tokenMode = computed(() => aiStore.jwtTokenMode) // anonymous | permanent | manual
const tokenMeta = computed(() => aiStore.jwtTokenMeta || { email: '', username: '' })

const creatingTestUser = ref(false)
const creatingTestUserForce = ref(false)
const gettingAnonToken = ref(false)

const mailUsersLoading = ref(false)
const mailUsers = ref([])
const selectedMailUserId = ref(null)
const refreshingMailUser = ref(false)

const mailUserSelectOptions = computed(() =>
  (mailUsers.value || []).map((u) => ({
    label: `${u.email || u.username || `user-${u.id}`}${
      u.has_refresh_token ? '' : '（no refresh_token）'
    }`,
    value: u.id,
    raw: u,
  }))
)

function applyJwtSession({ access_token, mode, meta }) {
  aiStore.setJwtSession({
    accessToken: access_token,
    mode,
    meta,
  })
}

async function loadMailUsers() {
  mailUsersLoading.value = true
  try {
    const res = await listMailUsers({ limit: 100 })
    const items = res?.data?.items
    mailUsers.value = Array.isArray(items) ? items : []
    if (!selectedMailUserId.value && mailUsers.value.length) {
      selectedMailUserId.value = mailUsers.value[0].id
    }
  } catch (error) {
    message.error(error?.message || '加载测试用户列表失败')
  } finally {
    mailUsersLoading.value = false
  }
}

async function handleCreateTestUser(forceNew) {
  if (forceNew) creatingTestUserForce.value = true
  else creatingTestUser.value = true
  try {
    const key = String(mailApiKey.value || '').trim()
    const res = await createMailUser({
      mail_api_key: key || undefined,
      username_prefix: 'gymbro-test-01',
      force_new: !!forceNew,
    })
    const data = res?.data
    if (!data?.access_token) {
      message.error('生成失败：响应缺少 access_token')
      return
    }
    applyJwtSession({
      access_token: data.access_token,
      mode: data.mode || 'permanent',
      meta: { email: data.email, username: data.username },
    })
    await loadMailUsers()
    message.success(forceNew ? '已强制新建并获取 JWT' : '已复用/refresh 并获取 JWT')
  } catch (error) {
    message.error(error?.message || '生成测试用户失败')
  } finally {
    creatingTestUser.value = false
    creatingTestUserForce.value = false
  }
}

async function handleUseSelectedMailUser() {
  if (!selectedMailUserId.value) {
    message.warning('请先选择一个已保存测试用户')
    return
  }
  refreshingMailUser.value = true
  try {
    const res = await refreshMailUserToken(selectedMailUserId.value)
    const data = res?.data
    if (!data?.access_token) {
      message.error('刷新失败：响应缺少 access_token')
      return
    }
    applyJwtSession({
      access_token: data.access_token,
      mode: data.mode || 'permanent',
      meta: { email: data.email, username: data.username },
    })
    await loadMailUsers()
    message.success('已刷新并切换到所选测试用户')
  } catch (error) {
    message.error(error?.message || '刷新测试用户 token 失败')
  } finally {
    refreshingMailUser.value = false
  }
}

async function handleGetAnonToken(forceNew) {
  gettingAnonToken.value = true
  try {
    const res = await createAnonToken({ force_new: !!forceNew })
    const data = res?.data
    if (!data?.access_token) {
      message.error('匿名 JWT 获取失败：响应缺少 access_token')
      return
    }
    applyJwtSession({
      access_token: data.access_token,
      mode: 'anonymous',
      meta: { email: '', username: 'anon' },
    })
    message.success(forceNew ? '已重新生成匿名用户' : '匿名 JWT 获取成功')
  } catch (error) {
    message.error(error?.message || '匿名 JWT 获取失败')
  } finally {
    gettingAnonToken.value = false
  }
}

function handleCopyToken() {
  if (!jwtToken.value) return
  navigator.clipboard.writeText(jwtToken.value)
  message.success('Token 已复制')
}

const tokenModeLabel = computed(() => {
  if (tokenMode.value === 'anonymous') return '匿名'
  if (tokenMode.value === 'permanent') return '永久'
  if (tokenMode.value === 'manual') return '手动'
  return tokenMode.value || 'unknown'
})

// ---------------- Models (SSOT) ----------------
const modelsLoading = ref(false)
const appModels = ref([])
const selectedModel = ref('')

const modelSelectOptions = computed(() =>
  (appModels.value || []).map((m) => {
    const name = String(m?.name || '').trim()
    const target = String(m?.default_model || '').trim()
    const suffix = target ? ` → ${target}` : ''
    return { label: `${name}${suffix}`, value: name, raw: m }
  })
)

async function loadAppModels() {
  modelsLoading.value = true
  try {
    const res = await fetchAppModels({ only_active: true })
    const items = res?.data
    appModels.value = Array.isArray(items) ? items : []
    if (!selectedModel.value && appModels.value.length) {
      selectedModel.value = String(appModels.value[0].name || '')
    }
  } catch (error) {
    message.error(error?.message || '加载模型列表失败')
  } finally {
    modelsLoading.value = false
  }
}

// ---------------- Chat ----------------
const sending = ref(false)
const chatText = ref('Hello, this is a JWT SSE test message.')
const conversationId = ref('')
const messageId = ref('')
const activeStreamKind = ref('messages') // messages | agent_runs
const aiResponseText = ref('')
const aiResponseRaw = ref('')
const resultModeEffective = ref('')
const lastCreateRequestId = ref('')
const lastSseRequestId = ref('')
const activeChatTab = ref('agent') // agent | messages

// prompt / result mode
const promptMode = ref('server') // server | passthrough
const DEFAULT_EXTRA_SYSTEM_PROMPT = `请严格按原样输出 Strict-XML（ThinkingML v4.5）：\n1) 必须输出且仅输出一个 XML 文本：<thinking>...</thinking> 紧接 <final>...</final>\n2) 只允许标签：think/serp/thinking/phase/title/final（phase 必须有 id=\"1..N\" 且递增）\n3) <final> 内容最后必须追加：\n<!-- <serp_queries>\n[\"q1\",\"q2\",\"q3\"]\n</serp_queries> -->\n4) 不要解释协议，不要使用 Markdown 代码块包裹 XML；若无法满足，输出 <<ParsingError>>`
const extraSystemPrompt = ref('')
const agentPromptMode = ref('server') // server | passthrough
const agentExtraSystemPrompt = ref('')
const resultMode = ref('xml_plaintext') // xml_plaintext | raw_passthrough | auto
const toolChoice = ref('') // '' | none | auto（OpenAI tool_choice）
const autoValidateOnCompleted = ref(true)
const thinkingmlValidation = ref({ ok: false, reason: 'empty_reply' })
const jsonseqValidation = ref({ ok: false, reason: 'empty_events' })

const sseEvents = ref([])
const streamStartedAtMs = ref(0)
const firstDeltaAtMs = ref(0)
const lastDeltaAtMs = ref(0)

// Agent tools（请求级开关；默认遵循后端配置，避免与 Dashboard 漂移）
const agentEnableExerciseSearch = ref(true)
const agentExerciseTopK = ref(5)
const agentDisableWebSearch = ref(false)
const agentWebSearchTopK = ref(5)

// LLM App Config（SSOT：/api/v1/llm/app/config）
const appConfigLoading = ref(false)
const appConfigError = ref('')
const dashboardDefaultResultMode = ref('')
const dashboardAppOutputProtocol = ref('thinkingml_v45')
const dashboardPromptMode = ref('server')
const dashboardWebSearchEnabled = ref(false)
const dashboardWebSearchProvider = ref('exa')
const dashboardWebSearchExaApiKeyMasked = ref('')
const dashboardWebSearchExaApiKeySource = ref('none')
const didInitResultModeFromDashboard = ref(false)
const didInitPromptModeFromDashboard = ref(false)
const appOutputProtocolSaving = ref(false)

const appOutputProtocolOptions = [
  { label: 'ThinkingML v4.5（兼容旧客户端）', value: 'thinkingml_v45' },
  { label: 'JSONSeq v1（事件流：客户端只认事件）', value: 'jsonseq_v1' },
]

async function loadAppConfig() {
  appConfigLoading.value = true
  appConfigError.value = ''
  try {
    const res = await api.getLlmAppConfig()
    const data = res?.data?.data || res?.data || {}
    const mode = String(data?.default_result_mode || '').trim()
    const normalizedMode = ['xml_plaintext', 'raw_passthrough', 'auto'].includes(mode)
      ? mode
      : 'raw_passthrough'
    dashboardDefaultResultMode.value = normalizedMode

    const protocol = String(data?.app_output_protocol || '').trim().toLowerCase()
    dashboardAppOutputProtocol.value = ['thinkingml_v45', 'jsonseq_v1'].includes(protocol)
      ? protocol
      : 'thinkingml_v45'

    const pm = String(data?.prompt_mode || '').trim().toLowerCase()
    const normalizedPromptMode = pm === 'passthrough' ? 'passthrough' : 'server'
    dashboardPromptMode.value = normalizedPromptMode

    dashboardWebSearchEnabled.value = Boolean(data?.web_search_enabled)
    dashboardWebSearchProvider.value = String(data?.web_search_provider || 'exa').trim().toLowerCase() || 'exa'
    dashboardWebSearchExaApiKeyMasked.value = String(data?.web_search_exa_api_key_masked || '').trim()
    dashboardWebSearchExaApiKeySource.value = String(data?.web_search_exa_api_key_source || 'none').trim()

    // 默认跟随 Dashboard（避免 JWT 页与 Dashboard 漂移）
    if (!didInitResultModeFromDashboard.value && normalizedMode) {
      resultMode.value = normalizedMode
      didInitResultModeFromDashboard.value = true
    }
    if (!didInitPromptModeFromDashboard.value && normalizedPromptMode) {
      promptMode.value = normalizedPromptMode
      agentPromptMode.value = normalizedPromptMode
      didInitPromptModeFromDashboard.value = true
    }
  } catch (error) {
    appConfigError.value = error?.message || '加载 App 配置失败'
  } finally {
    appConfigLoading.value = false
  }
}

async function saveAppOutputProtocol(nextProtocol) {
  appOutputProtocolSaving.value = true
  try {
    const protocol = String(nextProtocol || '').trim().toLowerCase()
    if (!['thinkingml_v45', 'jsonseq_v1'].includes(protocol)) {
      message.warning('请选择输出协议（ThinkingML v4.5 / JSONSeq v1）')
      return
    }
    const res = await api.upsertLlmAppConfig({ app_output_protocol: protocol })
    const data = res?.data?.data || res?.data || {}
    const saved = String(data?.app_output_protocol || '').trim().toLowerCase()
    dashboardAppOutputProtocol.value = ['thinkingml_v45', 'jsonseq_v1'].includes(saved) ? saved : protocol
    message.success('已更新 App 输出协议（全局 SSOT）')
  } catch (error) {
    message.error(error?.message || '保存 App 输出协议失败')
  } finally {
    appOutputProtocolSaving.value = false
  }
}

async function handleSaveAppOutputProtocol() {
  await saveAppOutputProtocol(dashboardAppOutputProtocol.value)
}

async function handleRestoreDefaultAppOutputProtocol() {
  await saveAppOutputProtocol('thinkingml_v45')
}

// Dashboard active prompts（只读预览，避免 JWT 页与 Dashboard 漂移）
const activePromptsLoading = ref(false)
const activePromptsSnapshot = ref(null)
const activePromptsError = ref('')

const activeAgentPromptsSnapshot = ref(null)
const activeAgentPromptsError = ref('')

const effectiveSystemMessagePreview = computed(() =>
  String(activePromptsSnapshot.value?.effective_system_message || '').trim()
)
const effectiveAgentSystemMessagePreview = computed(() =>
  String(activeAgentPromptsSnapshot.value?.effective_system_message || '').trim()
)
const promptsSnapshotForPreview = computed(() =>
  activeChatTab.value === 'agent' ? activeAgentPromptsSnapshot.value : activePromptsSnapshot.value
)
const promptsErrorForPreview = computed(() =>
  activeChatTab.value === 'agent' ? activeAgentPromptsError.value : activePromptsError.value
)
const effectiveSystemMessageForPreview = computed(() =>
  activeChatTab.value === 'agent' ? effectiveAgentSystemMessagePreview.value : effectiveSystemMessagePreview.value
)

const toolChoiceRisk = computed(() => String(toolChoice.value || '').trim() === 'auto')
const agentWebSearchStatus = computed(() => {
  const enabled = Boolean(dashboardWebSearchEnabled.value)
  const masked = String(dashboardWebSearchExaApiKeyMasked.value || '').trim()
  const keySource = String(dashboardWebSearchExaApiKeySource.value || 'none').trim() || 'none'
  const requestDisabled = Boolean(agentDisableWebSearch.value)
  return {
    enabled,
    provider: String(dashboardWebSearchProvider.value || 'exa').trim() || 'exa',
    keyMasked: masked,
    keySource,
    hasKey: !!masked,
    requestDisabled,
    willRun: enabled && !requestDisabled,
  }
})

async function loadActivePrompts() {
  activePromptsLoading.value = true
  activePromptsError.value = ''
  activeAgentPromptsError.value = ''
  try {
    const [chatRes, agentRes] = await Promise.allSettled([
      fetchActivePromptsSnapshot(),
      fetchActiveAgentPromptsSnapshot(),
    ])
    if (chatRes.status === 'fulfilled') activePromptsSnapshot.value = chatRes.value?.data ?? null
    else activePromptsError.value = chatRes.reason?.message || '加载 active prompts 失败'

    if (agentRes.status === 'fulfilled') activeAgentPromptsSnapshot.value = agentRes.value?.data ?? null
    else activeAgentPromptsError.value = agentRes.reason?.message || '加载 agent prompts 失败'
  } catch (error) {
    activePromptsError.value = error?.message || '加载 prompts 失败'
  } finally {
    activePromptsLoading.value = false
  }
}

function handleFillExtraPromptFromDashboard() {
  const text = effectiveSystemMessagePreview.value
  if (!text) {
    message.warning('当前无可用的 Dashboard system message（请先在 Prompt 管理页启用）')
    return
  }
  promptMode.value = 'passthrough'
  extraSystemPrompt.value = text
  message.success('已填充为 Dashboard 有效 system message（包含 tools prompt patch）')
}

function handleFillExtraPromptTemplate() {
  promptMode.value = 'passthrough'
  extraSystemPrompt.value = DEFAULT_EXTRA_SYSTEM_PROMPT
  message.success('已填充默认 Strict-XML 模板')
}

function pushSseEvent(ev, receivedAtMs) {
  const entry = {
    ts_ms: receivedAtMs,
    event: String(ev?.event || 'message'),
    data: ev?.data ?? null,
  }
  sseEvents.value.push(entry)
  if (sseEvents.value.length > 600) sseEvents.value.splice(0, sseEvents.value.length - 600)
}

function genRequestId(prefix) {
  const rid =
    globalThis.crypto?.randomUUID?.() ||
    `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
  return String(rid)
}

function handleSwitchToServerAndClearPrompt() {
  promptMode.value = 'server'
  extraSystemPrompt.value = ''
}

function handleSwitchAgentToServerAndClearPrompt() {
  agentPromptMode.value = 'server'
  agentExtraSystemPrompt.value = ''
}

function handleFillAgentExtraPromptFromDashboard() {
  const text = effectiveAgentSystemMessagePreview.value
  if (!text) {
    message.warning('当前无可用的 Dashboard agent system message（请先在 Prompt 管理页启用）')
    return
  }
  agentPromptMode.value = 'passthrough'
  agentExtraSystemPrompt.value = text
  message.success('已填充为 Dashboard agent 有效 system message（包含 agent tools prompt patch）')
}

function handleFillAgentExtraPromptTemplate() {
  agentPromptMode.value = 'passthrough'
  agentExtraSystemPrompt.value = DEFAULT_EXTRA_SYSTEM_PROMPT
  message.success('已填充默认 Strict-XML 模板（用于 agent passthrough）')
}

function handleResetPromptDefaults() {
  promptMode.value = dashboardPromptMode.value || 'server'
  extraSystemPrompt.value = ''
  agentPromptMode.value = dashboardPromptMode.value || 'server'
  agentExtraSystemPrompt.value = ''
  toolChoice.value = ''
  resultMode.value = dashboardDefaultResultMode.value || 'xml_plaintext'
  agentEnableExerciseSearch.value = true
  agentExerciseTopK.value = 5
  agentDisableWebSearch.value = false
  agentWebSearchTopK.value = 5
  activeChatTab.value = 'agent'
}

async function handleSend() {
  if (!jwtToken.value) {
    message.warning('请先获取 JWT Token')
    return
  }
  if (!selectedModel.value) {
    message.warning('请先选择模型（来自 /api/v1/llm/models）')
    return
  }
  if (!chatText.value.trim()) {
    message.warning('请输入对话内容')
    return
  }

  sending.value = true
  activeStreamKind.value = 'messages'
  aiResponseText.value = ''
  aiResponseRaw.value = ''
  messageId.value = ''
  resultModeEffective.value = ''
  sseEvents.value = []
  streamStartedAtMs.value = 0
  firstDeltaAtMs.value = 0
  lastDeltaAtMs.value = 0
  thinkingmlValidation.value = { ok: false, reason: 'empty_reply' }
  jsonseqValidation.value = { ok: false, reason: 'empty_events' }

  try {
    const createRequestId = genRequestId('web-create')
    lastCreateRequestId.value = createRequestId

    const resolvedPromptMode = promptMode.value === 'passthrough' ? 'passthrough' : 'server'
    const userText = chatText.value.trim()
    const normalizedToolChoice = String(toolChoice.value || '').trim()

    const openai =
      resolvedPromptMode === 'passthrough'
        ? {
            model: selectedModel.value,
            messages: [
              {
                role: 'system',
                content: String(extraSystemPrompt.value || '').trim() || undefined,
              },
              { role: 'user', content: userText },
            ].filter((m) => m && m.content),
            tool_choice: normalizedToolChoice ? normalizedToolChoice : undefined,
          }
        : { model: selectedModel.value, tool_choice: normalizedToolChoice ? normalizedToolChoice : undefined }

    const created = await createMessage({
      text: resolvedPromptMode === 'server' ? userText : undefined,
      conversationId: conversationId.value || null,
      metadata: {
        scenario: 'ai_jwt_ssot_sse',
        model: selectedModel.value,
        prompt_mode: resolvedPromptMode,
        extra_prompt_len:
          resolvedPromptMode === 'passthrough'
            ? String(extraSystemPrompt.value || '').trim().length
            : 0,
        result_mode: resultMode.value,
        tool_choice: normalizedToolChoice || null,
      },
      requestId: createRequestId,
      promptMode: resolvedPromptMode,
      resultMode: resultMode.value,
      openai,
      accessToken: jwtToken.value,
    })

    messageId.value = created.message_id
    conversationId.value = created.conversation_id

    const sseRequestId = genRequestId('web-sse')
    lastSseRequestId.value = sseRequestId
    await streamSse(messageId.value, conversationId.value, sseRequestId, { kind: 'messages' })
  } catch (error) {
    message.error(error?.message || '发送失败')
  } finally {
    sending.value = false
  }
}

async function handleSendAgentRun() {
  if (!jwtToken.value) {
    message.warning('请先获取 JWT Token')
    return
  }
  if (!selectedModel.value) {
    message.warning('请先选择模型（来自 /api/v1/llm/models）')
    return
  }
  if (!chatText.value.trim()) {
    message.warning('请输入对话内容')
    return
  }

  sending.value = true
  activeStreamKind.value = 'agent_runs'
  aiResponseText.value = ''
  aiResponseRaw.value = ''
  messageId.value = ''
  resultModeEffective.value = ''
  sseEvents.value = []
  streamStartedAtMs.value = 0
  firstDeltaAtMs.value = 0
  lastDeltaAtMs.value = 0
  thinkingmlValidation.value = { ok: false, reason: 'empty_reply' }
  jsonseqValidation.value = { ok: false, reason: 'empty_events' }

  try {
    const createRequestId = genRequestId('web-agent-create')
    lastCreateRequestId.value = createRequestId

    const resolvedPromptMode = agentPromptMode.value === 'passthrough' ? 'passthrough' : 'server'
    const userText = chatText.value.trim()
    if (resolvedPromptMode === 'passthrough' && !String(agentExtraSystemPrompt.value || '').trim()) {
      message.warning('agent passthrough 需要提供 system message（建议“填充 Dashboard agent system message”）')
      return
    }

    const openai =
      resolvedPromptMode === 'passthrough'
        ? {
            model: selectedModel.value,
            messages: [
              { role: 'system', content: String(agentExtraSystemPrompt.value || '').trim() || undefined },
              { role: 'user', content: userText },
            ].filter((m) => m && m.content),
          }
        : undefined

    const created = await createAgentRun({
      model: selectedModel.value,
      text: userText,
      conversationId: conversationId.value || null,
      metadata: {
        scenario: 'ai_jwt_agent_run_sse',
        model: selectedModel.value,
        prompt_mode: resolvedPromptMode,
        extra_prompt_len: resolvedPromptMode === 'passthrough' ? String(agentExtraSystemPrompt.value || '').trim().length : 0,
        result_mode: resultMode.value,
        enable_exercise_search: agentEnableExerciseSearch.value,
        exercise_top_k: agentExerciseTopK.value,
        disable_web_search: agentDisableWebSearch.value,
        web_search_top_k: agentWebSearchTopK.value,
      },
      resultMode: resultMode.value,
      promptMode: resolvedPromptMode,
      openai,
      enableExerciseSearch: agentEnableExerciseSearch.value,
      exerciseTopK: agentExerciseTopK.value,
      enableWebSearch: agentDisableWebSearch.value ? false : undefined,
      webSearchTopK: agentWebSearchTopK.value,
      requestId: createRequestId,
      accessToken: jwtToken.value,
    })

    messageId.value = created.run_id
    conversationId.value = created.conversation_id

    const sseRequestId = genRequestId('web-agent-sse')
    lastSseRequestId.value = sseRequestId
    await streamSse(messageId.value, conversationId.value, sseRequestId, { kind: 'agent_runs' })
  } catch (error) {
    message.error(error?.message || 'Agent Run 失败')
  } finally {
    sending.value = false
  }
}

async function consumeSseReader(reader, { url, requestId, onEvent }) {
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
          requestLogAppendEvent({ kind: 'sse', url, requestId, event: ev })
          pushSseEvent(ev, receivedAtMs)
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

async function streamSse(msgId, convId, requestId, { kind = 'messages' } = {}) {
  const baseURL = import.meta.env.VITE_BASE_API || '/api/v1'
  const normalizedBase = String(baseURL).replace(/\/+$/, '')
  const path =
    String(kind) === 'agent_runs'
      ? convId
        ? `/agent/runs/${msgId}/events?conversation_id=${encodeURIComponent(convId)}`
        : `/agent/runs/${msgId}/events`
      : convId
        ? `/messages/${msgId}/events?conversation_id=${encodeURIComponent(convId)}`
        : `/messages/${msgId}/events`
  const url = `${normalizedBase}${path}`

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${jwtToken.value}`,
      Accept: 'text/event-stream',
      'X-Request-Id': requestId,
    },
  })

  if (!response.ok) {
    const text = await response.text().catch(() => '')
    throw new Error(`SSE 连接失败：${response.status} ${text}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('SSE 响应不支持流式读取')

  streamStartedAtMs.value = Date.now()

  await consumeSseReader(reader, {
    url,
    requestId,
    onEvent: async (ev, receivedAtMs) => {
      if (ev.event === 'status') {
        if (typeof ev.data?.result_mode_effective === 'string') {
          resultModeEffective.value = ev.data.result_mode_effective
        }
      }
      if (ev.event === 'upstream_raw') {
        const chunk =
          typeof ev.data === 'string' ? ev.data : typeof ev.data?.raw === 'string' ? ev.data.raw : ''
        if (chunk) aiResponseRaw.value += `${chunk}\n`
      }
      if (ev.event === 'content_delta' && ev.data?.delta) {
        if (!firstDeltaAtMs.value) firstDeltaAtMs.value = receivedAtMs
        lastDeltaAtMs.value = receivedAtMs
        aiResponseText.value += String(ev.data.delta)
      }
      if (ev.event === 'final_delta' && ev.data?.text) {
        if (!firstDeltaAtMs.value) firstDeltaAtMs.value = receivedAtMs
        lastDeltaAtMs.value = receivedAtMs
        aiResponseText.value += String(ev.data.text)
      }
      if (ev.event === 'completed') {
        if (typeof ev.data?.result_mode_effective === 'string') {
          resultModeEffective.value = ev.data.result_mode_effective
        }
        if (typeof ev.data === 'object' && ev.data && typeof ev.data.reply === 'string') {
          aiResponseText.value = ev.data.reply
        }
        if (resultMode.value !== 'raw_passthrough') {
          try {
            aiResponseRaw.value = JSON.stringify(ev.data ?? ev, null, 2)
          } catch {
            aiResponseRaw.value = String(ev.data ?? ev)
          }
        } else {
          let tail = ''
          try {
            tail = JSON.stringify(ev.data ?? ev, null, 2)
          } catch {
            tail = String(ev.data ?? ev)
          }
          if (tail) aiResponseRaw.value += `\n[completed]\n${tail}\n`
        }

        const effective = String(resultModeEffective.value || resultMode.value || '').trim()
        const protocol = String(dashboardAppOutputProtocol.value || '').trim().toLowerCase()
        const shouldValidateThinkingml =
          autoValidateOnCompleted.value && effective !== 'raw_passthrough' && protocol !== 'jsonseq_v1'
        if (shouldValidateThinkingml) thinkingmlValidation.value = validateThinkingMLV45(aiResponseText.value)

        const shouldValidateJsonseq =
          autoValidateOnCompleted.value && effective !== 'raw_passthrough' && protocol === 'jsonseq_v1'
        if (shouldValidateJsonseq) jsonseqValidation.value = validateJsonseqV1Events(sseEvents.value)
        return true
      }
      if (ev.event === 'error') {
        if (typeof ev.data?.result_mode_effective === 'string') {
          resultModeEffective.value = ev.data.result_mode_effective
        }
        const msg = typeof ev.data === 'string' ? ev.data : JSON.stringify(ev.data)
        if (resultMode.value !== 'raw_passthrough') {
          try {
            aiResponseRaw.value = JSON.stringify(ev.data ?? ev, null, 2)
          } catch {
            aiResponseRaw.value = String(ev.data ?? ev)
          }
        } else {
          let tail = ''
          try {
            tail = JSON.stringify(ev.data ?? ev, null, 2)
          } catch {
            tail = String(ev.data ?? ev)
          }
          if (tail) aiResponseRaw.value += `\n[error]\n${tail}\n`
        }
        throw new Error(msg || 'SSE error')
      }
      return false
    },
  })
}

onMounted(() => {
  loadMailUsers()
  loadAppModels()
  loadAppConfig()
  loadActivePrompts()
})

const sseStats = computed(() => {
  const events = Array.isArray(sseEvents.value) ? sseEvents.value : []
  const deltas = events
    .filter((e) => {
      if (!e || !e.data) return false
      if (e.event === 'content_delta') return typeof e.data.delta === 'string'
      if (e.event === 'final_delta') return typeof e.data.text === 'string'
      return false
    })
    .map((e) => {
      const text = e.event === 'content_delta' ? String(e.data.delta || '') : String(e.data.text || '')
      return { ts_ms: Number(e.ts_ms || 0), len: text.length }
    })

  const count = deltas.length
  const totalLen = deltas.reduce((sum, d) => sum + (Number.isFinite(d.len) ? d.len : 0), 0)
  const avgLen = count ? Math.round((totalLen / count) * 10) / 10 : 0
  let maxGapMs = 0
  for (let i = 1; i < deltas.length; i += 1) {
    const gap = deltas[i].ts_ms - deltas[i - 1].ts_ms
    if (gap > maxGapMs) maxGapMs = gap
  }

  const started = Number(streamStartedAtMs.value || 0)
  const ttftMs =
    started && firstDeltaAtMs.value ? Math.max(0, Number(firstDeltaAtMs.value) - started) : 0
  const durationMs = started ? Math.max(0, Date.now() - started) : 0

  return { deltaCount: count, avgDeltaLen: avgLen, maxGapMs, ttftMs, durationMs }
})

const sseEventsText = computed(() => {
  const events = Array.isArray(sseEvents.value) ? sseEvents.value : []
  return events
    .map((e) => {
      const ts = new Date(Number(e.ts_ms || 0)).toISOString()
      const ev = String(e.event || 'message')
      const data = e.data
      let brief = ''
      if (ev === 'content_delta') {
        const delta = typeof data?.delta === 'string' ? data.delta : ''
        brief = `seq=${data?.seq ?? '--'} len=${delta.length} "${delta.slice(0, 80).replace(/\n/g, '\\n')}"`
      } else if (ev === 'final_delta') {
        const text = typeof data?.text === 'string' ? data.text : ''
        brief = `len=${text.length} "${text.slice(0, 80).replace(/\n/g, '\\n')}"`
      } else if (ev === 'serp_summary') {
        const text = typeof data?.text === 'string' ? data.text : ''
        brief = `len=${text.length} "${text.slice(0, 80).replace(/\n/g, '\\n')}"`
      } else if (ev === 'serp_queries') {
        const queries = Array.isArray(data?.queries) ? data.queries : []
        const preview = queries.map((q) => String(q || '').slice(0, 32)).join(' | ')
        brief = `count=${queries.length} "${preview}"`
      } else if (ev === 'phase_start') {
        const id = data?.id ?? '--'
        const title = String(data?.title || '').slice(0, 60)
        brief = `id=${id} title="${title}"`
      } else if (ev === 'phase_delta') {
        const id = data?.id ?? '--'
        const text = typeof data?.text === 'string' ? data.text : ''
        brief = `id=${id} len=${text.length} "${text.slice(0, 80).replace(/\n/g, '\\n')}"`
      } else if (ev === 'upstream_raw') {
        const raw = typeof data?.raw === 'string' ? data.raw : typeof data === 'string' ? data : ''
        brief = `seq=${data?.seq ?? '--'} len=${raw.length} "${raw.slice(0, 80).replace(/\n/g, '\\n')}"`
      } else if (ev === 'status') {
        brief = `status=${data?.status ?? '--'} effective=${data?.result_mode_effective ?? '--'}`
      } else if (ev === 'tool_start') {
        const tool = String(data?.tool_name || '--')
        let args = ''
        try {
          args = JSON.stringify(data?.args ?? {})
        } catch {
          args = ''
        }
        if (args.length > 160) args = `${args.slice(0, 159)}…`
        brief = `tool=${tool} args=${args}`
      } else if (ev === 'tool_result') {
        const tool = String(data?.tool_name || '--')
        const ok = typeof data?.ok === 'boolean' ? data.ok : '--'
        const ms = data?.elapsed_ms ?? '--'
        let hint = ''
        if (data?.result?.total !== undefined) hint = `total=${data.result.total}`
        else if (data?.error?.code) hint = `err=${data.error.code}`
        brief = `tool=${tool} ok=${ok} ms=${ms} ${hint}`.trim()
      } else if (ev === 'completed') {
        brief = `reply_len=${typeof data?.reply === 'string' ? data.reply.length : '--'} effective=${
          data?.result_mode_effective ?? '--'
        }`
      } else if (ev === 'error') {
        brief = `code=${data?.code ?? '--'}`
      }
      return `${ts} ${ev} ${brief}`.trim()
    })
    .join('\n')
})

const toolEventsText = computed(() => {
  const events = Array.isArray(sseEvents.value) ? sseEvents.value : []
  const lines = []
  for (const e of events) {
    if (!e || (e.event !== 'tool_start' && e.event !== 'tool_result')) continue
    const ts = new Date(Number(e.ts_ms || 0)).toISOString()
    const ev = String(e.event || 'message')
    let brief = ''
    if (ev === 'tool_start') {
      const tool = String(e?.data?.tool_name || '--')
      brief = tool
    } else if (ev === 'tool_result') {
      const tool = String(e?.data?.tool_name || '--')
      const ok = typeof e?.data?.ok === 'boolean' ? e.data.ok : '--'
      const ms = e?.data?.elapsed_ms ?? '--'
      let hint = ''
      if (e?.data?.result?.total !== undefined) hint = `total=${e.data.result.total}`
      else if (e?.data?.error?.code) hint = `err=${e.data.error.code}`
      brief = `${tool} ok=${ok} ms=${ms} ${hint}`.trim()
    }
    lines.push(`${ts} ${ev} ${brief}`.trim())
  }
  return lines.join('\n')
})

function handleValidateThinkingML() {
  thinkingmlValidation.value = validateThinkingMLV45(aiResponseText.value)
  if (thinkingmlValidation.value.ok) message.success('ThinkingML 校验通过')
  else message.warning(`ThinkingML 校验失败：${thinkingmlValidation.value.reason}`)
}

function hasSensitiveQueryToken(query) {
  const q = String(query || '').trim()
  if (!q) return false
  const lower = q.toLowerCase()
  if (lower.includes('@') && /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/i.test(q)) return true
  if (/\b\d{1,3}(\.\d{1,3}){3}\b/.test(q)) return true
  if (/\b1\d{10}\b/.test(q)) return true
  return false
}

function validateJsonseqV1Events(allEvents) {
  const allowed = new Set([
    'serp_summary',
    'thinking_start',
    'phase_start',
    'phase_delta',
    'thinking_end',
    'final_delta',
    'serp_queries',
    'final_end',
  ])

  const seq = (Array.isArray(allEvents) ? allEvents : []).filter((e) => e && allowed.has(String(e.event || '')))
  if (!seq.length) return { ok: false, reason: 'no_jsonseq_events' }

  let serpSummaryCount = 0
  let serpQueriesCount = 0
  let sawThinkingStart = false
  let sawThinkingEnd = false
  let sawFinalEnd = false
  let currentPhaseId = 0
  let finalDeltaCount = 0
  let finalTextLen = 0

  for (const e of seq) {
    const ev = String(e.event || '')
    const data = e.data || {}

    if (ev === 'serp_summary') {
      serpSummaryCount += 1
      if (serpSummaryCount > 1) return { ok: false, reason: 'serp_summary_multiple' }
      if (sawThinkingStart) return { ok: false, reason: 'serp_summary_after_thinking_start' }
      const text = typeof data?.text === 'string' ? data.text : ''
      if (!text.trim()) return { ok: false, reason: 'serp_summary_text_empty' }
      if (text.includes('<') || text.includes('>')) return { ok: false, reason: 'serp_summary_has_xml' }
      continue
    }

    if (ev === 'thinking_start') {
      if (sawThinkingStart) return { ok: false, reason: 'thinking_start_multiple' }
      if (sawThinkingEnd || finalDeltaCount || sawFinalEnd) return { ok: false, reason: 'thinking_start_after_end' }
      sawThinkingStart = true
      continue
    }

    if (ev === 'phase_start') {
      if (!sawThinkingStart) return { ok: false, reason: 'phase_start_before_thinking_start' }
      if (sawThinkingEnd) return { ok: false, reason: 'phase_start_after_thinking_end' }
      const id = Number(data?.id)
      if (!Number.isInteger(id) || id <= 0) return { ok: false, reason: 'phase_id_invalid' }
      const title = String(data?.title || '').trim()
      if (!title) return { ok: false, reason: 'phase_title_empty' }
      if (id !== currentPhaseId + 1) return { ok: false, reason: 'phase_id_not_incremental' }
      currentPhaseId = id
      continue
    }

    if (ev === 'phase_delta') {
      if (!sawThinkingStart) return { ok: false, reason: 'phase_delta_before_thinking_start' }
      if (sawThinkingEnd) return { ok: false, reason: 'phase_delta_after_thinking_end' }
      const id = Number(data?.id)
      if (!Number.isInteger(id) || id <= 0) return { ok: false, reason: 'phase_delta_id_invalid' }
      if (!currentPhaseId) return { ok: false, reason: 'phase_delta_without_phase_start' }
      if (id !== currentPhaseId) return { ok: false, reason: 'phase_delta_id_mismatch' }
      if (typeof data?.text !== 'string') return { ok: false, reason: 'phase_delta_text_invalid' }
      continue
    }

    if (ev === 'thinking_end') {
      if (!sawThinkingStart) return { ok: false, reason: 'thinking_end_before_thinking_start' }
      if (sawThinkingEnd) return { ok: false, reason: 'thinking_end_multiple' }
      if (currentPhaseId < 1) return { ok: false, reason: 'thinking_end_without_phase' }
      sawThinkingEnd = true
      continue
    }

    if (ev === 'final_delta') {
      if (!sawThinkingEnd) return { ok: false, reason: 'final_delta_before_thinking_end' }
      if (sawFinalEnd) return { ok: false, reason: 'final_delta_after_final_end' }
      if (typeof data?.text !== 'string') return { ok: false, reason: 'final_delta_text_invalid' }
      finalDeltaCount += 1
      finalTextLen += String(data.text || '').length
      continue
    }

    if (ev === 'serp_queries') {
      serpQueriesCount += 1
      if (serpQueriesCount > 1) return { ok: false, reason: 'serp_queries_multiple' }
      if (!finalDeltaCount) return { ok: false, reason: 'serp_queries_before_final_delta' }
      if (sawFinalEnd) return { ok: false, reason: 'serp_queries_after_final_end' }

      const queries = Array.isArray(data?.queries) ? data.queries : null
      if (!queries) return { ok: false, reason: 'serp_queries_invalid' }

      const normalized = queries.map((q) => String(q || '').trim()).filter((q) => q)
      if (!normalized.length) return { ok: false, reason: 'serp_queries_empty' }
      if (normalized.length > 5) return { ok: false, reason: 'serp_queries_too_many' }

      const seen = new Set()
      for (const q of normalized) {
        if (q.length > 80) return { ok: false, reason: 'serp_queries_too_long' }
        const key = q.toLowerCase()
        if (seen.has(key)) return { ok: false, reason: 'serp_queries_not_deduped' }
        if (hasSensitiveQueryToken(q)) return { ok: false, reason: 'serp_queries_sensitive' }
        seen.add(key)
      }
      continue
    }

    if (ev === 'final_end') {
      if (!finalDeltaCount) return { ok: false, reason: 'final_end_without_final_delta' }
      if (sawFinalEnd) return { ok: false, reason: 'final_end_multiple' }
      sawFinalEnd = true
      continue
    }
  }

  if (!sawThinkingStart) return { ok: false, reason: 'missing_thinking_start' }
  if (!sawThinkingEnd) return { ok: false, reason: 'missing_thinking_end' }
  if (!finalDeltaCount) return { ok: false, reason: 'missing_final_delta' }
  if (finalTextLen <= 0) return { ok: false, reason: 'final_delta_empty' }
  if (!sawFinalEnd) return { ok: false, reason: 'missing_final_end' }

  return { ok: true, reason: 'ok', stats: { phases: currentPhaseId, final_deltas: finalDeltaCount } }
}

function handleValidateJsonseq() {
  jsonseqValidation.value = validateJsonseqV1Events(sseEvents.value)
  if (jsonseqValidation.value.ok) message.success('JSONSeq v1 校验通过')
  else message.warning(`JSONSeq v1 校验失败：${jsonseqValidation.value.reason}`)
}

// ---------------- SSE Probe ----------------
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

async function handleRunSseProbe() {
  if (!jwtToken.value) {
    message.warning('请先获取 JWT Token')
    return
  }
  probeRunning.value = true
  probeEvents.value = []

  try {
    const baseURL = import.meta.env.VITE_BASE_API || '/api/v1'
    const normalizedBase = String(baseURL).replace(/\/+$/, '')
    const url = `${normalizedBase}/base/sse_probe`

    const requestId = genRequestId('web-probe')
    const response = await fetch(url, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${jwtToken.value}`,
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
      url,
      requestId,
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
</script>

<template>
  <NSpace vertical :size="16">
    <NCard title="JWT 测试（SSOT：仅使用映射后的 model key）" size="small">
      <NForm inline label-placement="left" label-width="auto">
        <NFormItem label="Mail API Key">
          <NInput
            v-model:value="mailApiKey"
            type="password"
            placeholder="用于生成测试用户（可选）"
            show-password-on="click"
            style="width: 320px"
          />
        </NFormItem>
        <NFormItem>
          <NButton secondary @click="handleSaveMailApiKey">保存</NButton>
        </NFormItem>
      </NForm>
      <NAlert type="info" :bordered="false" class="mt-2">
        此 Key 仅保存在浏览器 localStorage，用于「生成测试用户」。设置为
        <code>test-key-mock</code> 可开启 Mock 模式。
      </NAlert>

      <NSpace wrap>
        <NButton type="primary" :loading="creatingTestUser" @click="handleCreateTestUser(false)">
          一键获取测试用户（复用/refresh）
        </NButton>
        <NButton secondary :loading="creatingTestUserForce" @click="handleCreateTestUser(true)">
          强制新建测试用户
        </NButton>
        <NButton secondary :loading="gettingAnonToken" @click="handleGetAnonToken(false)">
          获取匿名 JWT（当日复用）
        </NButton>
        <NButton tertiary :loading="gettingAnonToken" @click="handleGetAnonToken(true)">
          重新生成匿名用户
        </NButton>
      </NSpace>

      <NSpace align="center" wrap class="mt-3">
        <NSelect
          v-model:value="selectedMailUserId"
          :options="mailUserSelectOptions"
          :loading="mailUsersLoading"
          filterable
          clearable
          placeholder="选择已保存测试用户"
          style="min-width: 320px"
        />
        <NButton
          secondary
          :disabled="!selectedMailUserId"
          :loading="refreshingMailUser"
          @click="handleUseSelectedMailUser"
        >
          刷新并使用
        </NButton>
        <NButton tertiary :loading="mailUsersLoading" @click="loadMailUsers">刷新列表</NButton>
        <NText v-if="mailUsers.length" depth="3">共 {{ mailUsers.length }} 个</NText>
      </NSpace>

      <NForm label-placement="left" label-width="100" class="mt-3">
        <NFormItem label="Token">
          <NInput v-model:value="jwtToken" type="textarea" placeholder="可手动粘贴 JWT" :rows="3" />
        </NFormItem>
      </NForm>

      <NAlert v-if="jwtToken" type="success" title="JWT Token" class="mt-2">
        <NSpace align="center" wrap>
          <NText depth="3">{{ tokenModeLabel }}</NText>
          <NText v-if="tokenMeta.email" depth="3">{{ tokenMeta.email }}</NText>
          <NButton secondary size="small" @click="handleCopyToken">复制</NButton>
        </NSpace>
      </NAlert>
    </NCard>

    <NCard title="发送消息 + SSE" size="small">
      <NSpace align="center" wrap>
        <NSelect
          v-model:value="selectedModel"
          :options="modelSelectOptions"
          :loading="modelsLoading"
          filterable
          placeholder="选择 model（即 App 发送的 model key）"
          style="min-width: 360px"
        />
        <NButton secondary :loading="modelsLoading" @click="loadAppModels">刷新模型</NButton>
      </NSpace>

      <NSpace align="center" wrap class="mt-3">
        <NSelect
          v-model:value="resultMode"
          :options="[
            { label: 'XML 纯文本（content_delta）', value: 'xml_plaintext' },
            { label: 'RAW 透明转发（upstream_raw）', value: 'raw_passthrough' },
            { label: 'AUTO（自动选择）', value: 'auto' },
          ]"
          style="min-width: 220px"
        />
        <NTag size="small" type="info">prompt_mode: {{ dashboardPromptMode }}</NTag>
        <NSelect
          v-model:value="dashboardAppOutputProtocol"
          :options="appOutputProtocolOptions"
          :disabled="appConfigLoading"
          style="min-width: 240px"
        />
        <NButton
          secondary
          size="small"
          :loading="appOutputProtocolSaving"
          :disabled="appConfigLoading"
          @click="handleSaveAppOutputProtocol"
          >保存协议</NButton
        >
        <NButton
          tertiary
          size="small"
          :loading="appOutputProtocolSaving"
          :disabled="appConfigLoading"
          @click="handleRestoreDefaultAppOutputProtocol"
          >恢复默认协议</NButton
        >
        <NCheckbox v-model:checked="autoValidateOnCompleted">
          completed 自动校验 {{ dashboardAppOutputProtocol === 'jsonseq_v1' ? 'JSONSeq v1' : 'ThinkingML' }}
        </NCheckbox>
        <NButton
          v-if="dashboardAppOutputProtocol === 'jsonseq_v1'"
          tertiary
          size="small"
          :disabled="!sseEvents.length"
          @click="handleValidateJsonseq"
          >立即校验</NButton
        >
        <NButton
          v-else
          tertiary
          size="small"
          :disabled="!aiResponseText"
          @click="handleValidateThinkingML"
          >立即校验</NButton
        >
        <NTag
          v-if="dashboardAppOutputProtocol === 'jsonseq_v1' && jsonseqValidation.reason !== 'empty_events'"
          :type="jsonseqValidation.ok ? 'success' : 'error'"
        >
          JSONSeq: {{ jsonseqValidation.reason }}
        </NTag>
        <NTag v-else-if="aiResponseText" :type="thinkingmlValidation.ok ? 'success' : 'error'">
          ThinkingML: {{ thinkingmlValidation.reason }}
        </NTag>
        <NText depth="3" v-if="resultModeEffective">effective: {{ resultModeEffective }}</NText>
        <NButton tertiary size="small" :loading="activePromptsLoading" @click="loadActivePrompts"
          >刷新 Prompts（SSOT）</NButton
        >
        <NButton tertiary size="small" :loading="appConfigLoading" @click="loadAppConfig">刷新 App Config</NButton>
        <NButton tertiary size="small" @click="handleResetPromptDefaults">恢复默认（SSOT）</NButton>
      </NSpace>

      <NAlert type="warning" :bordered="false" class="mt-2">
        注意：输出协议为全局 SSOT 配置，切换会影响 App/其它页面；测试后请恢复默认
        <code>thinkingml_v45</code>。
      </NAlert>

      <NAlert v-if="promptsErrorForPreview" type="error" class="mt-2">{{ promptsErrorForPreview }}</NAlert>
      <NCard
        size="small"
        class="mt-3"
        :title="activeChatTab === 'agent' ? 'Agent Prompt/Tools（SSOT 预览）' : 'Messages Prompt/Tools（SSOT 预览）'"
      >
        <NSpace align="center" wrap>
          <NText depth="3"
            >system: {{ promptsSnapshotForPreview?.system_prompt?.name || '--' }}#{{
              promptsSnapshotForPreview?.system_prompt?.id || '--'
            }}</NText
          >
          <NText depth="3"
            >tools: {{ promptsSnapshotForPreview?.tools_prompt?.name || '--' }}#{{
              promptsSnapshotForPreview?.tools_prompt?.id || '--'
            }}</NText
          >
          <NText depth="3">tools_schema: {{ promptsSnapshotForPreview?.tools_schema_count ?? 0 }}</NText>
        </NSpace>
        <NInput
          v-if="effectiveSystemMessageForPreview"
          :value="effectiveSystemMessageForPreview"
          type="textarea"
          :rows="6"
          readonly
        />
        <NText v-else depth="3" class="mt-2">未配置 active prompts（后端会回退到最小默认值）</NText>
      </NCard>

      <NTabs v-model:value="activeChatTab" type="line" animated class="mt-3">
        <NTabPane name="agent" tab="Agent（后端工具）" display-directive="show">
          <NSpace align="center" wrap>
            <NSelect
              v-model:value="agentPromptMode"
              :options="[
                { label: '后端组装 prompt（server）', value: 'server' },
                { label: '透传 prompt（passthrough）', value: 'passthrough' },
              ]"
              style="min-width: 240px"
            />
            <NButton tertiary size="small" @click="handleSwitchAgentToServerAndClearPrompt"
              >切回 server + 清空</NButton
            >
            <NButton tertiary size="small" @click="handleFillAgentExtraPromptFromDashboard"
              >填充 Dashboard agent system message</NButton
            >
            <NButton tertiary size="small" @click="handleFillAgentExtraPromptTemplate"
              >填充默认 Strict-XML 模板</NButton
            >
            <NText v-if="agentPromptMode === 'server'" depth="3">server 模式完全跟随后端 SSOT</NText>
          </NSpace>

          <NForm label-placement="left" label-width="100" class="mt-3">
            <NFormItem label="附加 Prompt">
              <NInput
                v-model:value="agentExtraSystemPrompt"
                type="textarea"
                :rows="4"
                :disabled="agentPromptMode === 'server'"
                placeholder="agent passthrough 模式下作为 system message 发送（建议点击“填充 Dashboard agent system message”）"
              />
            </NFormItem>
          </NForm>

          <NSpace align="center" wrap class="mt-3">
            <NCheckbox v-model:checked="agentEnableExerciseSearch">动作库检索</NCheckbox>
            <NInputNumber
              v-model:value="agentExerciseTopK"
              :min="1"
              :max="10"
              :step="1"
              size="small"
              style="width: 120px"
            />
            <NCheckbox v-model:checked="agentDisableWebSearch">请求级禁用 Web 搜索</NCheckbox>
            <NInputNumber
              v-model:value="agentWebSearchTopK"
              :min="1"
              :max="10"
              :step="1"
              size="small"
              :disabled="agentDisableWebSearch"
              style="width: 120px"
            />
            <NTag
              size="small"
              :type="agentWebSearchStatus.willRun ? (agentWebSearchStatus.hasKey ? 'success' : 'warning') : 'default'"
            >
              web_search: {{ agentWebSearchStatus.willRun ? 'will_run' : 'off' }}
            </NTag>
            <NText depth="3" v-if="agentWebSearchStatus.enabled">
              exa_key: {{ dashboardWebSearchExaApiKeyMasked || 'none' }} ({{ dashboardWebSearchExaApiKeySource }})
            </NText>
          </NSpace>

          <NAlert v-if="appConfigError" type="error" :bordered="false" class="mt-2">
            {{ appConfigError }}
          </NAlert>

          <NAlert type="info" :bordered="false" class="mt-2">
            Dashboard Web 搜索：{{ agentWebSearchStatus.enabled ? 'ON' : 'OFF' }} / provider={{
              agentWebSearchStatus.provider
            }}。开启/Key 请到「系统 → AI」配置；此页仅提供请求级关闭（控成本）。
          </NAlert>

          <NForm label-placement="left" label-width="100" class="mt-3">
            <NFormItem label="Message">
              <NInput v-model:value="chatText" type="textarea" :rows="3" placeholder="输入消息内容" />
            </NFormItem>
          </NForm>

          <NSpace align="center" wrap>
            <NButton type="primary" :loading="sending" @click="handleSendAgentRun">Agent Run 并拉流</NButton>
            <NText depth="3">create request_id: {{ lastCreateRequestId || '--' }}</NText>
            <NText depth="3">sse request_id: {{ lastSseRequestId || '--' }}</NText>
          </NSpace>
        </NTabPane>

        <NTabPane name="messages" tab="Messages（基线）" display-directive="show">
          <NSpace align="center" wrap>
            <NSelect
              v-model:value="promptMode"
              :options="[
                { label: '后端组装 prompt（server）', value: 'server' },
                { label: '透传 prompt（passthrough）', value: 'passthrough' },
              ]"
              style="min-width: 240px"
            />
            <NSelect
              v-model:value="toolChoice"
              :options="[
                { label: 'tool_choice: 默认（不传）', value: '' },
                { label: 'tool_choice: none', value: 'none' },
                { label: 'tool_choice: auto', value: 'auto' },
              ]"
              style="min-width: 220px"
            />
            <NButton tertiary size="small" @click="handleSwitchToServerAndClearPrompt"
              >切回 server + 清空</NButton
            >
            <NButton tertiary size="small" @click="handleFillExtraPromptFromDashboard"
              >填充 Dashboard system message</NButton
            >
            <NButton tertiary size="small" @click="handleFillExtraPromptTemplate"
              >填充默认 Strict-XML 模板</NButton
            >
            <NText v-if="promptMode === 'server'" depth="3">server 模式完全跟随后端 SSOT</NText>
          </NSpace>

          <NAlert v-if="toolChoiceRisk" type="warning" :bordered="false" class="mt-2">
            提示：当前后端不执行 tool_calls。若 tool_choice=auto 且 tools schema 下发，上游可能返回 tool_calls 导致 reply 不可用/ThinkingML 校验失败。
            建议用「Agent（后端工具）」来跑 Web 搜索链路。
          </NAlert>

          <NForm label-placement="left" label-width="100" class="mt-3">
            <NFormItem label="附加 Prompt">
              <NInput
                v-model:value="extraSystemPrompt"
                type="textarea"
                :rows="4"
                :disabled="promptMode === 'server'"
                placeholder="passthrough 模式下作为 system message 发送（建议点击“填充 Dashboard system message”）"
              />
            </NFormItem>
          </NForm>

          <NForm label-placement="left" label-width="100" class="mt-3">
            <NFormItem label="Message">
              <NInput v-model:value="chatText" type="textarea" :rows="3" placeholder="输入消息内容" />
            </NFormItem>
          </NForm>

          <NSpace align="center" wrap>
            <NButton type="primary" :loading="sending" @click="handleSend">发送并拉流</NButton>
            <NText depth="3">create request_id: {{ lastCreateRequestId || '--' }}</NText>
            <NText depth="3">sse request_id: {{ lastSseRequestId || '--' }}</NText>
          </NSpace>
        </NTabPane>
      </NTabs>

      <NAlert v-if="messageId" type="info" class="mt-3">
        <div v-if="activeStreamKind === 'agent_runs'">run_id: {{ messageId }}</div>
        <div v-else>message_id: {{ messageId }}</div>
        <div>conversation_id: {{ conversationId }}</div>
      </NAlert>

      <NDivider />

      <NCard v-if="sseEvents.length" size="small" class="mt-3" title="SSE 指标（接收侧）">
        <NSpace align="center" wrap>
          <NText depth="3">TTFT(ms): {{ sseStats.ttftMs }}</NText>
          <NText depth="3">delta_count: {{ sseStats.deltaCount }}</NText>
          <NText depth="3">avg_delta_len: {{ sseStats.avgDeltaLen }}</NText>
          <NText depth="3">max_gap_ms: {{ sseStats.maxGapMs }}</NText>
          <NText depth="3">duration_ms: {{ sseStats.durationMs }}</NText>
        </NSpace>
      </NCard>

      <NCard v-if="aiResponseText" size="small" class="mt-3" title="拼接 reply（content_delta / final_delta）">
        <NInput :value="aiResponseText" type="textarea" :rows="10" readonly />
      </NCard>
      <NCard v-if="aiResponseRaw" size="small" class="mt-3" title="RAW / 诊断（upstream_raw 或 completed）">
        <NInput :value="aiResponseRaw" type="textarea" :rows="10" readonly />
      </NCard>

      <NCard v-if="toolEventsText" size="small" class="mt-3" title="工具事件（tool_*）">
        <NInput :value="toolEventsText" type="textarea" :rows="8" readonly />
      </NCard>

      <NCard v-if="sseEvents.length" size="small" class="mt-3" title="SSE 事件（最近 600）">
        <NInput :value="sseEventsText" type="textarea" :rows="12" readonly />
      </NCard>
    </NCard>

    <NCard title="SSE 探针（判断是否被缓冲/压缩）" size="small">
      <NSpace align="center" wrap>
        <NButton secondary :loading="probeRunning" @click="handleRunSseProbe">运行探针</NButton>
        <NTag v-if="probeEvents.length" :type="probeSummary.ok ? 'success' : 'warning'">
          {{ probeSummary.ok ? 'PASS' : 'SUSPECT' }} ({{ probeSummary.note }})
        </NTag>
      </NSpace>
      <NText v-if="probeEvents.length" depth="3" class="mt-2">
        gaps(ms): {{ probeSummary.gaps.join(', ') }}
      </NText>
    </NCard>
  </NSpace>
</template>

<style scoped>
.mt-2 {
  margin-top: 8px;
}
.mt-3 {
  margin-top: 12px;
}
</style>
