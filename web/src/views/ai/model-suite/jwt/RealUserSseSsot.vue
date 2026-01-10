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
  NSelect,
  NSpace,
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
  createMessage,
} from '@/api/aiModelSuite'
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
const jwtToken = ref('')
const tokenMode = ref('') // anonymous | permanent | manual
const tokenMeta = ref({ email: '', username: '' })

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
  jwtToken.value = String(access_token || '')
  tokenMode.value = String(mode || '')
  tokenMeta.value = {
    email: meta?.email ? String(meta.email) : '',
    username: meta?.username ? String(meta.username) : '',
  }
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
const aiResponseText = ref('')
const aiResponseRaw = ref('')
const resultModeEffective = ref('')
const lastCreateRequestId = ref('')
const lastSseRequestId = ref('')

// prompt / result mode
const promptMode = ref('passthrough') // server | passthrough
const DEFAULT_EXTRA_SYSTEM_PROMPT =
  '请严格按原样输出带尖括号标签的 ThinkingML：<thinking>...</thinking> 紧接 <final>...</final>。不要转义尖括号，不要额外解释协议。'
const extraSystemPrompt = ref(DEFAULT_EXTRA_SYSTEM_PROMPT)
const resultMode = ref('xml_plaintext') // xml_plaintext | raw_passthrough | auto
const toolChoice = ref('none') // '' | none | auto（OpenAI tool_choice）
const autoValidateOnCompleted = ref(true)
const thinkingmlValidation = ref({ ok: false, reason: 'empty_reply' })

const sseEvents = ref([])
const streamStartedAtMs = ref(0)
const firstDeltaAtMs = ref(0)
const lastDeltaAtMs = ref(0)

function pushSseEvent(ev, receivedAtMs) {
  const entry = {
    ts_ms: receivedAtMs,
    event: String(ev?.event || 'message'),
    data: ev?.data ?? null,
  }
  sseEvents.value.push(entry)
  if (sseEvents.value.length > 200) sseEvents.value.splice(0, sseEvents.value.length - 200)
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

function handleResetPromptDefaults() {
  promptMode.value = 'passthrough'
  extraSystemPrompt.value = DEFAULT_EXTRA_SYSTEM_PROMPT
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
  aiResponseText.value = ''
  aiResponseRaw.value = ''
  messageId.value = ''
  resultModeEffective.value = ''
  sseEvents.value = []
  streamStartedAtMs.value = 0
  firstDeltaAtMs.value = 0
  lastDeltaAtMs.value = 0
  thinkingmlValidation.value = { ok: false, reason: 'empty_reply' }

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
    await streamSse(messageId.value, conversationId.value, sseRequestId)
  } catch (error) {
    message.error(error?.message || '发送失败')
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

async function streamSse(msgId, convId, requestId) {
  const baseURL = import.meta.env.VITE_BASE_API || '/api/v1'
  const normalizedBase = String(baseURL).replace(/\/+$/, '')
  const url = convId
    ? `${normalizedBase}/messages/${msgId}/events?conversation_id=${encodeURIComponent(convId)}`
    : `${normalizedBase}/messages/${msgId}/events`

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
        const shouldValidate = autoValidateOnCompleted.value && effective !== 'raw_passthrough'
        if (shouldValidate) thinkingmlValidation.value = validateThinkingMLV45(aiResponseText.value)
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
})

const sseStats = computed(() => {
  const events = Array.isArray(sseEvents.value) ? sseEvents.value : []
  const deltas = events
    .filter((e) => e?.event === 'content_delta' && e?.data && typeof e.data.delta === 'string')
    .map((e) => ({ ts_ms: Number(e.ts_ms || 0), len: String(e.data.delta || '').length }))

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
      } else if (ev === 'upstream_raw') {
        const raw = typeof data?.raw === 'string' ? data.raw : typeof data === 'string' ? data : ''
        brief = `seq=${data?.seq ?? '--'} len=${raw.length} "${raw.slice(0, 80).replace(/\n/g, '\\n')}"`
      } else if (ev === 'status') {
        brief = `status=${data?.status ?? '--'} effective=${data?.result_mode_effective ?? '--'}`
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

function handleValidateThinkingML() {
  thinkingmlValidation.value = validateThinkingMLV45(aiResponseText.value)
  if (thinkingmlValidation.value.ok) message.success('ThinkingML 校验通过')
  else message.warning(`ThinkingML 校验失败：${thinkingmlValidation.value.reason}`)
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
          v-model:value="promptMode"
          :options="[
            { label: '透传 prompt（passthrough）', value: 'passthrough' },
            { label: '后端组装 prompt（server）', value: 'server' },
          ]"
          style="min-width: 240px"
        />
        <NSelect
          v-model:value="resultMode"
          :options="[
            { label: 'XML 纯文本（content_delta）', value: 'xml_plaintext' },
            { label: 'RAW 透明转发（upstream_raw）', value: 'raw_passthrough' },
            { label: 'AUTO（自动选择）', value: 'auto' },
          ]"
          style="min-width: 220px"
        />
        <NSelect
          v-model:value="toolChoice"
          :options="[
            { label: 'tool_choice: 默认（不传）', value: '' },
            { label: 'tool_choice: none（禁用 tools）', value: 'none' },
            { label: 'tool_choice: auto', value: 'auto' },
          ]"
          style="min-width: 240px"
        />
        <NButton tertiary size="small" @click="handleSwitchToServerAndClearPrompt"
          >切回 server + 清空</NButton
        >
        <NButton tertiary size="small" @click="handleResetPromptDefaults">恢复默认</NButton>
        <NText v-if="promptMode === 'server'" depth="3"
          >server 模式不会注入“附加 prompt”（由后端 SSOT 决定）</NText
        >
      </NSpace>

      <NSpace align="center" wrap class="mt-2">
        <NCheckbox v-model:checked="autoValidateOnCompleted">completed 自动校验 ThinkingML</NCheckbox>
        <NButton tertiary size="small" :disabled="!aiResponseText" @click="handleValidateThinkingML"
          >立即校验</NButton
        >
        <NTag v-if="aiResponseText" :type="thinkingmlValidation.ok ? 'success' : 'error'">
          ThinkingML: {{ thinkingmlValidation.reason }}
        </NTag>
        <NText depth="3" v-if="resultModeEffective">effective: {{ resultModeEffective }}</NText>
      </NSpace>

      <NForm label-placement="left" label-width="100" class="mt-3">
        <NFormItem label="附加 Prompt">
          <NInput
            v-model:value="extraSystemPrompt"
            type="textarea"
            :rows="3"
            :disabled="promptMode === 'server'"
            placeholder="passthrough 模式下作为 system message 发送（可包含 <...> 标签要求）"
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

      <NAlert v-if="messageId" type="info" class="mt-3">
        <div>message_id: {{ messageId }}</div>
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

      <NCard v-if="aiResponseText" size="small" class="mt-3" title="拼接 reply（content_delta）">
        <NInput :value="aiResponseText" type="textarea" :rows="10" readonly />
      </NCard>
      <NCard v-if="aiResponseRaw" size="small" class="mt-3" title="RAW / 诊断（upstream_raw 或 completed）">
        <NInput :value="aiResponseRaw" type="textarea" :rows="10" readonly />
      </NCard>

      <NCard v-if="sseEvents.length" size="small" class="mt-3" title="SSE 事件（最近 200）">
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
