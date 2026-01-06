import { useRequestLogStore } from '@/store'

const MAX_RAW_LENGTH = 50_000

const SENSITIVE_KEYS = [
  'authorization',
  'cookie',
  'set-cookie',
  'apikey',
  'api_key',
  'x-api-key',
  'access_token',
  'refresh_token',
  'token',
  'password',
  'secret',
  'client_secret',
]

function isSensitiveKey(key) {
  if (!key) return false
  const normalized = String(key).toLowerCase()
  return SENSITIVE_KEYS.includes(normalized)
}

function safeJsonStringify(value) {
  const seen = new WeakSet()
  return JSON.stringify(
    value,
    (key, val) => {
      if (isSensitiveKey(key)) return '[REDACTED]'
      if (typeof val === 'string') return val
      if (!val || typeof val !== 'object') return val
      if (seen.has(val)) return '[Circular]'
      seen.add(val)
      return val
    },
    2
  )
}

function clampText(text, maxLen = MAX_RAW_LENGTH) {
  const raw = String(text ?? '')
  if (!raw) return ''
  if (raw.length <= maxLen) return raw
  return `${raw.slice(0, maxLen)}\n...[TRUNCATED length=${raw.length}]`
}

function safeToRawText(value) {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') {
    const text = String(value)
    const trimmed = text.trim()
    if (trimmed && (trimmed.startsWith('{') || trimmed.startsWith('['))) {
      try {
        return clampText(safeJsonStringify(JSON.parse(trimmed)))
      } catch {
        // ignore
      }
    }
    return clampText(text)
  }
  try {
    return clampText(safeJsonStringify(value))
  } catch {
    try {
      return clampText(String(value))
    } catch {
      return '[Unserializable]'
    }
  }
}

function normalizeHeaders(input) {
  if (!input) return {}
  if (typeof input?.toJSON === 'function') {
    try {
      return input.toJSON()
    } catch {
      // ignore
    }
  }
  if (typeof Headers !== 'undefined' && input instanceof Headers) {
    const obj = {}
    input.forEach((v, k) => {
      obj[k] = v
    })
    return obj
  }
  if (typeof input === 'object') {
    return { ...input }
  }
  return {}
}

function redactHeaders(headers) {
  const obj = normalizeHeaders(headers)
  const out = {}
  Object.entries(obj).forEach(([k, v]) => {
    out[k] = isSensitiveKey(k) ? '[REDACTED]' : v
  })
  return out
}

export function getRequestLogStoreSafe() {
  try {
    return useRequestLogStore()
  } catch {
    return null
  }
}

export function requestLogIsEnabled() {
  const store = getRequestLogStoreSafe()
  return Boolean(store?.enabled)
}

export function requestLogPersistIsEnabled() {
  const store = getRequestLogStoreSafe()
  return Boolean(store?.persistEnabled)
}

export function requestLogGet(id) {
  if (!id) return null
  const store = getRequestLogStoreSafe()
  if (!store) return null
  const list = Array.isArray(store.items) ? store.items : []
  return list.find((it) => it?.id === id) || null
}

export function requestLogBegin({ kind, method, url, requestId, request }) {
  const store = getRequestLogStoreSafe()
  if (!store || !store.enabled) return null

  const entry = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    kind: String(kind || 'unknown'),
    status: 'pending',
    method: String(method || '').toUpperCase(),
    url: String(url || ''),
    request_id: requestId ? String(requestId) : null,
    created_at: new Date().toISOString(),
    duration_ms: null,
    request_raw: safeToRawText({
      method: String(method || '').toUpperCase(),
      url: String(url || ''),
      headers: redactHeaders(request?.headers),
      params: request?.params,
      body: request?.body,
    }),
    response_raw: '',
    error: null,
  }

  store.appendPending(entry)
  return entry.id
}

export function requestLogFinish(id, { status, durationMs, response, error }) {
  if (!id) return
  const store = getRequestLogStoreSafe()
  if (!store) return

  const patch = {
    status: status || 'success',
    duration_ms: Number.isFinite(durationMs) ? Math.max(0, Math.round(durationMs)) : null,
    response_raw: safeToRawText(
      response
        ? {
            status: response.status,
            statusText: response.statusText,
            headers: redactHeaders(response.headers),
            body: response.body,
          }
        : null
    ),
    error: error ? safeToRawText(error) : null,
  }

  store.update(id, patch)
}

export function requestLogAppendEvent({ kind, url, requestId, event }) {
  const store = getRequestLogStoreSafe()
  if (!store || !store.enabled) return null

  store.append({
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    kind: String(kind || 'event'),
    status: 'event',
    method: 'EVENT',
    url: String(url || ''),
    request_id: requestId ? String(requestId) : null,
    created_at: new Date().toISOString(),
    duration_ms: null,
    request_raw: '',
    response_raw: safeToRawText(event),
    error: null,
  })
  return true
}
