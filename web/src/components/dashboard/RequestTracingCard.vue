<template>
  <n-card title="请求追踪">
    <n-space vertical>
      <n-space align="center">
        <n-switch v-model:value="tracingEnabled" :loading="loading" @update:value="handleToggle">
          <template #checked>开启</template>
          <template #unchecked>关闭</template>
        </n-switch>
        <n-text depth="3" style="font-size: 14px">
          {{ tracingEnabled ? '正在记录详细请求日志' : '追踪已关闭' }}
        </n-text>
      </n-space>

      <n-alert v-if="tracingEnabled" type="info" size="small" :show-icon="false">
        自动保存最近 50 条 trace 详细日志（App 请求 / 上游 raw / SSE 统计），超出自动清理
      </n-alert>

      <n-space v-if="tracingEnabled">
        <n-button size="small" @click="$emit('view-logs')">
          <template #icon>
            <HeroIcon name="document-text" :size="16" />
          </template>
          查看日志
        </n-button>
      </n-space>
    </n-space>
  </n-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { getTracingConfig, setTracingConfig } from '@/api/dashboard'
import HeroIcon from '@/components/common/HeroIcon.vue'

defineProps({
  autoLoad: { type: Boolean, default: true },
})

const emit = defineEmits(['view-logs', 'config-change'])

const message = useMessage()
const loading = ref(false)
const tracingEnabled = ref(false)

async function loadConfig() {
  try {
    loading.value = true
    const res = await getTracingConfig()
    tracingEnabled.value = res.enabled || false
  } catch (err) {
    message.error(`加载追踪配置失败: ${err.message || '未知错误'}`)
  } finally {
    loading.value = false
  }
}

async function handleToggle(value) {
  try {
    loading.value = true
    const res = await setTracingConfig(value)
    tracingEnabled.value = res.enabled
    message.success(value ? '追踪已开启' : '追踪已关闭')
    emit('config-change', res.enabled)
  } catch (err) {
    // 恢复开关状态
    tracingEnabled.value = !value
    message.error(`更新追踪配置失败: ${err.message || '未知错误'}`)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadConfig()
})

defineExpose({
  loadConfig,
})
</script>

<style scoped>
.n-card {
  min-height: 180px;
}
</style>
