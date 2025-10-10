import { request } from '@/utils'

export default {
  login: (data) => request.post('/base/access_token', data, { noNeedToken: true }),
  getUserInfo: () => request.get('/base/userinfo'),
  getUserMenu: () => request.get('/base/usermenu'),
  getUserApi: () => request.get('/base/userapi'),
  // profile
  updatePassword: (data = {}) => request.post('/base/update_password', data),
  // users
  getUserList: (params = {}) => request.get('/user/list', { params }),
  getUserById: (params = {}) => request.get('/user/get', { params }),
  createUser: (data = {}) => request.post('/user/create', data),
  updateUser: (data = {}) => request.post('/user/update', data),
  deleteUser: (params = {}) => request.delete(`/user/delete`, { params }),
  resetPassword: (data = {}) => request.post(`/user/reset_password`, data),
  // role
  getRoleList: (params = {}) => request.get('/role/list', { params }),
  createRole: (data = {}) => request.post('/role/create', data),
  updateRole: (data = {}) => request.post('/role/update', data),
  deleteRole: (params = {}) => request.delete('/role/delete', { params }),
  updateRoleAuthorized: (data = {}) => request.post('/role/authorized', data),
  getRoleAuthorized: (params = {}) => request.get('/role/authorized', { params }),
  // menus
  getMenus: (params = {}) => request.get('/menu/list', { params }),
  createMenu: (data = {}) => request.post('/menu/create', data),
  updateMenu: (data = {}) => request.post('/menu/update', data),
  deleteMenu: (params = {}) => request.delete('/menu/delete', { params }),
  // apis
  getApis: (params = {}) => request.get('/api/list', { params }),
  createApi: (data = {}) => request.post('/api/create', data),
  updateApi: (data = {}) => request.post('/api/update', data),
  deleteApi: (params = {}) => request.delete('/api/delete', { params }),
  refreshApi: (data = {}) => request.post('/api/refresh', data),
  // llm models
  getAIModels: (params = {}) => request.get('/llm/models', { params }),
  createAIModel: (data = {}) => request.post('/llm/models', data),
  updateAIModel: (data = {}) => request.put('/llm/models', data),
  deleteAIModel: (endpointId) => request.delete(`/llm/models/${endpointId}`),
  checkAIModel: (endpointId) => request.post(`/llm/models/${endpointId}/check`),
  checkAllAIModels: () => request.post('/llm/models/check-all'),
  syncAIModel: (endpointId, direction = 'push') =>
    request.post(`/llm/models/${endpointId}/sync`, { direction }),
  syncAllAIModels: (direction = 'push') => request.post('/llm/models/sync', { direction }),
  getSupabaseStatus: () => request.get('/llm/status/supabase'),
  getMonitorStatus: () => request.get('/llm/monitor/status'),
  startMonitor: (intervalSeconds) =>
    request.post('/llm/monitor/start', { interval_seconds: intervalSeconds }),
  stopMonitor: () => request.post('/llm/monitor/stop'),
  // llm prompts
  getAIPrompts: (params = {}) => request.get('/llm/prompts', { params }),
  getAIPromptDetail: (promptId) => request.get(`/llm/prompts/${promptId}`),
  createAIPrompt: (data = {}) => request.post('/llm/prompts', data),
  updateAIPrompt: (promptId, data = {}) => request.put(`/llm/prompts/${promptId}`, data),
  deleteAIPrompt: (promptId) => request.delete(`/llm/prompts/${promptId}`),
  activateAIPrompt: (promptId) => request.post(`/llm/prompts/${promptId}/activate`),
  syncPrompts: (direction = 'push') => request.post('/llm/prompts/sync', { direction }),
  getPromptTests: (promptId, params = {}) =>
    request.get(`/llm/prompts/${promptId}/tests`, { params }),
  // llm test
  testPrompt: (data = {}) => request.post('/llm/prompts/test', data),
  simulateJwtDialog: (data = {}) => request.post('/llm/tests/dialog', data),
  runJwtLoadTest: (data = {}) => request.post('/llm/tests/load', data),
  getJwtRun: (runId) => request.get(`/llm/tests/runs/${runId}`),
  // depts
  getDepts: (params = {}) => request.get('/dept/list', { params }),
  createDept: (data = {}) => request.post('/dept/create', data),
  updateDept: (data = {}) => request.post('/dept/update', data),
  deleteDept: (params = {}) => request.delete('/dept/delete', { params }),
  // auditlog
  getAuditLogList: (params = {}) => request.get('/auditlog/list', { params }),
}
