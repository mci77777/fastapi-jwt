<template>
  <n-card title="Supabase 连接状态">
    <n-space vertical>
      <n-space align="center">
        <n-tag :type="statusType" size="small">
          {{ statusText }}
        </n-tag>
        <n-button text :loading="loading" @click="loadStatus">
          <template #icon>
            <HeroIcon name="arrow-path" :size="16" />
          </template>
        </n-button>
      </n-space>

      <n-descriptions :column="1" size="small">
        <n-descriptions-item label="延迟">
          {{ latencyText }}
        </n-descriptions-item>
        <n-descriptions-item label="最近同步">
          {{ formatTime(status.last_synced_at) }}
        </n-descriptions-item>
        <n-descriptions-item v-if="status.detail && status.status !== 'online'" label="详情">
          <n-text depth="3" style="font-size: 12px">
            {{ status.detail }}
          </n-text>
        </n-descriptions-item>
      </n-descriptions>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getSupabaseStatus } from '@/api/dashboard'
import HeroIcon from '@/components/common/HeroIcon.vue'

const props = defineProps({
  autoRefresh: { type: Boolean, default: true },
  refreshInterval: { type: Number, default: 30 },
})

const emit = defineEmits(['status-change'])

const loading = ref(false)
const status = ref({
  status: 'unknown',
  detail: '',
  latency_ms: null,
  last_synced_at: null,
})

let refreshTimer = null

const statusType = computed(() => {
  switch (status.value.status) {
    case 'online':
      return 'success'
    case 'offline':
      return 'error'
    case 'disabled':
      return 'warning'
    default:
      return 'default'
  }
})

const statusText = computed(() => {
  switch (status.value.status) {
    case 'online':
      return '在线'
    case 'offline':
      return '离线'
    case 'disabled':
      return '未配置'
    default:
      return '未知'
  }
})

const latencyText = computed(() => {
  if (status.value.latency_ms === null || status.value.latency_ms === undefined) {
    return '-'
  }
  return `${Math.round(status.value.latency_ms)} ms`
})

async function loadStatus() {
  loading.value = true
  try {
    const res = await getSupabaseStatus()
    const payload =
      res && typeof res === 'object' && res.data && typeof res.data === 'object' ? res.data : res
    if (payload && typeof payload === 'object') {
      status.value = {
        status: payload.status ?? 'unknown',
        detail: payload.detail ?? '',
        latency_ms: payload.latency_ms ?? null,
        last_synced_at: payload.last_synced_at ?? null,
      }
    } else {
      status.value = {
        status: 'unknown',
        detail: '无法获取状态',
        latency_ms: null,
        last_synced_at: null,
      }
    }
    emit('status-change', status.value)
  } catch (error) {
    status.value = {
      status: 'offline',
      detail: error.message || '连接失败',
      latency_ms: null,
      last_synced_at: null,
    }
    window.$message?.error('获取 Supabase 状态失败')
  } finally {
    loading.value = false
  }
}

function formatTime(time) {
  if (!time) return '-'
  try {
    return new Date(time).toLocaleString('zh-CN')
  } catch {
    return '-'
  }
}

onMounted(() => {
  loadStatus()
  if (props.autoRefresh && props.refreshInterval > 0) {
    refreshTimer = setInterval(loadStatus, props.refreshInterval * 1000)
  }
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.n-card {
  height: 100%;
}
</style>
