<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NProgress,
  NSelect,
  NSpace,
  NSwitch,
  NTable,
  NTag,
  NTooltip,
} from 'naive-ui'
import { storeToRefs } from 'pinia'

import { useAiModelSuiteStore } from '@/store'

defineOptions({ name: 'AiJwtSimulation' })

const store = useAiModelSuiteStore()
const { models, prompts, latestRun, latestRunSummary, latestRunLoading } = storeToRefs(store)
const singleForm = reactive({
  prompt_id: null,
  endpoint_id: null,
  model: null,
  message: '',
  username: 'tester',
})
const loadForm = reactive({
  prompt_id: null,
  endpoint_id: null,
  model: null,
  message: '',
  batch_size: 10,
  concurrency: 5,
  stop_on_error: false,
  username: 'load-test',
})
const singleResult = ref(null)
const singleError = ref(null)
const pollingTimer = ref(null)
const isPolling = ref(false)

const endpointOptions = computed(() => store.endpointOptions)
const modelDirectory = computed(() => {
  const map = new Map()
  models.value.forEach((endpoint) => {
    const list = []
    if (Array.isArray(endpoint.model_list)) {
      endpoint.model_list.forEach((model) => {
        if (model) list.push(model)
      })
    }
    if (endpoint.model) {
      list.push(endpoint.model)
    }
    map.set(endpoint.id, Array.from(new Set(list)))
  })
  return map
})
const globalModelOptions = computed(() =>
  store.modelCandidates.map((item) => ({ label: item, value: item }))
)

const buildModelOptions = (endpointId) => {
  const list = endpointId ? modelDirectory.value.get(endpointId) || [] : store.modelCandidates
  return Array.from(new Set(list)).map((item) => ({ label: item, value: item }))
}

const singleModelOptions = computed(() => buildModelOptions(singleForm.endpoint_id))
const loadModelOptions = computed(() => buildModelOptions(loadForm.endpoint_id))
const promptOptions = computed(() =>
  prompts.value.map((item) => ({ label: item.name, value: item.id }))
)

const loadSummary = computed(() => latestRunSummary.value || {})
const loadTests = computed(() => latestRun.value?.tests || [])
const loadProgress = computed(() => {
  const summary = loadSummary.value
  if (!summary.batch_size || summary.batch_size === 0) return 0
  const completed = summary.completed_count || 0
  return Math.round((completed / summary.batch_size) * 100)
})

watch(
  () => singleForm.endpoint_id,
  (endpointId) => {
    const options = buildModelOptions(endpointId)
    if (!singleForm.model && options.length) {
      singleForm.model = options[0].value
    } else if (
      singleForm.model &&
      options.length &&
      !options.some((option) => option.value === singleForm.model)
    ) {
      singleForm.model = options[0].value
    }
  }
)

watch(
  () => loadForm.endpoint_id,
  (endpointId) => {
    const options = buildModelOptions(endpointId)
    if (!loadForm.model && options.length) {
      loadForm.model = options[0].value
    } else if (
      loadForm.model &&
      options.length &&
      !options.some((option) => option.value === loadForm.model)
    ) {
      loadForm.model = options[0].value
    }
  }
)

async function runSingle() {
  singleError.value = null
  singleResult.value = null
  try {
    const payload = {
      prompt_id: singleForm.prompt_id,
      endpoint_id: singleForm.endpoint_id,
      message: singleForm.message,
      model: singleForm.model,
      username: singleForm.username,
    }
    const { data } = await store.simulateDialog(payload)
    singleResult.value = data
    window.$message?.success('模拟完成')
  } catch (error) {
    singleError.value = error?.message || String(error)
  }
}

async function runLoadTest() {
  const payload = {
    prompt_id: loadForm.prompt_id,
    endpoint_id: loadForm.endpoint_id,
    message: loadForm.message,
    batch_size: loadForm.batch_size,
    concurrency: loadForm.concurrency,
    stop_on_error: loadForm.stop_on_error,
    model: loadForm.model,
    username: loadForm.username,
  }

  try {
    const result = await store.triggerLoadTest(payload)
    // 开始轮询进度
    const runId = result?.summary?.id
    if (runId) {
      startPolling(runId)
    }
    window.$message?.success('压测已启动,正在执行中...')
  } catch (error) {
    window.$message?.error(error?.message || '压测启动失败')
  }
}

