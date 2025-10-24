<template>
  <n-card title="API 端点连通性">
    <n-space vertical :size="12">
      <!-- 操作按钮 -->
      <n-space justify="space-between">
        <n-button type="primary" size="small" :loading="checking" @click="handleCheckAll">
          <template #icon>
            <HeroIcon name="signal" :size="16" />
          </template>
          检测所有端点
        </n-button>
        <n-button secondary size="small" :loading="loading" @click="loadEndpoints">
          <template #icon>
            <HeroIcon name="arrow-path" :size="16" />
          </template>
          刷新列表
        </n-button>
      </n-space>

      <!-- 统计摘要 -->
      <n-space v-if="endpoints.length > 0" align="center">
        <n-tag :bordered="false" type="success">
          在线: {{ onlineCount }}
        </n-tag>
        <n-tag :bordered="false" type="error">
          离线: {{ offlineCount }}
        </n-tag>
        <n-tag :bordered="false" type="warning">
          未检测: {{ unknownCount }}
        </n-tag>
      </n-space>

      <!-- 端点列表 -->
      <n-data-table
        :columns="columns"
        :data="endpoints"
        :loading="loading"
        :pagination="false"
        :max-height="400"
        size="small"
      />
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, computed, h, onMounted } from 'vue'
import { NButton, NTag, useMessage } from 'naive-ui'
import { fetchModels, checkEndpointConnectivity, checkAllEndpointsConnectivity } from '@/api/aiModelSuite'
import HeroIcon from '@/components/common/HeroIcon.vue'

defineOptions({ name: 'EndpointConnectivityCard' })

const message = useMessage()
const loading = ref(false)
const checking = ref(false)
const endpoints = ref([])

// 统计数据（后端返回 online/offline/unknown，前端统一映射）
const onlineCount = computed(() => endpoints.value.filter((e) => e.status === 'online').length)
const offlineCount = computed(() => endpoints.value.filter((e) => e.status === 'offline').length)
const unknownCount = computed(() => endpoints.value.filter((e) => !e.status || e.status === 'unknown').length)

// 表格列定义
const columns = [
  {
    title: '端点名称',
    key: 'name',
    width: 150,
    ellipsis: { tooltip: true },
  },
  {
    title: '模型',
    key: 'model',
    width: 120,
    ellipsis: { tooltip: true },
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => {
      const statusMap = {
        online: { type: 'success', text: '在线' },
        offline: { type: 'error', text: '离线' },
        unknown: { type: 'default', text: '未检测' },
        checking: { type: 'info', text: '检测中' },
      }
      const status = statusMap[row.status] || statusMap.unknown
      return h(NTag, { type: status.type, size: 'small', bordered: false }, { default: () => status.text })
    },
  },
  {
    title: '响应时间',
    key: 'latency_ms',
    width: 100,
    render: (row) => {
      if (!row.latency_ms) return '--'
      const latency = Math.round(row.latency_ms)
      let type = 'success'
      if (latency > 2000) type = 'error'
      else if (latency > 1000) type = 'warning'
      return h(NTag, { type, size: 'small', bordered: false }, { default: () => `${latency}ms` })
    },
  },
  {
    title: '错误信息',
    key: 'last_error',
    ellipsis: { tooltip: true },
    render: (row) => row.last_error || '--',
  },
  {
    title: '操作',
    key: 'actions',
    width: 80,
    render: (row) =>
      h(
        NButton,
        {
          size: 'small',
          type: 'primary',
          text: true,
          loading: row.checking,
          onClick: () => handleCheckSingle(row),
        },
        { default: () => '检测' }
      ),
  },
]

/**
 * 加载端点列表
 */
async function loadEndpoints() {
  loading.value = true
  try {
    const { data } = await fetchModels()
    endpoints.value = (data || []).map((endpoint) => ({
      ...endpoint,
      status: endpoint.status || 'unknown',
      latency: endpoint.latency || null,
      error: endpoint.error || null,
      checking: false,
    }))
  } catch (error) {
    message.error('加载端点列表失败')
  } finally {
    loading.value = false
  }
}

/**
 * 检测所有端点
 */
async function handleCheckAll() {
  checking.value = true
  try {
    const { data } = await checkAllEndpointsConnectivity()
    const results = data || []

    // 更新端点状态（后端返回完整的端点对象）
    endpoints.value = results.map((endpoint) => ({
      ...endpoint,
      checking: false,
    }))

    message.success(`检测完成：${onlineCount.value} 个在线，${offlineCount.value} 个离线`)
  } catch (error) {
    message.error('批量检测失败：' + (error.message || '未知错误'))
  } finally {
    checking.value = false
  }
}

/**
 * 检测单个端点
 */
async function handleCheckSingle(endpoint) {
  const index = endpoints.value.findIndex((e) => e.id === endpoint.id)
  if (index === -1) return

  endpoints.value[index].checking = true
  try {
    const { data } = await checkEndpointConnectivity(endpoint.id)
    // 后端返回完整的端点对象
    endpoints.value[index] = {
      ...data,
      checking: false,
    }
    message.success(`${endpoint.name} 检测完成`)
  } catch (error) {
    endpoints.value[index] = {
      ...endpoints.value[index],
      status: 'offline',
      last_error: error.message || '检测失败',
      checking: false,
    }
    message.error(`${endpoint.name} 检测失败`)
  }
}

onMounted(() => {
  loadEndpoints()
})
</script>

<style scoped>
/* 使用 Naive UI 默认样式 */
</style>
