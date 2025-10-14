import { getToken } from '@/utils'
import { resolveResError } from './helpers'

export function reqResolve(config) {
  // 处理不需要token的请求
  if (config.noNeedToken) {
    return config
  }

  const token = getToken()
  if (token) {
    // 使用 Bearer token 格式,符合后端的认证要求
    config.headers.Authorization = config.headers.Authorization || `Bearer ${token}`
  }

  if (
    config.baseURL &&
    typeof config.url === 'string' &&
    config.url.startsWith('/') &&
    !/^https?:\/\//.test(config.url)
  ) {
    config.url = config.url.replace(/^\/+/, '')
  }

  return config
}

export function reqReject(error) {
  return Promise.reject(error)
}

export function resResolve(response) {
  const { data, status, statusText } = response

  if (data === null || data === undefined) {
    return Promise.resolve(data)
  }

  if (typeof data !== 'object') {
    return Promise.resolve(data)
  }

  // 如果响应数据没有 code 字段，且 HTTP 状态码是 2xx，则认为是成功的
  if (data && typeof data === 'object' && !('code' in data) && status >= 200 && status < 300) {
    return Promise.resolve(data)
  }

  // 如果有 code 字段，检查是否为 200
  if (data?.code !== 200) {
    const code = data?.code ?? status
    /** 根据code处理对应的操作，并返回处理后的message */
    const message = resolveResError(code, data?.msg ?? statusText)
    window.$message?.error(message, { keepAliveOnHover: true })
    return Promise.reject({ code, message, error: data || response })
  }
  return Promise.resolve(data)
}

export async function resReject(error) {
  if (!error || !error.response) {
    const code = error?.code
    /** 根据code处理对应的操作，并返回处理后的message */
    const message = resolveResError(code, error.message)
    window.$message?.error(message)
    return Promise.reject({ code, message, error })
  }
  const { data, status } = error.response

  // 修复：检查 HTTP 状态码 401（Token 过期）
  if (status === 401 || data?.code === 401) {
    try {
      // 清除本地存储
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')

      // 显示友好提示
      window.$message?.error('登录已过期，请重新登录')

      // 重定向到登录页
      window.location.href = '/login'

      // 阻止后续错误处理
      return Promise.reject({ code: 401, message: 'Token expired', error: data })
    } catch (err) {
      console.error('Token 过期处理失败:', err)
      // 即使出错也要重定向到登录页
      window.location.href = '/login'
      return Promise.reject({ code: 401, message: 'Token expired', error: data })
    }
  }
  // 后端返回的response数据
  const code = data?.code ?? status
  const message = resolveResError(code, data?.msg ?? error.message)
  window.$message?.error(message, { keepAliveOnHover: true })
  return Promise.reject({ code, message, error: error.response?.data || error.response })
}
