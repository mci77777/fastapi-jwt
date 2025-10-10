<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NDivider,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NRadioButton,
  NRadioGroup,
  NSelect,
  NSpace,
  NStatistic,
  NTable,
  NTag,
  NTooltip,
  useDialog,
} from 'naive-ui'
import { storeToRefs } from 'pinia'

import { useAiModelSuiteStore } from '@/store'

defineOptions({ name: 'AiModelCatalog' })

const store = useAiModelSuiteStore()
const { models, modelsLoading, syncAllLoading, syncingEndpoints } = storeToRefs(store)
const filters = reactive({
  keyword: '',
  only_active: null,
})

const statusType = {
  online: 'success',
  offline: 'error',
  checking: 'warning',
  unknown: 'default',
}

const statusLabel = {
  online: '在线',
  offline: '离线',
  checking: '检测中',
  unknown: '未知',
}

const defaultModel = computed(() => models.value.find((item) => item.is_default))
const totalEndpoints = computed(() => models.value.length)
const totalActive = computed(() => models.value.filter((item) => item.is_active).length)
const availableModelNames = computed(() => store.modelCandidates)
const syncingMap = computed(() => syncingEndpoints.value)
const isEndpointSyncing = (endpointId) => syncingMap.value?.has?.(endpointId)
const dialog = useDialog()

async function loadModels() {
  await store.loadModels({
    keyword: filters.keyword || undefined,
    only_active: filters.only_active,
  })
}

function handleSearch() {
  loadModels()
}

const syncDialogVisible = ref(false)
const syncingAll = ref(false)
const syncTarget = ref(null)
const syncForm = reactive({
  direction: 'both',
  overwrite: false,
  deleteMissing: false,
})

function openSetDefault(row) {
  if (row.is_default) return
  dialog.warning({
    title: '修改默认模型',
    content: `确认将 ${row.name} 设置为默认模型？`,
    positiveText: '确认',
    negativeText: '取消',
    async onPositiveClick() {
      await store.setDefaultModel(row)
      window.$message?.success('默认模型已更新')
    },
  })
}

function openSync(row) {
  syncingAll.value = false
  syncTarget.value = row
  Object.assign(syncForm, {
    direction: 'both',
    overwrite: false,
    deleteMissing: false,
  })
  syncDialogVisible.value = true
}

function openSyncAll() {
  syncingAll.value = true
  syncTarget.value = null
  Object.assign(syncForm, {
    direction: 'both',
    overwrite: true,
    deleteMissing: true,
  })
  syncDialogVisible.value = true
}

async function submitSync() {
  const payload = {
    direction: syncForm.direction,
    overwrite: syncForm.overwrite,
    deleteMissing: syncForm.deleteMissing,
  }
  if (syncingAll.value) {
    await store.syncAll(payload)
  } else if (syncTarget.value) {
    await store.syncModel(syncTarget.value.id, payload)
  }
  window.$message?.success('同步任务已完成')
  syncDialogVisible.value = false
}

onMounted(() => {
  loadModels()
})
</script>


