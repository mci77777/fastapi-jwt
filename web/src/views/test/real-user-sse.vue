<template>
  <div class="real-user-container">
    <n-card title="真实用户 SSE 测试 - JWT 与 AI 对话">
      <n-space vertical :size="20">
        <!-- 步骤 1: 获取 JWT Token -->
        <n-card title="步骤 1: 获取真实 Supabase JWT" size="small">
          <n-space style="margin-bottom: 12px">
            <n-button type="primary" :loading="creatingTestUser" @click="handleCreateTestUser(false)">
              一键获取测试用户（复用/refresh）
            </n-button>
            <n-button secondary :loading="creatingTestUserForce" @click="handleCreateTestUser(true)">
              强制新建测试用户
            </n-button>
            <n-button secondary :loading="gettingAnonToken" @click="handleGetAnonToken(false)">
              获取匿名 JWT（当日复用）
            </n-button>
            <n-button tertiary :loading="gettingAnonToken" @click="handleGetAnonToken(true)">
              重新生成匿名用户
            </n-button>
          </n-space>

          <n-space align="center" wrap style="margin-bottom: 12px">
            <n-select
              v-model:value="selectedMailUserId"
              :options="mailUserSelectOptions"
              :loading="mailUsersLoading"
              filterable
              clearable
              placeholder="选择已保存测试用户（用于并发分配）"
              style="min-width: 320px"
              :disabled="creatingTestUser || creatingTestUserForce || gettingToken"
            />
            <n-button
              secondary
              :disabled="!selectedMailUserId"
              :loading="refreshingMailUser"
              @click="handleUseSelectedMailUser"
            >
              刷新并使用
            </n-button>
            <n-button tertiary :loading="mailUsersLoading" @click="loadMailUsers"> 刷新列表 </n-button>
            <n-text v-if="mailUsers.length" depth="3"> 共 {{ mailUsers.length }} 个 </n-text>
          </n-space>

          <n-form ref="loginFormRef" :model="loginForm" label-placement="left" label-width="100">
            <n-form-item label="Email" path="email">
              <n-input
                v-model:value="loginForm.email"
                placeholder="输入真实 Supabase 用户 email"
                @keyup.enter="handleGetToken"
              />
            </n-form-item>
            <n-form-item label="Password" path="password">
              <n-input
                v-model:value="loginForm.password"
                type="password"
                placeholder="输入真实密码"
                @keyup.enter="handleGetToken"
              />
            </n-form-item>
            <n-form-item>
              <n-space>
                <n-button type="primary" :loading="gettingToken" @click="handleGetToken">
                  获取 JWT Token
                </n-button>
                <n-button v-if="jwtToken" secondary @click="handleCopyToken"> 复制 Token </n-button>
              </n-space>
            </n-form-item>
          </n-form>

          <!-- Token 显示 -->
          <n-alert v-if="jwtToken" type="success" title="JWT Token 获取成功" closable>
            <div style="margin-bottom: 8px">
              <n-space>
                <n-tag size="small" :type="tokenMode === 'anonymous' ? 'warning' : 'info'">
                  {{ tokenModeLabel }}
                </n-tag>
                <n-text v-if="tokenMeta.email" depth="3"> {{ tokenMeta.email }} </n-text>
              </n-space>
            </div>
            <n-text code style="word-break: break-all; font-size: 12px">
              {{ jwtToken }}
            </n-text>
          </n-alert>
        </n-card>

        <!-- 步骤 2: AI 对话测试 -->
        <n-card title="步骤 2: AI 对话测试" size="small">
          <n-form ref="chatFormRef" :model="chatForm" label-placement="left" label-width="100">
            <n-form-item label="API（端点）" path="endpoint_id">
              <n-select
                v-model:value="chatForm.endpoint_id"
                :options="endpointSelectOptions"
                :loading="modelsLoading"
                filterable
                clearable
                placeholder="选择一个已配置的 AI 端点"
                :disabled="sendingMessage"
              />
            </n-form-item>
            <n-form-item label="模型" path="model">
              <n-select
                v-model:value="chatForm.model"
                :options="modelSelectOptions"
                :loading="modelsLoading"
                filterable
                clearable
                placeholder="选择模型（可选）"
                :disabled="sendingMessage"
              />
            </n-form-item>
            <n-form-item label="对话内容" path="message">
              <n-input
                v-model:value="chatForm.message"
                type="textarea"
                placeholder="输入对话内容"
                :rows="3"
                :disabled="!jwtToken"
              />
            </n-form-item>
            <n-form-item>
              <n-space>
                <n-button
                  type="primary"
                  :loading="sendingMessage"
                  :disabled="!jwtToken"
                  @click="handleSendMessage"
                >
                  发送消息
                </n-button>
                <n-button secondary :disabled="!lastRequestId" @click="exportTraceJSON">
                  导出 trace
                </n-button>
              </n-space>
            </n-form-item>
          </n-form>

          <!-- AI 响应显示 -->
          <n-alert v-if="aiResponse" type="info" title="AI 响应" closable>
            <n-text style="white-space: pre-wrap">{{ aiResponse }}</n-text>
          </n-alert>

          <!-- SSE 事件日志 -->
          <n-collapse v-if="sseEvents.length > 0" style="margin-top: 12px">
            <n-collapse-item title="SSE 事件日志" name="sse-events">
              <n-timeline>
                <n-timeline-item
                  v-for="(event, index) in sseEvents"
                  :key="index"
                  :type="event.type === 'error' ? 'error' : 'success'"
                  :title="event.event"
                  :time="event.time"
                >
                  <n-text code style="font-size: 12px">{{ event.data }}</n-text>
                </n-timeline-item>
              </n-timeline>
            </n-collapse-item>
          </n-collapse>
        </n-card>

        <!-- 步骤 3: 测试结果 -->
        <n-card title="步骤 3: 测试结果" size="small">
          <n-descriptions :column="2" bordered size="small">
            <n-descriptions-item label="JWT Token 状态">
              <n-tag :type="jwtToken ? 'success' : 'default'">
                {{ jwtToken ? '已获取' : '未获取' }}
              </n-tag>
            </n-descriptions-item>
            <n-descriptions-item label="Message ID">
              <n-text code>{{ messageId || '--' }}</n-text>
            </n-descriptions-item>
            <n-descriptions-item label="SSE 事件数">
              <n-text>{{ sseEvents.length }}</n-text>
            </n-descriptions-item>
            <n-descriptions-item label="AI 响应状态">
              <n-tag :type="aiResponse ? 'success' : 'default'">
                {{ aiResponse ? '已接收' : '未接收' }}
              </n-tag>
            </n-descriptions-item>
          </n-descriptions>
        </n-card>
      </n-space>
    </n-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import {
  createAnonToken,
  createMailUser,
  createMessage,
  listMailUsers,
  refreshMailUserToken,
} from '@/api/aiModelSuite'
import api from '@/api'
import { supabaseRefreshSession, supabaseSignInAnonymously } from '@/utils/supabase/auth'
import { useAiModelSuiteStore } from '@/store'

