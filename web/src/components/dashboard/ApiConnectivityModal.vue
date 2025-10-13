<template>
  <NModal v-model:show="visible" preset="card" title="API 连通性详情" style="width: 800px">
    <NSpace vertical :size="16">
      <NSpace>
        <NButton type="primary" :loading="monitorLoading" @click="handleStartMonitor">
          启动监控
        </NButton>
        <NButton :loading="monitorLoading" @click="handleStopMonitor"> 停止监控 </NButton>
        <NText v-if="monitorStatus.is_running" type="success">
          监控运行中（间隔: {{ monitorStatus.interval_seconds }}s）
        </NText>
        <NText v-else depth="3"> 监控已停止 </NText>
      </NSpace>

      <NDataTable :columns="columns" :data="endpoints" :loading="loading" :pagination="false" />
    </NSpace>
  </NModal>
</template>

<script setup>
import { ref, computed, watch, h } from 'vue'
import { NModal, NSpace, NButton, NText, NDataTable, NTag, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'
import api from '@/api'

defineOptions({ name: 'ApiConnectivityModal' })

const props = defineProps({
  show: {
    type: Boolean,
    required: true,
  },
})

const emit = defineEmits(['update:show'])

const store = useAiModelSuiteStore()
const { models } = storeToRefs(store)
const message = useMessage()

const visible = computed({
  get: () => props.show,
  set: (val) => emit('update:show', val),
})

const loading = ref(false)
const monitorLoading = ref(false)
const monitorStatus = ref({
  is_running: false,
  interval_seconds: 60,
})

// 表格列定义
const columns = [
  {
    title: '名称',
    key: 'name',
    width: 150,
    ellipsis: {
      tooltip: true,
    },
  },
  {
    title: '模型',
    key: 'model',
    width: 120,
    ellipsis: {
      tooltip: true,
    },
  },
  {
    title: '状态',
    key: 'status',
    width: 100,
    render: (row) => {
      const typeMap = {
        online: 'success',
        offline: 'error',
        checking: 'warning',
        unknown: 'default',
      }
      const labelMap = {
        online: '在线',
        offline: '离线',
        checking: '检测中',
        unknown: '未知',
      }
      return h(
        NTag,
        { type: typeMap[row.status] || 'default', size: 'small' },
        { default: () => labelMap[row.status] || row.status }
      )
    },
  },
  {
    title: '延迟 (ms)',
    key: 'latency_ms',
    width: 100,
    render: (row) => {
      return row.latency_ms !== null && row.latency_ms !== undefined
        ? row.latency_ms.toFixed(0)
        : '-'
    },
  },
  {
    title: 'Base URL',
    key: 'base_url',
    ellipsis: {
      tooltip: true,
    },
  },
  {
    title: '最近检测',
    key: 'last_checked_at',
    width: 160,
    render: (row) => {
      if (!row.last_checked_at) return '-'
      return new Date(row.last_checked_at).toLocaleString('zh-CN')
    },
  },
]

const endpoints = computed(() => models.value || [])

/**
 * 加载监控状态
 */
async function loadMonitorStatus() {
  loading.value = true
  try {
    const res = await api.getMonitorStatus()
    if (res.data) {
      monitorStatus.value = res.data
    }
    // 同时刷新模型列表以获取最新状态
    await store.loadModels()
  } catch (error) {
    console.error('加载监控状态失败:', error)
    message.error('加载监控状态失败')
  } finally {
    loading.value = false
  }
}

/**
 * 启动监控
 */
async function handleStartMonitor() {
  monitorLoading.value = true
  try {
    await api.startMonitor(60)
    message.success('监控已启动')
    await loadMonitorStatus()
  } catch (error) {
    console.error('启动监控失败:', error)
    message.error('启动监控失败')
  } finally {
    monitorLoading.value = false
  }
}

/**
 * 停止监控
 */
async function handleStopMonitor() {
  monitorLoading.value = true
  try {
    await api.stopMonitor()
    message.success('监控已停止')
    await loadMonitorStatus()
  } catch (error) {
    console.error('停止监控失败:', error)
    message.error('停止监控失败')
  } finally {
    monitorLoading.value = false
  }
}

// 监听弹窗显示状态，打开时加载数据
watch(
  () => props.show,
  (newVal) => {
    if (newVal) {
      loadMonitorStatus()
    }
  }
)
</script>
