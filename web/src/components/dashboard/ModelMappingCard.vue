<template>
  <n-card title="模型映射管理">
    <n-space vertical :size="12">
      <!-- 操作按钮 -->
      <n-space justify="space-between">
        <n-space>
          <n-button type="primary" size="small" @click="showAddModal = true">
            <template #icon>
              <HeroIcon name="plus" :size="16" />
            </template>
            新增映射
          </n-button>
          <n-button secondary size="small" :loading="diagnosing" @click="handleDiagnose">
            <template #icon>
              <HeroIcon name="wrench-screwdriver" :size="16" />
            </template>
            诊断模型
          </n-button>
          <n-button secondary size="small" :loading="syncing" @click="handleSyncToSupabase">
            <template #icon>
              <HeroIcon name="cloud-arrow-up" :size="16" />
            </template>
            同步到 Supabase
          </n-button>
        </n-space>
        <n-button secondary size="small" :loading="loading" @click="loadMappings">
          <template #icon>
            <HeroIcon name="arrow-path" :size="16" />
          </template>
          刷新
        </n-button>
      </n-space>

      <!-- 映射列表 -->
      <n-data-table
        :columns="columns"
        :data="mappings"
        :loading="loading"
        :pagination="false"
        size="small"
        :max-height="400"
      />

      <!-- 新增/编辑弹窗 -->
  <n-modal v-model:show="showAddModal" preset="dialog" title="新增模型映射">
    <n-form ref="formRef" :model="formData" label-placement="left" label-width="100">
      <n-form-item label="业务域类型" path="scope_type">
        <n-select
          v-model:value="formData.scope_type"
          :options="scopeTypeOptions"
          placeholder="选择业务域类型"
        />
      </n-form-item>
      <n-form-item label="业务域标识" path="scope_key">
        <n-input v-model:value="formData.scope_key" :placeholder="scopeKeyPlaceholder" />
      </n-form-item>
      <n-form-item label="名称" path="name">
        <n-input v-model:value="formData.name" placeholder="输入映射名称" />
      </n-form-item>
      <n-form-item label="绑定 API（可选）">
        <n-select
          v-model:value="endpointSelection"
          :options="endpointOptions"
          placeholder="选择端点：用于路由偏好 & 快速导入候选模型"
          filterable
          clearable
          @update:value="handleEndpointPick"
        />
      </n-form-item>
      <n-form-item label="默认模型" path="default_model">
        <n-select
          v-model:value="formData.default_model"
          :options="modelCandidateOptions"
              placeholder="选择默认模型"
              filterable
              tag
            />
          </n-form-item>
          <n-form-item label="候选模型" path="candidates">
            <n-select
              v-model:value="formData.candidates"
              :options="modelCandidateOptions"
              placeholder="选择候选模型"
              filterable
              tag
              multiple
            />
          </n-form-item>
        </n-form>
        <template #action>
          <n-space justify="end">
            <n-button @click="showAddModal = false">取消</n-button>
            <n-button type="primary" :loading="saving" @click="handleSave">保存</n-button>
          </n-space>
        </template>
      </n-modal>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { NButton, NTag, NSpace, useDialog, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'
import HeroIcon from '@/components/common/HeroIcon.vue'

defineOptions({ name: 'ModelMappingCard' })

const emit = defineEmits(['mapping-change'])

const store = useAiModelSuiteStore()
const { mappings, mappingsLoading, modelCandidates, models, syncMappingsLoading } = storeToRefs(store)
const message = useMessage()
const dialog = useDialog()

const loading = computed(() => mappingsLoading.value)
const syncing = computed(() => syncMappingsLoading.value)
const showAddModal = ref(false)
const saving = ref(false)
const diagnosing = ref(false)
const formRef = ref(null)

const formData = ref({
  scope_type: 'mapping',
  scope_key: '',
  name: '',
  default_model: null,
  candidates: [],
  metadata: {},
})

const scopeTypeOptions = [
  { label: 'User（普通用户）', value: 'user' },
  { label: 'Premium User（高级用户）', value: 'premium_user' },
  { label: 'Mapping（映射名）', value: 'mapping' },
  { label: 'Global（全局）', value: 'global' },
]

const scopeKeyPlaceholder = computed(() => {
  if (formData.value.scope_type === 'mapping') return '映射名（客户端 model）：例如 xai / deepseek / gpt-5'
  return '输入业务域唯一标识'
})

const modelCandidateOptions = computed(() => {
  return modelCandidates.value.map((model) => ({
    label: model,
    value: model,
  }))
})

const endpointOptions = computed(() => store.endpointOptions)
const endpointLabelById = computed(() => {
  const map = new Map()
  ;(models.value || []).forEach((endpoint) => {
    if (!endpoint) return
    map.set(endpoint.id, endpoint.name || endpoint.model || endpoint.base_url || String(endpoint.id))
  })
  return map
})

const endpointSelection = ref(null)

function preferredEndpointId(row) {
  const meta = row?.metadata || {}
  return meta.preferred_endpoint_id ?? meta.endpoint_id ?? meta.endpointId ?? null
}

function endpointLabel(row) {
  const id = preferredEndpointId(row)
  if (!id) return '--'
  return endpointLabelById.value.get(id) || String(id)
}

function handleEndpointPick(value) {
  endpointSelection.value = value
  if (value) formData.value.metadata = { ...(formData.value.metadata || {}), preferred_endpoint_id: value }
  else if (formData.value.metadata) delete formData.value.metadata.preferred_endpoint_id

  const endpoint = (models.value || []).find((item) => item.id === value)
  if (!endpoint) return
  const candidateSet = new Set(formData.value.candidates || [])
  if (Array.isArray(endpoint.model_list) && endpoint.model_list.length) {
    endpoint.model_list.forEach((model) => {
      if (model) candidateSet.add(model)
    })
  }
  if (endpoint.model) candidateSet.add(endpoint.model)
  formData.value.candidates = Array.from(candidateSet)
  if (!formData.value.default_model && formData.value.candidates.length) {
    ;[formData.value.default_model] = formData.value.candidates
  }
}

const columns = [
  {
    title: '业务域',
    key: 'scope_type',
    width: 100,
    render: (row) =>
      h(NTag, { type: 'info', size: 'small', bordered: false }, { default: () => row.scope_type }),
  },
  {
    title: '对象',
    key: 'name',
    width: 150,
    render: (row) => row.name || row.scope_key,
  },
  {
    title: 'API',
    key: 'preferred_endpoint',
    width: 180,
    render: (row) => endpointLabel(row),
  },
  {
    title: '默认模型',
    key: 'default_model',
    width: 150,
    render: (row) => row.default_model || '--',
  },
  {
    title: '候选模型',
    key: 'candidates',
    render: (row) => {
      if (!row.candidates || row.candidates.length === 0) return '--'
      if (row.candidates.length <= 3) {
        return h(
          NSpace,
          { wrap: true, size: 4 },
          {
            default: () =>
              row.candidates.map((model) =>
                h(NTag, { size: 'small', bordered: false }, { default: () => model })
              ),
          }
        )
      }
      return `${row.candidates.length} 个模型`
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) =>
      h(
        NButton,
        {
          size: 'small',
          type: 'error',
          text: true,
          onClick: () => handleDelete(row),
        },
        { default: () => '删除' }
      ),
  },
]

async function loadMappings() {
  try {
    await store.loadMappings()
    emit('mapping-change', mappings.value)
  } catch (error) {
    message.error('加载映射列表失败')
  }
}

async function handleSave() {
  saving.value = true
  try {
    await store.saveMapping(formData.value)
    message.success('保存成功')
    showAddModal.value = false
    formData.value = {
      scope_type: 'mapping',
      scope_key: '',
      name: '',
      default_model: null,
      candidates: [],
      metadata: {},
    }
    endpointSelection.value = null
    await loadMappings()
  } catch (error) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  // 已在后端实现 DELETE /llm/model-groups/{id}
  const id = row?.id
  if (!id) return

  dialog.warning({
    title: '确认删除',
    content: `将删除映射：${id}。该操作会影响 App 侧可选模型与路由解析。`,
    positiveText: '删除',
    negativeText: '取消',
    async onPositiveClick() {
      try {
        await store.deleteMapping(id)
        message.success('已删除')
        emit('mapping-change', mappings.value)
      } catch (error) {
        message.error('删除失败')
      }
    },
  })
}

/**
 * 诊断所有模型可用性
 */
async function handleDiagnose() {
  diagnosing.value = true
  try {
    const { diagnoseModels } = await import('@/api/aiModelSuite')
    await diagnoseModels()
    message.success('已触发端点检测（后台刷新中）')
    // 刷新模型候选列表（端点状态/模型列表会异步更新）
    await store.loadModels()
  } catch (error) {
    message.error('诊断失败：' + (error.message || '未知错误'))
  } finally {
    diagnosing.value = false
  }
}

/**
 * 同步映射到 Supabase
 */
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
    message.error('同步失败：' + (error.message || '未知错误'))
  }
}

onMounted(() => {
  loadMappings()
  // 加载模型候选列表
  if (!store.models.length) {
    store.loadModels()
  }
})
</script>

<style scoped>
.n-card {
  height: 100%;
}
</style>
