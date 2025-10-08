<script setup>
import { computed, h, onBeforeUnmount, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NDropdown,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
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

defineOptions({ name: 'AIConfigModels' })

const vPermission = resolveDirective('permission')
const $table = ref(null)

const supabaseStatus = ref(null)
const supabaseLoading = ref(false)
const bulkSyncing = ref(null)
const bulkChecking = ref(false)
const syncingRowId = ref(null)
const checkingRowId = ref(null)

const queryItems = ref({ keyword: null, only_active: null })

const statusOptions = [
  { label: '全部', value: null },
  { label: '启用', value: true },
  { label: '停用', value: false },
]

const syncOptions = [
  { label: '推送到 Supabase', key: 'push' },
  { label: '从 Supabase 拉取', key: 'pull' },
  { label: '推送后拉取', key: 'both' },
]

const statusTypeMap = {
  online: 'success',
  offline: 'error',
  checking: 'warning',
  unknown: 'default',
}

const statusLabelMap = {
  online: '在线',
  offline: '离线',
  checking: '检测中',
  unknown: '未知',
}

const supabaseTagType = computed(() => {
  const status = supabaseStatus.value?.status
  if (status === 'online') return 'success'
  if (status === 'offline') return 'error'
  if (status === 'disabled') return 'default'
  return 'warning'
})

const supabaseLabel = computed(() => {
  const status = supabaseStatus.value?.status
  if (status === 'online') return '已连接'
  if (status === 'offline') return '连接失败'
  if (status === 'disabled') return '未配置'
  return '检测中'
})

const monitorStatus = ref({
  is_running: false,
  interval_seconds: 60,
  last_run_at: null,
  last_error: null,
})
const monitorIntervalSeconds = ref(60)
const monitorLoading = ref(false)
const monitorIntervalOptions = [
  { label: '10s', value: 10 },
  { label: '30s', value: 30 },
  { label: '60s', value: 60 },
  { label: '120s', value: 120 },
  { label: '300s', value: 300 },
  { label: '600s', value: 600 },
]
let monitorStatusTimer = null

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
  auto_sync: false,
  api_key_masked: '',
}

function normalizePayload(form, isUpdate = false) {
  const payload = {
    name: form.name?.trim(),
    model: form.model?.trim() || null,
    base_url: form.base_url?.trim(),
    api_key: form.api_key?.trim() || undefined,
    description: form.description?.trim() || undefined,
    timeout: form.timeout,
    is_active: form.is_active,
    is_default: form.is_default,
    auto_sync: form.auto_sync,
  }
  if (!payload.base_url) delete payload.base_url
  if (!payload.model) delete payload.model
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
  name: '端点',
  initForm,
  doCreate: (form) => api.createAIModel(normalizePayload(form, false)),
  doUpdate: (form) => api.updateAIModel(normalizePayload(form, true)),
  refresh: () => {
    loadSupabaseStatus()
    $table.value?.handleSearch()
  },
})

function openEdit(row) {
  const {
    api_key_masked = '',
    created_at,
    updated_at,
    model_list,
    resolved_endpoints,
    last_checked_at,
    last_synced_at,
    status,
    latency_ms,
    sync_status,
    ...rest
  } = row
  innerHandleEdit({ ...rest, api_key: '', api_key_masked, auto_sync: false })
}

