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
        <div class="system-actions">
          <span class="request-actions-label">详细</span>
          <NSwitch v-model:value="systemDetailEnabled" size="small" />
        </div>
      </div>
        <div v-else class="header-actions">
          <div class="request-actions">
            <span class="request-actions-label">请求日志</span>
            <NSwitch v-model:value="requestLogEnabledModel" size="small" />
            <span class="request-actions-label">SQLite</span>
            <NSwitch v-model:value="requestLogPersistEnabledModel" size="small" />
            <NButton text size="small" :loading="sqliteLoading" @click="handleRequestLogSync">拉取</NButton>
            <span class="request-actions-label">详情</span>
            <NSwitch v-model:value="requestDetailEnabled" size="small" />
            <span class="request-actions-label">保留</span>
            <NInputNumber
            v-model:value="requestLogRetentionSizeModel"
            size="small"
            style="width: 110px"
            :min="10"
            :max="1000"
            :step="10"
          />
          <NButton text size="small" :loading="sqliteLoading" @click="handleRequestLogClear">清空</NButton>
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
              <div v-if="systemDetailEnabled" class="log-detail">
                <span class="log-meta">{{ log.module }}.{{ log.function }}:{{ log.line }}</span>
                <span v-if="log.request_id" class="log-meta">request_id: {{ log.request_id }}</span>
                <span v-if="log.user_id" class="log-meta">user: {{ log.user_id }}</span>
              </div>
              <div v-if="log.user_id && !systemDetailEnabled" class="log-user">用户: {{ log.user_id }}</div>
            </div>
          </div>
        </div>
      </NTabPane>

      <NTabPane name="request" tab="请求日志" display-directive="show">
        <div class="log-content">
          <div class="request-filter-bar">
            <NSelect v-model:value="requestCategoryFilter" size="small" :options="requestCategoryOptions" style="width: 140px" />
            <NSelect v-model:value="requestKindFilter" size="small" :options="requestKindOptions" style="width: 140px" />
            <NSelect v-model:value="requestStatusFilter" size="small" :options="requestStatusOptions" style="width: 140px" />
            <NInput v-model:value="requestKeyword" size="small" clearable placeholder="搜索 URL / request_id" />
          </div>
          <div v-if="requestLogItems.length === 0" class="log-empty">
            <span>暂无请求日志（打开开关后开始记录）</span>
          </div>
          <div v-else-if="filteredRequestLogItems.length === 0" class="log-empty">
            <span>无匹配结果（请调整筛选条件）</span>
          </div>

          <div v-else class="log-list">
            <div
              v-for="item in filteredRequestLogItems"
              :key="item.id"
              class="log-item request-log-item"
              @click="handleRequestLogClick(item.id)"
            >
              <div class="log-header">
                <div class="request-tags">
                  <NTag size="small" :bordered="false" type="info">{{ item.method || 'REQ' }}</NTag>
                  <NTag size="small" :bordered="false" :type="getRequestStatusTagType(item.status)">
                    {{ formatRequestStatus(item.status) }}
                  </NTag>
                  <NTag v-if="getRequestCategory(item)" size="small" :bordered="false" type="default">
                    {{ getRequestCategory(item) }}
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

              <div v-if="requestDetailEnabled && isRequestLogExpanded(item.id)" class="request-raw">
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
        <span v-else class="log-count">显示 {{ filteredRequestLogItems.length }} / {{ requestLogItems.length }} 条请求日志</span>

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
import { NCard, NTag, NSelect, NInput, NButton, NInputNumber, NSwitch, NTabs, NTabPane, useMessage } from 'naive-ui'
import { useRequestLogStore } from '@/store'
import { getToken } from '@/utils'

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
const systemDetailEnabled = ref(false)
const requestDetailEnabled = ref(true)

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

