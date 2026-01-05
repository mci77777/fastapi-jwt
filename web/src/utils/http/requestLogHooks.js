import { requestLogBegin, requestLogFinish, requestLogAppendEvent } from './requestLog'

const HOOK_STATE_KEY = '__gymbro_request_log_hooks__'

function readHeader(headers, name) {
  if (!headers) return undefined
  if (typeof headers.get === 'function') return headers.get(name)
  return headers[name] ?? headers[String(name).toLowerCase()]
}

function normalizeFetchHeaders(headers) {
  if (!headers) return undefined
  if (typeof Headers !== 'undefined' && headers instanceof Headers) return headers
  try {
    return new Headers(headers)
  } catch {
    return undefined
  }
}

function guessRequestIdFromFetch(input, init) {
  const fromInit = readHeader(init?.headers, 'X-Request-Id') || readHeader(init?.headers, 'x-request-id')
  if (fromInit) return String(fromInit)
  if (typeof Request !== 'undefined' && input instanceof Request) {
    const v = input.headers.get('X-Request-Id') || input.headers.get('x-request-id')
    if (v) return String(v)
  }
  return null
}

function getFetchMethod(input, init) {
  if (init?.method) return String(init.method).toUpperCase()
  if (typeof Request !== 'undefined' && input instanceof Request) return String(input.method || 'GET').toUpperCase()
  return 'GET'
}

function getFetchUrl(input) {
  if (typeof Request !== 'undefined' && input instanceof Request) return String(input.url || '')
  return String(input || '')
}

function isEventStream(response, init) {
  const accept = readHeader(init?.headers, 'Accept') || readHeader(init?.headers, 'accept') || ''
  if (String(accept).includes('text/event-stream')) return true
  try {
    const ct = response?.headers?.get?.('content-type') || ''
    return String(ct).includes('text/event-stream')
  } catch {
    return false
  }
}

function patchFetch() {
  const originalFetch = globalThis.fetch
  if (typeof originalFetch !== 'function') return
  if (originalFetch[HOOK_STATE_KEY]) return

  const wrapped = async function patchedFetch(input, init) {
    const startAt = Date.now()
    const method = getFetchMethod(input, init)
    const url = getFetchUrl(input)
    const requestId = guessRequestIdFromFetch(input, init)
    const headers =
      normalizeFetchHeaders(init?.headers) ||
      (typeof Request !== 'undefined' && input instanceof Request ? input.headers : init?.headers)

    const logId = requestLogBegin({
      kind: 'fetch',
      method,
      url,
      requestId,
      request: { headers, params: null, body: init?.body },
    })

    try {
      const response = await originalFetch(input, init)
      const durationMs = Date.now() - startAt

      if (logId) {
        if (isEventStream(response, init)) {
          requestLogFinish(logId, {
            status: response.ok ? 'success' : 'error',
            durationMs,
            response: {
              status: response.status,
              statusText: response.statusText,
              headers: response.headers,
              body: '[stream:text/event-stream]',
            },
            error: null,
          })
        } else {
          const clone = response.clone()
          void (async () => {
            let bodyText = ''
            try {
              bodyText = await clone.text()
            } catch {
              bodyText = '[unreadable-body]'
            }
            requestLogFinish(logId, {
              status: response.ok ? 'success' : 'error',
              durationMs,
              response: {
                status: response.status,
                statusText: response.statusText,
                headers: response.headers,
                body: bodyText,
              },
              error: null,
            })
          })()
        }
      }

      return response
    } catch (err) {
      const durationMs = Date.now() - startAt
      if (logId) {
        requestLogFinish(logId, {
          status: 'error',
          durationMs,
          response: null,
          error: { message: err?.message || 'Fetch failed' },
        })
      }
      throw err
    }
  }

  wrapped[HOOK_STATE_KEY] = true
  wrapped.__gymbro_original_fetch = originalFetch
  globalThis.fetch = wrapped
}

function patchEventSource() {
  const Original = globalThis.EventSource
  if (typeof Original !== 'function') return
  if (Original[HOOK_STATE_KEY]) return

  function PatchedEventSource(url, config) {
    const es = new Original(url, config)

    const requestId =
      String(readHeader(config?.headers, 'X-Request-Id') || readHeader(config?.headers, 'x-request-id') || '') || null

    requestLogAppendEvent({
      kind: 'eventsource',
      url: String(url || ''),
      requestId,
      event: { type: 'open', detail: 'EventSource created' },
    })

    es.addEventListener('open', () => {
      requestLogAppendEvent({
        kind: 'eventsource',
        url: String(url || ''),
        requestId,
        event: { type: 'open' },
      })
    })

    es.addEventListener('error', (e) => {
      requestLogAppendEvent({
        kind: 'eventsource',
        url: String(url || ''),
        requestId,
        event: { type: 'error', error: e?.message || '[eventsource error]' },
      })
    })

    es.addEventListener('message', (e) => {
      requestLogAppendEvent({
        kind: 'eventsource',
        url: String(url || ''),
        requestId,
        event: { type: 'message', data: e?.data ?? null, lastEventId: e?.lastEventId ?? null },
      })
    })

    const originalClose = es.close?.bind(es)
    if (typeof originalClose === 'function') {
      es.close = () => {
        requestLogAppendEvent({
          kind: 'eventsource',
          url: String(url || ''),
          requestId,
          event: { type: 'close' },
        })
        return originalClose()
      }
    }

    return es
  }

  PatchedEventSource.prototype = Original.prototype
  try {
    Object.setPrototypeOf(PatchedEventSource, Original)
  } catch {
    // ignore
  }

  PatchedEventSource[HOOK_STATE_KEY] = true
  PatchedEventSource.__gymbro_original_eventsource = Original
  globalThis.EventSource = PatchedEventSource
}

export function setupRequestLogHooks() {
  patchFetch()
  patchEventSource()
}
