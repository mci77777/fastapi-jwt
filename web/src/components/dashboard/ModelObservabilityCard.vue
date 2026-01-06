<template>
  <n-card title="模型管理与观测" size="small" :bordered="true">
    <n-space vertical :size="12">
      <n-alert type="info" :bordered="false" show-icon>
        观测链路：映射模型 → 实际模型 → API 供应商 → health/status。屏蔽为服务端强制生效（解析时跳过被屏蔽模型）。
      </n-alert>

      <n-tabs type="line" animated>
        <n-tab-pane name="app" tab="App 实际可用模型">
          <n-space justify="space-between" align="center" wrap>
            <div class="text-xs text-gray-500">
              recommended_model：<span class="font-mono">{{ appModels?.recommended_model || '--' }}</span>
            </div>
            <n-space>
              <n-button secondary size="small" :loading="loading" @click="refreshAll">刷新</n-button>
            </n-space>
          </n-space>

          <n-divider />

          <n-data-table
            size="small"
            :columns="appColumns"
            :data="appModels?.data || []"
            :loading="loading"
            :pagination="false"
            :max-height="360"
          />
        </n-tab-pane>

        <n-tab-pane name="vendor" tab="供应商模型（可屏蔽）">
          <n-space justify="space-between" align="center" wrap>
            <n-input
              v-model:value="keyword"
              size="small"
              placeholder="按模型名过滤"
              style="width: 240px"
              clearable
            />
            <n-space>
              <n-button
                secondary
                size="small"
                :loading="loading"
                @click="refreshAll"
              >
                刷新
              </n-button>
            </n-space>
          </n-space>

          <n-divider />

          <n-data-table
            size="small"
            :columns="vendorColumns"
            :data="filteredVendorRows"
            :loading="loading"
            :pagination="false"
            :max-height="420"
          />
        </n-tab-pane>

        <n-tab-pane name="mapping" tab="映射管理">
          <n-alert v-if="!userStore.isSuperUser" type="warning" :bordered="false" show-icon>
            当前账号非管理员，仅可观测；如需编辑映射/屏蔽模型请使用 admin 登录。
          </n-alert>
          <ModelMappingCard v-if="userStore.isSuperUser" @mapping-change="() => refreshAppModels()" />
        </n-tab-pane>
      </n-tabs>
    </n-space>
  </n-card>
</template>

