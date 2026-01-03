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
  },
})