defineOptions({ name: 'RealUserSseTest' })

const message = useMessage()
const aiSuiteStore = useAiModelSuiteStore()
const { modelsLoading, models } = storeToRefs(aiSuiteStore)

// 登录表单
const loginFormRef = ref(null)
const loginForm = ref({
  email: '',
  password: '',
})

// JWT Token
const jwtToken = ref('')
const tokenMode = ref('')
const tokenMeta = ref({ email: '', username: '', user_id: '' })
const gettingToken = ref(false)
const creatingTestUser = ref(false)
const creatingTestUserForce = ref(false)
const gettingAnonToken = ref(false)

const ANON_CACHE_DAY_KEY = 'jwt_test_anon_day'
const ANON_CACHE_REFRESH_KEY = 'jwt_test_anon_refresh_token'
const MAIL_USER_SELECTED_ID_KEY = 'jwt_test_mail_user_id'

const mailUsersLoading = ref(false)
const refreshingMailUser = ref(false)
const mailUsers = ref([])
const selectedMailUserId = ref(null)

const mailUserSelectOptions = computed(() => {
  const items = Array.isArray(mailUsers.value) ? mailUsers.value : []
  return items.map((u) => {
    const id = u?.id
    const label = u?.label ? String(u.label) : 'mail-user'
    const email = u?.email ? String(u.email) : '--'
    const createdAt = u?.created_at ? String(u.created_at) : ''
    const hasRefresh = u?.has_refresh_token ? '✓' : '×'
    return {
      label: `${label} | ${email} | refresh:${hasRefresh}${createdAt ? ` | ${createdAt}` : ''}`,
      value: id,
    }
  })
})

