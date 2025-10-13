<template>
  <n-card :title="compact ? undefined : '当前 Prompt'">
    <n-space vertical>
      <n-select
        v-model:value="selectedPromptId"
        :options="promptOptions"
        :loading="loading"
        placeholder="选择 Prompt"
        @update:value="handlePromptChange"
      />
      <n-space v-if="!compact && currentPrompt" vertical :size="8">
        <n-text depth="3" style="font-size: 12px">
          {{ currentPrompt.description || '无描述' }}
        </n-text>
        <n-space align="center" :size="8">
          <n-tag :type="currentPrompt.is_active ? 'success' : 'default'" size="small">
            {{ currentPrompt.is_active ? '已激活' : '未激活' }}
          </n-tag>
          <n-tag v-if="currentPrompt.tools_json" type="info" size="small"> Tools 已配置 </n-tag>
        </n-space>
      </n-space>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'

const props = defineProps({
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['change'])

const store = useAiModelSuiteStore()
const { prompts, promptsLoading } = storeToRefs(store)

const selectedPromptId = ref(null)
const loading = computed(() => promptsLoading.value)

const promptOptions = computed(() => {
  return prompts.value.map((prompt) => ({
    label: prompt.name,
    value: prompt.id,
  }))
})

const currentPrompt = computed(() => {
  return prompts.value.find((p) => p.id === selectedPromptId.value)
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
