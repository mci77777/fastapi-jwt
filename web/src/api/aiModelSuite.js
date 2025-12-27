import { request } from '@/utils'

export const fetchModels = (params = {}) => request.get('/llm/models', { params })
export const updateModel = (data = {}) => request.put('/llm/models', data)
export const diagnoseModels = () => request.post('/llm/models/check-all')
export const syncModel = (endpointId, options = {}) =>
  request.post(`/llm/models/${endpointId}/sync`, {
    direction: options.direction ?? 'push',
    overwrite: !!options.overwrite,
    delete_missing: !!options.deleteMissing,
  })
export const syncAllModels = (options = {}) =>
  request.post('/llm/models/sync', {
    direction: options.direction ?? 'both',
    overwrite: !!options.overwrite,
    delete_missing: !!options.deleteMissing,
  })

export const fetchMappings = (params = {}) => request.get('/llm/model-groups', { params })
export const saveMapping = (data = {}) => request.post('/llm/model-groups', data)
export const activateMapping = (mappingId, data = {}) =>
  request.post(`/llm/model-groups/${mappingId}/activate`, data)
export const syncMappingsToSupabase = () => request.post('/llm/model-groups/sync-to-supabase')

export const fetchPrompts = (params = {}) => request.get('/llm/prompts', { params })
export const fetchPromptTests = (promptId, params = {}) =>
  request.get(`/llm/prompts/${promptId}/tests`, { params })

// JWT 测试相关（增加超时配置）
export const simulateDialog = (data = {}) =>
  request.post('/llm/tests/dialog', data, { timeout: 30000 }) // 30秒超时

export const runLoadTest = (data = {}) => request.post('/llm/tests/load', data, { timeout: 60000 }) // 60秒超时（压测可能较慢）

export const fetchLoadRun = (runId) => request.get(`/llm/tests/runs/${runId}`)

// 邮件用户创建（调试用）
export const createMailUser = (data = {}) => request.post('/llm/tests/create-mail-user', data)

// 消息与对话相关
/**
 * 创建消息会话（统一请求体构建）
 * @param {Object} options - 消息选项
 * @param {string} options.text - 消息文本（必需）
 * @param {string} [options.conversationId] - 会话 ID
 * @param {Object} [options.metadata] - 元数据
 * @returns {Promise<{message_id: string, conversation_id: string}>} 消息ID与会话ID
 */
export const createMessage = ({ text, conversationId, metadata = {} }) => {
  // 输入验证
  if (!text || typeof text !== 'string' || !text.trim()) {
    return Promise.reject(new Error('消息文本不能为空'))
  }

  // 构建符合后端 schema 的请求体
  const payload = {
    text: text.trim(),
    conversation_id: conversationId || null,
    metadata: {
      source: 'web_ui',
      timestamp: new Date().toISOString(),
      ...metadata,
    },
  }

  return request.post('/messages', payload, { timeout: 30000 })
}

// API 端点连通性检测
/**
 * 检测单个 API 端点的连通性
 * @param {number} endpointId - 端点 ID
 * @returns {Promise<{status: string, latency: number, error?: string}>}
 */
export const checkEndpointConnectivity = (endpointId) =>
  request.post(`/llm/models/${endpointId}/check`, {}, { timeout: 15000 })

/**
 * 批量检测所有端点的连通性
 * @returns {Promise<Array<{id: number, name: string, status: string, latency: number}>>}
 */
export const checkAllEndpointsConnectivity = () =>
  request.post('/llm/models/check-all', {}, { timeout: 60000 })
