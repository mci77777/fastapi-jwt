<template>
  <NCard :title="compact ? undefined : 'AI 供应商 / 映射模型'" size="small">
    <NSpace vertical :size="12">
      <NSelect
        v-model:value="selectedEndpointId"
        :options="endpointOptions"
        :loading="loading"
        placeholder="选择 API（端点）"
        filterable
        @update:value="handleEndpointChange"
      />

      <NSelect
        v-model:value="selectedMappedModel"
        :options="mappedModelOptions"
        :loading="loading"
        placeholder="选择映射模型名（推荐）"
        filterable
        clearable
        @update:value="handleMappedModelChange"
      />

      <div v-if="!compact && currentEndpoint" class="model-info">
        <NText depth="3" style="font-size: 12px">
          {{ currentEndpoint.base_url }}
        </NText>
        <NSpace :size="4" style="margin-top: 4px">
          <NTag v-if="currentEndpoint.is_active" type="success" size="small">启用</NTag>
          <NTag v-if="currentEndpoint.is_default" type="info" size="small">默认</NTag>
          <NTag :type="statusType[currentEndpoint.status] || 'default'" size="small">
            {{ statusLabel[currentEndpoint.status] || '未知' }}
          </NTag>
        </NSpace>
      </div>
    </NSpace>
  </NCard>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { NCard, NSelect, NSpace, NText, NTag, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'

defineOptions({ name: 'ModelSwitcher' })

defineProps({
  compact: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['change'])

const store = useAiModelSuiteStore()
const { models, modelsLoading, mappings, mappingsLoading } = storeToRefs(store)
const message = useMessage()

const ENDPOINT_ID_KEY = 'dashboard_default_endpoint_id'
const MAPPED_MODEL_KEY = 'dashboard_default_mapped_model'

const selectedEndpointId = ref(null)
const selectedMappedModel = ref('')
const actionLoading = ref(false)
const loading = computed(() => modelsLoading.value || actionLoading.value || mappingsLoading.value)

// 状态映射
const statusType = {
  online: 'success',
  offline: 'error',
  checking: 'warning',
  unknown: 'default',
}

const statusLabel = {
  online: '在线',
  offline: '离线',
  checking: '检测中',
  unknown: '未知',
}

const endpointOptions = computed(() => {
  return (models.value || []).map((endpoint) => ({
    label: endpoint.name || endpoint.base_url || String(endpoint.id),
    value: endpoint.id,
    disabled: !endpoint.is_active,
  }))
})

const currentEndpoint = computed(() => {
  return (models.value || []).find((m) => m.id === selectedEndpointId.value)
})

function buildMappedModelOptionsForEndpoint(endpoint) {
  const items = Array.isArray(mappings.value) ? mappings.value : []
  const active = items.filter((m) => m && m.is_active !== false && (m.name || m.id || m.scope_key))

  const endpointModels = new Set()
  if (endpoint && Array.isArray(endpoint.model_list)) {
    endpoint.model_list.forEach((x) => {
      if (typeof x === 'string' && x.trim()) endpointModels.add(x.trim())
    })
  }

  const filtered =
    endpoint && endpointModels.size
      ? active.filter((m) => {
          const target = new Set()
          if (typeof m.default_model === 'string' && m.default_model.trim()) target.add(m.default_model.trim())
          if (Array.isArray(m.candidates)) {
            m.candidates.forEach((x) => {
              if (typeof x === 'string' && x.trim()) target.add(x.trim())
            })
          }
          for (const t of target) {
            if (endpointModels.has(t)) return true
          }
          return false
        })
      : active

  const list = filtered.length ? filtered : active
  return list.map((m) => {
    const name = (m.name || '').trim()
    const fallback = typeof m.id === 'string' && m.id ? m.id : `${m.scope_type}:${m.scope_key}`
    const value = fallback
    const target =
      (typeof m.default_model === 'string' && m.default_model.trim() ? m.default_model.trim() : '') ||
      (Array.isArray(m.candidates) && typeof m.candidates[0] === 'string' ? String(m.candidates[0]) : '')
    const suffix = target ? ` → ${target}` : ''
    const label = `${(name || fallback)}${suffix}`
    return { label, value }
  })
}

const mappedModelOptions = computed(() => {
  return buildMappedModelOptionsForEndpoint(currentEndpoint.value)
})

// 监听 mappings 变化，自动刷新选项
watch(
  () => mappings.value,
  () => {
    // mappings 变更时：若当前映射模型不可用则清理
    const exists = mappedModelOptions.value.some((opt) => opt.value === selectedMappedModel.value)
    if (selectedMappedModel.value && !exists) {
      selectedMappedModel.value = ''
    }
  },
  { deep: true }
)

/**
 * 处理端点切换（仍保留“设为默认端点”的语义）
 */
async function handleEndpointChange(endpointId) {
  if (!endpointId) return

  actionLoading.value = true
  try {
    const endpoint = models.value.find((m) => m.id === endpointId)
    if (!endpoint) {
      message.error('端点不存在')
      return
    }

    // 调用 store action 设置默认端点（SSOT：后端 config）
    await store.setDefaultModel(endpoint)

    selectedEndpointId.value = endpointId
    try {
      localStorage.setItem(ENDPOINT_ID_KEY, String(endpointId))
    } catch {
      // ignore
    }

    emit('change', {
      endpoint_id: endpointId,
      model_source: 'mapping',
      model: selectedMappedModel.value || null,
    })
    message.success(`已切换到端点: ${endpoint.name || endpoint.base_url}`)
  } catch (error) {
    console.error('端点切换失败:', error)
    message.error('端点切换失败，请重试')

    // 恢复到之前的选择
    const defaultEndpoint = models.value.find((m) => m.is_default)
    if (defaultEndpoint) {
      selectedEndpointId.value = defaultEndpoint.id
    }
  } finally {
    actionLoading.value = false
  }
}

function handleMappedModelChange(value) {
  const v = typeof value === 'string' ? value.trim() : ''
  selectedMappedModel.value = v
  try {
    if (v) localStorage.setItem(MAPPED_MODEL_KEY, v)
    else localStorage.removeItem(MAPPED_MODEL_KEY)
  } catch {
    // ignore
  }
  emit('change', {
    endpoint_id: selectedEndpointId.value,
    model_source: 'mapping',
    model: v || null,
  })
}

/**
 * 初始化：加载模型列表、映射数据并设置默认选中
 */
async function initializeModels() {
  actionLoading.value = true
  try {
    // 并行加载模型列表和映射数据
    await Promise.all([store.loadModels(), store.loadMappings()])

    // 1) 端点：优先 localStorage，其次后端 default，其次第一个启用
    const savedEndpointIdRaw = (() => {
      try {
        return localStorage.getItem(ENDPOINT_ID_KEY)
      } catch {
        return null
      }
    })()
    const savedEndpointId = savedEndpointIdRaw ? Number(savedEndpointIdRaw) : null
    const savedEndpoint = savedEndpointId ? models.value.find((m) => m.id === savedEndpointId) : null

    const defaultEndpoint = models.value.find((m) => m.is_default)
    const firstActive = models.value.find((m) => m.is_active)
    selectedEndpointId.value = (savedEndpoint || defaultEndpoint || firstActive || models.value[0] || {}).id ?? null

    // 2) 映射模型：只做客户端默认值（不修改后端）
    try {
      const savedMapped = localStorage.getItem(MAPPED_MODEL_KEY)
      if (savedMapped) selectedMappedModel.value = savedMapped
    } catch {
      // ignore
    }

    // 如果当前映射不在候选中，自动选择第一个
    if (!mappedModelOptions.value.some((opt) => opt.value === selectedMappedModel.value)) {
      selectedMappedModel.value = mappedModelOptions.value[0]?.value || ''
    }

    emit('change', {
      endpoint_id: selectedEndpointId.value,
      model_source: 'mapping',
      model: selectedMappedModel.value || null,
    })
  } catch (error) {
    console.error('加载模型列表失败:', error)
    message.error('加载模型列表失败')
  } finally {
    actionLoading.value = false
  }
}

onMounted(() => {
  initializeModels()
})
</script>

<style scoped>
.model-info {
  padding: 8px 0;
  border-top: 1px solid var(--n-border-color);
}
</style>
