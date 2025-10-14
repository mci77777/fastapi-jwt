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
    validator: (value) =>
      ['connected', 'disconnected', 'connecting', 'error', 'polling'].includes(value),
  },
})

// 状态文本映射
const statusText = computed(() => {
  const textMap = {
    connected: 'WebSocket 已连接',
    disconnected: 'WebSocket 已断开',
    connecting: '正在连接...',
    error: '连接错误',
    polling: '轮询模式',
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
    polling: 'warning',
  }
  return typeMap[props.status] || 'default'
})

// 状态点样式类
const statusClass = computed(() => {
  return `status-${props.status}`
})
</script>

<style scoped>
/* ========== Claude 风格实时状态指示器 ========== */
.real-time-indicator {
  display: inline-flex;
  align-items: center;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: var(--spacing-xs);
}

.status-connected {
  background-color: var(--claude-success);
  animation: pulse 2s infinite;
}

.status-disconnected {
  background-color: var(--claude-text-gray);
}

.status-connecting {
  background-color: var(--claude-info);
  animation: blink 1s infinite;
}

.status-error {
  background-color: var(--claude-error);
}

.status-polling {
  background-color: var(--claude-warning);
  animation: pulse 2s infinite;
}

/* 使用 Design Tokens 中定义的 pulse 动画 */
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

@keyframes blink {
  0%,
  50%,
  100% {
    opacity: 1;
  }
  25%,
  75% {
    opacity: 0.3;
  }
}
</style>
