<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NForm, NFormItem, NInput, NInputNumber, NSelect, NSwitch, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

import { renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'

defineOptions({ name: 'AIConfigModels' })

const $table = ref(null)
const queryItems = ref({ keyword: null, only_active: null })
const vPermission = resolveDirective('permission')

const statusOptions = [
  { label: '全部', value: null },
  { label: '启用', value: true },
  { label: '停用', value: false },
]

const initForm = {
  id: null,
  name: '',
  model: '',
  base_url: '',
  api_key: '',
  description: '',
  timeout: 60,
  is_active: true,
  is_default: false,
  api_key_masked: '',
}

function normalizePayload(form, isUpdate = false) {
  const payload = {
    name: form.name?.trim(),
    model: form.model?.trim(),
    base_url: form.base_url?.trim(),
    api_key: form.api_key?.trim(),
    description: form.description?.trim(),
    timeout: form.timeout,
    is_active: form.is_active,
    is_default: form.is_default,
  }
  if (!payload.base_url) delete payload.base_url
  if (!payload.description) delete payload.description
  if (!payload.api_key) delete payload.api_key
  if (isUpdate) payload.id = form.id
  return payload
}

function ensureDefaultActive(value) {
  if (value) {
    modalForm.value.is_active = true
  }
}

const {
  modalVisible,
  modalTitle,
  modalLoading,
  modalForm,
  modalFormRef,
  modalAction,
  handleAdd,
  handleSave,
  handleEdit: innerHandleEdit,
} = useCRUD({
  name: '模型',
  initForm,
  doCreate: (form) => api.createAIModel(normalizePayload(form, false)),
  doUpdate: (form) => api.updateAIModel(normalizePayload(form, true)),
  refresh: () => $table.value?.handleSearch(),
})

function openEdit(row) {
  const { api_key_masked = '', created_at, updated_at, ...rest } = row
  innerHandleEdit({ ...rest, api_key: '', api_key_masked })
}

const formRules = {
  name: [
    {
      required: true,
      message: '请输入模型别名',
      trigger: ['input', 'blur'],
    },
  ],
  model: [
    {
      required: true,
      message: '请输入上游模型标识',
      trigger: ['input', 'blur'],
    },
  ],
  timeout: [
    {
      required: true,
      type: 'number',
      message: '请输入超时时间',
      trigger: ['blur', 'change'],
    },
  ],
}

const columns = [
  {
    title: '模型别名',
    key: 'name',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '上游模型',
    key: 'model',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '基础地址',
    key: 'base_url',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '超时(秒)',
    key: 'timeout',
    width: 100,
    align: 'center',
  },
  {
    title: '默认',
    key: 'is_default',
    width: 80,
    align: 'center',
    render(row) {
      return h(
        NTag,
        { type: row.is_default ? 'primary' : 'default', bordered: false },
        { default: () => (row.is_default ? '是' : '否') },
      )
    },
  },
  {
    title: '状态',
    key: 'is_active',
    width: 80,
    align: 'center',
    render(row) {
      return h(
        NTag,
        { type: row.is_active ? 'success' : 'error', bordered: false },
        { default: () => (row.is_active ? '启用' : '停用') },
      )
    },
  },
  {
    title: '密钥',
    key: 'api_key_masked',
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      return row.api_key_masked || '——'
    },
  },
  {
    title: '更新时间',
    key: 'updated_at',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    align: 'center',
    render(row) {
      return withDirectives(
        h(
          NButton,
          {
            size: 'small',
            type: 'primary',
            onClick: () => openEdit(row),
          },
          {
            default: () => '编辑',
            icon: renderIcon('material-symbols:edit', { size: 16 }),
          },
        ),
        [[vPermission, 'put/api/v1/llm/models']],
      )
    },
  },
]

onMounted(() => {
  $table.value?.handleSearch()
})
</script>

<template>
  <CommonPage show-footer title="AI 配置 · 模型">
    <template #action>
      <NButton
        v-permission="'post/api/v1/llm/models'"
        type="primary"
        class="float-right mr-15"
        @click="handleAdd"
      >
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新增模型
      </NButton>
    </template>
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getAIModels"
    >
      <template #queryBar>
        <QueryBarItem label="关键词" :label-width="60">
          <NInput
            v-model:value="queryItems.keyword"
            clearable
            placeholder="按别名或模型搜索"
            @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="状态" :label-width="40">
          <NSelect v-model:value="queryItems.only_active" :options="statusOptions" clearable />
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :loading="modalLoading"
      @save="handleSave"
    >
      <NForm
        ref="modalFormRef"
        :model="modalForm"
        :rules="formRules"
        label-placement="left"
        label-align="left"
        :label-width="100"
      >
        <NFormItem label="模型别名" path="name">
          <NInput v-model:value="modalForm.name" placeholder="请输入模型别名" />
        </NFormItem>
        <NFormItem label="上游模型" path="model">
          <NInput v-model:value="modalForm.model" placeholder="请输入模型 ID" />
        </NFormItem>
        <NFormItem v-if="modalForm.api_key_masked && modalAction === 'edit'" label="当前密钥">
          <NInput :value="modalForm.api_key_masked" disabled />
        </NFormItem>
        <NFormItem label="密钥" path="api_key">
          <NInput
            v-model:value="modalForm.api_key"
            type="password"
            placeholder="留空则保留原值"
            show-password-on="click"
          />
        </NFormItem>
        <NFormItem label="基础地址">
          <NInput v-model:value="modalForm.base_url" placeholder="可覆盖全局 base_url" />
        </NFormItem>
        <NFormItem label="超时(秒)" path="timeout">
          <NInputNumber v-model:value="modalForm.timeout" :min="1" :max="600" />
        </NFormItem>
        <NFormItem label="启用">
          <NSwitch v-model:value="modalForm.is_active" />
        </NFormItem>
        <NFormItem label="设为默认">
          <NSwitch v-model:value="modalForm.is_default" @update:value="ensureDefaultActive" />
        </NFormItem>
        <NFormItem label="描述">
          <NInput v-model:value="modalForm.description" type="textarea" placeholder="可选" />
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
