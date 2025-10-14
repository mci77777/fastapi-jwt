<template>
  <NCard :title="compact ? undefined : '当前模型'" size="small">
    <NSpace vertical :size="12">
      <NSelect
        v-model:value="selectedModelId"
        :options="modelOptions"
        :loading="loading"
        placeholder="选择模型"
        filterable
        @update:value="handleModelChange"
      />
      <div v-if="!compact && currentModel" class="model-info">
        <NText depth="3" style="font-size: 12px">
          {{ currentModel.base_url }}
        </NText>
        <NSpace :size="4" style="margin-top: 4px">
          <NTag v-if="currentModel.is_active" type="success" size="small">启用</NTag>
          <NTag v-if="currentModel.is_default" type="info" size="small">默认</NTag>
          <NTag :type="statusType[currentModel.status] || 'default'" size="small">
            {{ statusLabel[currentModel.status] || '未知' }}
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

const selectedModelId = ref(null)
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

// 标准模型名称映射（从 Model Mapping 数据生成）
const standardModelMap = computed(() => {
  const map = new Map()

  // 从 mappings 中提取标准模型名称
  mappings.value.forEach((mapping) => {
    if (mapping.default_model && mapping.candidates && mapping.candidates.length > 0) {
      // 使用 mapping.name 作为标准模型名称
      const standardName = mapping.name || mapping.default_model
      const apiModel = mapping.default_model

      // 查找对应的 model 对象
      const modelObj = models.value.find((m) => m.model === apiModel || m.name === apiModel)
      if (modelObj) {
        map.set(standardName, {
          standardName,
          apiModel,
          modelId: modelObj.id,
          modelObj,
        })
      }
    }
  })

  return map
})

// 模型选项（优先使用标准模型名称）
const modelOptions = computed(() => {
  // 如果有 Model Mapping 数据，使用标准名称
  if (standardModelMap.value.size > 0) {
    return Array.from(standardModelMap.value.values()).map((item) => ({
      label: `${item.standardName} (${item.apiModel})`,
      value: item.modelId,
      disabled: !item.modelObj.is_active,
    }))
  }

  // 否则回退到原始模型列表
  return models.value.map((model) => ({
    label: `${model.model || model.name} (${model.provider || 'Unknown'})`,
    value: model.id,
    disabled: !model.is_active,
  }))
})

// 当前选中的模型对象
const currentModel = computed(() => {
  return models.value.find((m) => m.id === selectedModelId.value)
})

// 监听 mappings 变化，自动刷新选项
watch(
  () => mappings.value,
  () => {
    // 如果当前选中的模型不在新的选项中，重置为默认模型
    if (selectedModelId.value) {
      const exists = modelOptions.value.some((opt) => opt.value === selectedModelId.value)
      if (!exists) {
        const defaultModel = models.value.find((m) => m.is_default)
        if (defaultModel) {
          selectedModelId.value = defaultModel.id
        }
      }
    }
  },
  { deep: true }
)

/**
 * 处理模型切换
 */
async function handleModelChange(modelId) {
  if (!modelId) return

  actionLoading.value = true
  try {
    const model = models.value.find((m) => m.id === modelId)
    if (!model) {
      message.error('模型不存在')
      return
    }

    // 调用 store action 设置默认模型
    await store.setDefaultModel(model)

    emit('change', modelId)
    message.success(`已切换到模型: ${model.model || model.name}`)
  } catch (error) {
    console.error('模型切换失败:', error)
    message.error('模型切换失败，请重试')

    // 恢复到之前的选择
    const defaultModel = models.value.find((m) => m.is_default)
    if (defaultModel) {
      selectedModelId.value = defaultModel.id
    }
  } finally {
    actionLoading.value = false
  }
}

/**
 * 初始化：加载模型列表、映射数据并设置默认选中
 */
async function initializeModels() {
  actionLoading.value = true
  try {
    // 并行加载模型列表和映射数据
    await Promise.all([store.loadModels(), store.loadMappings()])

    // 设置默认选中的模型
    const defaultModel = models.value.find((m) => m.is_default)
    if (defaultModel) {
      selectedModelId.value = defaultModel.id
    } else if (models.value.length > 0) {
      // 如果没有默认模型，选择第一个启用的模型
      const firstActive = models.value.find((m) => m.is_active)
      if (firstActive) {
        selectedModelId.value = firstActive.id
      }
    }
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
