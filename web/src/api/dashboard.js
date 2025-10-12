import { request } from '@/utils'

/**
 * Dashboard API 封装
 * 提供统计数据、日志查询、配置管理等功能
 */

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
 * 获取 API 连通性状态
 * @returns {Promise} API 连通性数据
 */
export function getApiConnectivity() {
  return request.get('/stats/api-connectivity')
}

/**
 * 获取 JWT 可获取性
 * @returns {Promise} JWT 可获取性数据
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
  const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  // 使用当前页面的 host（例如 localhost:3101）
  // 但是 WebSocket 需要连接到后端服务器（localhost:9999）
  // 在开发环境中，Vite 代理会将 /api/v1 转发到 localhost:9999
  // 所以 WebSocket 应该直接连接到 localhost:9999
  const wsHost = window.location.hostname
  const wsPort = 9999 // 后端服务器端口
  return `${wsProtocol}//${wsHost}:${wsPort}/api/v1/ws/dashboard?token=${token}`
}

