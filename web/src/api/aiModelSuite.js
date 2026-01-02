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

// JWT 测试相关
export const createMailUser = (data = {}) => request.post('/llm/tests/create-mail-user', data)
export const createAnonToken = (data = {}) => request.post('/llm/tests/anon-token', data)
export const listMailUsers = (params = {}) => request.get('/llm/tests/mail-users', { params })
export const refreshMailUserToken = (testUserId, data = {}) =>
  request.post(`/llm/tests/mail-users/${testUserId}/refresh`, data)

// 消息与对话相关
/**
 * 创建消息会话（统一请求体构建）
 * @param {Object} options - 消息选项
 * @param {string} [options.text] - 用户消息文本（messages 不为空时可省略）
 * @param {string} [options.conversationId] - 会话 ID
 * @param {Object} [options.metadata] - 元数据
 * @param {('server'|'passthrough')} [options.promptMode='server'] - prompt 策略：使用后端 prompt 或透传 OpenAI 字段
 * @param {Object} [options.openai] - OpenAI 兼容字段（后端 SSOT）
 * @param {string} [options.openai.model]
 * @param {Array<Object>} [options.openai.messages]
 * @param {string} [options.openai.system_prompt]
 * @param {Array<any>} [options.openai.tools]
 * @param {any} [options.openai.tool_choice]
 * @param {number} [options.openai.temperature]
 * @param {number} [options.openai.top_p]
 * @param {number} [options.openai.max_tokens]
 * @param {string} [options.requestId] - 透传请求追踪 Header：X-Request-Id（建议由调用方生成并用于 SSE 对账）
 * @param {string} [options.accessToken] - 覆盖 Authorization（用于 JWT 测试页，不污染全局登录态）
 * @returns {Promise<{message_id: string, conversation_id: string}>} 消息ID与会话ID
 */
export const createMessage = ({
  text,
  conversationId,
  metadata = {},
  promptMode = 'server',
  openai = {},
  requestId,
  accessToken,
} = {}) => {
  const hasText = typeof text === 'string' && !!text.trim()
  const hasMessages = Array.isArray(openai?.messages) && openai.messages.length > 0
  if (!hasText && !hasMessages) {
    return Promise.reject(new Error('text 或 openai.messages 至少提供一个'))
  }

  const resolvedPromptMode = promptMode === 'passthrough' ? 'passthrough' : 'server'

  // 构建符合后端 schema 的请求体
  const payload = {
    conversation_id: conversationId || null,
    metadata: {
      source: 'web_ui',
      timestamp: new Date().toISOString(),
      ...metadata,
    },
  }

  if (hasText) payload.text = text.trim()

  // prompt 策略：server=使用后端 prompt 注入；passthrough=仅透传 OpenAI 字段，不注入默认 prompt
  payload.skip_prompt = resolvedPromptMode === 'passthrough'

  // OpenAI 兼容字段（仅白名单字段进入 body 顶层；扩展信息仍应放 metadata）
  if (openai && typeof openai === 'object') {
    if (typeof openai.model === 'string' && openai.model.trim()) payload.model = openai.model.trim()
    if (typeof openai.system_prompt === 'string' && openai.system_prompt.trim()) {
      if (resolvedPromptMode === 'passthrough') payload.system_prompt = openai.system_prompt.trim()
    }

    if (Array.isArray(openai.messages)) {
      payload.messages =
        resolvedPromptMode === 'server'
          ? openai.messages.filter((item) => item && item.role !== 'system')
          : openai.messages
    }

    if (openai.tools !== undefined) payload.tools = openai.tools
    if (openai.tool_choice !== undefined) payload.tool_choice = openai.tool_choice
    if (openai.temperature !== undefined) payload.temperature = openai.temperature
    if (openai.top_p !== undefined) payload.top_p = openai.top_p
    if (openai.max_tokens !== undefined) payload.max_tokens = openai.max_tokens
  }

  const headers = {}
  if (typeof requestId === 'string' && requestId.trim()) headers['X-Request-Id'] = requestId.trim()
  if (typeof accessToken === 'string' && accessToken.trim()) headers['Authorization'] = `Bearer ${accessToken.trim()}`

  return request.post('/messages', payload, {
    timeout: 30000,
    headers,
  })
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
