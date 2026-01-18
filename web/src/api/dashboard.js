import { request } from '@/utils'

/**
 * Dashboard API 封装
 * 提供统计数据、日志查询、配置管理等功能
 */

// ==================== 模型管理 ====================

/**
 * 获取 AI 模型列表
 * @param {Object} params - 查询参数
 * @param {string} params.keyword - 关键词搜索
 * @param {boolean} params.only_active - 仅显示活跃模型
 * @param {number} params.page - 页码
 * @param {number} params.page_size - 每页数量
 * @returns {Promise} 模型列表
 */
export function getModels(params = {}) {
  return request.get('/llm/models', { params: { view: 'endpoints', ...params } })
}

/**
 * 设置默认模型
 * @param {number} modelId - 模型 ID
 * @returns {Promise} 更新结果
 */
export function setDefaultModel(modelId) {
  return request.put('/llm/models', { id: modelId, is_default: true })
}

// ==================== Prompt 管理 ====================

/**
 * 获取 Prompt 列表
 * @param {Object} params - 查询参数
 * @param {string} params.keyword - 关键词搜索
 * @param {boolean} params.only_active - 仅显示活跃 Prompt
 * @param {number} params.page - 页码
 * @param {number} params.page_size - 每页数量
 * @returns {Promise} Prompt 列表
 */
export function getPrompts(params = {}) {
  return request.get('/llm/prompts', { params })
}

/**
 * 激活 Prompt（设置为活跃状态）
 * @param {number} promptId - Prompt ID
 * @returns {Promise} 激活结果
 */
export function setActivePrompt(promptId) {
  return request.post(`/llm/prompts/${promptId}/activate`)
}

// ==================== 统计数据 ====================

/**
 * 获取聚合统计数据
 * @param {Object} params - 查询参数
 * @param {string} params.time_window - 时间窗口 ('1h' | '24h' | '7d')
 * @returns {Promise} 统计数据
 */
export function getDashboardStats(params = {}) {
  return request.get('/stats/dashboard', { params })
}

/**
 * 获取日活用户数
 * @param {Object} params - 查询参数
 * @param {string} params.time_window - 时间窗口 ('1h' | '24h' | '7d')
 * @returns {Promise} 日活用户数据
 */
export function getDailyActiveUsers(params = {}) {
  return request.get('/stats/daily-active-users', { params })
}

/**
 * 获取 AI 请求统计
 * @param {Object} params - 查询参数
 * @param {string} params.time_window - 时间窗口 ('1h' | '24h' | '7d')
 * @returns {Promise} AI 请求统计数据
 */
export function getAiRequests(params = {}) {
  return request.get('/stats/ai-requests', { params })
}

/**
 * 获取映射模型可用性与调用统计（Dashboard）
 * @param {Object} params - 查询参数
 * @param {string} params.time_window - 时间窗口 ('24h' | '7d')
 * @param {boolean} params.include_inactive - 是否包含未激活映射
 * @returns {Promise} 映射模型统计数据
 */
export function getMappedModelsStats(params = {}) {
  return request.get('/stats/mapped-models', { params })
}

/**
 * 获取每日 E2E 映射模型可用性结果
 * @returns {Promise} E2E 结果
 */
export function getE2EMappedModelsStats() {
  return request.get('/stats/e2e-mapped-models')
}

/**
 * 获取 API 连通性状态
 * @returns {Promise} API 连通性数据
 */
export function getApiConnectivity() {
  return request.get('/stats/api-connectivity')
}

/**
 * 获取 JWT 连通性
 * @returns {Promise} JWT 连通性数据
 */
export function getJwtAvailability() {
  return request.get('/stats/jwt-availability')
}

/**
 * 获取最近日志
 * @param {Object} params - 查询参数
 * @param {string} params.level - 日志级别 ('ERROR' | 'WARNING' | 'INFO')
 * @param {number} params.limit - 最大返回条数
 * @returns {Promise} 日志列表
 */
export function getRecentLogs(params = {}) {
  return request.get('/logs/recent', { params })
}

/**
 * 获取 Dashboard 配置
 * @returns {Promise} 配置数据
 */
export function getStatsConfig() {
  return request.get('/stats/config')
}

/**
 * 更新 Dashboard 配置
 * @param {Object} data - 配置数据
 * @param {number} data.websocket_push_interval - WebSocket 推送间隔（秒）
 * @param {number} data.http_poll_interval - HTTP 轮询间隔（秒）
 * @param {number} data.log_retention_size - 日志保留数量
 * @returns {Promise} 更新后的配置
 */
