<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NEmpty,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NRadio,
  NRadioGroup,
  NSelect,
  NSpace,
  NTable,
  NTag,
  NTooltip,
  useDialog,
  useMessage,
} from 'naive-ui'
import { storeToRefs } from 'pinia'

import CrudModal from '@/components/table/CrudModal.vue'
import { useAiModelSuiteStore } from '@/store'

	defineOptions({ name: 'AiModelMapping' })

	const store = useAiModelSuiteStore()
	const { mappings, mappingsLoading, syncMappingsLoading, models, prompts, promptsLoading } = storeToRefs(store)
	const message = useMessage()
	const dialog = useDialog()

const modalVisible = ref(false)
const isEdit = ref(false)
	const formRef = ref(null)
	const formModel = reactive({
	  scope_type: 'mapping',
	  scope_key: '',
	  name: '',
	  default_model: null,
	  candidates: [],
	  metadata: {},
})
const endpointSelection = ref(null)
const importInputRef = ref(null)
const importingLocal = ref(false)

	const scopeOptions = [
	  { label: 'Prompt', value: 'prompt' },
	  { label: '模块', value: 'module' },
	  { label: '映射名', value: 'mapping' },
	]

	const endpointOptions = computed(() => store.endpointOptions)
	const endpointLabelById = computed(() => {
	  const map = new Map()
	  ;(models.value || []).forEach((endpoint) => {
	    if (!endpoint) return
	    map.set(
	      endpoint.id,
	      endpoint.name || endpoint.model || endpoint.base_url || String(endpoint.id)
	    )
	  })
	  return map
	})
	const modelOptions = computed(() =>
	  store.modelCandidates.map((name) => ({ label: name, value: name }))
	)
	const promptOptions = computed(() =>
	  prompts.value.map((item) => ({ label: item.name, value: String(item.id), raw: item }))
	)
	const scopeLabelMap = computed(() => {
	  const map = new Map()
	  scopeOptions.forEach((opt) => map.set(opt.value, opt.label))
	  return map
	})

	function scopeLabel(scopeType) {
	  return scopeLabelMap.value.get(scopeType) || scopeType
	}

	function preferredEndpointId(record) {
	  const meta = record?.metadata || {}
	  return meta.preferred_endpoint_id ?? meta.endpoint_id ?? meta.endpointId ?? null
	}

	function endpointLabel(record) {
	  const id = preferredEndpointId(record)
	  if (!id) return '--'
	  return endpointLabelById.value.get(id) || String(id)
	}

	watch(
	  () => formModel.scope_type,
	  (scope) => {
    if (scope === 'prompt') {
      formModel.metadata = { type: 'prompt' }
    }
  }
)

	function openCreate() {
	  Object.assign(formModel, {
	    scope_type: 'mapping',
	    scope_key: '',
	    name: '',
	    default_model: null,
	    candidates: [],
	    metadata: {},
	  })
	  endpointSelection.value = null
	  isEdit.value = false
	  modalVisible.value = true
	}

	function openEdit(record) {
	  const preferred = preferredEndpointId(record)
	  Object.assign(formModel, {
	    scope_type: record.scope_type,
	    scope_key: record.scope_key,
	    name: record.name,
	    default_model: record.default_model,
	    candidates: [...(record.candidates || [])],
	    metadata: record.metadata || {},
	  })
	  endpointSelection.value = preferred || null
	  isEdit.value = true
	  modalVisible.value = true
	}