function getLocalDateKey() {
  // 形如 2026-01-02（按本地时区）
  return new Date().toLocaleDateString('sv-SE')
}

function formatApiError(prefix, error) {
  const resp = error?.response
  const data = resp?.data
  const requestId = data?.request_id || data?.requestId
  const hint = data?.hint
  const msg = data?.msg || data?.message || data?.code
  const status = resp?.status || data?.status
  const parts = []
  parts.push(prefix)
  if (status) parts.push(`status=${status}`)
  if (msg) parts.push(String(msg))
  if (requestId) parts.push(`request_id=${requestId}`)
  if (hint) parts.push(String(hint))
  if (parts.length > 1) return parts.join(' | ')
  return `${prefix}：${error?.message || '未知错误'}`
}

function applyJwtSession({ access_token, mode, meta } = {}) {
  if (typeof access_token === 'string' && access_token) jwtToken.value = access_token
  if (typeof mode === 'string') tokenMode.value = mode
  tokenMeta.value = {
    email: meta?.email || '',
    username: meta?.username || '',
    user_id: meta?.user_id || '',
  }
}

const tokenModeLabel = computed(() => {
  if (tokenMode.value === 'anonymous') return '匿名（当日复用）'
  if (tokenMode.value === 'permanent') return '测试用户（永久）'
  if (tokenMode.value === 'mock') return 'Mock（非真实JWT）'
  if (tokenMode.value === 'manual') return '手动登录'
  return '未知'
})

async function tryResumeAnonToken() {
  const today = getLocalDateKey()
  const cachedDay = localStorage.getItem(ANON_CACHE_DAY_KEY)
  const cachedRefresh = localStorage.getItem(ANON_CACHE_REFRESH_KEY)
  if (cachedDay !== today || !cachedRefresh) return
  try {
    const refreshed = await supabaseRefreshSession(cachedRefresh)
    applyJwtSession({
      access_token: refreshed.access_token,
      mode: 'anonymous',
      meta: { username: 'anon', email: '' },
    })
  } catch {
    // 静默失败：仅在用户点击按钮时才重新生成
  }
}

async function loadMailUsers() {
  mailUsersLoading.value = true
  try {
    const res = await listMailUsers({ limit: 100 })
    const items = res?.data?.items
    mailUsers.value = Array.isArray(items) ? items : []

    const cachedIdRaw = localStorage.getItem(MAIL_USER_SELECTED_ID_KEY)
    const cachedId = cachedIdRaw ? Number(cachedIdRaw) : null
    if (cachedId && mailUsers.value.some((u) => Number(u?.id) === cachedId)) {
      selectedMailUserId.value = cachedId
    } else if (!selectedMailUserId.value && mailUsers.value.length) {
      selectedMailUserId.value = mailUsers.value[0].id
    }
  } catch (error) {
    message.error(formatApiError('加载测试用户列表失败', error))
  } finally {
    mailUsersLoading.value = false
  }
}

watch(
  () => selectedMailUserId.value,
  (val) => {
    if (val === null || val === undefined || val === '') {
      localStorage.removeItem(MAIL_USER_SELECTED_ID_KEY)
      return
    }
    localStorage.setItem(MAIL_USER_SELECTED_ID_KEY, String(val))
  }
)

