<template>
  <n-card title="模型映射管理">
    <n-space vertical :size="12">
      <!-- 操作按钮 -->
      <n-space justify="space-between">
        <n-button type="primary" size="small" @click="showAddModal = true">
          <template #icon>
            <HeroIcon name="plus" :size="16" />
          </template>
          新增映射
        </n-button>
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
            <n-input v-model:value="formData.scope_key" placeholder="输入业务域唯一标识" />
          </n-form-item>
          <n-form-item label="名称" path="name">
            <n-input v-model:value="formData.name" placeholder="输入映射名称" />
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
              multiple
              filterable
              tag
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
import { NButton, NTag, NSpace, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'
import HeroIcon from '@/components/common/HeroIcon.vue'

defineOptions({ name: 'ModelMappingCard' })

const emit = defineEmits(['mapping-change'])

const store = useAiModelSuiteStore()
const { mappings, mappingsLoading, modelCandidates } = storeToRefs(store)
const message = useMessage()

const loading = computed(() => mappingsLoading.value)
const showAddModal = ref(false)
const saving = ref(false)
const formRef = ref(null)

const formData = ref({
  scope_type: 'tenant',
  scope_key: '',
  name: '',
  default_model: null,
  candidates: [],
})

const scopeTypeOptions = [
  { label: 'Tenant（租户）', value: 'tenant' },
  { label: 'Prompt（提示词）', value: 'prompt' },
  { label: 'Module（模块）', value: 'module' },
]

const modelCandidateOptions = computed(() => {
  return modelCandidates.value.map((model) => ({
    label: model,
    value: model,
  }))
})

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
      scope_type: 'tenant',
      scope_key: '',
      name: '',
      default_model: null,
      candidates: [],
    }
    await loadMappings()
  } catch (error) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  // 注意：后端暂无删除 API，此处仅为占位
  message.warning('删除功能暂未实现')
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

