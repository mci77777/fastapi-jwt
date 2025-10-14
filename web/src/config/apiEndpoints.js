/**
 * API 端点配置清单
 * 用于 API 监控页面的端点健康检查
 */

export const API_ENDPOINTS = [
  // ==================== 健康探针 ====================
  {
    path: '/healthz',
    method: 'GET',
    type: 'http',
    description: '健康检查',
    category: 'health',
    requiresAuth: false,
  },
  {
    path: '/livez',
    method: 'GET',
    type: 'http',
    description: '存活探针',
    category: 'health',
    requiresAuth: false,
  },
  {
    path: '/readyz',
    method: 'GET',
    type: 'http',
    description: '就绪探针',
    category: 'health',
    requiresAuth: false,
  },

  // ==================== 认证相关 ====================
  {
    path: '/base/access_token',
    method: 'POST',
    type: 'http',
    description: '获取 JWT Token',
    category: 'auth',
    requiresAuth: false,
    skipCheck: true, // 需要凭证，跳过自动检测
  },
  {
    path: '/base/userinfo',
    method: 'GET',
    type: 'http',
    description: '获取用户信息',
    category: 'auth',
    requiresAuth: true,
  },
  {
    path: '/base/usermenu',
    method: 'GET',
    type: 'http',
    description: '获取用户菜单',
    category: 'auth',
    requiresAuth: true,
  },

  // ==================== LLM 模型管理 ====================
  {
    path: '/llm/models',
    method: 'GET',
    type: 'http',
    description: '获取模型列表',
    category: 'llm',
    requiresAuth: true,
  },
  {
    path: '/llm/models/check-all',
    method: 'POST',
    type: 'http',
    description: '批量诊断模型',
    category: 'llm',
    requiresAuth: true,
    skipCheck: true, // 会触发实际检测，跳过
  },
  {
    path: '/llm/model-groups',
    method: 'GET',
    type: 'http',
    description: '获取模型映射',
    category: 'llm',
    requiresAuth: true,
  },
  {
    path: '/llm/prompts',
    method: 'GET',
    type: 'http',
    description: '获取 Prompt 列表',
    category: 'llm',
    requiresAuth: true,
  },
  {
    path: '/llm/monitor/status',
    method: 'GET',
    type: 'http',
    description: '获取监控状态',
    category: 'llm',
    requiresAuth: true,
  },
  {
    path: '/llm/status/supabase',
    method: 'GET',
    type: 'http',
    description: 'Supabase 连接状态',
    category: 'llm',
    requiresAuth: true,
  },

  // ==================== Dashboard 统计 ====================
  {
    path: '/stats/dashboard',
    method: 'GET',
    type: 'http',
    description: 'Dashboard 聚合统计',
    category: 'dashboard',
    requiresAuth: true,
  },
  {
    path: '/stats/daily-active-users',
    method: 'GET',
    type: 'http',
    description: '日活用户数',
    category: 'dashboard',
    requiresAuth: true,
  },
  {
    path: '/stats/ai-requests',
    method: 'GET',
    type: 'http',
    description: 'AI 请求统计',
    category: 'dashboard',
    requiresAuth: true,
  },
  {
    path: '/stats/api-connectivity',
    method: 'GET',
    type: 'http',
    description: 'API 连通性状态',
    category: 'dashboard',
    requiresAuth: true,
  },
  {
    path: '/stats/jwt-availability',
    method: 'GET',
    type: 'http',
    description: 'JWT 可获取性',
    category: 'dashboard',
    requiresAuth: true,
  },
  {
    path: '/logs/recent',
    method: 'GET',
    type: 'http',
    description: '最近日志',
    category: 'dashboard',
    requiresAuth: true,
  },

  // ==================== 消息与 SSE ====================
  {
    path: '/messages',
    method: 'POST',
    type: 'http',
    description: '创建消息会话',
    category: 'messages',
    requiresAuth: true,
    skipCheck: true, // 需要请求体，跳过
  },
  {
    path: '/messages/{id}/events',
    method: 'GET',
    type: 'sse',
    description: 'SSE 流式消息推送',
    category: 'messages',
    requiresAuth: true,
    skipCheck: true, // SSE 端点，跳过
  },

  // ==================== WebSocket 端点 ====================
  {
    path: '/ws/dashboard',
    method: 'WebSocket',
    type: 'websocket',
    description: 'Dashboard 实时推送',
    category: 'websocket',
    requiresAuth: true,
  },
  {
    path: '/agents',
    method: 'WebSocket',
    type: 'websocket',
    description: 'Multi-Agent 对话',
    category: 'websocket',
    requiresAuth: true,
  },

  // ==================== 监控指标 ====================
  {
    path: '/metrics',
    method: 'GET',
    type: 'http',
    description: 'Prometheus 指标',
    category: 'metrics',
    requiresAuth: false,
  },
]

/**
 * 按分类分组端点
 */
export function groupEndpointsByCategory() {
  const groups = {}
  API_ENDPOINTS.forEach((endpoint) => {
    if (!groups[endpoint.category]) {
      groups[endpoint.category] = []
    }
    groups[endpoint.category].push(endpoint)
  })
  return groups
}

/**
 * 获取可检测的端点（排除 skipCheck 的端点）
 */
export function getCheckableEndpoints() {
  return API_ENDPOINTS.filter((endpoint) => !endpoint.skipCheck)
}

/**
 * 分类标签映射
 */
export const CATEGORY_LABELS = {
  health: '健康探针',
  auth: '认证',
  llm: 'AI 模型',
  dashboard: 'Dashboard',
  messages: '消息',
  websocket: 'WebSocket',
  metrics: '监控指标',
}

/**
 * 分类颜色映射（Naive UI Tag 类型）
 */
export const CATEGORY_COLORS = {
  health: 'success',
  auth: 'warning',
  llm: 'info',
  dashboard: 'primary',
  messages: 'default',
  websocket: 'error',
  metrics: 'default',
}
