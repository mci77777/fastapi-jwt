<template>
  <NModal
    v-model:show="visible"
    preset="dialog"
    title="Dashboard 配置"
    positive-text="保存"
    negative-text="取消"
    @positive-click="handleSave"
    @negative-click="handleCancel"
  >
    <NForm ref="formRef" :model="formData" :rules="rules" label-placement="left" label-width="160">
      <NFormItem label="WebSocket 推送间隔" path="websocket_push_interval">
        <NInputNumber
          v-model:value="formData.websocket_push_interval"
          :min="1"
          :max="300"
          :step="1"
          placeholder="请输入推送间隔（秒）"
        >
          <template #suffix>秒</template>
        </NInputNumber>
      </NFormItem>

      <NFormItem label="HTTP 轮询间隔" path="http_poll_interval">
        <NInputNumber
          v-model:value="formData.http_poll_interval"
          :min="5"
          :max="600"
          :step="5"
          placeholder="请输入轮询间隔（秒）"
        >
          <template #suffix>秒</template>
        </NInputNumber>
      </NFormItem>

      <NFormItem label="日志保留数量" path="log_retention_size">
        <NInputNumber
          v-model:value="formData.log_retention_size"
          :min="10"
          :max="1000"
          :step="10"
          placeholder="请输入日志保留数量"
        >
          <template #suffix>条</template>
        </NInputNumber>
      </NFormItem>
    </NForm>

    <template #action>
      <div class="config-tips">
        <span>💡 提示：配置保存后将立即生效</span>
      </div>
    </template>
  </NModal>
</template>

<script setup>
import { ref, watch } from 'vue'
import { NModal, NForm, NFormItem, NInputNumber, useMessage } from 'naive-ui'

defineOptions({ name: 'PollingConfig' })

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  config: {
    type: Object,
    default: () => ({
      websocket_push_interval: 10,
      http_poll_interval: 30,
      log_retention_size: 100
    })
  }
})

const emit = defineEmits(['update:show', 'save'])

const message = useMessage()

// 响应式状态
const visible = ref(props.show)
const formRef = ref(null)
const formData = ref({
  websocket_push_interval: 10,
  http_poll_interval: 30,
  log_retention_size: 100
})

// 表单验证规则
const rules = {
  websocket_push_interval: [
    {
      required: true,
      type: 'number',
      message: '请输入 WebSocket 推送间隔',
      trigger: 'blur'
    },
    {
      type: 'number',
      min: 1,
      max: 300,
      message: '推送间隔必须在 1-300 秒之间',
      trigger: 'blur'
    }
  ],
  http_poll_interval: [
    {
      required: true,
      type: 'number',
      message: '请输入 HTTP 轮询间隔',
      trigger: 'blur'
    },
    {
      type: 'number',
      min: 5,
      max: 600,
      message: '轮询间隔必须在 5-600 秒之间',
      trigger: 'blur'
    }
  ],
  log_retention_size: [
    {
      required: true,
      type: 'number',
      message: '请输入日志保留数量',
      trigger: 'blur'
    },
    {
      type: 'number',
      min: 10,
      max: 1000,
      message: '日志保留数量必须在 10-1000 条之间',
      trigger: 'blur'
    }
  ]
}

/**
 * 保存配置
 */
function handleSave() {
  formRef.value?.validate((errors) => {
    if (!errors) {
      emit('save', { ...formData.value })
      message.success('配置已保存')
      visible.value = false
    } else {
      message.error('请检查表单输入')
    }
  })
}

/**
 * 取消配置
 */
function handleCancel() {
  visible.value = false
}

// 监听 props 变化
watch(
  () => props.show,
  (newValue) => {
    visible.value = newValue
  }
)

watch(
  () => props.config,
  (newValue) => {
    if (newValue) {
      formData.value = { ...newValue }
    }
  },
  { immediate: true, deep: true }
)

// 监听 visible 变化，同步到父组件
watch(visible, (newValue) => {
  emit('update:show', newValue)
})
</script>

<style scoped>
.config-tips {
  width: 100%;
  padding: 12px;
  background-color: #f0f9ff;
  border-radius: 4px;
  font-size: 13px;
  color: #2080f0;
  text-align: center;
}
</style>

