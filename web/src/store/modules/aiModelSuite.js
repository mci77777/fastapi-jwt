import { defineStore } from 'pinia'

import {
  fetchModels,
  fetchMappings,
  fetchPrompts,
  fetchLoadRun,
  runLoadTest,
  simulateDialog,
  saveMapping,
  activateMapping,
  updateModel,
  syncModel,
  syncAllModels,
} from '@/api/aiModelSuite'

export const useAiModelSuiteStore = defineStore('aiModelSuite', {
  state: () => ({
    models: [],
    modelsLoading: false,
    mappings: [],
    mappingsLoading: false,
    prompts: [],
    promptsLoading: false,
    latestRun: null,
    latestRunSummary: null,
    latestRunLoading: false,
    syncingEndpoints: new Set(),
    syncAllLoading: false,
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
      ;(state.models || []).forEach((endpoint) => {
        if (Array.isArray(endpoint.model_list)) {
          endpoint.model_list.forEach((model) => {
            if (model) models.add(model)
          })
        } else if (endpoint.model) {
          models.add(endpoint.model)
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
        await syncModel(endpointId, options)
      } finally {
        this.syncingEndpoints.delete(endpointId)
        await this.loadModels()
      }
    },
    async syncAll(directionOptions = {}) {
      this.syncAllLoading = true
      try {
        await syncAllModels(directionOptions)
      } finally {
        this.syncAllLoading = false
        await this.loadModels()
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
    async loadPrompts(params = {}) {
      this.promptsLoading = true
      try {
        const { data } = await fetchPrompts(params)
        this.prompts = data || []
      } finally {
        this.promptsLoading = false
      }
    },
    async simulateDialog(payload) {
      return simulateDialog(payload)
    },
    async triggerLoadTest(payload) {
      this.latestRunLoading = true
      try {
        const result = await runLoadTest(payload)
        this.latestRun = result
        this.latestRunSummary = result?.summary || null
        return result
      } finally {
        this.latestRunLoading = false
      }
    },
    async refreshRun(runId) {
      if (!runId) return null
      this.latestRunLoading = true
      try {
        const result = await fetchLoadRun(runId)
        this.latestRun = result
        this.latestRunSummary = result?.summary || null
        return result
      } finally {
        this.latestRunLoading = false
      }
    },
  },
})
