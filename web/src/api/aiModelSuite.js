import { request } from '@/utils'

export const fetchModels = (params = {}) => request.get('/llm/models', { params })
export const updateModel = (data = {}) => request.put('/llm/models', data)
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

export const fetchPrompts = (params = {}) => request.get('/llm/prompts', { params })
export const fetchPromptTests = (promptId, params = {}) =>
  request.get(`/llm/prompts/${promptId}/tests`, { params })

export const simulateDialog = (data = {}) => request.post('/llm/tests/dialog', data)
export const runLoadTest = (data = {}) => request.post('/llm/tests/load', data)
export const fetchLoadRun = (runId) => request.get(`/llm/tests/runs/${runId}`)
