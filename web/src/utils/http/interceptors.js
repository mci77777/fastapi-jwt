import { getRefreshToken, getToken, removeToken, setRefreshToken, setToken } from '@/utils'
import { resolveResError } from './helpers'
import { supabaseRefreshSession } from '@/utils/supabase/auth'
import { requestLogBegin, requestLogFinish, requestLogGet, requestLogPersistIsEnabled } from './requestLog'

// Token 刷新状态管理
let isRefreshing = false
let refreshPromise = null

function readHeader(headers, name) {
  if (!headers) return undefined
  if (typeof headers.get === 'function') return headers.get(name)
  return headers[name] ?? headers[String(name).toLowerCase()]
}

function writeHeader(headers, name, value) {
  if (!headers) return
  if (typeof headers.set === 'function') {
    headers.set(name, value)
    return
  }
  headers[name] = value
}

function getOrCreateRequestId(headers) {
  const existing = readHeader(headers, 'X-Request-Id') || readHeader(headers, 'x-request-id')
  if (existing) return String(existing)

  return (
    globalThis.crypto?.randomUUID?.() ||
    `web-${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`
  )
}

function resolveAxiosUrl(config) {
  const baseURL = String(config?.baseURL || '')
  const rawUrl = String(config?.url || '')
  if (!rawUrl) return baseURL || ''
  if (/^https?:\/\//i.test(rawUrl)) return rawUrl
  if (!baseURL) return rawUrl
  return `${baseURL.replace(/\/+$/, '')}/${rawUrl.replace(/^\/+/, '')}`
}

function resolveBaseApiUrl(path) {
  const rawBaseApi = import.meta.env.VITE_BASE_API || '/api/v1'
  const baseApi = String(rawBaseApi || '').trim().replace(/\/+$/, '')
  const cleanPath = String(path || '').trim().replace(/^\/+/, '')
  if (!baseApi) return `/${cleanPath}`
  if (/^https?:\/\//i.test(baseApi)) return `${baseApi}/${cleanPath}`
  return `${baseApi}/${cleanPath}`
}

async function persistRequestLogToSqlite(entry) {
  try {
    if (!entry) return
    if (!requestLogPersistIsEnabled()) return

    const token = getToken()
    if (!token) return

    const url = resolveBaseApiUrl('logs/request')
    const payload = {
      request_id: entry.request_id || null,
      kind: entry.kind || null,
      method: entry.method || null,
      url: entry.url || null,
      status: entry.status || null,
      duration_ms: entry.duration_ms ?? null,
      request_raw: entry.request_raw || null,
      response_raw: entry.response_raw || null,
      error: entry.error || null,
      created_at: entry.created_at || null,
    }

    await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
        ...(entry.request_id ? { 'X-Request-Id': String(entry.request_id) } : {}),
      },
      body: JSON.stringify(payload),
    })
  } catch {
    // 不阻塞主流程
  }
}

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
      const refresh = getRefreshToken()
      if (!refresh) throw new Error('No refresh_token found')

      const session = await supabaseRefreshSession(refresh)
      const newToken = session.access_token

      // 保存新 Token
      setToken(newToken)
      if (session.refresh_token) setRefreshToken(session.refresh_token)

      console.log('✅ Token 刷新成功')

      return newToken
    } catch (error) {
      console.error('❌ Token 刷新失败:', error)
      // 刷新失败，清除 Token 并重定向到登录页
      removeToken()
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
  const startAt = Date.now()
  const skipRequestLog = Boolean(config?.skipRequestLog)
  // 处理不需要token的请求
  if (config.noNeedToken) {
    // SSOT：统一透传请求追踪 Header（X-Request-Id）。
    config.headers = config.headers || {}
    const requestId = getOrCreateRequestId(config.headers)
    writeHeader(config.headers, 'X-Request-Id', requestId)

    if (!skipRequestLog) {
      const logId = requestLogBegin({
        kind: 'axios',
        method: config.method,
        url: resolveAxiosUrl(config),
        requestId,
        request: { headers: config.headers, params: config.params, body: config.data },
      })
      config.__gymbro_request_log = { id: logId, startAt, requestId }
    }
    return config
  }

  const token = getToken()
  const refresh = getRefreshToken()

  config.headers = config.headers || {}
  const requestId = getOrCreateRequestId(config.headers)
  writeHeader(config.headers, 'X-Request-Id', requestId)

  if (!skipRequestLog) {
    const logId = requestLogBegin({
      kind: 'axios',
      method: config.method,
      url: resolveAxiosUrl(config),
      requestId,
      request: { headers: config.headers, params: config.params, body: config.data },
    })
    config.__gymbro_request_log = { id: logId, startAt, requestId }
  }

  // 允许调用方显式覆盖 Authorization（用于 JWT 测试等场景，避免污染全局登录态）
  const explicitAuth = readHeader(config.headers, 'Authorization') || readHeader(config.headers, 'authorization')
  if (explicitAuth) {
    console.log(
      `request_id=${readHeader(config.headers, 'X-Request-Id')} action=http_request_auth_override url=${config.url}`
    )
    return config
  }

  if (token) {
    // 检查 Token 是否即将过期
    // SSOT：仅在存在 refresh_token 时才尝试 Supabase refresh，避免本地账号/测试 token 被误刷新导致掉线。
    if (refresh && shouldRefreshToken(token)) {
      try {
        console.log('⏰ Token 即将过期，自动刷新...')
        const newToken = await refreshToken()
        // 使用新 Token
        writeHeader(config.headers, 'Authorization', `Bearer ${newToken}`)
      } catch (error) {
        // 刷新失败，使用旧 Token（可能会导致 401）
        writeHeader(config.headers, 'Authorization', `Bearer ${token}`)
      }
    } else {
      // 使用 Bearer token 格式，符合后端的认证要求
      writeHeader(config.headers, 'Authorization', `Bearer ${token}`)
    }

    console.log(
      `request_id=${readHeader(config.headers, 'X-Request-Id')} action=http_request_auth url=${config.url}`
    )
  } else {
    console.warn(
      `request_id=${readHeader(config.headers, 'X-Request-Id')} action=http_request_no_token url=${config.url}`
    )
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
  const requestId = response?.headers?.['x-request-id'] || data?.request_id

  const meta = response?.config?.__gymbro_request_log
  if (meta?.id) {
    const durationMs = Number.isFinite(meta?.startAt) ? Date.now() - meta.startAt : null
    const httpOk = status >= 200 && status < 300
    let logStatus = httpOk ? 'success' : 'error'
    if (data && typeof data === 'object' && 'code' in data) {
      logStatus = data?.code === 200 || (data?.code === 202 && status === 202) ? 'success' : 'app_error'
    }
    requestLogFinish(meta.id, {
      status: logStatus,
      durationMs,
      response: { status, statusText, headers: response?.headers, body: data },
      error: null,
    })
    const entry = requestLogGet(meta.id)
    if (entry) void persistRequestLogToSqlite(entry)
  }

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
  // 兼容：部分异步接口返回 202（HTTP 202 + code=202），前端应视为成功（例如批量检测触发）。
  if (data?.code === 202 && status === 202) {
    return Promise.resolve(data)
  }

  if (data?.code !== 200) {
    const code = data?.code ?? status
    /** 根据code处理对应的操作，并返回处理后的message */
    const message = resolveResError(code, data?.msg ?? statusText)
    const suffix = requestId ? `（request_id=${requestId}）` : ''
    window.$message?.error(message + suffix, { keepAliveOnHover: true })
    return Promise.reject({ code, message, request_id: requestId, error: data || response })
  }
  return Promise.resolve(data)
}

export async function resReject(error) {
  if (!error || !error.response) {
    const meta = error?.config?.__gymbro_request_log
    if (meta?.id) {
      const durationMs = Number.isFinite(meta?.startAt) ? Date.now() - meta.startAt : null
      requestLogFinish(meta.id, {
        status: 'error',
        durationMs,
        response: null,
        error: { message: error?.message || 'Request failed', code: error?.code || null },
      })
      const entry = requestLogGet(meta.id)
      if (entry) void persistRequestLogToSqlite(entry)
    }
    const code = error?.code
    /** 根据code处理对应的操作，并返回处理后的message */
    const message = resolveResError(code, error.message)
    window.$message?.error(message)
    return Promise.reject({ code, message, request_id: undefined, error })
  }
  const { data, status } = error.response
  const requestId = error?.response?.headers?.['x-request-id'] || data?.request_id

  const meta = error?.config?.__gymbro_request_log
  if (meta?.id) {
    const durationMs = Number.isFinite(meta?.startAt) ? Date.now() - meta.startAt : null
    requestLogFinish(meta.id, {
      status: 'error',
      durationMs,
      response: {
        status,
        statusText: error?.response?.statusText,
        headers: error?.response?.headers,
        body: data,
      },
      error: { message: error?.message || 'Request failed', code: status },
    })
    const entry = requestLogGet(meta.id)
    if (entry) void persistRequestLogToSqlite(entry)
  }

  // 修复：检查 HTTP 状态码 401（Token 过期）
  if (status === 401 || data?.code === 401) {
    try {
      // 清除本地存储
      removeToken()

      // 显示友好提示
      window.$message?.error(requestId ? `登录已过期，请重新登录（request_id=${requestId}）` : '登录已过期，请重新登录')

      // 重定向到登录页
      window.location.href = '/login'

      // 阻止后续错误处理
      return Promise.reject({ code: 401, message: 'Token expired', request_id: requestId, error: data })
    } catch (err) {
      console.error('Token 过期处理失败:', err)
      // 即使出错也要重定向到登录页
      window.location.href = '/login'
      return Promise.reject({ code: 401, message: 'Token expired', request_id: requestId, error: data })
    }
  }
  // 后端返回的response数据
  const code = data?.code ?? status
  const message = resolveResError(code, data?.msg ?? error.message)
  const suffix = requestId ? `（request_id=${requestId}）` : ''
  window.$message?.error(message + suffix, { keepAliveOnHover: true })
  return Promise.reject({ code, message, request_id: requestId, error: error.response?.data || error.response })
}
