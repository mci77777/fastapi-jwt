<template>
  <!-- WebSocket 客户端组件 - 无 UI，仅提供连接管理 -->
  <div style="display: none;"></div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'

defineOptions({ name: 'WebSocketClient' })

const props = defineProps({
  url: {
    type: String,
    required: true
  },
  token: {
    type: String,
    required: true
  },
  autoReconnect: {
    type: Boolean,
    default: true
  },
  maxReconnectAttempts: {
    type: Number,
    default: 3
  },
  reconnectDelay: {
    type: Number,
    default: 2000
  }
})

const emit = defineEmits(['message', 'connected', 'disconnected', 'error'])

// 响应式状态
const status = ref('disconnected') // 'connected' | 'disconnected' | 'connecting' | 'error'
const isConnected = ref(false)
const reconnectAttempts = ref(0)

// WebSocket 实例
let ws = null
let reconnectTimer = null

/**
 * 创建 WebSocket 连接
 */
function connect() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
    return
  }

  status.value = 'connecting'
  // props.url 已经包含了 token，不需要再次添加
  const wsUrl = props.url

  try {
    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      status.value = 'connected'
      isConnected.value = true
      reconnectAttempts.value = 0
      emit('connected')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        emit('message', data)
      } catch (error) {
        console.error('WebSocket message parse error:', error)
        emit('error', error)
      }
    }

    ws.onerror = (error) => {
      status.value = 'error'
      isConnected.value = false
      emit('error', error)
    }

    ws.onclose = () => {
      status.value = 'disconnected'
      isConnected.value = false
      emit('disconnected')

      // 自动重连逻辑
      if (props.autoReconnect && reconnectAttempts.value < props.maxReconnectAttempts) {
        reconnectAttempts.value++
        const delay = props.reconnectDelay * reconnectAttempts.value
        reconnectTimer = setTimeout(() => {
          connect()
        }, delay)
      }
    }
  } catch (error) {
    status.value = 'error'
    isConnected.value = false
    emit('error', error)
  }
}

/**
 * 手动重连
 */
function reconnect() {
  reconnectAttempts.value = 0
  connect()
}

/**
 * 断开连接
 */
function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }

  if (ws) {
    ws.close()
    ws = null
  }

  status.value = 'disconnected'
  isConnected.value = false
}

// 监听 URL 或 token 变化，重新连接
watch([() => props.url, () => props.token], () => {
  disconnect()
  connect()
})

// 生命周期钩子
onMounted(() => {
  connect()
})

onBeforeUnmount(() => {
  disconnect()
})

// 暴露方法给父组件
defineExpose({
  connect,
  disconnect,
  reconnect,
  status,
  isConnected
})
</script>

