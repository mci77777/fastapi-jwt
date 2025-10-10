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
  useMessage,
} from 'naive-ui'
import { storeToRefs } from 'pinia'

import { useAiModelSuiteStore } from '@/store'

defineOptions({ name: 'AiModelMapping' })

const store = useAiModelSuiteStore()
const { mappings, mappingsLoading, models, prompts, promptsLoading } = storeToRefs(store)
const message = useMessage()

const modalVisible = ref(false)
const isEdit = ref(false)
const formRef = ref(null)
const formModel = reactive({
  scope_type: 'prompt',
  scope_key: '',
  name: '',
  default_model: null,
  candidates: [],
  metadata: {},
})
const endpointSelection = ref(null)

const scopeOptions = [
  { label: 'Prompt', value: 'prompt' },
  { label: '模块', value: 'module' },
  { label: '租户', value: 'tenant' },
]

const endpointOptions = computed(() => store.endpointOptions)
const modelOptions = computed(() => store.modelCandidates.map((name) => ({ label: name, value: name })))
const promptOptions = computed(() => prompts.value.map((item) => ({ label: item.name, value: String(item.id), raw: item })))

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
    scope_type: 'prompt',
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
  Object.assign(formModel, {
    scope_type: record.scope_type,
    scope_key: record.scope_key,
    name: record.name,
    default_model: record.default_model,
    candidates: [...(record.candidates || [])],
    metadata: record.metadata || {},
  })
  endpointSelection.value = null
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

onMounted(() => {
  store.loadModels()
  store.loadPrompts()
  store.loadMappings()
})
</script>


<template>
  <NSpace vertical size="large">
    <NCard title="模型映射" size="small" :loading="mappingsLoading">
      <NSpace justify="space-between" align="center" class="mb-3">
        <NButton type="primary" @click="openCreate">新增映射</NButton>
        <NButton secondary @click="store.loadMappings()" :loading="mappingsLoading">刷新</NButton>
      </NSpace>
      <NTable :loading="mappingsLoading" :single-line="false" class="mt-4" size="small" striped>
        <thead>
          <tr>
            <th style="width: 160px">业务域</th>
            <th style="width: 200px">对象</th>
            <th style="width: 200px">默认模型</th>
            <th>候选模型</th>
            <th style="width: 180px">更新时间</th>
            <th style="width: 180px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!mappings.length">
            <td colspan="6" class="text-center text-gray-500 py-6">
              <NEmpty description="暂无映射数据" size="small" />
            </td>
          </tr>
          <tr v-for="item in mappings" :key="item.id">
            <td><NTag type="info" size="small" bordered={false}>{{ item.scope_type }}</NTag></td>
            <td>{{ item.name || item.scope_key }}</td>
            <td>{{ item.default_model || '--' }}</td>
            <td>
              <NSpace wrap>
                <NTag v-for="model in item.candidates" :key="model" size="small" bordered={false}>{{ model }}</NTag>
              </NSpace>
            </td>
            <td>{{ item.updated_at || '--' }}</td>
            <td>
              <NSpace>
                <NButton size="small" @click="openEdit(item)">编辑</NButton>
                <NButton size="small" type="primary" @click="openDefaultModal(item)">设为默认</NButton>
              </NSpace>
            </td>
          </tr>
        </tbody>
      </NTable>
    </NCard>

    <NModal v-model:show="modalVisible" preset="card" :title="isEdit ? '编辑映射' : '新增映射'" class="w-96">
      <NForm ref="formRef" :model="formModel" label-placement="left" label-width="90">
        <NFormItem label="业务域" path="scope_type">
          <NSelect v-model:value="formModel.scope_type" :options="scopeOptions" />
        </NFormItem>
        <NFormItem v-if="formModel.scope_type === 'prompt'" label="选择 Prompt" path="scope_key">
          <NSelect
            :loading="promptsLoading"
            v-model:value="formModel.scope_key"
            :options="promptOptions"
            filterable
            @update:value="handlePromptChange"
          />
        </NFormItem>
        <NFormItem v-else label="业务键" path="scope_key">
          <NInput v-model:value="formModel.scope_key" placeholder="请输入唯一键" />
        </NFormItem>
        <NFormItem label="名称" path="name">
          <NInput v-model:value="formModel.name" placeholder="显示名称" />
        </NFormItem>
        <NFormItem label="候选来源">
          <NSelect
            v-model:value="endpointSelection"
            :options="endpointOptions"
            placeholder="可选：选择端点快速导入候选模型"
            filterable
            clearable
            @update:value="handleEndpointPick"
          />
        </NFormItem>
        <NFormItem label="默认模型" path="default_model">
          <NSelect
            v-model:value="formModel.default_model"
            :options="modelOptions"
            filterable
            clearable
            @update:value="ensureDefaultInCandidates"
          />
        </NFormItem>
        <NFormItem label="候选模型" path="candidates">
          <NSelect v-model:value="formModel.candidates" multiple :options="modelOptions" filterable clearable />
        </NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="modalVisible = false">取消</NButton>
          <NButton type="primary" @click="handleSubmit">保存</NButton>
        </NSpace>
      </template>
    </NModal>

    <NModal v-model:show="defaultModalVisible" preset="dialog" title="选择默认模型">
      <NRadioGroup v-model:value="defaultModalState.value">
        <NSpace vertical>
          <NRadio v-for="candidate in defaultModalState.candidates" :key="candidate" :value="candidate">
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
</style>