function handlePromptChange(value) {
  const option = promptOptions.value.find((item) => item.value === value)
  if (option) {
    formModel.name = option.label
    formModel.scope_key = option.value
  }
	}

	function _formatExportTs() {
	  const d = new Date()
	  const pad = (n) => String(n).padStart(2, '0')
	  return (
	    `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}` +
	    `-${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`
	  )
	}

	function _downloadJson(filename, payload) {
	  const json = JSON.stringify(payload, null, 2)
	  const blob = new Blob([json], { type: 'application/json;charset=utf-8' })
	  const url = URL.createObjectURL(blob)
	  const a = document.createElement('a')
	  a.href = url
	  a.download = filename
	  a.click()
	  URL.revokeObjectURL(url)
	}

	function handleExportLocal() {
	  const exported = (mappings.value || []).map((item) => ({
	    id: item?.id ?? null,
	    scope_type: item?.scope_type ?? null,
	    scope_key: item?.scope_key ?? null,
	    name: item?.name ?? null,
	    default_model: item?.default_model ?? null,
	    candidates: Array.isArray(item?.candidates) ? item.candidates : [],
	    is_active: item?.is_active ?? true,
	    updated_at: item?.updated_at ?? null,
	    source: item?.source ?? null,
	    metadata: item?.metadata && typeof item.metadata === 'object' ? item.metadata : {},
	  }))
	  _downloadJson(`model-mappings-${_formatExportTs()}.json`, {
	    exported_at: new Date().toISOString(),
	    mappings: exported,
	  })
	  message.success('已导出本地 JSON')
	}

  function triggerImportLocal() {
    importInputRef.value?.click()
  }

  async function handleImportLocalChange(event) {
    const file = event?.target?.files?.[0]
    if (!file) return
    importingLocal.value = true
    try {
      const result = await store.importMappingsLocal(file)
      const imported = Number(result?.imported_count || 0)
      const skipped = Number(result?.skipped_count || 0)
      message.success(`导入完成：成功 ${imported} 条，跳过 ${skipped} 条`)
      if (Array.isArray(result?.errors) && result.errors.length) {
        const preview = result.errors
          .slice(0, 5)
          .map((item) => `#${item.index ?? '-'} ${item.reason || 'unknown_error'}`)
          .join('\n')
        dialog.warning({
          title: '部分条目导入失败',
          content:
            preview + (result.errors.length > 5 ? `\n... 还有 ${result.errors.length - 5} 条` : ''),
        })
      }
    } catch (error) {
      message.error('导入失败：' + (error?.message || '未知错误'))
    } finally {
      importingLocal.value = false
      if (event?.target) event.target.value = ''
    }
  }

	async function handleSyncToSupabase() {
	  try {
	    const result = await store.syncMappingsToSupabase()
	    const status = String(result?.status || '')
	    if (status.startsWith('skipped:')) {
	      message.warning(`已跳过同步：${status}`)
	      return
	    }
	    message.success(`同步成功：已同步 ${result?.synced_count || 0} 条映射到 Supabase`)
	  } catch (error) {
	    message.error('同步失败：' + (error?.message || '未知错误'))
	  }
	}

  async function handleOverwriteSupabase() {
    dialog.warning({
      title: '确认覆盖 Supabase',
      content: '将以本地映射覆盖 Supabase（并删除 Supabase 中本地不存在的映射）。建议先导出本地 JSON 备份。',
      positiveText: '覆盖',
      negativeText: '取消',
      async onPositiveClick() {
        try {
          const result = await store.syncMappings({ direction: 'push', deleteMissing: true })
          const pushed = result?.push || {}
          const status = String(pushed?.status || '')
          if (status.startsWith('skipped:')) {
            message.warning(`已跳过同步：${status}`)
            return
          }
          message.success(`覆盖成功：已同步 ${pushed?.synced_count || 0} 条，删除 ${pushed?.deleted_count || 0} 条`)
        } catch (error) {
          message.error('覆盖失败：' + (error?.message || '未知错误'))
        }
      },
    })
  }

  async function handlePullFromSupabase() {
    dialog.warning({
      title: '确认从 Supabase 拉取',
      content: '将从 Supabase 拉取映射并覆盖本地（不会删除本地多余项）。建议先导出本地 JSON 备份。',
      positiveText: '拉取',
      negativeText: '取消',
      async onPositiveClick() {
        try {
          const pulled = await store.pullMappingsFromSupabase({ overwrite: true })
          const status = String(pulled?.status || '')
          if (status.startsWith('skipped:')) {
            message.warning(`已跳过拉取：${status}`)
            return
          }
          await store.loadMappings()
          message.success(`拉取成功：更新 ${pulled?.pulled_count || 0} 条，跳过 ${pulled?.skipped_count || 0} 条`)
        } catch (error) {
          message.error('拉取失败：' + (error?.message || '未知错误'))
        }
      },
    })
  }

	async function handleSubmit() {
	  await store.saveMapping({
    scope_type: formModel.scope_type,
    scope_key: formModel.scope_key,
    name: formModel.name,
    default_model: formModel.default_model,
    candidates: formModel.candidates,
    metadata: formModel.metadata,
    is_active: true,
  })
  window.$message?.success('映射已保存')
	  modalVisible.value = false
	}

