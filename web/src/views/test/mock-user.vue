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
    // 步骤 1: 创建消息
    const createResponse = await request.post(
      '/messages',
      {
        text: chatForm.value.message,
        conversation_id: null,
        metadata: {
          source: 'mock_user_ui',
          test_type: 'manual',
        },
      },
      {
        headers: {
          Authorization: `Bearer ${jwtToken.value}`,
        },
      }
    )

    messageId.value = createResponse.message_id
    message.success(`消息创建成功，ID: ${messageId.value}`)

    // 步骤 2: 建立 SSE 连接
    await streamSSEEvents(messageId.value)
  } catch (error) {
    message.error('发送消息失败：' + (error.message || '未知错误'))
  } finally {
    sendingMessage.value = false
  }
}

/**
 * 流式接收 SSE 事件
 */
async function streamSSEEvents(msgId) {
  const baseURL = import.meta.env.VITE_BASE_API || '/api/v1'
  const url = `${baseURL}/messages/${msgId}/events`

  const eventSource = new EventSource(url, {
    headers: {
      Authorization: `Bearer ${jwtToken.value}`,
    },
  })

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data)
    sseEvents.value.push({
      event: event.type || 'message',
      data: JSON.stringify(data, null, 2),
      time: new Date().toLocaleTimeString(),
      type: 'info',
    })

    // 提取 AI 响应内容
    if (data.event === 'chunk' && data.data && data.data.content) {
      aiResponse.value += data.data.content
    }
  }

  eventSource.addEventListener('done', (event) => {
    sseEvents.value.push({
      event: 'done',
      data: event.data,
      time: new Date().toLocaleTimeString(),
      type: 'success',
    })
    eventSource.close()
    message.success('SSE 流式接收完成')
  })

  eventSource.addEventListener('error', (event) => {
    sseEvents.value.push({
      event: 'error',
      data: JSON.stringify(event, null, 2),
      time: new Date().toLocaleTimeString(),
      type: 'error',
    })
    eventSource.close()
    message.error('SSE 连接错误')
  })

  eventSource.onerror = (error) => {
    console.error('SSE Error:', error)
    eventSource.close()
  }
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
