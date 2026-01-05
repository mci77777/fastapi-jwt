import { defineStore } from 'pinia'
import { lStorage } from '@/utils'

const STORAGE_KEYS = {
  enabled: 'request_log_enabled',
  retentionSize: 'request_log_retention_size',
}

function readBool(key, fallback) {
  const v = lStorage.get(key)
  if (v === true || v === false) return v
  if (typeof v === 'string') {
    if (v === 'true') return true
    if (v === 'false') return false
  }
  return fallback
}

function readNumber(key, fallback) {
  const v = lStorage.get(key)
  const n = typeof v === 'number' ? v : Number(v)
  if (Number.isFinite(n)) return n
  return fallback
}

export const useRequestLogStore = defineStore('requestLog', {
  state() {
    return {
      enabled: readBool(STORAGE_KEYS.enabled, false),
      retentionSize: readNumber(STORAGE_KEYS.retentionSize, 200),
      items: [],
    }
  },
  actions: {
    setEnabled(enabled) {
      this.enabled = Boolean(enabled)
      lStorage.set(STORAGE_KEYS.enabled, this.enabled)
    },
    setRetentionSize(size) {
      const next = Math.max(10, Math.min(1000, Number(size) || 200))
      this.retentionSize = next
      lStorage.set(STORAGE_KEYS.retentionSize, next)
      this.trim()
    },
    trim() {
      const limit = Math.max(10, Math.min(1000, Number(this.retentionSize) || 200))
      if (this.items.length > limit) {
        this.items = this.items.slice(0, limit)
      }
    },
    clear() {
      this.items = []
    },
    append(item) {
      if (!item) return
      this.items.unshift(item)
      this.trim()
    },
    appendPending(item) {
      if (!item) return null
      const id = item.id || `${Date.now()}-${Math.random().toString(16).slice(2)}`
      this.items.unshift({ ...item, id })
      this.trim()
      return id
    },
    update(id, patch) {
      if (!id) return
      const idx = this.items.findIndex((it) => it?.id === id)
      if (idx === -1) return
      this.items[idx] = { ...this.items[idx], ...(patch || {}) }
    },
  },
})

