<template>
  <NCard title="日志" :bordered="true" class="log-window">
    <template #header-extra>
      <div v-if="activeTab === 'system'" class="header-actions">
        <NSelect
          v-model:value="currentLevel"
          :options="levelOptions"
          size="small"
          style="width: 120px"
          @update:value="handleLevelChange"
        />
      </div>
      <div v-else class="header-actions">
        <div class="request-actions">
          <span class="request-actions-label">请求日志</span>
          <NSwitch v-model:value="requestLogEnabledModel" size="small" />
          <span class="request-actions-label">保留</span>
          <NInputNumber
            v-model:value="requestLogRetentionSizeModel"
            size="small"
            style="width: 110px"
            :min="10"
            :max="1000"
            :step="10"
          />
          <NButton text size="small" @click="handleRequestLogClear">清空</NButton>
        </div>
      </div>
    </template>

    <NTabs v-model:value="activeTab" type="line" animated class="log-tabs">
      <NTabPane name="system" tab="系统日志" display-directive="show">
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
      </NTabPane>

      <NTabPane name="request" tab="请求日志" display-directive="show">
        <div class="log-content">
          <div v-if="requestLogItems.length === 0" class="log-empty">
            <span>暂无请求日志（打开开关后开始记录）</span>
          </div>

          <div v-else class="log-list">
            <div
              v-for="item in requestLogItems"
              :key="item.id"
              class="log-item request-log-item"
              @click="toggleRequestLogExpand(item.id)"
            >
              <div class="log-header">
                <div class="request-tags">
                  <NTag size="small" :bordered="false" type="info">{{ item.method || 'REQ' }}</NTag>
                  <NTag size="small" :bordered="false" :type="getRequestStatusTagType(item.status)">
                    {{ formatRequestStatus(item.status) }}
                  </NTag>
                  <NTag v-if="item.kind" size="small" :bordered="false" type="default">{{ item.kind }}</NTag>
                </div>
                <div class="request-meta">
                  <span class="log-time">{{ formatTime(item.created_at) }}</span>
                  <span v-if="item.duration_ms !== null && item.duration_ms !== undefined" class="request-duration">
                    {{ item.duration_ms }}ms
                  </span>
                  <NButton text size="small" @click.stop="handleRequestLogCopy(item)">复制</NButton>
                </div>
              </div>

              <div class="request-url">{{ item.url }}</div>
              <div v-if="item.request_id" class="log-user">request_id: {{ item.request_id }}</div>

              <div v-if="isRequestLogExpanded(item.id)" class="request-raw">
                <div v-if="item.request_raw" class="raw-section">
                  <div class="raw-title">Request</div>
                  <pre class="raw-block">{{ item.request_raw }}</pre>
                </div>
                <div v-if="item.response_raw" class="raw-section">
                  <div class="raw-title">Response</div>
                  <pre class="raw-block">{{ item.response_raw }}</pre>
                </div>
                <div v-if="item.error" class="raw-section">
                  <div class="raw-title">Error</div>
                  <pre class="raw-block">{{ item.error }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </NTabPane>
    </NTabs>

    <template #footer>
      <div class="log-footer">
        <span v-if="activeTab === 'system'" class="log-count">共 {{ filteredLogs.length }} 条日志</span>
        <span v-else class="log-count">共 {{ requestLogItems.length }} 条请求日志</span>

        <div v-if="activeTab === 'system'">
          <NButton text size="small" @click="handleRefresh">
            <template #icon>
              <span>🔄</span>
            </template>
            刷新
          </NButton>
        </div>
      </div>
    </template>
  </NCard>
</template>

<script setup>
import { ref, computed } from 'vue'
import { NCard, NTag, NSelect, NButton, NInputNumber, NSwitch, NTabs, NTabPane, useMessage } from 'naive-ui'
import { useRequestLogStore } from '@/store'

defineOptions({ name: 'LogWindow' })

const props = defineProps({
  logs: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['log-click', 'filter-change', 'refresh'])

const message = useMessage()

const activeTab = ref('system')

// 当前选中的日志级别
const currentLevel = ref('WARNING')

// 日志级别选项
const levelOptions = [
  { label: '全部', value: 'ALL' },
  { label: 'ERROR', value: 'ERROR' },
  { label: 'WARNING', value: 'WARNING' },
  { label: 'INFO', value: 'INFO' },
]

// 过滤后的日志
const filteredLogs = computed(() => {
  if (currentLevel.value === 'ALL') {
    return props.logs
  }

  const levelPriority = {
    ERROR: 3,
    WARNING: 2,
    INFO: 1,
  }

  const minLevel = levelPriority[currentLevel.value] || 0

  return props.logs.filter((log) => {
    const logLevel = levelPriority[log.level] || 0
    return logLevel >= minLevel
  })
})

const requestLogStore = useRequestLogStore()
const requestLogEnabledModel = computed({
  get() {
    return requestLogStore.enabled
  },
  set(val) {
    requestLogStore.setEnabled(val)
  },
})

const requestLogRetentionSizeModel = computed({
  get() {
    return requestLogStore.retentionSize
  },
  set(val) {
    requestLogStore.setRetentionSize(val)
  },
})

const requestLogItems = computed(() => requestLogStore.items || [])
const expandedRequestLogIds = ref([])

function toggleRequestLogExpand(id) {
  if (!id) return
  const list = expandedRequestLogIds.value || []
  if (list.includes(id)) {
    expandedRequestLogIds.value = list.filter((x) => x !== id)
    return
  }
  expandedRequestLogIds.value = [id, ...list].slice(0, 20)
}

function isRequestLogExpanded(id) {
  return (expandedRequestLogIds.value || []).includes(id)
}

function formatRequestStatus(status) {
  const s = String(status || '')
  if (s === 'pending') return 'PENDING'
  if (s === 'success') return 'OK'
  if (s === 'app_error') return 'APP_ERR'
  if (s === 'error') return 'ERROR'
  if (s === 'event') return 'EVENT'
  return s.toUpperCase() || 'UNKNOWN'
}

function getRequestStatusTagType(status) {
  const s = String(status || '')
  if (s === 'error') return 'error'
  if (s === 'app_error') return 'warning'
  if (s === 'pending') return 'default'
  if (s === 'event') return 'info'
  return 'success'
}

function handleRequestLogClear() {
  requestLogStore.clear()
  expandedRequestLogIds.value = []
  message.success('请求日志已清空')
}

function handleRequestLogCopy(item) {
  const text = [
    `[${formatRequestStatus(item?.status)}] ${String(item?.method || '').toUpperCase()} ${item?.url || ''}`,
    item?.request_id ? `request_id=${item.request_id}` : '',
    item?.duration_ms !== null && item?.duration_ms !== undefined ? `duration_ms=${item.duration_ms}` : '',
    item?.request_raw ? `\n--- REQUEST ---\n${item.request_raw}` : '',
    item?.response_raw ? `\n--- RESPONSE ---\n${item.response_raw}` : '',
    item?.error ? `\n--- ERROR ---\n${item.error}` : '',
  ]
    .filter(Boolean)
    .join('\n')

  navigator.clipboard
    .writeText(text)
    .then(() => message.success('已复制'))
    .catch(() => message.error('复制失败'))
}

/**
 * 获取日志级别对应的 Tag 类型
 */
function getLevelTagType(level) {
  const typeMap = {
    ERROR: 'error',
    WARNING: 'warning',
    INFO: 'info',
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
      minute: '2-digit',
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
/* ========== Claude 风格日志窗口 ========== */
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

.header-actions {
  display: flex;
  align-items: center;
}

.request-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.request-actions-label {
  font-size: var(--font-size-xs);
  color: var(--claude-text-gray);
}

.log-tabs {
  height: 100%;
}

.log-window :deep(.n-tabs) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.log-window :deep(.n-tabs-nav) {
  padding: 0 var(--spacing-md);
}

.log-window :deep(.n-tabs-pane-wrapper) {
  flex: 1;
  overflow: hidden;
}

.log-content {
  height: 100%;
  overflow-y: auto;
  padding: var(--spacing-md);
  /* 应用 Claude 自定义滚动条 */
  scrollbar-width: thin;
  scrollbar-color: var(--claude-terra-cotta) var(--claude-bg-warm);
}

.log-content::-webkit-scrollbar {
  width: 8px;
}

.log-content::-webkit-scrollbar-track {
  background: var(--claude-bg-warm);
  border-radius: 4px;
}

.log-content::-webkit-scrollbar-thumb {
  background: var(--claude-terra-cotta);
  border-radius: 4px;
  transition: background var(--duration-fast);
}

.log-content::-webkit-scrollbar-thumb:hover {
  background: var(--claude-button-orange);
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
  color: var(--claude-text-gray);
  font-size: var(--font-size-base);
}

.log-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.log-item {
  padding: var(--spacing-md);
  /* Claude 暖白背景 */
  background-color: var(--claude-bg-warm);
  border: 1px solid var(--claude-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-smooth);
}

.request-log-item {
  cursor: pointer;
}

.request-tags {
  display: flex;
  align-items: center;
  gap: 6px;
}

.request-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.request-duration {
  font-size: var(--font-size-xs);
  color: var(--claude-text-gray);
}

.request-url {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace);
  font-size: var(--font-size-xs);
  color: var(--claude-text-gray);
  word-break: break-all;
  margin-bottom: var(--spacing-xs);
}

.request-raw {
  margin-top: var(--spacing-sm);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.raw-section {
  padding: var(--spacing-sm);
  border: 1px dashed var(--claude-border);
  border-radius: var(--radius-sm);
  background: rgba(255, 255, 255, 0.5);
}

.raw-title {
  font-size: var(--font-size-xs);
  color: var(--claude-text-gray);
  margin-bottom: var(--spacing-xs);
}

.raw-block {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.4;
  color: var(--claude-black);
}

.log-item:hover {
  /* 悬停时背景变为淡橙色 + 横向滑入 */
  background-color: var(--claude-hover-bg);
  border-color: var(--claude-terra-cotta);
  transform: translateX(4px);
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--spacing-sm);
}

.log-time {
  font-size: var(--font-size-xs);
  color: var(--claude-text-gray);
}

.log-message {
  font-family: var(--font-sans);
  font-size: var(--font-size-sm);
  color: var(--claude-black); /* 使用纯黑色提高可读性 */
  line-height: 1.5;
  word-break: break-word;
  font-weight: var(--font-weight-medium);
}

.log-user {
  margin-top: var(--spacing-xs);
  font-size: var(--font-size-xs);
  color: var(--claude-text-gray);
}

.log-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-sm) var(--spacing-md);
  border-top: 1px solid var(--claude-border);
}

.log-count {
  font-size: var(--font-size-xs);
  color: var(--claude-text-gray);
}
</style>
