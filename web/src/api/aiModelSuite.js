import { request } from '@/utils'

export const fetchModels = (params = {}) =>
  request.get('/llm/models', { params: { view: 'endpoints', ...params } })
export const updateModel = (data = {}) => request.put('/llm/models', data)
// 触发端点批量检测（后端 202 Accepted，后台刷新；返回 monitor snapshot）
export const diagnoseModels = () => request.post('/llm/models/check-all', {}, { timeout: 10000 })
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
export const deleteMapping = (mappingId) => request.delete(`/llm/model-groups/${mappingId}`)
export const syncMappingsToSupabase = () => request.post('/llm/model-groups/sync-to-supabase')
export const syncMappings = (options = {}) =>
  request.post('/llm/model-groups/sync', {
    direction: options.direction ?? 'push',
    overwrite: !!options.overwrite,
    delete_missing: !!options.deleteMissing,
  })
export const importMappingsLocal = (file) => {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/llm/model-groups/import-local-json', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const fetchPrompts = (params = {}) => request.get('/llm/prompts', { params })
export const fetchPromptTests = (promptId, params = {}) =>
  request.get(`/llm/prompts/${promptId}/tests`, { params })

export const fetchAppModels = (params = {}) => request.get('/llm/app/models', { params })

export const fetchBlockedModels = () => request.get('/llm/models/blocked')
export const upsertBlockedModels = (updates = []) => request.put('/llm/models/blocked', { updates })

// JWT 测试相关
export const createMailUser = (data = {}) => request.post('/llm/tests/create-mail-user', data)
export const createAnonToken = (data = {}) => request.post('/llm/tests/anon-token', data)
export const listMailUsers = (params = {}) => request.get('/llm/tests/mail-users', { params })
export const refreshMailUserToken = (testUserId, data = {}) =>
  request.post(`/llm/tests/mail-users/${testUserId}/refresh`, data)
export const fetchActivePromptsSnapshot = (params = {}) =>
  request.get('/llm/tests/active-prompts', { params })
export const fetchActiveAgentPromptsSnapshot = (params = {}) =>
  request.get('/llm/tests/active-agent-prompts', { params })

// 消息与对话相关
/**
 * 创建消息会话（统一请求体构建）
 * @param {Object} options - 消息选项
 * @param {string} [options.text] - 用户消息文本（messages 不为空时可省略）
 * @param {string} [options.conversationId] - 会话 ID
 * @param {Object} [options.metadata] - 元数据
 * @param {('server'|'passthrough')} [options.promptMode='server'] - prompt 策略：使用后端 prompt 或透传 OpenAI 字段
 * @param {('xml_plaintext'|'raw_passthrough'|'auto'|'text'|'raw')} [options.resultMode='xml_plaintext'] - SSE 输出：xml_plaintext=解析后纯文本（含 XML 标签）；raw_passthrough=上游 RAW 透明转发；auto=自动检测；兼容旧值 text/raw
 * @param {Object} [options.openai] - OpenAI 兼容字段（后端 SSOT）
 * @param {string} [options.openai.model]
 * @param {Array<Object>} [options.openai.messages]
 * @param {string} [options.openai.system_prompt]
 * @param {Array<any>} [options.openai.tools]
 * @param {any} [options.openai.tool_choice]
 * @param {number} [options.openai.temperature]
 * @param {number} [options.openai.top_p]
 * @param {number} [options.openai.max_tokens]
 * @param {boolean} [options.skipPrompt] - 覆盖 skip_prompt（默认随 promptMode 推导）
 * @param {string} [options.requestId] - 透传请求追踪 Header：X-Request-Id（建议由调用方生成并用于 SSE 对账）
 * @param {string} [options.accessToken] - 覆盖 Authorization（用于 JWT 测试页，不污染全局登录态）
 * @returns {Promise<{message_id: string, conversation_id: string}>} 消息ID与会话ID
 */
export const createMessage = ({
  text,
  conversationId,
  metadata = {},
  promptMode = 'server',
  resultMode = 'xml_plaintext',
  openai = {},
  skipPrompt,
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
  if (typeof skipPrompt === 'boolean') payload.skip_prompt = skipPrompt
  else payload.skip_prompt = resolvedPromptMode === 'passthrough'

  // SSE 结果模式（SSOT：后端枚举为 xml_plaintext/raw_passthrough/auto；这里兼容旧值）
  const normalizedResultMode = String(resultMode || '').trim()
  const resolvedResultMode =
    normalizedResultMode === 'raw_passthrough' || normalizedResultMode === 'xml_plaintext' || normalizedResultMode === 'auto'
      ? normalizedResultMode
      : normalizedResultMode === 'raw'
        ? 'raw_passthrough'
        : 'xml_plaintext'
  payload.result_mode = resolvedResultMode

  // OpenAI 兼容字段（仅白名单字段进入 body 顶层；扩展信息仍应放 metadata）
  if (openai && typeof openai === 'object') {
    if (typeof openai.model === 'string' && openai.model.trim()) payload.model = openai.model.trim()
    if (typeof openai.system_prompt === 'string' && openai.system_prompt.trim()) payload.system_prompt = openai.system_prompt.trim()

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

// Agent Run（后端工具：Web 搜索 / 动作库检索）
/**
 * 创建 Agent Run（后端执行工具，App/Web 只消费 SSE 结果）
 * @param {Object} options
 * @param {string} options.model - 映射模型 key（来自 /api/v1/llm/models 的 data[].name）
 * @param {string} options.text - 用户输入
 * @param {string|null} [options.conversationId] - 会话 ID（UUID）
 * @param {Object} [options.metadata] - 扩展元信息（用于对账/调试）
 * @param {('xml_plaintext'|'raw_passthrough'|'auto')} [options.resultMode] - SSE 输出模式
 * @param {('server'|'passthrough')} [options.promptMode='server'] - prompt 策略：后端 SSOT 或透传 OpenAI messages
 * @param {Object} [options.openai] - OpenAI 兼容字段（仅 passthrough 生效）
 * @param {Array<Object>} [options.openai.messages]
 * @param {string} [options.openai.system_prompt]
 * @param {Array<any>} [options.openai.tools]
 * @param {any} [options.openai.tool_choice]
 * @param {number} [options.openai.temperature]
 * @param {number} [options.openai.top_p]
 * @param {number} [options.openai.max_tokens]
 * @param {string} [options.requestId] - X-Request-Id
 * @param {string} [options.accessToken] - 覆盖 Authorization（用于 JWT 测试页）
 * @returns {Promise<{run_id: string, message_id: string, conversation_id: string}>}
 */
export const createAgentRun = ({
  model,
  text,
  conversationId,
  metadata = {},
  resultMode,
  promptMode = 'server',
  openai = {},
  enableExerciseSearch,
  exerciseTopK,
  enableWebSearch,
  webSearchTopK,
  requestId,
  accessToken,
} = {}) => {
  const resolvedModel = String(model || '').trim()
  const resolvedText = String(text || '').trim()
  if (!resolvedModel) return Promise.reject(new Error('model 不能为空（请从 /api/v1/llm/models 选择）'))
  if (!resolvedText) return Promise.reject(new Error('text 不能为空'))

  const payload = {
    model: resolvedModel,
    text: resolvedText,
    conversation_id: conversationId || null,
    metadata: {
      source: 'web_ui',
      timestamp: new Date().toISOString(),
      ...metadata,
    },
  }

  const resolvedPromptMode = String(promptMode || '').trim() === 'passthrough' ? 'passthrough' : 'server'
  if (resolvedPromptMode === 'passthrough') {
    payload.skip_prompt = true
    if (Array.isArray(openai?.messages)) payload.messages = openai.messages
    if (openai?.system_prompt !== undefined) payload.system_prompt = openai.system_prompt
    if (openai?.tools !== undefined) payload.tools = openai.tools
    if (openai?.tool_choice !== undefined) payload.tool_choice = openai.tool_choice
    if (openai?.temperature !== undefined) payload.temperature = openai.temperature
    if (openai?.top_p !== undefined) payload.top_p = openai.top_p
    if (openai?.max_tokens !== undefined) payload.max_tokens = openai.max_tokens
  }

  // SSE 输出模式（与 /messages 保持一致；兼容旧值）
  const normalizedResultMode = String(resultMode || '').trim()
  const resolvedResultMode =
    normalizedResultMode === 'raw_passthrough' || normalizedResultMode === 'xml_plaintext' || normalizedResultMode === 'auto'
      ? normalizedResultMode
      : normalizedResultMode === 'raw'
        ? 'raw_passthrough'
        : normalizedResultMode === 'text'
          ? 'xml_plaintext'
          : ''
  if (resolvedResultMode) payload.result_mode = resolvedResultMode

  if (typeof enableExerciseSearch === 'boolean') payload.enable_exercise_search = enableExerciseSearch
  if (exerciseTopK !== undefined && exerciseTopK !== null) payload.exercise_top_k = Number(exerciseTopK)
  if (typeof enableWebSearch === 'boolean') payload.enable_web_search = enableWebSearch
  if (webSearchTopK !== undefined && webSearchTopK !== null) payload.web_search_top_k = Number(webSearchTopK)

  const headers = {}
  if (typeof requestId === 'string' && requestId.trim()) headers['X-Request-Id'] = requestId.trim()
  if (typeof accessToken === 'string' && accessToken.trim()) headers['Authorization'] = `Bearer ${accessToken.trim()}`

  return request.post('/agent/runs', payload, { timeout: 30000, headers })
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
  request.post('/llm/models/check-all', {}, { timeout: 10000 })
