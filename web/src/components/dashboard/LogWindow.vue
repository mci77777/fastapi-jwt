<template>
  <NCard title="系统日志" :bordered="true" class="log-window">
    <template #header-extra>
      <NSelect
        v-model:value="currentLevel"
        :options="levelOptions"
        size="small"
        style="width: 120px"
        @update:value="handleLevelChange"
      />
    </template>

    <div class="log-content" :class="{ 'log-loading': loading }">
      <div v-if="filteredLogs.length === 0" class="log-empty">
        <span>暂无日志</span>
      </div>

      <div v-else class="log-list">
        <div
          v-for="log in filteredLogs"
          :key="log.id || log.timestamp"
          class="log-item"
          @click="handleLogClick(log)"
        >
          <div class="log-header">
            <NTag :type="getLevelTagType(log.level)" size="small" :bordered="false">
              {{ log.level }}
            </NTag>
            <span class="log-time">{{ formatTime(log.timestamp) }}</span>
          </div>
          <div class="log-message">{{ log.message }}</div>
          <div v-if="log.user_id" class="log-user">用户: {{ log.user_id }}</div>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="log-footer">
        <span class="log-count">共 {{ filteredLogs.length }} 条日志</span>
        <NButton text size="small" @click="handleRefresh">
          <template #icon>
            <span>🔄</span>
          </template>
          刷新
        </NButton>
      </div>
    </template>
  </NCard>
</template>

<script setup>
import { ref, computed } from 'vue'
import { NCard, NTag, NSelect, NButton, useMessage } from 'naive-ui'

defineOptions({ name: 'LogWindow' })

const props = defineProps({
  logs: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['log-click', 'filter-change', 'refresh'])

const message = useMessage()

// 当前选中的日志级别
const currentLevel = ref('WARNING')

// 日志级别选项
const levelOptions = [
  { label: '全部', value: 'ALL' },
  { label: 'ERROR', value: 'ERROR' },
  { label: 'WARNING', value: 'WARNING' },
  { label: 'INFO', value: 'INFO' }
]

// 过滤后的日志
const filteredLogs = computed(() => {
  if (currentLevel.value === 'ALL') {
    return props.logs
  }

  const levelPriority = {
    ERROR: 3,
    WARNING: 2,
    INFO: 1
  }

  const minLevel = levelPriority[currentLevel.value] || 0

  return props.logs.filter((log) => {
    const logLevel = levelPriority[log.level] || 0
    return logLevel >= minLevel
  })
})

/**
 * 获取日志级别对应的 Tag 类型
 */
function getLevelTagType(level) {
  const typeMap = {
    ERROR: 'error',
    WARNING: 'warning',
    INFO: 'info'
  }
  return typeMap[level] || 'default'
}

/**
 * 格式化时间
 */
function formatTime(timestamp) {
  if (!timestamp) return ''

  try {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now - date

    // 小于 1 分钟显示"刚刚"
    if (diff < 60000) {
      return '刚刚'
    }

    // 小于 1 小时显示"X 分钟前"
    if (diff < 3600000) {
      const minutes = Math.floor(diff / 60000)
      return `${minutes} 分钟前`
    }

    // 小于 24 小时显示"X 小时前"
    if (diff < 86400000) {
      const hours = Math.floor(diff / 3600000)
      return `${hours} 小时前`
    }

    // 否则显示完整时间
    return date.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch (error) {
    return timestamp
  }
}

/**
 * 点击日志项（复制到剪贴板）
 */
function handleLogClick(log) {
  const logText = `[${log.level}] ${log.timestamp}\n${log.message}${
    log.user_id ? `\n用户: ${log.user_id}` : ''
  }`

  navigator.clipboard
    .writeText(logText)
    .then(() => {
      message.success('日志已复制到剪贴板')
      emit('log-click', log)
    })
    .catch(() => {
      message.error('复制失败')
    })
}

/**
 * 切换日志级别
 */
function handleLevelChange(level) {
  emit('filter-change', level)
}

/**
 * 刷新日志
 */
function handleRefresh() {
  emit('refresh')
}
</script>

<style scoped>
.log-window {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.log-window :deep(.n-card__content) {
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.log-content {
  height: 100%;
  overflow-y: auto;
  padding: 12px;
}

.log-loading {
  opacity: 0.6;
  pointer-events: none;
}

.log-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: #999;
  font-size: 14px;
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.log-item {
  padding: 12px;
  background-color: #f5f5f5;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.log-item:hover {
  background-color: #e8e8e8;
  transform: translateX(2px);
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.log-time {
  font-size: 12px;
  color: #999;
}

.log-message {
  font-size: 13px;
  color: #333;
  line-height: 1.5;
  word-break: break-word;
}

.log-user {
  margin-top: 4px;
  font-size: 12px;
  color: #666;
}

.log-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-top: 1px solid #e8e8e8;
}

.log-count {
  font-size: 12px;
  color: #999;
}

/* 滚动条样式 */
.log-content::-webkit-scrollbar {
  width: 6px;
}

.log-content::-webkit-scrollbar-thumb {
  background-color: #d0d0d0;
  border-radius: 3px;
}

.log-content::-webkit-scrollbar-thumb:hover {
  background-color: #b0b0b0;
}
</style>