<script setup>
import { computed, h, onMounted, ref } from 'vue'
import { NButton, NTag, NSpace, NSwitch, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'

import ModelMappingCard from '@/components/dashboard/ModelMappingCard.vue'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'
import { useUserStore } from '@/store'
import { fetchAppModels, upsertBlockedModels } from '@/api/aiModelSuite'

defineOptions({ name: 'ModelObservabilityCard' })

const store = useAiModelSuiteStore()
const userStore = useUserStore()
const message = useMessage()

const { models, modelsLoading } = storeToRefs(store)

const blocked = computed(() => store.blockedModels || [])
const blockedSet = computed(() => new Set(blocked.value || []))
const appModels = ref(null)
const keyword = ref('')

const localLoading = ref(false)
const loading = computed(() => modelsLoading.value || localLoading.value)

function endpointStatusTag(status) {
  const value = String(status || 'unknown').toLowerCase()
  const type = value === 'online' ? 'success' : value === 'offline' ? 'error' : value === 'checking' ? 'warning' : 'default'
  const label = value === 'online' ? '在线' : value === 'offline' ? '离线' : value === 'checking' ? '检测中' : '未知'
  return { type, label }
}

function endpointsForVendorModel(vendorModel) {
  const modelName = String(vendorModel || '').trim()
  if (!modelName) return []
  return (models.value || []).filter((ep) => {
    const list = Array.isArray(ep.model_list) ? ep.model_list : []
    return list.includes(modelName) || ep.model === modelName
  })
}

const vendorRows = computed(() => {
  const rows = []
  const map = new Map()
  ;(models.value || []).forEach((ep) => {
    const list = Array.isArray(ep.model_list) ? ep.model_list : []
    const candidates = list.length ? list : ep.model ? [ep.model] : []
    candidates.forEach((name) => {
      const modelName = String(name || '').trim()
      if (!modelName) return
      if (!map.has(modelName)) {
        map.set(modelName, { model: modelName, endpoints: [] })
      }
      map.get(modelName).endpoints.push(ep)
    })
  })
  for (const value of map.values()) {
    const endpoints = value.endpoints || []
    const online = endpoints.filter((ep) => String(ep.status || '').toLowerCase() === 'online').length
    const offline = endpoints.filter((ep) => String(ep.status || '').toLowerCase() === 'offline').length
    rows.push({
      model: value.model,
      blocked: blockedSet.value.has(value.model),
      endpoints,
      endpointCount: endpoints.length,
      onlineCount: online,
      offlineCount: offline,
    })
  }
  // 先展示 blocked，再按 endpointCount 降序
  return rows.sort((a, b) => {
    if (a.blocked !== b.blocked) return a.blocked ? -1 : 1
    return (b.endpointCount || 0) - (a.endpointCount || 0)
  })
})

const filteredVendorRows = computed(() => {
  const kw = String(keyword.value || '').trim().toLowerCase()
  if (!kw) return vendorRows.value
  return vendorRows.value.filter((row) => String(row.model || '').toLowerCase().includes(kw))
})

async function refreshBlocked() {
  await store.loadBlockedModels()
}

async function refreshAppModels() {
  // admin 需要 debug 字段用于观测链路（后端会做门禁）
  const params = userStore.isSuperUser ? { debug: true } : {}
  const res = await fetchAppModels(params)
  appModels.value = res
}

async function refreshAll() {
  localLoading.value = true
  try {
    await Promise.all([
      store.loadModels({ page_size: 100, refresh_missing_models: true }),
      store.loadBlockedModels(),
      refreshAppModels(),
      store.loadMappings(),
    ])
  } finally {
    localLoading.value = false
  }
}

async function toggleBlocked(model, nextBlocked) {
  if (!userStore.isSuperUser) {
    message.warning('需要管理员权限')
    return
  }
  localLoading.value = true
  try {
    await upsertBlockedModels([{ model, blocked: !!nextBlocked }])
    await store.loadBlockedModels()
    await refreshAppModels()
    message.success(nextBlocked ? '已屏蔽' : '已解除屏蔽')
  } finally {
    localLoading.value = false
  }
}

const appColumns = computed(() => {
  const base = [
    {
      title: '映射模型 key',
      key: 'model',
      width: 220,
      render: (row) => h('span', { class: 'font-mono' }, String(row.model || '')),
    },
    {
      title: 'label',
      key: 'label',
      width: 220,
      render: (row) => String(row.label || ''),
    },
    {
      title: 'scope',
      key: 'scope_type',
      width: 90,
      render: (row) =>
        h(NTag, { size: 'small', bordered: false, type: row.scope_type === 'user' ? 'info' : 'default' }, { default: () => String(row.scope_type || '') }),
    },
  ]

  if (!userStore.isSuperUser) return base

  return base.concat([
    {
      title: 'resolved_model',
      key: 'resolved_model',
      width: 220,
      render: (row) => h('span', { class: 'font-mono' }, String(row.resolved_model || '--')),
    },
    {
      title: '命中供应商/health',
      key: 'endpoint',
      render: (row) => {
        const resolved = String(row.resolved_model || '').trim()
        if (!resolved) return '--'
        const eps = endpointsForVendorModel(resolved).slice(0, 2)
        if (!eps.length) return '未命中端点'
        return h(
          NSpace,
          { size: 6, wrap: true },
          {
            default: () =>
              eps.map((ep) => {
                const tag = endpointStatusTag(ep.status)
                const text = ep.name || ep.base_url || String(ep.id)
                return h(NTag, { size: 'small', bordered: false, type: tag.type }, { default: () => text })
              }),
          }
        )
      },
    },
  ])
})

const vendorColumns = computed(() => [
  {
    title: 'model',
    key: 'model',
    width: 260,
    render: (row) => h('span', { class: 'font-mono' }, String(row.model || '')),
  },
  {
    title: '供应商/health',
    key: 'endpoints',
    render: (row) => {
      const eps = (row.endpoints || []).slice(0, 3)
      if (!eps.length) return '--'
      return h(
        NSpace,
        { size: 6, wrap: true },
        {
          default: () =>
            eps.map((ep) => {
              const tag = endpointStatusTag(ep.status)
              const text = ep.name || ep.base_url || String(ep.id)
              return h(NTag, { size: 'small', bordered: false, type: tag.type }, { default: () => text })
            }),
        }
      )
    },
  },
  {
    title: '屏蔽',
    key: 'blocked',
    width: 90,
    render: (row) =>
      h(NSwitch, {
        value: !!row.blocked,
        disabled: !userStore.isSuperUser,
        onUpdateValue: (val) => toggleBlocked(row.model, val),
      }),
  },
])

onMounted(() => {
  refreshAll()
})
</script>
