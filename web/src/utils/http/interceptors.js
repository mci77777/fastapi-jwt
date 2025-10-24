import { getToken, setToken } from '@/utils'
import { resolveResError } from './helpers'

// Token 刷新状态管理
let isRefreshing = false
let refreshPromise = null

/**
 * 检查 Token 是否即将过期
 * @param {string} token - JWT token
 * @returns {boolean} - 是否需要刷新
 */
function shouldRefreshToken(token) {
  if (!token) return false

  try {
    // 解码 JWT payload（不验证签名，只读取过期时间）
    const parts = token.split('.')
    if (parts.length !== 3) return false

    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')))
    const exp = payload.exp

    if (!exp) return false

    // 当前时间（秒）
    const now = Math.floor(Date.now() / 1000)
    // 剩余时间（秒）
    const remaining = exp - now

    // 如果剩余时间少于 5 分钟（300 秒），则需要刷新
    return remaining > 0 && remaining < 300
  } catch (error) {
    console.error('解析 Token 失败:', error)
    return false
  }
}

/**
 * 刷新 Token
 * @returns {Promise<string>} - 新的 Token
 */
async function refreshToken() {
  // 如果正在刷新，返回现有的 Promise
  if (isRefreshing && refreshPromise) {
    return refreshPromise
  }

  isRefreshing = true

  refreshPromise = (async () => {
    try {
      const token = getToken()
      if (!token) {
        throw new Error('No token to refresh')
      }

      // 调用后端刷新端点
      const response = await fetch('/api/v1/base/refresh_token', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
      })

      if (!response.ok) {
        throw new Error(`Token refresh failed: ${response.status}`)
      }

      const data = await response.json()

      if (data.code !== 200 || !data.data?.access_token) {
        throw new Error('Invalid refresh response')
      }

      const newToken = data.data.access_token

      // 保存新 Token
      setToken(newToken)

      console.log('✅ Token 刷新成功')

      return newToken
    } catch (error) {
      console.error('❌ Token 刷新失败:', error)
      // 刷新失败，清除 Token 并重定向到登录页
      localStorage.removeItem('ACCESS_TOKEN')
      localStorage.removeItem('token')
      localStorage.removeItem('userInfo')
      window.location.href = '/login'
      throw error
    } finally {
      isRefreshing = false
      refreshPromise = null
    }
  })()

  return refreshPromise
}

export async function reqResolve(config) {
  // 处理不需要token的请求
  if (config.noNeedToken) {
    return config
  }

  const token = getToken()

  if (token) {
    // 检查 Token 是否即将过期
    if (shouldRefreshToken(token)) {
      try {
        console.log('⏰ Token 即将过期，自动刷新...')
        const newToken = await refreshToken()
        // 使用新 Token
        config.headers.Authorization = `Bearer ${newToken}`
      } catch (error) {
        // 刷新失败，使用旧 Token（可能会导致 401）
        config.headers.Authorization = `Bearer ${token}`
      }
    } else {
      // 使用 Bearer token 格式，符合后端的认证要求
      config.headers.Authorization = `Bearer ${token}`
    }

    console.log(`📤 请求 ${config.url} 已注入 Authorization header`)
  } else {
    console.warn(`⚠️ 请求 ${config.url} 没有有效的 token`)
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