function ensureDefaultInCandidates(value) {
  if (value && !formModel.candidates.includes(value)) {
    formModel.candidates.push(value)
  }
}

	function handleEndpointPick(value) {
	  endpointSelection.value = value
	  if (value) formModel.metadata = { ...(formModel.metadata || {}), preferred_endpoint_id: value }
	  else if (formModel.metadata) delete formModel.metadata.preferred_endpoint_id
	  const endpoint = models.value.find((item) => item.id === value)
	  if (!endpoint) return
	  const candidateSet = new Set(formModel.candidates)
	  if (Array.isArray(endpoint.model_list) && endpoint.model_list.length) {
    endpoint.model_list.forEach((model) => {
      if (model) candidateSet.add(model)
    })
  }
  if (endpoint.model) {
    candidateSet.add(endpoint.model)
  }
  formModel.candidates = Array.from(candidateSet)
  if (!formModel.default_model && formModel.candidates.length) {
    ;[formModel.default_model] = formModel.candidates
  }
}

const defaultModalVisible = ref(false)
const defaultModalState = reactive({
  id: null,
  candidates: [],
  value: null,
})

function openDefaultModal(record) {
  if (!record.candidates?.length) {
    message.error('当前映射没有候选模型，请先编辑配置。')
    return
  }
  defaultModalState.id = record.id
  defaultModalState.candidates = record.candidates
  defaultModalState.value = record.default_model || record.candidates[0]
  defaultModalVisible.value = true
}

async function confirmDefault() {
  if (!defaultModalState.id) return
  await store.activateMapping(defaultModalState.id, defaultModalState.value)
  window.$message?.success('默认模型已更新')
  defaultModalVisible.value = false
}

function handleDeleteMapping(record) {
  const id = record?.id
  if (!id) return
  dialog.warning({
    title: '确认删除',
    content: `将删除映射：${id}`,
    positiveText: '删除',
    negativeText: '取消',
    async onPositiveClick() {
      try {
        await store.deleteMapping(id)
        message.success('已删除')
      } catch (error) {
        message.error('删除失败')
      }
    },
  })
}

	onMounted(() => {
	  store.loadModels()
	  store.loadBlockedModels()
	  store.loadPrompts()
	  store.loadMappings()
	})
</script>