const requestLogPersistEnabledModel = computed({
  get() {
    return requestLogStore.persistEnabled
  },
  set(val) {
    const enabled = Boolean(val)
    requestLogStore.setPersistEnabled(enabled)
    if (enabled && !requestLogStore.enabled) {
      requestLogStore.setEnabled(true)
    }
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
const requestCategoryFilter = ref('all')
const requestKindFilter = ref('all')
const requestStatusFilter = ref('all')
const requestKeyword = ref('')
const expandedRequestLogIds = ref([])
const sqliteLoading = ref(false)

function getRequestCategory(item) {
  const rawUrl = String(item?.url || '').trim()
  if (!rawUrl) return ''

  const kind = String(item?.kind || '').trim().toLowerCase()
  const method = String(item?.method || '').trim().toUpperCase()
  if (kind === 'eventsource' || method === 'EVENT') return 'sse'

  let urlObj = null
  try {
    const origin = globalThis.location?.origin || 'http://localhost'
    urlObj = new URL(rawUrl, origin)
  } catch {
    urlObj = null
  }

  const host = urlObj?.host ? String(urlObj.host) : ''
  const localHost = globalThis.location?.host ? String(globalThis.location.host) : ''
  if (host && localHost && host !== localHost) return 'external'

  const path = String(urlObj?.pathname || rawUrl)
  const normalized = path.replace(/^\/+/, '')
  const idx = normalized.indexOf('api/v1/')
  const rest = idx >= 0 ? normalized.slice(idx + 'api/v1/'.length) : normalized

  if (rest.startsWith('messages')) return 'messages'
  if (rest.startsWith('llm/')) return 'llm'
  if (rest.startsWith('stats/') || rest.startsWith('logs/') || rest.startsWith('dashboard/')) return 'dashboard'
  if (rest.startsWith('ai/') || rest.startsWith('base/') || rest.startsWith('auth/')) return 'auth'
  return 'other'
}

const requestCategoryOptions = computed(() => {
  const base = [{ label: '全部分类', value: 'all' }]
  const set = new Set()
  ;(requestLogItems.value || []).forEach((it) => {
    const c = getRequestCategory(it)
    if (c) set.add(c)
  })
  Array.from(set)
    .sort()
    .forEach((c) => base.push({ label: c, value: c }))
  return base
})

const requestKindOptions = computed(() => {
  const base = [{ label: '全部来源', value: 'all' }]
  const set = new Set()
  ;(requestLogItems.value || []).forEach((it) => {
    const k = String(it?.kind || '').trim()
    if (k) set.add(k)
  })
  Array.from(set)
    .sort()
    .forEach((k) => base.push({ label: k, value: k }))
  return base
})

const requestStatusOptions = [
  { label: '全部状态', value: 'all' },
  { label: 'OK', value: 'success' },
  { label: 'APP_ERR', value: 'app_error' },
  { label: 'ERROR', value: 'error' },
  { label: 'PENDING', value: 'pending' },
  { label: 'EVENT', value: 'event' },
]

const filteredRequestLogItems = computed(() => {
  const list = Array.isArray(requestLogItems.value) ? requestLogItems.value : []
  const kw = String(requestKeyword.value || '').trim().toLowerCase()
  return list.filter((it) => {
    if (requestCategoryFilter.value !== 'all') {
      if (getRequestCategory(it) !== requestCategoryFilter.value) return false
    }
    if (requestKindFilter.value !== 'all') {
      if (String(it?.kind || '') !== requestKindFilter.value) return false
    }
    if (requestStatusFilter.value !== 'all') {
      if (String(it?.status || '') !== requestStatusFilter.value) return false
    }
    if (kw) {
      const url = String(it?.url || '').toLowerCase()
      const rid = String(it?.request_id || '').toLowerCase()
      if (!url.includes(kw) && !rid.includes(kw)) return false
    }
    return true
  })
})

function resolveBaseApiUrl(path) {
  const rawBaseApi = import.meta.env.VITE_BASE_API || '/api/v1'
  const baseApi = String(rawBaseApi || '').trim().replace(/\/+$/, '')
  const cleanPath = String(path || '').trim().replace(/^\/+/, '')
  if (!baseApi) return `/${cleanPath}`
  if (/^https?:\/\//i.test(baseApi)) return `${baseApi}/${cleanPath}`
  return `${baseApi}/${cleanPath}`
}

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

function handleRequestLogClick(id) {
  if (!requestDetailEnabled.value) return
  toggleRequestLogExpand(id)
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
  const clearLocal = () => {
    requestLogStore.clear()
    expandedRequestLogIds.value = []
  }

  if (!requestLogPersistEnabledModel.value) {
    clearLocal()
    message.success('请求日志已清空')
    return
  }

  sqliteLoading.value = true
  fetch(resolveBaseApiUrl('logs/request'), {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${getToken()}` },
  })
    .then(async (resp) => {
      const json = await resp.json().catch(() => null)
      if (!resp.ok) throw json || new Error('清空失败')
      clearLocal()
      message.success('请求日志已清空（含 SQLite）')
    })
    .catch(() => {
      message.error('清空 SQLite 请求日志失败')
      clearLocal()
    })
    .finally(() => {
      sqliteLoading.value = false
    })
}

function handleRequestLogSync() {
  sqliteLoading.value = true
  const token = getToken()
  fetch(resolveBaseApiUrl(`logs/request?limit=${requestLogRetentionSizeModel.value || 200}`), {
    headers: { Authorization: `Bearer ${token}` },
  })
    .then(async (resp) => {
      const json = await resp.json().catch(() => null)
      if (!resp.ok) throw json || new Error('拉取失败')

      const payload = json?.data && typeof json.data === 'object' ? json.data : json
      const items = Array.isArray(payload?.items) ? payload.items : []

      requestLogStore.clear()
      expandedRequestLogIds.value = []
      items.forEach((it) => {
        requestLogStore.append({
          id: `db-${it?.id}`,
          kind: it?.kind || 'sqlite',
          status: it?.status || 'unknown',
          method: it?.method || '',
          url: it?.url || '',
          request_id: it?.request_id || null,
          created_at: it?.created_at || null,
          duration_ms: it?.duration_ms ?? null,
          request_raw: it?.request_raw || '',
          response_raw: it?.response_raw || '',
          error: it?.error || null,
        })
      })
      message.success('已从 SQLite 拉取请求日志')
    })
    .catch(() => {
      message.error('拉取 SQLite 请求日志失败')
    })
    .finally(() => {
      sqliteLoading.value = false
    })
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
  const logText = [
    `[${log.level}] ${log.timestamp}`,
    log.request_id ? `request_id: ${log.request_id}` : '',
    log.message,
    log.user_id ? `用户: ${log.user_id}` : '',
  ]
    .filter(Boolean)
    .join('\n')

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

.request-filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px 6px;
}

.request-filter-bar :deep(.n-input) {
  flex: 1;
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

.system-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: 10px;
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

.log-detail {
  margin-top: var(--spacing-xs);
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.log-meta {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace);
  font-size: 12px;
  color: var(--claude-text-gray);
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
