<template>
  <n-card :title="compact ? undefined : 'Prompt 选择器'">
    <n-space vertical :size="12">
      <!-- Tabs 分类：System 和 Tools -->
      <n-tabs v-model:value="activeTab" type="segment" size="small">
        <n-tab-pane name="system" tab="System Prompts">
          <n-select
            v-model:value="selectedPromptId"
            :options="systemPromptOptions"
            :loading="loading"
            placeholder="选择 System Prompt"
            @update:value="handlePromptChange"
          />
        </n-tab-pane>
        <n-tab-pane name="tools" tab="Tools Prompts">
          <n-select
            v-model:value="selectedPromptId"
            :options="toolsPromptOptions"
            :loading="loading"
            placeholder="选择 Tools Prompt"
            @update:value="handlePromptChange"
          />
        </n-tab-pane>
      </n-tabs>

      <!-- 当前 Prompt 详情 -->
      <n-space v-if="!compact && currentPrompt" vertical :size="8">
        <n-text depth="3" style="font-size: 12px">
          {{ currentPrompt.description || '无描述' }}
        </n-text>
        <n-space align="center" :size="8">
          <n-tag :type="currentPrompt.is_active ? 'success' : 'default'" size="small">
            {{ currentPrompt.is_active ? '已激活' : '未激活' }}
          </n-tag>
          <n-tag v-if="currentPrompt.tools_json" type="info" size="small"> Tools 已配置 </n-tag>
          <n-tag v-if="promptType" type="warning" size="small">
            {{ promptType === 'system' ? 'System' : 'Tools' }}
          </n-tag>
        </n-space>
      </n-space>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'

defineProps({
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['change'])

const store = useAiModelSuiteStore()
const { prompts, promptsLoading } = storeToRefs(store)

const selectedPromptId = ref(null)
const activeTab = ref('system')
const loading = computed(() => promptsLoading.value)

/**
 * 判断 Prompt 类型（基于 tools_json 字段）
 * - 如果 tools_json 存在且非空，认为是 Tools Prompt
 * - 否则认为是 System Prompt
 */
function getPromptType(prompt) {
  if (!prompt) return null
  if (prompt.tools_json && Object.keys(prompt.tools_json).length > 0) {
    return 'tools'
  }
  return 'system'
}

// System Prompts 选项
const systemPromptOptions = computed(() => {
  return prompts.value
    .filter((p) => getPromptType(p) === 'system')
    .map((prompt) => ({
      label: prompt.name,
      value: prompt.id,
    }))
})

// Tools Prompts 选项
const toolsPromptOptions = computed(() => {
  return prompts.value
    .filter((p) => getPromptType(p) === 'tools')
    .map((prompt) => ({
      label: prompt.name,
      value: prompt.id,
    }))
})

const currentPrompt = computed(() => {
  return prompts.value.find((p) => p.id === selectedPromptId.value)
})

const promptType = computed(() => {
  return getPromptType(currentPrompt.value)
})

async function handlePromptChange(promptId) {
  if (!promptId) return

  try {
    await store.activatePrompt(promptId)
    emit('change', promptId)
    window.$message?.success('Prompt 已切换')
  } catch (error) {
    window.$message?.error('Prompt 切换失败')
    // 回滚到之前的选择
    const activePrompt = prompts.value.find((p) => p.is_active)
    if (activePrompt) {
      selectedPromptId.value = activePrompt.id
    }
  }
}

onMounted(async () => {
  try {
    await store.loadPrompts()
    const activePrompt = prompts.value.find((p) => p.is_active)
    if (activePrompt) {
      selectedPromptId.value = activePrompt.id
    }
  } catch (error) {
    window.$message?.error('加载 Prompt 列表失败')
  }
})
</script>

<style scoped>
.n-card {
  height: 100%;
}
</style>
