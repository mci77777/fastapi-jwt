<template>
  <div class="mock-user-container">
    <n-card title="Mock 用户测试 - JWT 与 AI 对话">
      <n-space vertical :size="20">
        <!-- 步骤 1: 获取 JWT Token -->
        <n-card title="步骤 1: 获取 JWT Token" size="small">
          <n-form ref="loginFormRef" :model="loginForm" label-placement="left" label-width="100">
            <n-form-item label="Email" path="email">
              <n-input
                v-model:value="loginForm.email"
                placeholder="输入真实 email 地址"
                @keyup.enter="handleGetToken"
              />
            </n-form-item>
            <n-form-item label="Password" path="password">
              <n-input
                v-model:value="loginForm.password"
                type="password"
                placeholder="输入密码"
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
            <n-text code style="word-break: break-all; font-size: 12px">
              {{ jwtToken }}
            </n-text>
          </n-alert>
        </n-card>

        <!-- 步骤 2: AI 对话测试 -->
        <n-card title="步骤 2: AI 对话测试" size="small">
          <n-form ref="chatFormRef" :model="chatForm" label-placement="left" label-width="100">
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
              <n-button
                type="primary"
                :loading="sendingMessage"
                :disabled="!jwtToken"
                @click="handleSendMessage"
              >
                发送消息
              </n-button>
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
import { ref } from 'vue'
import { useMessage } from 'naive-ui'
import { request } from '@/utils'
import { createMessage } from '@/api/aiModelSuite'

defineOptions({ name: 'MockUserTest' })

const message = useMessage()

// 登录表单
const loginFormRef = ref(null)
const loginForm = ref({
  email: '',
  password: '',
})

// JWT Token
const jwtToken = ref('')
const gettingToken = ref(false)

// 对话表单
const chatFormRef = ref(null)
const chatForm = ref({
  message: 'Hello, this is a test message from Mock User UI.',
})

// AI 响应
const messageId = ref('')
const aiResponse = ref('')
const sendingMessage = ref(false)
const sseEvents = ref([])
const conversationId = ref('')

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
    // 调用后端登录接口
    const response = await request.post(
      '/base/access_token',
      {
        username: loginForm.value.email,
        password: loginForm.value.password,
      },
      { noNeedToken: true }
    )

    if (response.data && response.data.access_token) {
      jwtToken.value = response.data.access_token
      message.success('JWT Token 获取成功')
    } else {
      message.error('JWT Token 获取失败：响应格式错误')
    }
  } catch (error) {
    message.error('JWT Token 获取失败：' + (error.message || '未知错误'))
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

    // 步骤 1: 创建消息
    const createResponse = await createMessage({
      text: chatForm.value.message,
      conversationId: conversationId.value || null,
      metadata: {
        source: 'mock_user_ui',
        test_type: 'manual',
      },
      requestId,
      promptMode: 'server',
    })

    messageId.value = createResponse.message_id
    conversationId.value = createResponse.conversation_id
    message.success(`消息创建成功，ID: ${messageId.value}`)

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
}
</script>

<style scoped>
.mock-user-container {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.n-card {
  margin-bottom: 16px;
}
</style>