<template>
	  <NSpace vertical size="large">
	    <NCard title="模型映射" size="small" :loading="mappingsLoading">
	      <NSpace justify="space-between" align="center" class="mb-3">
	        <NSpace>
	          <NButton type="primary" @click="openCreate">新增映射</NButton>
	          <NButton secondary :loading="importingLocal" @click="triggerImportLocal"
	            >导入本地 JSON</NButton
	          >
	          <NButton secondary @click="handleExportLocal">导出本地 JSON</NButton>
	          <NButton secondary :loading="syncMappingsLoading" @click="handleSyncToSupabase"
	            >同步到 Supabase</NButton
	          >
	          <NButton secondary :loading="syncMappingsLoading" @click="handleOverwriteSupabase"
	            >覆盖 Supabase</NButton
	          >
	          <NButton secondary :loading="syncMappingsLoading" @click="handlePullFromSupabase"
	            >从 Supabase 拉取</NButton
	          >
	        </NSpace>
	        <NButton secondary :loading="mappingsLoading" @click="store.loadMappings()">刷新</NButton>
	      </NSpace>
	      <input
	        ref="importInputRef"
	        type="file"
	        accept="application/json"
	        style="display: none"
	        @change="handleImportLocalChange"
	      />
	      <NTable :loading="mappingsLoading" :single-line="false" class="mt-4" size="small" striped>
	        <thead>
	          <tr>
	            <th style="width: 160px">业务域</th>
	            <th style="width: 200px">对象</th>
	            <th style="width: 220px">API</th>
	            <th style="width: 200px">默认模型</th>
	            <th>候选模型</th>
	            <th style="width: 180px">更新时间</th>
	            <th style="width: 180px">操作</th>
	          </tr>
	        </thead>
	        <tbody>
	          <tr v-if="!mappings.length">
	            <td colspan="7" class="py-6 text-center text-gray-500">
	              <NEmpty description="暂无映射数据" size="small" />
	            </td>
	          </tr>
	          <tr v-for="item in mappings" :key="item.id">
	            <td>
	              <NTag type="info" size="small" :bordered="false">{{ scopeLabel(item.scope_type) }}</NTag>
	            </td>
	            <td>{{ item.name || item.scope_key }}</td>
	            <td>{{ endpointLabel(item) }}</td>
	            <td>{{ item.default_model || '--' }}</td>
	            <td>
	              <template v-if="item.candidates && item.candidates.length">
                <div v-if="item.candidates.length <= 3">
                  <NSpace wrap>
                    <NTag
                      v-for="model in item.candidates"
                      :key="model"
                      size="small"
                      :bordered="false"
                    >
                      {{ model }}
                    </NTag>
                  </NSpace>
                </div>
                <div v-else>
                  <NTag size="small" :bordered="false"> {{ item.candidates.length }} 个模型 </NTag>
                  <NTooltip>
                    <template #trigger>
                      <NButton text size="tiny" type="info" class="ml-2">查看全部</NButton>
                    </template>
                    <template #default>
                      <div class="max-w-xs">
                        <div v-for="model in item.candidates" :key="model" class="mb-1">
                          {{ model }}
                        </div>
                      </div>
                    </template>
                  </NTooltip>
                </div>
              </template>
              <template v-else>
                <span class="text-gray-400">--</span>
              </template>
            </td>
            <td>{{ item.updated_at || '--' }}</td>
            <td>
              <NSpace>
                <NButton size="small" @click="openEdit(item)">编辑</NButton>
                <NButton size="small" type="primary" @click="openDefaultModal(item)"
                  >设为默认</NButton
                >
                <NButton size="small" type="error" secondary @click="handleDeleteMapping(item)"
                  >删除</NButton
                >
              </NSpace>
            </td>
          </tr>
        </tbody>
      </NTable>
    </NCard>

    <CrudModal
      v-model:visible="modalVisible"
      :title="isEdit ? '编辑映射' : '新增映射'"
      width="640px"
      @save="handleSubmit"
    >
      <NForm
        ref="formRef"
        :model="formModel"
        label-placement="left"
        label-align="left"
        :label-width="110"
      >
        <NFormItem label="业务域" path="scope_type">
          <NSelect
            v-model:value="formModel.scope_type"
            :options="scopeOptions"
            style="width: 100%"
          />
        </NFormItem>
        <NFormItem v-if="formModel.scope_type === 'prompt'" label="选择 Prompt" path="scope_key">
          <NSelect
            v-model:value="formModel.scope_key"
            :loading="promptsLoading"
            :options="promptOptions"
            filterable
            style="width: 100%"
            @update:value="handlePromptChange"
          />
        </NFormItem>
	        <NFormItem v-else label="业务键" path="scope_key">
	          <NInput
	            v-model:value="formModel.scope_key"
	            placeholder="映射名（客户端 model）：例如 xai / deepseek / gpt-5"
	            style="width: 100%"
	          />
	        </NFormItem>
        <NFormItem label="名称" path="name">
          <NInput v-model:value="formModel.name" placeholder="显示名称" style="width: 100%" />
        </NFormItem>
	        <NFormItem label="绑定 API（可选）">
	          <NSelect
	            v-model:value="endpointSelection"
	            :options="endpointOptions"
	            placeholder="选择端点：用于路由偏好 & 快速导入候选模型"
	            filterable
	            clearable
	            style="width: 100%"
	            @update:value="handleEndpointPick"
	          />
	        </NFormItem>
        <NFormItem label="默认模型" path="default_model">
          <NSelect
            v-model:value="formModel.default_model"
            :options="modelOptions"
            filterable
            clearable
            style="width: 100%"
            @update:value="ensureDefaultInCandidates"
          />
        </NFormItem>
        <NFormItem label="候选模型" path="candidates">
          <NSelect
            v-model:value="formModel.candidates"
            :options="modelOptions"
            filterable
            clearable
            multiple
            style="width: 100%"
          />
        </NFormItem>
      </NForm>
    </CrudModal>

    <NModal v-model:show="defaultModalVisible" preset="dialog" title="选择默认模型">
      <NRadioGroup v-model:value="defaultModalState.value">
        <NSpace vertical>
          <NRadio
            v-for="candidate in defaultModalState.candidates"
            :key="candidate"
            :value="candidate"
          >
            {{ candidate }}
          </NRadio>
        </NSpace>
      </NRadioGroup>
      <template #action>
        <NSpace justify="end">
          <NButton @click="defaultModalVisible = false">取消</NButton>
          <NButton type="primary" @click="confirmDefault">确认</NButton>
        </NSpace>
      </template>
    </NModal>
  </NSpace>
</template>

<style scoped>
.mt-4 {
  margin-top: 16px;
}
.ml-2 {
  margin-left: 8px;
}
.mb-1 {
  margin-bottom: 4px;
}
.max-w-xs {
  max-width: 320px;
}
.text-gray-400 {
  color: #9ca3af;
}
</style>