// 对话表单
const chatFormRef = ref(null)
const chatForm = ref({
  endpoint_id: null,
  model: '',
  message: 'Hello, this is a test message from Real User SSE UI.',
})

const endpointSelectOptions = computed(() => aiSuiteStore.endpointOptions || [])

function buildModelCandidatesForEndpoint(endpointId) {
  if (!endpointId) return aiSuiteStore.modelCandidates || []
  const endpoint = (models.value || []).find((item) => item && item.id === endpointId)
  if (!endpoint) return aiSuiteStore.modelCandidates || []
  const candidateSet = new Set()
  if (Array.isArray(endpoint.model_list)) {
    endpoint.model_list.forEach((m) => {
      if (m) candidateSet.add(String(m))
    })
  }
  if (endpoint.model) candidateSet.add(String(endpoint.model))
  return Array.from(candidateSet).filter(Boolean).sort()
}

const modelSelectOptions = computed(() => {
  const candidates = buildModelCandidatesForEndpoint(chatForm.value.endpoint_id)
  return candidates.map((m) => ({ label: m, value: m }))
})

function ensureChatFormModelValid(endpointId) {
  const candidates = buildModelCandidatesForEndpoint(endpointId)
  if (!candidates.length) return
  const current = String(chatForm.value.model || '').trim()
  if (!current || !candidates.includes(current)) {
    chatForm.value.model = candidates[0]
  }
}

// AI 响应
const messageId = ref('')
const aiResponse = ref('')
const sendingMessage = ref(false)
const sseEvents = ref([])
const conversationId = ref('')
const lastRequestId = ref('')