function startPolling(runId) {
  stopPolling()
  isPolling.value = true

  const poll = async () => {
    try {
      const result = await store.refreshRun(runId)
      const isRunning = result?.is_running ?? false

      if (!isRunning) {
        // 压测完成
        stopPolling()
        window.$message?.success('压测完成')
      }
    } catch (error) {
      console.error('轮询压测状态失败:', error)
    }
  }

  // 立即执行一次
  poll()
  // 每2秒轮询一次
  pollingTimer.value = setInterval(poll, 2000)
}

function stopPolling() {
  if (pollingTimer.value) {
    clearInterval(pollingTimer.value)
    pollingTimer.value = null
  }
  isPolling.value = false
}

async function refreshRun() {
  if (!loadSummary.value.id) return
  await store.refreshRun(loadSummary.value.id)
}

onMounted(() => {
  store.loadModels()
  store.loadPrompts()
})

onBeforeUnmount(() => {
  stopPolling()
})
</script>

<template>
  <NSpace vertical size="large">
    <NCard title="单次对话模拟" size="small">
      <NForm :model="singleForm" label-placement="left" label-width="90">
        <NSpace wrap>
          <NFormItem label="Prompt" path="prompt_id">
            <NSelect v-model:value="singleForm.prompt_id" :options="promptOptions" filterable />
          </NFormItem>
          <NFormItem label="模型接口" path="endpoint_id">
            <NSelect v-model:value="singleForm.endpoint_id" :options="endpointOptions" filterable />
          </NFormItem>
          <NFormItem label="模型名称" path="model">
            <NSelect
              v-model:value="singleForm.model"
              :options="singleModelOptions.length ? singleModelOptions : globalModelOptions"
              filterable
              clearable
              tag
              placeholder="选择或输入模型名称"
            />
          </NFormItem>
          <NFormItem label="用户名" path="username">
            <NInput v-model:value="singleForm.username" placeholder="用于生成 JWT" />
          </NFormItem>
        </NSpace>
        <NFormItem label="对话内容" path="message">
          <NInput
            v-model:value="singleForm.message"
            type="textarea"
            rows="4"
            placeholder="请输入用户消息"
          />
        </NFormItem>
        <NSpace justify="end">
          <NButton type="primary" @click="runSingle">执行模拟</NButton>
        </NSpace>
      </NForm>
      <div v-if="singleResult" class="mt-4">
        <div class="mb-2 text-sm text-gray-500">生成 JWT：{{ singleResult.jwt_token }}</div>
        <NCard size="small" title="模型回应">
          <div v-if="singleResult.result">
            <div class="mb-2 font-semibold">回复:</div>
            <pre class="whitespace-pre-wrap">{{ singleResult.result.response || '无回复' }}</pre>
            <div class="mt-2 text-xs text-gray-500">
              延迟：{{ singleResult.result.latency_ms?.toFixed?.(0) || '--' }} ms
            </div>
          </div>
          <div v-else class="text-error">{{ singleResult.error || '发生错误' }}</div>
        </NCard>
      </div>
      <div v-else-if="singleError" class="mt-4 text-error">{{ singleError }}</div>
    </NCard>

    <NCard title="并发压测" size="small" :loading="latestRunLoading">
      <NForm :model="loadForm" label-placement="left" label-width="90">
        <NSpace wrap>
          <NFormItem label="Prompt" path="prompt_id">
            <NSelect v-model:value="loadForm.prompt_id" :options="promptOptions" filterable />
          </NFormItem>
          <NFormItem label="模型接口" path="endpoint_id">
            <NSelect v-model:value="loadForm.endpoint_id" :options="endpointOptions" filterable />
          </NFormItem>
          <NFormItem label="模型名称" path="model">
            <NSelect
              v-model:value="loadForm.model"
              :options="loadModelOptions.length ? loadModelOptions : globalModelOptions"
              filterable
              clearable
              tag
              placeholder="选择或输入模型名称"
            />
          </NFormItem>
          <NFormItem label="批次数" path="batch_size">
            <NInputNumber v-model:value="loadForm.batch_size" :min="1" :max="1000" />
          </NFormItem>
          <NFormItem label="并发数" path="concurrency">
            <NInputNumber v-model:value="loadForm.concurrency" :min="1" :max="1000" />
          </NFormItem>
          <NFormItem label="出错即停" path="stop_on_error">
            <NSwitch v-model:value="loadForm.stop_on_error" />
          </NFormItem>
        </NSpace>
        <NFormItem label="压测消息" path="message">
          <NInput
            v-model:value="loadForm.message"
            type="textarea"
            rows="3"
            placeholder="请输入压测消息"
          />
        </NFormItem>
        <NSpace justify="end">
          <NButton type="primary" @click="runLoadTest">执行压测</NButton>
          <NButton tertiary :disabled="!loadSummary.id" @click="refreshRun">刷新结果</NButton>
        </NSpace>
      </NForm>

      <div v-if="loadSummary.id" class="mt-4">
        <!-- 进度条 -->
        <div v-if="isPolling || loadSummary.status === 'running'" class="mb-4">
          <NCard size="small" title="执行进度">
            <NProgress
              type="line"
              :percentage="loadProgress"
              :status="loadSummary.failure_count > 0 ? 'warning' : 'success'"
              :show-indicator="true"
            />
            <div class="mt-2 text-sm text-gray-500">
              进度: {{ loadSummary.completed_count || 0 }} / {{ loadSummary.batch_size || 0 }}
              (成功: {{ loadSummary.success_count || 0 }}, 失败: {{ loadSummary.failure_count || 0 }})
            </div>
          </NCard>
        </div>

        <NCard size="small" title="压测摘要">
          <NSpace split="|" wrap>
            <span>运行ID：{{ loadSummary.id }}</span>
            <span>成功：{{ loadSummary.success_count }}</span>
            <span>失败：{{ loadSummary.failure_count }}</span>
            <span>状态：{{ loadSummary.status }}</span>
            <span>开始：{{ loadSummary.started_at }}</span>
            <span>结束：{{ loadSummary.finished_at }}</span>
          </NSpace>
          <div v-if="latestRun?.jwt_token" class="mt-2 text-sm text-gray-500">
            JWT：{{ latestRun.jwt_token }}
          </div>
        </NCard>

        <NTable :single-line="false" class="mt-4" size="small" striped>
          <thead>
            <tr>
              <th style="width: 80px">序号</th>
              <th>请求内容</th>
              <th style="width: 120px">成功</th>
              <th style="width: 120px">耗时(ms)</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!loadTests.length">
              <td colspan="5" class="py-4 text-center text-gray-500">暂无压测记录</td>
            </tr>
            <tr v-for="(item, index) in loadTests" :key="item.id || index">
              <td>{{ index + 1 }}</td>
              <td>
                <NTooltip>
                  <template #trigger>
                    <span class="cursor-pointer text-primary">查看消息</span>
                  </template>
                  <template #default>
                    <div class="max-w-xs whitespace-pre-wrap">{{ item.request_message }}</div>
                  </template>
                </NTooltip>
              </td>
              <td>
                <NTag :type="item.success ? 'success' : 'error'" size="small" :bordered="false">
                  {{ item.success ? '成功' : '失败' }}
                </NTag>
              </td>
              <td>{{ item.latency_ms ? item.latency_ms.toFixed?.(0) : '--' }}</td>
              <td>{{ item.error || '--' }}</td>
            </tr>
          </tbody>
        </NTable>
      </div>
    </NCard>
  </NSpace>
</template>

<style scoped>
.cursor-pointer {
  cursor: pointer;
}
.text-primary {
  color: #2080f0;
}
.text-error {
  color: #d03050;
}
</style>