const formRules = {
  name: [
    {
      required: true,
      message: '请输入端点名称',
      trigger: ['input', 'blur'],
    },
  ],
  base_url: [
    {
      required: true,
      message: '请输入 Base URL',
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

function renderStatusTag(row) {
  const status = row.status || 'unknown'
  const type = statusTypeMap[status] || 'default'
  return h(
    NTag,
    { type, round: true, bordered: false },
    { default: () => statusLabelMap[status] || status },
  )
}

function renderModelList(row) {
  const models = row.model_list || []
  if (!models.length) return h('span', { class: 'text-gray-400' }, '--')
  return h(
    NTooltip,
    {},
    {
      trigger: () =>
        h(
          NTag,
          { type: 'info', bordered: false, size: 'small' },
          { default: () => `${models.length} 个模型` },
        ),
      default: () => models.map((model) => h('div', { key: model }, model)),
    },
  )
}

function renderEndpoints(row) {
  const endpoints = row.resolved_endpoints || {}
  const items = Object.entries(endpoints)
  if (!items.length) return h('span', { class: 'text-gray-400' }, '--')
  return h(
    NTooltip,
    {},
    {
      trigger: () =>
        h(
          NTag,
          { type: 'default', bordered: false, size: 'small' },
          { default: () => '查看路径' },
        ),
      default: () => items.map(([key, value]) => h('div', { key }, `${key}: ${value}`)),
    },
  )
}

function formatLatency(value) {
  if (value === null || value === undefined) return '--'
  return `${value.toFixed(0)} ms`
}

async function loadSupabaseStatus() {
  try {
    supabaseLoading.value = true
    const response = await api.getSupabaseStatus()
    supabaseStatus.value = response.data || null
  } catch (error) {
    supabaseStatus.value = { status: 'offline', detail: error.message }
  } finally {
    supabaseLoading.value = false
  }
}

function clearMonitorTimer() {
  if (monitorStatusTimer) {
    clearInterval(monitorStatusTimer)
    monitorStatusTimer = null
  }
}
function setupMonitorTimer() {
  clearMonitorTimer()
  if (!monitorStatus.value.is_running) {
    return
  }
  const interval = Math.min(Math.max((monitorStatus.value.interval_seconds || 60) * 1000, 5000), 600000)
  monitorStatusTimer = setInterval(() => {
    loadMonitorStatus(true)
  }, interval)
}


async function loadMonitorStatus(triggerTableRefresh = false) {
  try {
    const response = await api.getMonitorStatus()
    const data = response.data || {}
    monitorStatus.value = {
      is_running: !!data.is_running,
      interval_seconds: data.interval_seconds ?? monitorStatus.value.interval_seconds,
      last_run_at: data.last_run_at ?? null,
      last_error: data.last_error ?? null,
    }
    monitorIntervalSeconds.value = Number(monitorStatus.value.interval_seconds || monitorIntervalSeconds.value)
    if (triggerTableRefresh && monitorStatus.value.is_running) {
      $table.value?.handleSearch()
    }
    setupMonitorTimer()
  } catch (error) {
    monitorStatus.value = {
      is_running: false,
      interval_seconds: Number(monitorIntervalSeconds.value),
      last_run_at: null,
      last_error: error.message,
    }
    clearMonitorTimer()
  }
}

async function handleStartMonitor() {
  if (monitorLoading.value) return
  try {
    monitorLoading.value = true
    await api.startMonitor(monitorIntervalSeconds.value)
    await loadMonitorStatus()
    window.$message?.success(`Monitor started (${monitorIntervalSeconds.value}s/round)`)
  } catch (error) {
    window.$message?.error(error.message || "Failed to start monitor")
  } finally {
    monitorLoading.value = false
  }
}


async function handleStopMonitor() {
  if (monitorLoading.value) return
  try {
    monitorLoading.value = true
    await api.stopMonitor()
    await loadMonitorStatus()
    window.$message?.success("Monitor stopped")
  } catch (error) {
    window.$message?.error(error.message || "Failed to stop monitor")
  } finally {
    monitorLoading.value = false
  }
}



async function handleCheckAll() {
  try {
    bulkChecking.value = true
    await api.checkAllAIModels()
    window.$message?.success('已触发批量检测')
    $table.value?.handleSearch()
  } catch (error) {
    window.$message?.error(error.message || '批量检测失败')
  } finally {
    bulkChecking.value = false
  }
}

async function handleSyncAll(direction) {
  try {
    bulkSyncing.value = direction
    await api.syncAllAIModels(direction)
    window.$message?.success('批量同步已完成')
    await loadSupabaseStatus()
    $table.value?.handleSearch()
  } catch (error) {
    window.$message?.error(error.message || '批量同步失败')
  } finally {
    bulkSyncing.value = null
  }
}

async function handleCheckRow(row) {
  try {
    checkingRowId.value = row.id
    await api.checkAIModel(row.id)
    window.$message?.success(`已检测端点「${row.name}」`)
    $table.value?.handleSearch()
  } catch (error) {
    window.$message?.error(error.message || '检测失败')
  } finally {
    checkingRowId.value = null
  }
}

async function handleSyncRow(row, direction) {
  try {
    syncingRowId.value = row.id
    await api.syncAIModel(row.id, direction)
    window.$message?.success(`端点「${row.name}」同步完成`)
    await loadSupabaseStatus()
    $table.value?.handleSearch()
  } catch (error) {
    window.$message?.error(error.message || '同步失败')
  } finally {
    syncingRowId.value = null
  }
}

async function handleDelete(row) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确认要删除端点「${row.name}」吗？`,
    positiveText: '删除',
    negativeText: '取消',
    positiveButtonProps: { type: 'error' },
    async onPositiveClick() {
      try {
        await api.deleteAIModel(row.id)
        window.$message?.success('删除成功')
        await loadSupabaseStatus()
        $table.value?.handleSearch()
      } catch (error) {
        window.$message?.error(error.message || '删除失败')
      }
    },
  })
}

const columns = [
  {
    title: '端点名称',
    key: 'name',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '默认模型',
    key: 'model',
    align: 'center',
    ellipsis: { tooltip: true },
    render: (row) => row.model || '--',
  },
  {
    title: 'Base URL',
    key: 'base_url',
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '状态',
    key: 'status',
    align: 'center',
    width: 100,
    render: renderStatusTag,
  },
  {
    title: '响应时间',
    key: 'latency_ms',
    align: 'center',
    width: 110,
    render: (row) => formatLatency(row.latency_ms),
  },
  {
    title: '模型列表',
    key: 'model_list',
    align: 'center',
    render: renderModelList,
  },
  {
    title: '标准路径',
    key: 'resolved_endpoints',
    align: 'center',
    render: renderEndpoints,
  },
  {
    title: '最后检测',
    key: 'last_checked_at',
    align: 'center',
    render: (row) => row.last_checked_at || '--',
  },
  {
    title: '最后同步',
    key: 'last_synced_at',
    align: 'center',
    render: (row) => row.last_synced_at || '--',
  },
  {
    title: '操作',
    key: 'actions',
    width: 240,
    align: 'center',
    render(row) {
      const buttons = [
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              loading: checkingRowId.value === row.id,
              onClick: () => handleCheckRow(row),
            },
            {
              default: () => '检测',
              icon: renderIcon('mdi:stethoscope', { size: 16 }),
            },
          ),
          [[vPermission, 'post/api/v1/llm/models']],
        ),
        withDirectives(
          h(
            NDropdown,
            {
              options: syncOptions,
              trigger: 'click',
              disabled: syncingRowId.value === row.id,
              onSelect: (key) => handleSyncRow(row, key),
            },
            {
              default: () =>
                h(
                  NButton,
                  {
                    size: 'small',
                    loading: syncingRowId.value === row.id,
                  },
                  {
                    default: () => '同步',
                    icon: renderIcon('mdi:backup-restore', { size: 16 }),
                  },
                ),
            },
          ),
          [[vPermission, 'post/api/v1/llm/models']],
        ),
        withDirectives(
          h(
            NButton,
            {
              size: 'small',
              type: 'primary',
              onClick: () => openEdit(row),
            },
            {
              default: () => '编辑',
              icon: renderIcon('material-symbols:edit-outline-rounded', { size: 16 }),
            },
          ),
          [[vPermission, 'put/api/v1/llm/models']],
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
          [[vPermission, 'delete/api/v1/llm/models']],
        ),
      ]
      return h(NSpace, { justify: 'center' }, buttons)
    },
  },
]

onMounted(async () => {
  await loadSupabaseStatus()
  await loadMonitorStatus()
  $table.value?.handleSearch()
})

onBeforeUnmount(() => {
  clearMonitorTimer()
})
</script>

<template>
  <CommonPage show-footer title="AI 接入配置">
    <template #action>
      <NSpace justify="end">
        <NDropdown
          :options="syncOptions"
          trigger="click"
          :loading="!!bulkSyncing"
          @select="handleSyncAll"
        >
          <NButton
            v-permission="'post/api/v1/llm/models'"
            :loading="!!bulkSyncing"
            type="primary"
            class="mr-10"
          >
            <TheIcon icon="mdi:database-sync" :size="18" class="mr-5" />同步所有端点
          </NButton>
        </NDropdown>
        <NButton
          v-permission="'post/api/v1/llm/models'"
          :loading="bulkChecking"
          secondary
          @click="handleCheckAll"
        >
          <TheIcon icon="mdi:waveform" :size="18" class="mr-5" />检测所有端点
        </NButton>
        <NButton
          v-permission="'post/api/v1/llm/models'"
          type="primary"
          class="float-right"
          @click="handleAdd"
        >
          <TheIcon icon="material-symbols:add" :size="18" class="mr-5" />新建端点
        </NButton>
      </NSpace>
    </template>

    <NSpace vertical size="large">
      <NCard :loading="supabaseLoading" title="Supabase 状态" size="small">
        <template #header-extra>
          <NButton text size="small" @click="loadSupabaseStatus">
            <TheIcon icon="mdi:refresh" :size="16" class="mr-4" />Refresh
          </NButton>
        </template>
        <NSpace vertical size="small">
          <div class="flex items-center gap-3">
            <NTag :type="supabaseTagType" round bordered={false}>
              {{ supabaseLabel }}
            </NTag>
            <span v-if="supabaseStatus?.latency_ms">
              Latency: {{ `${supabaseStatus.latency_ms.toFixed(0)} ms` }}
            </span>
            <span v-if="supabaseStatus?.last_synced_at">
              Last sync: {{ supabaseStatus.last_synced_at }}
            </span>
          </div>
          <NAlert v-if="supabaseStatus?.detail" type="info" :bordered="false">
            {{ supabaseStatus.detail }}
          </NAlert>
        </NSpace>
      </NCard>
      <NCard
        :loading="monitorLoading"
        size="small"
        title="Endpoint Monitor"
      >
        <NSpace vertical size="small">
          <div class="flex flex-wrap items-center gap-3">
            <NSelect
              v-model:value="monitorIntervalSeconds"
              style="width: 180px"
              :disabled="monitorStatus.is_running || monitorLoading"
              :options="monitorIntervalOptions"
              placeholder="Select interval"
            />
            <NButton
              type="primary"
              :loading="monitorLoading"
              :disabled="monitorStatus.is_running"
              @click="handleStartMonitor"
            >
              <TheIcon icon="mdi:play" :size="16" class="mr-5" />Start Monitor
            </NButton>
            <NButton
              type="default"
              tertiary
              :loading="monitorLoading"
              :disabled="!monitorStatus.is_running"
              @click="handleStopMonitor"
            >
              <TheIcon icon="mdi:stop" :size="16" class="mr-5" />Stop Monitor
            </NButton>
          </div>
          <div class="text-sm text-gray-500">
            <span>Status: {{ monitorStatus.is_running ? "Running" : "Stopped" }}</span>
            <span class="ml-4">Last run: {{ monitorStatus.last_run_at || "--" }}</span>
            <span class="ml-4">Interval (s): {{ monitorStatus.interval_seconds }}</span>
            <span v-if="monitorStatus.last_error" class="ml-4 text-error">Error: {{ monitorStatus.last_error }}</span>
          </div>
        </NSpace>
      </NCard>

      <CrudTable
        ref="$table"
        v-model:query-items="queryItems"
        :columns="columns"
        :get-data="api.getAIModels"
      >
        <template #queryBar>
          <QueryBarItem label="关键字" :label-width="60">
            <NInput
              v-model:value="queryItems.keyword"
              clearable
              placeholder="搜索名称或模型"
              @keypress.enter="$table?.handleSearch()"
            />
          </QueryBarItem>
          <QueryBarItem label="状态" :label-width="50">
            <NSelect
              v-model:value="queryItems.only_active"
              :options="statusOptions"
              clearable
              @update:value="$table?.handleSearch()"
            />
          </QueryBarItem>
        </template>
      </CrudTable>
    </NSpace>

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
        :label-width="110"
      >
        <NFormItem label="端点名称" path="name">
          <NInput v-model:value="modalForm.name" placeholder="请输入端点名称" />
        </NFormItem>
        <NFormItem label="默认模型" path="model">
          <NInput v-model:value="modalForm.model" placeholder="例如 gpt-4o-mini" />
        </NFormItem>
        <NFormItem label="Base URL" path="base_url">
          <NInput v-model:value="modalForm.base_url" placeholder="例如 https://api.openai.com/v1" />
        </NFormItem>
        <NFormItem v-if="modalForm.api_key_masked && modalAction === 'edit'" label="当前密钥">
          <NInput :value="modalForm.api_key_masked" disabled />
        </NFormItem>
        <NFormItem label="API Key" path="api_key">
          <NInput
            v-model:value="modalForm.api_key"
            type="password"
            placeholder="留空则保留原值"
            show-password-on="click"
          />
        </NFormItem>
        <NFormItem label="超时时间(秒)" path="timeout">
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
        <NFormItem>
          <NCheckbox v-model:checked="modalForm.auto_sync">保存后立即同步到 Supabase</NCheckbox>
        </NFormItem>
      </NForm>
    </CrudModal>
  </CommonPage>
</template>
