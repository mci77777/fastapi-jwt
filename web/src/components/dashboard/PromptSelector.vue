<template>
  <n-card :title="compact ? undefined : 'Prompt 选择器'">
    <n-space vertical :size="12">
      <n-space align="center" justify="space-between">
        <n-text depth="3">Prompt 模式</n-text>
      <n-select
        v-model:value="promptMode"
        :options="promptModeOptions"
        :disabled="loading || promptModeLoading || promptModeSaving"
        size="small"
        style="min-width: 180px"
        @update:value="handlePromptModeChange"
      />
      </n-space>

      <n-alert v-if="promptMode === 'passthrough'" type="info" :show-icon="false">
        透传模式：客户端请求默认跳过后端 prompt 注入；下方 Prompt 选择不影响线上输出，但可提前配置，切回 server 后生效。
      </n-alert>

      <!-- Tabs 分类：System 和 Tools -->
      <n-tabs v-model:value="activeTab" type="segment" size="small">
        <n-tab-pane name="system" tab="System（XML/ThinkingML）">
          <n-select
            v-model:value="selectedSystemPromptId"
            :options="systemPromptOptions"
            :loading="loading"
            placeholder="选择 System Prompt"
            @update:value="handlePromptChange"
          />
        </n-tab-pane>
        <n-tab-pane name="tools" tab="Tools（XML/ThinkingML）">
          <n-select
            v-model:value="selectedToolsPromptId"
            :options="toolsPromptOptions"
            :loading="loading"
            placeholder="选择 Tools Prompt"
            @update:value="handlePromptChange"
          />
        </n-tab-pane>
        <n-tab-pane name="system_jsonseq_v1" tab="System（JSONSeq v1）">
          <n-select
            v-model:value="selectedSystemJsonseqPromptId"
            :options="systemJsonseqPromptOptions"
            :loading="loading"
            placeholder="选择 System Prompt（JSONSeq v1）"
            @update:value="handlePromptChange"
          />
        </n-tab-pane>
        <n-tab-pane name="tools_jsonseq_v1" tab="Tools（JSONSeq v1）">
          <n-select
            v-model:value="selectedToolsJsonseqPromptId"
            :options="toolsJsonseqPromptOptions"
            :loading="loading"
            placeholder="选择 Tools Prompt（JSONSeq v1）"
            @update:value="handlePromptChange"
          />
        </n-tab-pane>
        <n-tab-pane name="agent_system" tab="Agent System">
          <n-select
            v-model:value="selectedAgentSystemPromptId"
            :options="agentSystemPromptOptions"
            :loading="loading"
            placeholder="选择 Agent System Prompt"
            @update:value="handlePromptChange"
          />
        </n-tab-pane>
        <n-tab-pane name="agent_tools" tab="Agent Tools">
          <n-select
            v-model:value="selectedAgentToolsPromptId"
            :options="agentToolsPromptOptions"
            :loading="loading"
            placeholder="选择 Agent Tools Prompt"
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
          <n-tag v-if="promptTypeLabel" type="warning" size="small">{{ promptTypeLabel }}</n-tag>
        </n-space>
      </n-space>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'
import api from '@/api'

