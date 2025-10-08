<script setup>
import { computed, h, onMounted, ref, resolveDirective, watch } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NDropdown,
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

defineOptions({ name: 'AIPromptManager' })

const vPermission = resolveDirective('permission')
const $table = ref(null)

const queryItems = ref({ keyword: null, only_active: null })
const statusOptions = [
  { label: '全部', value: null },
  { label: '已启用', value: true },
  { label: '未启用', value: false },
]

const initForm = {
  id: null,
  name: '',
  version: '',
  content: '',
  category: '',
  description: '',
  tools_json_text: '',
  is_active: false,
  auto_sync: false,
}

function normalizeForm(row) {
  return {
    id: row.id,
    name: row.name,
    version: row.version,
    content: row.content,
    category: row.category,
    description: row.description,
    is_active: row.is_active,
    tools_json_text: row.tools_json ? JSON.stringify(row.tools_json, null, 2) : '',
    auto_sync: false,
  }
}

function toPayload(form) {
  const payload = {
    name: form.name?.trim(),
    version: form.version?.trim() || undefined,
    content: form.content?.trim(),
    category: form.category?.trim() || undefined,
    description: form.description?.trim() || undefined,
    is_active: form.is_active,
    auto_sync: form.auto_sync,
  }
  if (form.tools_json_text && form.tools_json_text.trim().length) {
    payload.tools_json = form.tools_json_text
  }
  return payload
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
  name: 'Prompt',
  initForm,
  doCreate: (form) => api.createAIPrompt(toPayload(form)),
  doUpdate: (form) => api.updateAIPrompt(form.id, toPayload(form)),
  refresh: () => {
    $table.value?.handleSearch()
  },
})

function openEdit(row) {
  innerHandleEdit(normalizeForm(row))
}

const formRules = {
  name: [
    {
      required: true,
      message: '请输入名称',
      trigger: ['input', 'blur'],
    },
  ],
  content: [
    {
      required: true,
      message: '请输入 Prompt 内容',
      trigger: ['input', 'blur'],
    },
  ],
}

const columns = [
  {
    title: '名称',
    key: 'name',
    align: 'center',
    ellipsis: { tooltip: true },
    render(row) {
      const tags = []
      if (row.is_active) {
        tags.push(
          h(
            NTag,
            { type: 'success', size: 'small', bordered: false },
            { default: () => '启用' },
          ),
        )
      }
      return h(
        NSpace,
        { align: 'center', justify: 'center', size: 6 },
        [
          h('span', row.name),
          ...tags,
        ],
      )
    },
  },
  {
    title: '版本',
    key: 'version',
    align: 'center',
    width: 100,
    render: (row) => row.version || '--',
  },
  {
    title: '分类',
    key: 'category',
    align: 'center',
    width: 120,
    render: (row) => row.category || '--',
  },
  {
    title: '描述',
    key: 'description',
    align: 'center',
    ellipsis: { tooltip: true },
    render: (row) => row.description || '--',
  },
  {
    title: '最近更新',
    key: 'updated_at',
    align: 'center',
    width: 160,
    render: (row) => row.updated_at || '--',
  },
  {
    title: '操作',
    key: 'actions',
    width: 260,
    align: 'center',
    render(row) {
      const buttons = [
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              type: 'primary',
              onClick: () => openTestModal(row),
            },
            {
              default: () => '测试',
              icon: renderIcon('mdi:robot-love-outline', { size: 16 }),
            },
          ),
          [[vPermission, 'post/api/v1/llm/prompts']],
        ),
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              onClick: () => openEdit(row),
            },
            {
              default: () => '编辑',
              icon: renderIcon('material-symbols:edit-outline-rounded', { size: 16 }),
            },
          ),
          [[vPermission, 'put/api/v1/llm/prompts']],
        ),
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              type: 'success',
              disabled: row.is_active,
              onClick: () => handleActivate(row),
            },
            {
              default: () => '激活',
              icon: renderIcon('mdi:lightning-bolt', { size: 16 }),
            },
          ),
          [[vPermission, 'post/api/v1/llm/prompts/activate']],
        ),
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              type: 'error',
              onClick: () => handleDelete(row),
            },
            {
              default: () => '删除',
              icon: renderIcon('material-symbols:delete-outline', { size: 16 }),
            },
          ),
          [[vPermission, 'delete/api/v1/llm/prompts']],
        ),
      ]
      return h(NSpace, { justify: 'center' }, buttons)
    },
  },
]

