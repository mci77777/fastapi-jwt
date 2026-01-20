<template>
  <n-card :title="compact ? undefined : 'Prompt 配置'">
    <n-space vertical :size="12">
      <n-space align="center" justify="space-between">
        <n-space align="center" :size="8" :wrap="false" style="min-width: 0">
          <n-text depth="3">Prompt 注入</n-text>
          <n-tag size="small" :type="appOutputProtocol === 'jsonseq_v1' ? 'success' : 'default'">
            {{ appOutputProtocol === 'jsonseq_v1' ? 'jsonseq_v1' : 'thinkingml_v45' }}
          </n-tag>
        </n-space>
        <n-space align="center" :size="8" :wrap="false">
          <n-select
            v-model:value="promptMode"
            :options="promptModeOptions"
            :disabled="loading || promptModeLoading || promptModeSaving"
            size="small"
            style="width: 180px"
            @update:value="handlePromptModeChange"
          />
          <n-button v-if="!compact" size="small" secondary @click="handleGoPromptManager">
            管理 Prompts
          </n-button>
        </n-space>
      </n-space>

      <n-alert v-if="promptMode === 'passthrough'" type="info" :show-icon="false">
        透传模式：客户端请求默认跳过后端 prompt 注入；下方 Prompt 选择不影响线上输出，但可提前配置，切回 server 后生效。
      </n-alert>

      <n-tabs v-model:value="activeGroup" type="segment" size="small">
        <n-tab-pane name="messages_xml" tab="Messages · XML">
          <n-space vertical :size="10">
            <n-text depth="3" style="font-size: 12px">
              生效条件：<code>app_output_protocol=thinkingml_v45</code>
            </n-text>
            <n-form label-placement="left" label-width="72" size="small">
              <n-form-item label="System">
                <div class="prompt-row">
                  <n-select
                    v-model:value="selectedSystemPromptId"
                    class="prompt-select"
                    :options="systemPromptOptions"
                    :loading="loading"
                    filterable
                    placeholder="选择 System Prompt"
                    @update:value="handlePromptChange"
                  />
                  <n-button
                    v-if="!compact"
                    size="small"
                    tertiary
                    :disabled="!selectedSystemPromptId"
                    @click="openPreview(selectedSystemPromptId)"
                    >预览</n-button
                  >
                </div>
              </n-form-item>
              <n-form-item label="Tools">
                <div class="prompt-row">
                  <n-select
                    v-model:value="selectedToolsPromptId"
                    class="prompt-select"
                    :options="toolsPromptOptions"
                    :loading="loading"
                    filterable
                    placeholder="选择 Tools Prompt"
                    @update:value="handlePromptChange"
                  />
                  <n-button
                    v-if="!compact"
                    size="small"
                    tertiary
                    :disabled="!selectedToolsPromptId"
                    @click="openPreview(selectedToolsPromptId)"
                    >预览</n-button
                  >
                </div>
              </n-form-item>
            </n-form>
          </n-space>
        </n-tab-pane>

        <n-tab-pane name="messages_jsonseq" tab="Messages · JSON">
          <n-space vertical :size="10">
            <n-text depth="3" style="font-size: 12px">
              生效条件：<code>app_output_protocol=jsonseq_v1</code>
            </n-text>
            <n-form label-placement="left" label-width="72" size="small">
              <n-form-item label="System">
                <div class="prompt-row">
                  <n-select
                    v-model:value="selectedSystemJsonseqPromptId"
                    class="prompt-select"
                    :options="systemJsonseqPromptOptions"
                    :loading="loading"
                    filterable
                    placeholder="选择 System Prompt（JSONSeq v1）"
                    @update:value="handlePromptChange"
                  />
                  <n-button
                    v-if="!compact"
                    size="small"
                    tertiary
                    :disabled="!selectedSystemJsonseqPromptId"
                    @click="openPreview(selectedSystemJsonseqPromptId)"
                    >预览</n-button
                  >
                </div>
              </n-form-item>
              <n-form-item label="Tools">
                <div class="prompt-row">
                  <n-select
                    v-model:value="selectedToolsJsonseqPromptId"
                    class="prompt-select"
                    :options="toolsJsonseqPromptOptions"
                    :loading="loading"
                    filterable
                    placeholder="选择 Tools Prompt（JSONSeq v1）"
                    @update:value="handlePromptChange"
                  />
                  <n-button
                    v-if="!compact"
                    size="small"
                    tertiary
                    :disabled="!selectedToolsJsonseqPromptId"
                    @click="openPreview(selectedToolsJsonseqPromptId)"
                    >预览</n-button
                  >
                </div>
              </n-form-item>
            </n-form>
          </n-space>
        </n-tab-pane>

        <n-tab-pane name="agent" tab="Agent">
          <n-space vertical :size="10">
            <n-text depth="3" style="font-size: 12px">
              Agent Run 固定使用 <code>agent_system/agent_tools</code>（与 output_protocol 无关）
            </n-text>
            <n-form label-placement="left" label-width="72" size="small">
              <n-form-item label="System">
                <div class="prompt-row">
                  <n-select
                    v-model:value="selectedAgentSystemPromptId"
                    class="prompt-select"
                    :options="agentSystemPromptOptions"
                    :loading="loading"
                    filterable
                    placeholder="选择 Agent System Prompt"
                    @update:value="handlePromptChange"
                  />
                  <n-button
                    v-if="!compact"
                    size="small"
                    tertiary
                    :disabled="!selectedAgentSystemPromptId"
                    @click="openPreview(selectedAgentSystemPromptId)"
                    >预览</n-button
                  >
                </div>
              </n-form-item>
              <n-form-item label="Tools">
                <div class="prompt-row">
                  <n-select
                    v-model:value="selectedAgentToolsPromptId"
                    class="prompt-select"
                    :options="agentToolsPromptOptions"
                    :loading="loading"
                    filterable
                    placeholder="选择 Agent Tools Prompt"
                    @update:value="handlePromptChange"
                  />
                  <n-button
                    v-if="!compact"
                    size="small"
                    tertiary
                    :disabled="!selectedAgentToolsPromptId"
                    @click="openPreview(selectedAgentToolsPromptId)"
                    >预览</n-button
                  >
                </div>
              </n-form-item>
            </n-form>
          </n-space>
        </n-tab-pane>
      </n-tabs>
    </n-space>

    <n-modal
      v-model:show="previewVisible"
      preset="card"
      title="Prompt 预览（只读）"
      style="width: min(920px, calc(100vw - 48px))"
    >
      <n-space vertical :size="12">
        <n-space align="center" justify="space-between" :wrap="false">
          <n-space align="center" :size="8" :wrap="false" style="min-width: 0">
            <n-text style="font-weight: 600">{{ previewPrompt?.name || '--' }}</n-text>
            <n-tag size="small" type="info">#{{ previewPrompt?.id || '--' }}</n-tag>
            <n-tag v-if="previewPromptTypeLabel" size="small" type="warning">{{ previewPromptTypeLabel }}</n-tag>
          </n-space>
          <n-space align="center" :size="8">
            <n-button size="small" secondary :disabled="!previewPromptText" @click="handleCopy(previewPromptText)">
              复制内容
            </n-button>
            <n-button v-if="previewToolsText" size="small" tertiary @click="handleCopy(previewToolsText)">
              复制 Tools
            </n-button>
          </n-space>
        </n-space>

        <n-tabs type="line" size="small">
          <n-tab-pane name="content" tab="内容">
            <n-input :value="previewPromptText" type="textarea" :rows="12" readonly />
          </n-tab-pane>
          <n-tab-pane v-if="previewToolsText" name="tools" tab="Tools JSON">
            <n-input :value="previewToolsText" type="textarea" :rows="12" readonly />
          </n-tab-pane>
        </n-tabs>
      </n-space>
    </n-modal>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'