function exportTraceJSON() {
  if (!lastRequestId.value) {
    message.warning('暂无可导出的 request_id')
    return
  }
  const trace = {
    request_id: lastRequestId.value,
    message_id: messageId.value,
    conversation_id: conversationId.value,
    endpoint_id: chatForm.value.endpoint_id,
    model: chatForm.value.model,
    created_at: new Date().toISOString(),
    ai_response: aiResponse.value,
    sse_events: sseEvents.value,
  }
  const blob = new Blob([JSON.stringify(trace, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `web_real_user_sse_trace_${lastRequestId.value}.json`
  a.click()
  URL.revokeObjectURL(url)
  message.success('已导出 trace')
}

/**
 * 获取 JWT Token
 */
async function handleGetToken() {
  if (!loginForm.value.email || !loginForm.value.password) {
    message.warning('请输入 Email 和 Password')
    return
  }

  gettingToken.value = true
  try {
    const res = await api.login({
      email: loginForm.value.email,
      password: loginForm.value.password,
    })

    if (res?.data?.access_token) {
      applyJwtSession({
        access_token: res.data.access_token,
        refresh_token: res.data.refresh_token || null,
        mode: 'manual',
        meta: { email: loginForm.value.email, username: loginForm.value.email.split('@')[0] },
      })
      message.success('JWT Token 获取成功')
    } else {
      message.error('JWT Token 获取失败：响应格式错误')
    }
  } catch (error) {
    message.error(formatApiError('JWT Token 获取失败', error))
  } finally {
    gettingToken.value = false
  }
}

/**
 * 复制 Token
 */
function handleCopyToken() {
  navigator.clipboard.writeText(jwtToken.value)
  message.success('Token 已复制到剪贴板')
}

async function handleCreateTestUser(forceNew) {
  if (forceNew) creatingTestUserForce.value = true
  else creatingTestUser.value = true
  try {
    const res = await createMailUser({
      username_prefix: 'gymbro-test-01',
      force_new: !!forceNew,
    })
    const data = res?.data
    if (!data?.access_token) {
      message.error('生成失败：响应缺少 access_token')
      return
    }

    // 仅用于展示（不污染全局登录态）：把生成的邮箱/密码回填到表单，方便复制或重登
    if (data.email) loginForm.value.email = String(data.email)
    if (data.password) loginForm.value.password = String(data.password)

    applyJwtSession({
      access_token: String(data.access_token),
      refresh_token: data.refresh_token || null,
      mode: String(data.mode || 'permanent'),
      meta: { email: data.email, username: data.username, user_id: data.user_id },
    })

    if (data.test_user_id) {
      selectedMailUserId.value = Number(data.test_user_id)
      localStorage.setItem(MAIL_USER_SELECTED_ID_KEY, String(data.test_user_id))
    }
    loadMailUsers()
    message.success('测试用户已生成并获取 JWT')
  } catch (error) {
    message.error(formatApiError('生成测试用户失败', error))
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

    if (data.email) loginForm.value.email = String(data.email)
    if (data.password) loginForm.value.password = String(data.password)

    applyJwtSession({
      access_token: String(data.access_token),
      refresh_token: data.refresh_token || null,
      mode: String(data.mode || 'permanent'),
      meta: { email: data.email, username: data.username, user_id: data.user_id },
    })

    loadMailUsers()
    message.success('已刷新并切换到所选测试用户')
  } catch (error) {
    message.error(formatApiError('刷新测试用户 token 失败', error))
  } finally {
    refreshingMailUser.value = false
  }
}

async function handleGetAnonToken(forceNew) {
  gettingAnonToken.value = true
  try {
    const today = getLocalDateKey()
    const cachedDay = localStorage.getItem(ANON_CACHE_DAY_KEY)
    const cachedRefresh = localStorage.getItem(ANON_CACHE_REFRESH_KEY)

    // 1) 优先走后端（线上不依赖 VITE_SUPABASE_* 配置；需要后端 SUPABASE_ANON_KEY）
    try {
      const res = await createAnonToken({
        refresh_token: !forceNew && cachedDay === today ? cachedRefresh || null : null,
        force_new: !!forceNew,
      })
      const data = res?.data
      if (data?.access_token) {
        localStorage.setItem(ANON_CACHE_DAY_KEY, today)
        if (data.refresh_token) localStorage.setItem(ANON_CACHE_REFRESH_KEY, String(data.refresh_token))
        applyJwtSession({
          access_token: String(data.access_token),
          mode: 'anonymous',
          meta: { username: 'anon', email: '' },
        })
        message.success(forceNew ? '已重新生成匿名用户' : '匿名 JWT 获取成功')
        return
      }
    } catch {
      // 回退到前端直连 Supabase（本地开发可用）
    }

    // 2) 前端直连 Supabase（需要 VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY）
    if (!forceNew && cachedDay === today && cachedRefresh) {
      try {
        const refreshed = await supabaseRefreshSession(cachedRefresh)
        localStorage.setItem(ANON_CACHE_DAY_KEY, today)
        if (refreshed.refresh_token) localStorage.setItem(ANON_CACHE_REFRESH_KEY, refreshed.refresh_token)
        applyJwtSession({
          access_token: refreshed.access_token,
          mode: 'anonymous',
          meta: { username: 'anon', email: '' },
        })
        message.success('已复用当日匿名用户（refresh）')
        return
      } catch {
        // refresh 失败则回退重新生成
      }
    }

    const session = await supabaseSignInAnonymously()
    localStorage.setItem(ANON_CACHE_DAY_KEY, today)
    if (session.refresh_token) localStorage.setItem(ANON_CACHE_REFRESH_KEY, session.refresh_token)
    applyJwtSession({
      access_token: session.access_token,
      mode: 'anonymous',
      meta: { username: 'anon', email: '' },
    })
    message.success(forceNew ? '已重新生成匿名用户' : '匿名 JWT 获取成功')
  } catch (error) {
    message.error(formatApiError('匿名 JWT 获取失败', error))
  } finally {
    gettingAnonToken.value = false
  }
}

onMounted(() => {
  tryResumeAnonToken()
  loadMailUsers()
  aiSuiteStore.loadModels().then(() => {
    if (!chatForm.value.endpoint_id && endpointSelectOptions.value.length) {
      chatForm.value.endpoint_id = endpointSelectOptions.value[0].value
    }
    ensureChatFormModelValid(chatForm.value.endpoint_id)
  })
})

watch(
  () => chatForm.value.endpoint_id,
  (endpointId) => {
    ensureChatFormModelValid(endpointId)
  }
)

/**
 * 发送消息并接收 SSE 响应
 */
async function handleSendMessage() {
  if (!chatForm.value.message.trim()) {
    message.warning('请输入对话内容')
    return
  }

  sendingMessage.value = true
  aiResponse.value = ''
  sseEvents.value = []

  try {
    const requestId =
      globalThis.crypto?.randomUUID?.() || `web-${Date.now()}-${Math.random().toString(16).slice(2)}`
    lastRequestId.value = requestId
    console.log(`request_id=${requestId} action=create_message`)

    // 步骤 1: 创建消息
    const createResponse = await createMessage({
      text: chatForm.value.message,
      conversationId: conversationId.value || null,
      metadata: {
        scenario: 'real_user_sse_ui',
        test_type: 'manual',
        endpoint_id: chatForm.value.endpoint_id || null,
        requested_model: chatForm.value.model || null,
      },
      requestId,
      promptMode: 'server',
      openai: {
        model: chatForm.value.model || undefined,
      },
      accessToken: jwtToken.value,
    })

    messageId.value = createResponse.message_id
    conversationId.value = createResponse.conversation_id
    message.success(`消息创建成功，ID: ${messageId.value}`)
    console.log(`request_id=${requestId} message_id=${messageId.value} conversation_id=${conversationId.value}`)

    // 步骤 2: 建立 SSE 连接
    await streamSSEEvents(messageId.value, conversationId.value, requestId)
  } catch (error) {
    message.error('发送消息失败：' + (error.message || '未知错误'))
  } finally {
    sendingMessage.value = false
  }
}

/**
 * 流式接收 SSE 事件
 */
async function streamSSEEvents(msgId, convId, requestId) {
  console.log(`request_id=${requestId} action=stream_sse_start msg_id=${msgId}`)
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
  if (!reader) {
    throw new Error('SSE 响应不支持流式读取')
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = 'message'
  let dataLines = []

  const flushEvent = () => {
    if (!dataLines.length) return
    const rawData = dataLines.join('\n')
    dataLines = []

    let parsed = null
    try {
      parsed = JSON.parse(rawData)
    } catch {
      parsed = rawData
    }

    const eventType = currentEvent || 'message'
    sseEvents.value.push({
      event: eventType,
      data: typeof parsed === 'string' ? parsed : JSON.stringify(parsed, null, 2),
      time: new Date().toLocaleTimeString(),
      type: eventType === 'error' ? 'error' : eventType === 'completed' ? 'success' : 'info',
    })

    if (eventType === 'content_delta' && parsed && typeof parsed === 'object' && parsed.delta) {
      aiResponse.value += String(parsed.delta)
    } else if (eventType === 'completed' && parsed && typeof parsed === 'object' && parsed.reply) {
      aiResponse.value = String(parsed.reply)
    } else if (eventType === 'error') {
      const errMsg = parsed && typeof parsed === 'object' ? parsed.error : rawData
      message.error(`SSE 错误：${errMsg || '未知错误'}`)
      console.log(`request_id=${requestId} action=stream_sse_end reason=error`)
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    while (true) {
      const idx = buffer.indexOf('\n')
      if (idx < 0) break

      let line = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 1)
      if (line.endsWith('\r')) line = line.slice(0, -1)
      line = line.trimEnd()

      if (!line) {
        flushEvent()
        if (currentEvent === 'completed' || currentEvent === 'error') {
          console.log(`request_id=${requestId} action=stream_sse_end reason=${currentEvent}`)
          return
        }
        currentEvent = 'message'
        continue
      }

      if (line.startsWith('event:')) {
        currentEvent = line.slice('event:'.length).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice('data:'.length).trim())
      }
    }
  }

  // 处理尾部残留
  flushEvent()
  console.log(`request_id=${requestId} action=stream_sse_end reason=eof`)
}
</script>

<style scoped>
.real-user-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.n-card {
  margin-bottom: 16px;
}
</style>
