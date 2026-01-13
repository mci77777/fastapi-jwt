import { defineStore } from 'pinia'

import {
  fetchModels,
  fetchMappings,
  fetchPrompts,
  fetchBlockedModels,
  saveMapping,
  activateMapping,
  deleteMapping,
  updateModel,
  syncModel,
  syncAllModels,
} from '@/api/aiModelSuite'
import api from '@/api'

function _safeJsonParse(value, fallback) {
  if (typeof value !== 'string' || !value.trim()) return fallback
  try {
    const parsed = JSON.parse(value)
    return parsed ?? fallback
  } catch {
    return fallback
  }
}

function _normalizeJwtToken(value) {
  // JWT 本身不包含空白；允许用户粘贴时带换行/空格，统一清理。
  return String(value || '')
    .trim()
    .replace(/\s+/g, '')
}

function _normalizeJwtMeta(meta) {
  const email = meta?.email ? String(meta.email).trim() : ''
  const username = meta?.username ? String(meta.username).trim() : ''
  return { email, username }
}

export const useAiModelSuiteStore = defineStore('aiModelSuite', {
  state: () => ({
    models: [],
    modelsLoading: false,
    mappings: [],
    mappingsLoading: false,
    prompts: [],
    promptsLoading: false,
    blockedModels: [],
    blockedModelsLoading: false,
    syncingEndpoints: new Set(),
    syncAllLoading: false,
    mailApiKey: localStorage.getItem('ai_suite_mail_api_key') || '',
    // JWT 调试页：仅用于前端调试（不影响全局登录态）
    jwtToken: localStorage.getItem('ai_suite_jwt_token') || '',
    jwtTokenMode: localStorage.getItem('ai_suite_jwt_token_mode') || '',
    jwtTokenMeta: _normalizeJwtMeta(
      _safeJsonParse(localStorage.getItem('ai_suite_jwt_token_meta'), { email: '', username: '' })
    ),
  }),
  getters: {
    endpointOptions(state) {
      return (state.models || []).map((item) => ({
        label: item.name || item.model || item.base_url,
        value: item.id,
        raw: item,
      }))
    },
    modelCandidates(state) {
      const models = new Set()
      const blocked = new Set(state.blockedModels || [])
      ;(state.models || []).forEach((endpoint) => {
        if (Array.isArray(endpoint.model_list)) {
          endpoint.model_list.forEach((model) => {
            if (model && !blocked.has(model)) models.add(model)
          })
        } else if (endpoint.model) {
          if (!blocked.has(endpoint.model)) models.add(endpoint.model)
        }
      })
      return Array.from(models).sort()
    },
  },
  actions: {
    async loadModels(params = {}) {
      this.modelsLoading = true
      try {
        const { data } = await fetchModels(params)
        this.models = data || []
      } finally {
        this.modelsLoading = false
      }
    },
    async loadBlockedModels() {
      this.blockedModelsLoading = true
      try {
        const { data } = await fetchBlockedModels()
        this.blockedModels = data?.blocked || []
      } finally {
        this.blockedModelsLoading = false
      }
    },
    async setDefaultModel(model) {
      if (!model) return
      await updateModel({
        id: model.id,
        is_default: true,
        auto_sync: false,
      })
      await this.loadModels()
    },
    async syncModel(endpointId, options = {}) {
      if (!endpointId) return
      this.syncingEndpoints.add(endpointId)
      try {
        const result = await syncModel(endpointId, options)
        // 使用返回的数据更新对应的模型
        if (result?.data) {
          const index = this.models.findIndex((m) => m.id === endpointId)
          if (index !== -1) {
            this.models[index] = result.data
          }
        }
        // 仍然重新加载以确保完整性
        await this.loadModels()
      } finally {
        this.syncingEndpoints.delete(endpointId)
      }
    },
    async syncAll(directionOptions = {}) {
      this.syncAllLoading = true
      try {
        const result = await syncAllModels(directionOptions)
        // 使用返回的数据更新模型列表
        if (result?.data && Array.isArray(result.data)) {
          this.models = result.data
        }
        // 重新加载以确保数据完整
        await this.loadModels()
      } finally {
        this.syncAllLoading = false
      }
    },
    async loadMappings(params = {}) {
      this.mappingsLoading = true
      try {
        const { data } = await fetchMappings(params)
        this.mappings = data || []
      } finally {
        this.mappingsLoading = false
      }
    },
    async saveMapping(payload) {
      await saveMapping(payload)
      await this.loadMappings()
    },
    async activateMapping(mappingId, defaultModel) {
      await activateMapping(mappingId, { default_model: defaultModel })
      await this.loadMappings()
    },
    async deleteMapping(mappingId) {
      if (!mappingId) return
      await deleteMapping(mappingId)
      await this.loadMappings()
    },
    async loadPrompts(params = {}) {
      this.promptsLoading = true
      try {
        const { data } = await fetchPrompts(params)
        this.prompts = data || []
      } finally {
        this.promptsLoading = false
      }
    },
    async activatePrompt(promptId) {
      if (!promptId) return
      await api.activateAIPrompt(promptId)
      await this.loadPrompts()
    },
    setMailApiKey(key) {
      this.mailApiKey = key
      localStorage.setItem('ai_suite_mail_api_key', key)
    },
    setJwtSession({ accessToken, mode, meta } = {}) {
      const token = _normalizeJwtToken(accessToken)
      this.jwtToken = token
      this.jwtTokenMode = String(mode || '').trim() || 'manual'
      this.jwtTokenMeta = _normalizeJwtMeta(meta)
      localStorage.setItem('ai_suite_jwt_token', this.jwtToken)
      localStorage.setItem('ai_suite_jwt_token_mode', this.jwtTokenMode)
      localStorage.setItem('ai_suite_jwt_token_meta', JSON.stringify(this.jwtTokenMeta))
    },
    setJwtTokenManual(rawToken) {
      const token = _normalizeJwtToken(rawToken)
      if (!token) {
        this.clearJwtSession()
        return
      }
      this.jwtToken = token
      this.jwtTokenMode = 'manual'
      this.jwtTokenMeta = { email: '', username: '' }
      localStorage.setItem('ai_suite_jwt_token', this.jwtToken)
      localStorage.setItem('ai_suite_jwt_token_mode', this.jwtTokenMode)
      localStorage.setItem('ai_suite_jwt_token_meta', JSON.stringify(this.jwtTokenMeta))
    },
    clearJwtSession() {
      this.jwtToken = ''
      this.jwtTokenMode = ''
      this.jwtTokenMeta = { email: '', username: '' }
      localStorage.removeItem('ai_suite_jwt_token')
      localStorage.removeItem('ai_suite_jwt_token_mode')
      localStorage.removeItem('ai_suite_jwt_token_meta')
    },
  },
})