<template>
  <NSpace vertical size="large">
    <NCard title="模型概览" size="small" bordered>
      <NSpace justify="space-between" align="center" wrap>
        <NSpace wrap>
          <NStatistic label="端点数量" :value="totalEndpoints" />
          <NStatistic label="启用端点" :value="totalActive" />
          <NStatistic
            label="候选模型"
            :value="availableModelNames.length"
            v-if="availableModelNames.length"
          />
        </NSpace>
        <NSpace>
          <NButton secondary @click="loadModels" :loading="modelsLoading">刷新状态</NButton>
          <NButton type="primary" @click="openSyncAll" :loading="syncAllLoading">全量同步</NButton>
        </NSpace>
      </NSpace>
      <NDivider />
      <div class="text-xs text-gray-500" v-if="availableModelNames.length">
        <span class="mr-2">可用模型：</span>
        <NSpace wrap>
          <NTag v-for="name in availableModelNames" :key="name" size="small" bordered={false}>{{ name }}</NTag>
        </NSpace>
      </div>
      <NAlert v-else type="warning" class="mt-2" show-icon>暂未发现候选模型，请执行一次健康检测或同步。</NAlert>
    </NCard>

    <NCard title="模型筛选" size="small">
      <NSpace wrap>
        <NInput
          v-model:value="filters.keyword"
          placeholder="按名称或模型搜索"
          style="width: 220px"
          clearable
          @keyup.enter="handleSearch"
        />
        <NSelect
          v-model:value="filters.only_active"
          style="width: 160px"
          :options="[
            { label: '全部状态', value: null },
            { label: '仅启用', value: true },
            { label: '仅停用', value: false },
          ]"
          @update:value="handleSearch"
        />
        <NButton type="primary" @click="handleSearch">查询</NButton>
        <NButton tertiary @click="loadModels">刷新</NButton>
      </NSpace>
    </NCard>

    <NCard :loading="modelsLoading" title="模型列表" size="small">
      <div class="mb-4 text-sm text-gray-500">
        <span>当前默认模型：</span>
        <span v-if="defaultModel" class="font-semibold">{{ defaultModel.name || defaultModel.model }}</span>
        <span v-else class="text-warning">尚未设置</span>
      </div>
      <NTable :loading="modelsLoading" :single-line="false" size="small" striped>
        <thead>
          <tr>
            <th style="width: 200px">名称</th>
            <th>Base URL</th>
            <th style="width: 160px">可用模型</th>
            <th style="width: 120px">状态</th>
            <th style="width: 160px">上次检测</th>
            <th style="width: 180px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!models.length">
            <td colspan="6" class="text-center text-gray-500 py-6">暂无数据</td>
          </tr>
          <tr v-for="item in models" :key="item.id">
            <td>
              <div class="flex items-center gap-2">
                <span>{{ item.name }}</span>
                <NTag v-if="item.is_default" type="primary" size="small" bordered={false}>默认</NTag>
                <NTag v-if="item.is_active" type="success" size="small" bordered={false}>启用</NTag>
                <NTag v-else type="warning" size="small" bordered={false}>停用</NTag>
              </div>
            </td>
            <td>
              <div>{{ item.base_url }}</div>
              <div class="text-xs text-gray-500 mt-1">
                <template v-if="item.resolved_endpoints && Object.keys(item.resolved_endpoints).length">
                  <NTooltip>
                    <template #trigger>
                      <NTag size="small" bordered={false}>查看路径</NTag>
                    </template>
                    <template #default>
                      <div v-for="(value, key) in item.resolved_endpoints" :key="key">{{ key }}: {{ value }}</div>
                    </template>
                  </NTooltip>
                </template>
                <template v-else>--</template>
              </div>
            </td>
            <td>
              <template v-if="item.model_list && item.model_list.length">
                <NTooltip>
                  <template #trigger>
                    <NTag type="info" size="small" bordered={false}>{{ item.model_list.length }} 个模型</NTag>
                  </template>
                  <template #default>
                    <div v-for="model in item.model_list" :key="model">{{ model }}</div>
                  </template>
                </NTooltip>
              </template>
              <template v-else>
                <span v-if="item.model">{{ item.model }}</span>
                <span v-else class="text-gray-400">--</span>
              </template>
            </td>
            <td>
              <NTag :type="statusType[item.status] || 'default'" round bordered={false}>
                {{ statusLabel[item.status] || item.status || '未知' }}
              </NTag>
            </td>
            <td>{{ item.last_checked_at || '--' }}</td>
            <td>
              <NSpace>
                <NButton size="small" type="primary" @click="openSetDefault(item)">设为默认</NButton>
                <NButton
                  size="small"
                  @click="openSync(item)"
                  :loading="isEndpointSyncing(item.id)"
                  type="info"
                >
                  同步
                </NButton>
              </NSpace>
            </td>
          </tr>
        </tbody>
      </NTable>
    </NCard>

    <NModal v-model:show="syncDialogVisible" preset="card" :title="syncingAll ? '全量同步' : '同步端点'">
      <template #header-extra>
        <span v-if="!syncingAll && syncTarget" class="text-xs text-gray-500">ID: {{ syncTarget.id }}</span>
      </template>
      <div v-if="syncTarget && !syncingAll" class="mb-3 text-sm text-gray-500">
        <div>端点：{{ syncTarget.name }}（{{ syncTarget.base_url }}）</div>
        <div>当前模型：{{ syncTarget.model || '未配置' }}</div>
      </div>
      <NForm :model="syncForm" label-placement="left" label-width="100">
        <NFormItem label="同步方向">
          <NRadioGroup v-model:value="syncForm.direction">
            <NRadioButton value="push">推送本地 → Supabase</NRadioButton>
            <NRadioButton value="pull">拉取 Supabase → 本地</NRadioButton>
            <NRadioButton value="both">双向同步</NRadioButton>
          </NRadioGroup>
        </NFormItem>
        <NFormItem label="覆盖本地/远端">
          <NCheckbox v-model:checked="syncForm.overwrite">
            执行覆盖写入（以目标方向的数据为准）
          </NCheckbox>
        </NFormItem>
        <NFormItem label="删除缺失项">
          <NCheckbox v-model:checked="syncForm.deleteMissing">
            删除目标端不存在的记录，保持两端完全一致
          </NCheckbox>
        </NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="syncDialogVisible = false">取消</NButton>
          <NButton type="primary" @click="submitSync" :loading="syncAllLoading || (syncTarget && isEndpointSyncing(syncTarget.id))">
            开始同步
          </NButton>
        </NSpace>
      </template>
    </NModal>
  </NSpace>
</template>


<style scoped>
.text-warning {
  color: #e28934;
}
.text-gray-500 {
  color: #6b7280;
}
.mr-2 {
  margin-right: 8px;
}
.mt-2 {
  margin-top: 8px;
}
</style>