export function updateStatsConfig(data = {}) {
  return request.put('/stats/config', data)
}

/**
 * 创建 WebSocket 连接 URL
 * @param {string} token - JWT token
 * @returns {string} WebSocket URL
 */
export function createWebSocketUrl(token) {
  const rawBaseApi = import.meta.env.VITE_BASE_API || '/api/v1'
  const baseApi = String(rawBaseApi || '').trim().replace(/\/+$/, '')

  const tokenParam = encodeURIComponent(String(token || ''))

  // SSOT：WS 与 HTTP 走同一份 base api，避免本地 Docker(3101)/dev(3102)/生产(https) 端口漂移。
  // - baseApi 为相对路径（/api/v1）：使用当前 origin
  // - baseApi 为绝对 URL（https://api.xxx/api/v1）：跟随其 host 与协议（https->wss, http->ws）
  if (/^https?:\/\//i.test(baseApi)) {
    const wsBase = baseApi.replace(/^https:/i, 'wss:').replace(/^http:/i, 'ws:')
    return `${wsBase}/ws/dashboard?token=${tokenParam}`
  }

  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const origin = `${wsProtocol}//${window.location.host}`
  return `${origin}${baseApi}/ws/dashboard?token=${tokenParam}`
}

/**
 * 获取 Supabase 连接状态
 * @returns {Promise} Supabase 状态数据
 */
export function getSupabaseStatus() {
  return request.get('/llm/status/supabase')
}

/**
 * 获取监控状态
 * @returns {Promise} 监控状态数据
 */
export function getMonitorStatus() {
  return request.get('/llm/monitor/status')
}

/**
 * 启动监控
 * @param {number} intervalSeconds - 监控间隔（秒）
 * @returns {Promise} 启动结果
 */
export function startMonitor(intervalSeconds = 60) {
  return request.post('/llm/monitor/start', { interval_seconds: intervalSeconds })
}

/**
 * 停止监控
 * @returns {Promise} 停止结果
 */
export function stopMonitor() {
  return request.post('/llm/monitor/stop')
}

/**
 * 获取 Prometheus 系统指标
 * @returns {Promise<string>} Prometheus 文本格式的指标数据
 */
export function getSystemMetrics() {
  return request.get('metrics', { responseType: 'text' })
}

/**
 * 解析 Prometheus 文本格式指标
 * @param {string} text - Prometheus 文本格式数据
 * @returns {Object} 解析后的指标对象
 */
export function parsePrometheusMetrics(text) {
  const lines = String(text || '').split('\n')
  const metrics = {}

  const parseValue = (raw) => {
    const v = String(raw || '').trim()
    if (!v) return null
    const lower = v.toLowerCase()
    if (lower === '+inf' || lower === 'inf') return Number.POSITIVE_INFINITY
    if (lower === '-inf') return Number.NEGATIVE_INFINITY
    const n = Number(v)
    return Number.isFinite(n) ? n : null
  }

  lines.forEach((line) => {
    const trimmed = String(line || '').trim()
    if (!trimmed || trimmed.startsWith('#')) return

    // 匹配指标行：
    // - metric_name value
    // - metric_name{labels} value
    const match = trimmed.match(
      /^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([0-9.eE+-]+|[+-]?Inf)\s*$/
    )
    if (!match) return

    const [, name, labelBody, valueRaw] = match
    const value = parseValue(valueRaw)
    if (value === null) return

    // 1) 聚合：按指标名累加（兼容带标签的多行指标）
    metrics[name] = (metrics[name] || 0) + value

    // 2) 明细：保留带 labels 的原始 series key，供直方图/分组解析使用
    if (typeof labelBody === 'string' && labelBody.trim()) {
      metrics[`${name}{${labelBody}}`] = value
    }
  })

  return metrics
}

// ==================== 请求追踪 ====================

/**
 * 获取请求追踪配置
 * @returns {Promise} 追踪配置 { enabled: boolean }
 */
export function getTracingConfig() {
  return request.get('/tracing/config')
}

/**
 * 设置请求追踪配置
 * @param {boolean} enabled - 是否启用追踪
 * @returns {Promise} 更新后的配置 { enabled: boolean }
 */
export function setTracingConfig(enabled) {
  return request.post('/tracing/config', { enabled })
}

/**
 * 获取对话日志列表（最近 50 条）
 * @param {Object} params - 查询参数
 * @param {number} params.limit - 最大返回条数（默认 50，最大 50）
 * @returns {Promise} 日志列表 { logs: Array, total: number }
 */
export function getConversationLogs(params = {}) {
  return request.get('/tracing/logs', { params })
}
