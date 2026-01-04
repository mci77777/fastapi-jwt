<script setup>
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import {
  NAlert,
  NButton,
  NCard,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
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
    label: `${u.email || u.username || `user-${u.id}`}${u.has_refresh_token ? '' : '（no refresh_token）'}`,
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
const aiResponse = ref('')
const lastCreateRequestId = ref('')
const lastSseRequestId = ref('')

function genRequestId(prefix) {
  const rid = globalThis.crypto?.randomUUID?.() || `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
  return String(rid)
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
  aiResponse.value = ''
  messageId.value = ''

  try {
    const createRequestId = genRequestId('web-create')
    lastCreateRequestId.value = createRequestId

    const created = await createMessage({
      text: chatText.value.trim(),
      conversationId: conversationId.value || null,
      metadata: {
        scenario: 'ai_jwt_ssot_sse',
        model: selectedModel.value,
      },
      requestId: createRequestId,
      promptMode: 'server',
      openai: { model: selectedModel.value },
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

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    while (true) {
      const idx = buffer.indexOf('\n')
      if (idx === -1) break
      const line = buffer.slice(0, idx).replace(/\r$/, '')
      buffer = buffer.slice(idx + 1)

      if (!line) {
        const ev = flushEvent()
        if (ev) {
          if (ev.event === 'content_delta' && ev.data?.delta) {
            aiResponse.value += String(ev.data.delta)
          }
          if (ev.event === 'completed') return
          if (ev.event === 'error') {
            const msg = typeof ev.data === 'string' ? ev.data : JSON.stringify(ev.data)
            throw new Error(msg || 'SSE error')
          }
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

onMounted(() => {
  loadMailUsers()
  loadAppModels()
})
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
        此 Key 仅保存在浏览器 localStorage，用于「生成测试用户」。设置为 <code>test-key-mock</code> 可开启 Mock 模式。
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
        <NButton secondary :disabled="!selectedMailUserId" :loading="refreshingMailUser" @click="handleUseSelectedMailUser">
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

      <NCard v-if="aiResponse" size="small" class="mt-3" title="AI Response">
        <NInput :value="aiResponse" type="textarea" :rows="6" readonly />
      </NCard>
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