async function handleDelete(row) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确认要删除 Prompt「${row.name}」吗？`,
    positiveText: '删除',
    negativeText: '取消',
    positiveButtonProps: { type: 'error' },
    async onPositiveClick() {
      try {
        await api.deleteAIPrompt(row.id)
        window.$message?.success('删除成功')
        $table.value?.handleSearch()
      } catch (error) {
        window.$message?.error(error.message || '删除失败')
      }
    },
  })
}

async function handleActivate(row) {
  try {
    await api.activateAIPrompt(row.id)
    window.$message?.success(`Prompt「${row.name}」已激活`)
    $table.value?.handleSearch()
  } catch (error) {
    window.$message?.error(error.message || '激活失败')
  }
}

const testModalVisible = ref(false)
const testLoading = ref(false)
const testPrompt = ref({})
const aiEndpoints = ref([])
const selectedEndpointId = ref(null)
const selectedModel = ref(null)
const testMessage = ref('')
const testResponse = ref('')
const testHistory = ref([])
const syncPrompting = ref(false)

const availableModels = computed(() => {
  const endpoint = aiEndpoints.value.find((item) => item.id === selectedEndpointId.value)
  if (!endpoint) return []
  const models = endpoint.model_list || []
  if (!models.length && endpoint.model) {
    return [{ label: endpoint.model, value: endpoint.model }]
  }
  return models.map((model) => ({ label: model, value: model }))
})

watch(selectedEndpointId, (value) => {
  if (!value) {
    selectedModel.value = null
    return
  }
  const endpoint = aiEndpoints.value.find((item) => item.id === value)
  if (!endpoint) return
  const models = endpoint.model_list || []
  selectedModel.value = models.length ? models[0] : endpoint.model || null
})

async function loadAIEndpoints() {
  const response = await api.getAIModels({ only_active: true, page_size: 100 })
  aiEndpoints.value = response.data || []
  if (aiEndpoints.value.length && !selectedEndpointId.value) {
    selectedEndpointId.value = aiEndpoints.value[0].id
  }
}

async function loadPromptTests(promptId) {
  try {
    const response = await api.getPromptTests(promptId, { limit: 10 })
    testHistory.value = response.data || []
  } catch (error) {
    testHistory.value = []
    window.$message?.error(error.message || '加载测试历史失败')
  }
}

function openTestModal(row) {
  testPrompt.value = row
  testMessage.value = ''
  testResponse.value = ''
  testHistory.value = []
  selectedEndpointId.value = null
  selectedModel.value = null
  testModalVisible.value = true
  Promise.all([loadAIEndpoints(), loadPromptTests(row.id)]).catch(() => {})
}

async function handleTestPrompt() {
  if (!testMessage.value.trim()) {
    window.$message?.warning('请输入测试消息')
    return
  }
  if (!selectedEndpointId.value) {
    window.$message?.warning('请选择 API 端点')
    return
  }

  try {
    testLoading.value = true
    testResponse.value = ''
    const response = await api.testPrompt({
      prompt_id: testPrompt.value.id,
      endpoint_id: selectedEndpointId.value,
      message: testMessage.value,
      model: selectedModel.value || undefined,
    })
    const result = response.data || {}
    testResponse.value = result.response || '无返回内容'
    await loadPromptTests(testPrompt.value.id)
  } catch (error) {
    window.$message?.error(error.message || '测试失败')
  } finally {
    testLoading.value = false
  }
}

async function handleSyncPrompts(direction) {
  try {
    syncPrompting.value = true
    await api.syncPrompts(direction)
    window.$message?.success('Prompt 同步完成')
    $table.value?.handleSearch()
  } catch (error) {
    window.$message?.error(error.message || '同步失败')
  } finally {
    syncPrompting.value = false
  }
}

const promptSyncOptions = [
  { label: '推送到 Supabase', key: 'push' },
  { label: '从 Supabase 拉取', key: 'pull' },
  { label: '推送后拉取', key: 'both' },
]

onMounted(() => {
  $table.value?.handleSearch()
})
</script>

<template>
  <CommonPage show-footer title="Prompt 模板管理">
    <template #action>
      <NSpace justify="end">
        <NDropdown
          :options="promptSyncOptions"
          trigger="click"
          :loading="syncPrompting"
          @select="handleSyncPrompts"
        >
          <NButton v-permission="'post/api/v1/llm/prompts'" type="primary" :loading="syncPrompting">
            <TheIcon icon="mdi:backup-restore" :size="18" class="mr-5" />同步 Prompt
          </NButton>
        </NDropdown>
        <NButton
          v-permission="'post/api/v1/llm/prompts'"
          type="primary"
          class="float-right"
          @click="handleAdd"
        >
          <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建 Prompt
        </NButton>
      </NSpace>
    </template>

    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getAIPrompts"
    >
      <template #queryBar>
        <QueryBarItem label="关键字" :label-width="60">
          <NInput
            v-model:value="queryItems.keyword"
            clearable
            placeholder="搜索名称或分类"
            @keypress.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="启用" :label-width="50">
          <NSelect
            v-model:value="queryItems.only_active"
            :options="statusOptions"
            clearable
            @update:value="$table?.handleSearch()"
          />
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
        <NFormItem label="名称" path="name">
          <NInput v-model:value="modalForm.name" placeholder="请输入 Prompt 名称" />
        </NFormItem>
        <NFormItem label="版本" path="version">
          <NInput v-model:value="modalForm.version" placeholder="可选版本号" />
        </NFormItem>
        <NFormItem label="分类" path="category">
          <NInput v-model:value="modalForm.category" placeholder="可选分类" />
        </NFormItem>
        <NFormItem label="描述" path="description">
          <NInput v-model:value="modalForm.description" placeholder="用于说明的描述" />
        </NFormItem>
        <NFormItem label="Prompt 内容" path="content">
          <NInput
            v-model:value="modalForm.content"
            type="textarea"
            :autosize="{ minRows: 6 }"
            placeholder="系统 Prompt 内容"
          />
        </NFormItem>
        <NFormItem label="工具 JSON">
          <NInput
            v-model:value="modalForm.tools_json_text"
            type="textarea"
            :autosize="{ minRows: 4 }"
            placeholder="可选，输入工具定义 JSON"
          />
        </NFormItem>
        <NFormItem label="启用">
          <NSwitch v-model:value="modalForm.is_active" />
        </NFormItem>
        <NFormItem>
          <NCheckbox v-model:checked="modalForm.auto_sync">保存后同步到 Supabase</NCheckbox>
        </NFormItem>
      </NForm>
    </CrudModal>

    <NModal
      v-model:show="testModalVisible"
      preset="dialog"
      title="Prompt 测试"
      style="width: 860px"
    >
      <NSpace vertical size="large">
        <NCard size="small" title="Prompt 信息" bordered>
          <NSpace vertical size="small">
            <div>
              <strong>名称：</strong>{{ testPrompt.name }}
            </div>
            <div>
              <strong>版本：</strong>{{ testPrompt.version || '--' }}
            </div>
            <div>
              <strong>分类：</strong>{{ testPrompt.category || '--' }}
            </div>
            <div>
              <strong>内容：</strong>
              <NTooltip placement="bottom">
                <template #trigger>
                  <NButton text size="small">查看</NButton>
                </template>
                <div style="max-width: 400px; white-space: pre-wrap">
                  {{ testPrompt.content }}
                </div>
              </NTooltip>
            </div>
          </NSpace>
        </NCard>

        <NCard size="small" title="测试配置" bordered>
          <NSpace vertical size="medium">
            <div>
              <strong>选择端点</strong>
              <NSelect
                v-model:value="selectedEndpointId"
                :options="aiEndpoints.map(item => ({ label: item.name, value: item.id }))"
                placeholder="请选择 API 端点"
                clearable
              />
            </div>
            <div>
              <strong>选择模型</strong>
              <NSelect
                v-model:value="selectedModel"
                :options="availableModels"
                placeholder="可选，默认使用端点配置"
                clearable
              />
            </div>
            <div>
              <strong>输入消息</strong>
              <NInput
                v-model:value="testMessage"
                type="textarea"
                :autosize="{ minRows: 3 }"
                placeholder="请输入用户消息内容"
              />
            </div>
            <div>
              <NButton
                type="primary"
                :loading="testLoading"
                :disabled="!testMessage.trim() || !selectedEndpointId"
                @click="handleTestPrompt"
              >
                发送测试
              </NButton>
            </div>
          </NSpace>
        </NCard>

        <NCard v-if="testResponse" size="small" title="AI 响应" bordered>
          <NInput :value="testResponse" type="textarea" :autosize="{ minRows: 5 }" readonly />
        </NCard>

        <NCard size="small" title="最近测试记录" bordered>
          <div v-if="!testHistory.length" class="text-gray-400">暂无记录</div>
          <div v-else class="space-y-2">
            <div v-for="item in testHistory" :key="item.id" class="border rounded-md p-2">
              <div class="flex justify-between text-sm text-gray-500">
                <span>模型：{{ item.model || '--' }}</span>
                <span>{{ item.created_at }}</span>
              </div>
              <div class="mt-1">
                <strong>请求：</strong>{{ item.request_message }}
              </div>
              <div class="mt-1">
                <strong>响应：</strong>{{ item.response_message || '无响应' }}
              </div>
              <div class="mt-1 text-sm text-gray-500">
                <span>耗时：{{ item.latency_ms ? `${Math.round(item.latency_ms)} ms` : '--' }}</span>
                <span class="ml-4">结果：{{ item.success ? '成功' : '失败' }}</span>
                <span v-if="item.error" class="ml-4" style="color: #d03050">{{ item.error }}</span>
              </div>
            </div>
          </div>
        </NCard>
      </NSpace>
      <template #action>
        <NButton @click="testModalVisible = false">关闭</NButton>
      </template>
    </NModal>
  </CommonPage>
</template>
