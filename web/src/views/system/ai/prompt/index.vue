<script setup>
import { computed, h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  NTooltip,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import TheIcon from '@/components/icon/TheIcon.vue'

import { renderIcon } from '@/utils'
import { useCRUD } from '@/composables'
import api from '@/api'
import { useUserStore } from '@/store'

const userStore = useUserStore()

const isSuperuser = computed(() => userStore.userInfo?.is_superuser)

const $table = ref(null)
const queryItems = ref({ keyword: null, only_active: null })
const vPermission = resolveDirective('permission')

const statusOptions = [
  { label: '全部', value: null },
  { label: '激活', value: true },
  { label: '未激活', value: false },
]

const initForm = {
  name: '',
  version: '',
  system_prompt: '',
  tools_json_text: '',
  description: '',
  is_active: false,
}

function toPayload(form) {
  const payload = {
    name: form.name?.trim(),
    version: form.version?.trim(),
    system_prompt: form.system_prompt?.trim(),
    description: form.description?.trim() || undefined,
    is_active: form.is_active,
  }
  if (form.tools_json_text && form.tools_json_text.trim().length) {
    payload.tools_json = form.tools_json_text
  } else {
    payload.tools_json = null
  }
  return payload
}

function normalizeForm(row) {
  return {
    id: row.id,
    name: row.name,
    version: row.version,
    system_prompt: row.system_prompt,
    description: row.description,
    is_active: row.is_active,
    tools_json_text: row.tools_json ? JSON.stringify(row.tools_json, null, 2) : '',
  }
}

const testModalVisible = ref(false)
const testPrompt = ref({})

function openTestPrompt(row) {
  testPrompt.value = {
    name: row.name,
    version: row.version,
    system_prompt: row.system_prompt,
    tools_json: row.tools_json,
  }
  testModalVisible.value = true
}

async function handleActivate(row) {
  await $dialog.confirm({
    title: '提示',
    content: `确认激活 Prompt「${row.name}」？`,
    async confirm() {
      await api.activateAIPrompt(row.id)
      $message.success('已激活')
      $table.value?.handleSearch()
    },
  })
}

const formRules = {
  name: [{ required: true, message: '请输入 Prompt 名称', trigger: ['input', 'blur'] }],
  version: [{ required: true, message: '请输入 Prompt 版本', trigger: ['input', 'blur'] }],
  system_prompt: [{ required: true, message: '请输入系统 Prompt', trigger: ['input', 'blur'] }],
  tools_json_text: [
    {
      validator(_, value) {
        if (!value || !value.trim()) return true
        try {
          JSON.parse(value)
          return true
        } catch (error) {
          return new Error('工具定义需为合法 JSON')
        }
      },
      trigger: ['blur'],
    },
  ],
}

const columns = [
  {
    title: '名称',
    key: 'name',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '版本',
    key: 'version',
    align: 'center',
  },
  {
    title: '激活',
    key: 'is_active',
    align: 'center',
    width: 80,
    render(row) {
      return h(
        NTag,
        { type: row.is_active ? 'success' : 'default', bordered: false },
        { default: () => (row.is_active ? '是' : '否') },
      )
    },
  },
  {
    title: '最近更新人',
    key: 'updated_by',
    align: 'center',
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
    align: 'center',
    width: 200,
    render(row) {
      const editBtn = withDirectives(
        h(
          NButton,
          {
            size: 'small',
            type: 'primary',
            style: 'margin-right: 8px;',
            onClick: () => handleEditPrompt(row),
          },
          { default: () => '编辑', icon: renderIcon('material-symbols:edit', { size: 16 }) },
        ),
        [[vPermission, 'put/api/v1/llm/prompts/{prompt_id}']],
      )

      const activateBtn = withDirectives(
        h(
          NButton,
          {
            size: 'small',
            type: 'warning',
            style: 'margin-right: 8px;',
            disabled: row.is_active,
            onClick: () => handleActivate(row),
          },
          { default: () => '激活', icon: renderIcon('mdi:lightning-bolt', { size: 16 }) },
        ),
        [[vPermission, 'post/api/v1/llm/prompts/{prompt_id}/activate']],
      )

      const testBtn = withDirectives(
        h(
          NButton,
          {
            size: 'small',
            onClick: () => openTestPrompt(row),
          },
          { default: () => '测试', icon: renderIcon('material-symbols:science', { size: 16 }) },
        ),
        [[vPermission, 'get/api/v1/llm/prompts/{prompt_id}']],
      )

      return h(NSpace, { justify: 'center', size: 4 }, () => [editBtn, activateBtn, testBtn])
    },
  },
]

const {
  modalVisible,
  modalTitle,
  modalLoading,
  modalForm,
  modalFormRef,
  handleAdd,
  handleSave,
  handleEdit: baseHandleEdit,
  modalAction,
} = useCRUD({
  name: 'Prompt',
  initForm,
  doCreate: async (form) => {
    const payload = toPayload(form)
    await api.createAIPrompt(payload)
  },
  doUpdate: async (form) => {
    const payload = toPayload(form)
    await api.updateAIPrompt(form.id, payload)
  },
  refresh: () => $table.value?.handleSearch(),
})

function handleEditPrompt(row) {
  baseHandleEdit(normalizeForm(row))
}

function beforeSave() {
  return new Promise((resolve, reject) => {
    modalFormRef.value?.validate((errors) => {
      if (errors) {
        reject(errors)
      } else {
        resolve()
      }
    })
  })
}

async function submitForm() {
  try {
    await beforeSave()
    await handleSave()
  } catch (error) {
    // no-op, validation errors already shown
  }
}

onMounted(() => {
  if (!isSuperuser.value) {
    $message.error('当前页面仅限超级管理员访问')
    return
  }
  $table.value?.handleSearch()
})
</script>

<template>
  <CommonPage show-footer title="AI 配置 · Prompt">
    <template #action>
      <NButton
        v-permission="'post/api/v1/llm/prompts'"
        type="primary"
        class="float-right mr-15"
        @click="handleAdd"
      >
        <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新增 Prompt
      </NButton>
    </template>
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getAIPrompts"
    >
      <template #queryBar>
        <QueryBarItem label="名称" :label-width="40">
          <NInput
            v-model:value="queryItems.keyword"
            clearable
            placeholder="请输入名称或描述"
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
      @save="submitForm"
    >
      <NForm
        ref="modalFormRef"
        :model="modalForm"
        :rules="formRules"
        label-placement="left"
        label-align="left"
        :label-width="100"
      >
        <NFormItem label="名称" path="name">
          <NInput v-model:value="modalForm.name" placeholder="请输入 Prompt 名称" />
        </NFormItem>
        <NFormItem label="版本" path="version">
          <NInput v-model:value="modalForm.version" placeholder="请输入版本号" />
        </NFormItem>
        <NFormItem label="系统 Prompt" path="system_prompt">
          <NInput
            v-model:value="modalForm.system_prompt"
            type="textarea"
            :autosize="{ minRows: 6 }"
            placeholder="请输入系统 Prompt"
          />
        </NFormItem>
        <NFormItem label="工具 JSON" path="tools_json_text">
          <NInput
            v-model:value="modalForm.tools_json_text"
            type="textarea"
            :autosize="{ minRows: 4 }"
            placeholder="请输入工具定义 JSON（可选）"
          />
        </NFormItem>
        <NFormItem label="描述">
          <NInput v-model:value="modalForm.description" placeholder="简要描述（可选）" />
        </NFormItem>
        <NFormItem label="设置为激活">
          <NSwitch v-model:value="modalForm.is_active" />
        </NFormItem>
      </NForm>
    </CrudModal>

    <NModal
      v-model:show="testModalVisible"
      preset="dialog"
      title="Prompt 测试"
      style="width: 600px"
    >
      <NSpace vertical size="large">
        <div>
          <strong>名称</strong>
          <div>{{ testPrompt.name }}</div>
        </div>
        <div>
          <strong>版本</strong>
          <div>{{ testPrompt.version }}</div>
        </div>
        <div>
          <strong>系统 Prompt</strong>
          <NTooltip trigger="hover">
            <template #trigger>
              <NInput
                :value="testPrompt.system_prompt"
                type="textarea"
                :autosize="{ minRows: 6 }"
                readonly
              />
            </template>
            <span>只读预览，实际调用将在 Phase 3 通过聊天接口完成。</span>
          </NTooltip>
        </div>
        <div v-if="testPrompt.tools_json">
          <strong>工具定义</strong>
          <NInput
            :value="JSON.stringify(testPrompt.tools_json, null, 2)"
            type="textarea"
            :autosize="{ minRows: 4 }"
            readonly
          />
        </div>
      </NSpace>
      <template #action>
        <NButton type="primary" @click="testModalVisible = false">关闭</NButton>
      </template>
    </NModal>
  </CommonPage>
</template>