defineProps({
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['change'])

const store = useAiModelSuiteStore()
const { prompts, promptsLoading } = storeToRefs(store)

const activeTab = ref('system')
const loading = computed(() => promptsLoading.value)
const selectedSystemPromptId = ref(null)
const selectedToolsPromptId = ref(null)
const selectedSystemJsonseqPromptId = ref(null)
const selectedToolsJsonseqPromptId = ref(null)
const selectedAgentSystemPromptId = ref(null)
const selectedAgentToolsPromptId = ref(null)
const promptMode = ref('server') // 'server' | 'passthrough'
const promptModeLoading = ref(false)
const promptModeSaving = ref(false)
const promptModeOptions = [
  { label: '不透传（后端组装/注入）', value: 'server' },
  { label: '透传（跳过后端默认注入）', value: 'passthrough' },
]

/**
 * 判断 Prompt 类型（基于 tools_json 字段）
 * - 如果 tools_json 存在且非空，认为是 Tools Prompt
 * - 否则认为是 System Prompt
 */
function getPromptType(prompt) {
  if (!prompt) return null
  const pt = String(prompt.prompt_type || '').trim().toLowerCase()
  if (pt === 'system') return 'system'
  if (pt === 'tools') return 'tools'
  if (pt === 'system_jsonseq_v1') return 'system_jsonseq_v1'
  if (pt === 'tools_jsonseq_v1') return 'tools_jsonseq_v1'
  if (pt === 'agent_system') return 'agent_system'
  if (pt === 'agent_tools') return 'agent_tools'
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

const systemJsonseqPromptOptions = computed(() => {
  return prompts.value
    .filter((p) => getPromptType(p) === 'system_jsonseq_v1')
    .map((prompt) => ({
      label: prompt.name,
      value: prompt.id,
    }))
})

const toolsJsonseqPromptOptions = computed(() => {
  return prompts.value
    .filter((p) => getPromptType(p) === 'tools_jsonseq_v1')
    .map((prompt) => ({
      label: prompt.name,
      value: prompt.id,
    }))
})

const agentSystemPromptOptions = computed(() => {
  return prompts.value
    .filter((p) => getPromptType(p) === 'agent_system')
    .map((prompt) => ({
      label: prompt.name,
      value: prompt.id,
    }))
})

const agentToolsPromptOptions = computed(() => {
  return prompts.value
    .filter((p) => getPromptType(p) === 'agent_tools')
    .map((prompt) => ({
      label: prompt.name,
      value: prompt.id,
    }))
})

const currentPrompt = computed(() => {
  const id =
    activeTab.value === 'tools'
      ? selectedToolsPromptId.value
      : activeTab.value === 'system_jsonseq_v1'
        ? selectedSystemJsonseqPromptId.value
        : activeTab.value === 'tools_jsonseq_v1'
          ? selectedToolsJsonseqPromptId.value
          : activeTab.value === 'agent_system'
            ? selectedAgentSystemPromptId.value
            : activeTab.value === 'agent_tools'
              ? selectedAgentToolsPromptId.value
              : selectedSystemPromptId.value
  return prompts.value.find((p) => p.id === id)
})

const promptType = computed(() => {
  return getPromptType(currentPrompt.value)
})

const promptTypeLabel = computed(() => {
  const t = String(promptType.value || '').trim()
  if (!t) return ''
  if (t === 'system') return 'System（XML/ThinkingML）'
  if (t === 'tools') return 'Tools（XML/ThinkingML）'
  if (t === 'system_jsonseq_v1') return 'System（JSONSeq v1）'
  if (t === 'tools_jsonseq_v1') return 'Tools（JSONSeq v1）'
  if (t === 'agent_system') return 'Agent System'
  if (t === 'agent_tools') return 'Agent Tools'
  return t
})

async function handlePromptChange(promptId) {
  if (!promptId) return

  try {
    await store.activatePrompt(promptId)
    emit('change', {
      prompt_mode: promptMode.value,
      system_prompt_id: selectedSystemPromptId.value,
      tools_prompt_id: selectedToolsPromptId.value,
      system_jsonseq_v1_prompt_id: selectedSystemJsonseqPromptId.value,
      tools_jsonseq_v1_prompt_id: selectedToolsJsonseqPromptId.value,
      agent_system_prompt_id: selectedAgentSystemPromptId.value,
      agent_tools_prompt_id: selectedAgentToolsPromptId.value,
    })
    window.$message?.success(promptMode.value === 'passthrough' ? 'Prompt 已切换（当前为 passthrough，不会注入）' : 'Prompt 已切换')
  } catch (error) {
    window.$message?.error('Prompt 切换失败')
    // 回滚到之前的选择（按类型）
    const activeSystem = prompts.value.find((p) => p.is_active && getPromptType(p) === 'system')
    const activeTools = prompts.value.find((p) => p.is_active && getPromptType(p) === 'tools')
    const activeSystemJsonseq = prompts.value.find((p) => p.is_active && getPromptType(p) === 'system_jsonseq_v1')
    const activeToolsJsonseq = prompts.value.find((p) => p.is_active && getPromptType(p) === 'tools_jsonseq_v1')
    const activeAgentSystem = prompts.value.find((p) => p.is_active && getPromptType(p) === 'agent_system')
    const activeAgentTools = prompts.value.find((p) => p.is_active && getPromptType(p) === 'agent_tools')
    selectedSystemPromptId.value = activeSystem ? activeSystem.id : null
    selectedToolsPromptId.value = activeTools ? activeTools.id : null
    selectedSystemJsonseqPromptId.value = activeSystemJsonseq ? activeSystemJsonseq.id : null
    selectedToolsJsonseqPromptId.value = activeToolsJsonseq ? activeToolsJsonseq.id : null
    selectedAgentSystemPromptId.value = activeAgentSystem ? activeAgentSystem.id : null
    selectedAgentToolsPromptId.value = activeAgentTools ? activeAgentTools.id : null
  }
}

async function handlePromptModeChange(mode) {
  const resolved = mode === 'passthrough' ? 'passthrough' : 'server'
  const prev = promptMode.value
  promptMode.value = resolved
  promptModeSaving.value = true
  try {
    const res = await api.upsertLlmAppConfig({ prompt_mode: resolved })
    const data = res?.data?.data || res?.data || {}
    const saved = String(data?.prompt_mode || '').trim().toLowerCase()
    promptMode.value = saved === 'passthrough' ? 'passthrough' : 'server'
    emit('change', {
      prompt_mode: promptMode.value,
      system_prompt_id: selectedSystemPromptId.value,
      tools_prompt_id: selectedToolsPromptId.value,
      agent_system_prompt_id: selectedAgentSystemPromptId.value,
      agent_tools_prompt_id: selectedAgentToolsPromptId.value,
    })
    window.$message?.success('已更新 Prompt 模式')
  } catch (error) {
    promptMode.value = prev
    window.$message?.error(error?.message || '保存 Prompt 模式失败')
  } finally {
    promptModeSaving.value = false
  }
}

onMounted(async () => {
  promptModeLoading.value = true
  try {
    const res = await api.getLlmAppConfig()
    const data = res?.data?.data || res?.data || {}
    const savedMode = String(data?.prompt_mode || '').trim().toLowerCase()
    promptMode.value = savedMode === 'passthrough' ? 'passthrough' : 'server'
  } catch (error) {
    window.$message?.error(error?.message || '加载 Prompt 模式失败')
  } finally {
    promptModeLoading.value = false
  }

  try {
    await store.loadPrompts()
    const activeSystem = prompts.value.find((p) => p.is_active && getPromptType(p) === 'system')
    const activeTools = prompts.value.find((p) => p.is_active && getPromptType(p) === 'tools')
    const activeSystemJsonseq = prompts.value.find((p) => p.is_active && getPromptType(p) === 'system_jsonseq_v1')
    const activeToolsJsonseq = prompts.value.find((p) => p.is_active && getPromptType(p) === 'tools_jsonseq_v1')
    const activeAgentSystem = prompts.value.find((p) => p.is_active && getPromptType(p) === 'agent_system')
    const activeAgentTools = prompts.value.find((p) => p.is_active && getPromptType(p) === 'agent_tools')
    selectedSystemPromptId.value = activeSystem ? activeSystem.id : null
    selectedToolsPromptId.value = activeTools ? activeTools.id : null
    selectedSystemJsonseqPromptId.value = activeSystemJsonseq ? activeSystemJsonseq.id : null
    selectedToolsJsonseqPromptId.value = activeToolsJsonseq ? activeToolsJsonseq.id : null
    selectedAgentSystemPromptId.value = activeAgentSystem ? activeAgentSystem.id : null
    selectedAgentToolsPromptId.value = activeAgentTools ? activeAgentTools.id : null
  } catch (error) {
    window.$message?.error(error?.message || '加载 Prompt 列表失败')
  }
})

watch(
  () => promptMode.value,
  (mode) => {
    const resolved = mode === 'passthrough' ? 'passthrough' : 'server'
    if (resolved !== mode) promptMode.value = resolved
  }
)
</script>

<style scoped>
.n-card {
  height: 100%;
}
</style>
