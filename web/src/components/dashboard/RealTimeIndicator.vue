<template>
  <div class="real-time-indicator">
    <NTag :type="tagType" :bordered="false" size="small">
      <template #icon>
        <span class="status-dot" :class="statusClass"></span>
      </template>
      {{ statusText }}
    </NTag>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { NTag } from 'naive-ui'

defineOptions({ name: 'RealTimeIndicator' })

const props = defineProps({
  status: {
    type: String,
    default: 'disconnected',
    validator: (value) => ['connected', 'disconnected', 'connecting', 'error', 'polling'].includes(value)
  }
})

// 状态文本映射
const statusText = computed(() => {
  const textMap = {
    connected: 'WebSocket 已连接',
    disconnected: 'WebSocket 已断开',
    connecting: '正在连接...',
    error: '连接错误',
    polling: '轮询模式'
  }
  return textMap[props.status] || '未知状态'
})

// Tag 类型映射
const tagType = computed(() => {
  const typeMap = {
    connected: 'success',
    disconnected: 'default',
    connecting: 'info',
    error: 'error',
    polling: 'warning'
  }
  return typeMap[props.status] || 'default'
})

// 状态点样式类
const statusClass = computed(() => {
  return `status-${props.status}`
})
</script>

<style scoped>
.real-time-indicator {
  display: inline-flex;
  align-items: center;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
}

.status-connected {
  background-color: #18a058;
  animation: pulse 2s infinite;
}

.status-disconnected {
  background-color: #d0d0d0;
}

.status-connecting {
  background-color: #2080f0;
  animation: blink 1s infinite;
}

.status-error {
  background-color: #d03050;
}

.status-polling {
  background-color: #f0a020;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

@keyframes blink {
  0%, 50%, 100% {
    opacity: 1;
  }
  25%, 75% {
    opacity: 0.3;
  }
}
</style>

