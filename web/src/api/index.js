import { request } from '@/utils'
import { supabaseSignInWithPassword } from '@/utils/supabase/auth'

function resolveAuthMode() {
  return String(import.meta.env.VITE_AUTH_MODE || 'auto')
    .trim()
    .toLowerCase()
}

function isEmail(value) {
  const v = String(value || '').trim()
  return v.includes('@')
}

export default {
  login: async (data = {}) => {
    const identity = data.email ?? data.username
    const password = data.password

    const mode = resolveAuthMode()
    const normalizedIdentity = String(identity || '').trim()

    // SSOT：是否走 Supabase 只由「输入是否为邮箱」决定，避免误配 VITE_AUTH_MODE=supabase 导致用户名也被发到 Supabase。
    // - local：强制走本地 /base/access_token
    // - supabase：仅当输入为邮箱时走 Supabase
    // - auto：邮箱走 Supabase；否则走本地
    const isEmailIdentity = isEmail(normalizedIdentity)
    const useSupabase = mode !== 'local' && isEmailIdentity

    // 1) Supabase 登录（真实用户 email/password）
    if (useSupabase) {
      const session = await supabaseSignInWithPassword({ email: normalizedIdentity, password })
      return {
        code: 200,
        msg: 'ok',
        data: {
          access_token: session.access_token,
          refresh_token: session.refresh_token,
          expires_in: session.expires_in,
          token_type: session.token_type,
        },
      }
    }

    if (mode === 'supabase' && !isEmailIdentity) {
      // 兜底提示：Supabase 模式但输入不是邮箱时，仍然按本地登录处理（便于 dashboard 本地账号可用）。
      // 这里不抛错，避免把用户锁死在无法登录的状态。
    }

    // 2) 本地登录（兼容：admin/123456）
    return request.post(
      '/base/access_token',
      { username: normalizedIdentity, password: String(password || '').trim() },
      { noNeedToken: true }
    )
  },
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
  // depts
  getDepts: (params = {}) => request.get('/dept/list', { params }),
  createDept: (data = {}) => request.post('/dept/create', data),
  updateDept: (data = {}) => request.post('/dept/update', data),
  deleteDept: (params = {}) => request.delete('/dept/delete', { params }),
  // auditlog
  getAuditLogList: (params = {}) => request.get('/auditlog/list', { params }),
  // system monitoring
  getHealthStatus: () => request.get('/healthz'),
  getSystemMetrics: () => request.get('/metrics', { responseType: 'text' }),
}