import api from '@/api'
import { useRouter } from 'vue-router'

defineProps({
  compact: { type: Boolean, default: false },
})

const emit = defineEmits(['change'])

const store = useAiModelSuiteStore()
const { prompts, promptsLoading } = storeToRefs(store)

const router = useRouter()

const appOutputProtocol = ref('thinkingml_v45')
const activeGroup = ref('messages_xml')
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

const previewVisible = ref(false)
const previewPromptId = ref(null)

const previewPrompt = computed(() => prompts.value.find((p) => p?.id === previewPromptId.value) || null)
const previewPromptText = computed(() => String(previewPrompt.value?.content || '').trim())
const previewToolsText = computed(() => {
  const raw = previewPrompt.value?.tools_json
  if (!raw) return ''
  try {
    return JSON.stringify(raw, null, 2)
  } catch {
    return ''
  }
})

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

const previewPromptTypeLabel = computed(() => {
  const t = String(getPromptType(previewPrompt.value) || '').trim()
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
      system_jsonseq_v1_prompt_id: selectedSystemJsonseqPromptId.value,
      tools_jsonseq_v1_prompt_id: selectedToolsJsonseqPromptId.value,
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

    const protocol = String(data?.app_output_protocol || '').trim().toLowerCase()
    appOutputProtocol.value = protocol === 'jsonseq_v1' ? 'jsonseq_v1' : 'thinkingml_v45'
    activeGroup.value = appOutputProtocol.value === 'jsonseq_v1' ? 'messages_jsonseq' : 'messages_xml'
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

function openPreview(promptId) {
  const id = typeof promptId === 'number' ? promptId : null
  if (!id) return
  previewPromptId.value = id
  previewVisible.value = true
}

async function handleCopy(text) {
  const content = String(text || '').trim()
  if (!content) return
  try {
    await navigator.clipboard.writeText(content)
    window.$message?.success('已复制')
  } catch {
    window.$message?.warning('复制失败：浏览器不支持或无权限')
  }
}

function handleGoPromptManager() {
  router.push('/system/ai/prompt')
}
</script>

<style scoped>
.n-card {
  height: 100%;
}

.prompt-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.prompt-select {
  flex: 1;
  min-width: 0;
}

.prompt-select :deep(.n-base-selection-label) {
  overflow: hidden;
}

.prompt-select :deep(.n-base-selection-input__content) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.prompt-select :deep(.n-base-select-option__content) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 560px;
}
</style>
