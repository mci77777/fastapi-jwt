<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import {
  NButton,
  NCard,
  NCode,
  NCollapse,
  NCollapseItem,
  NDivider,
  NForm,
  NFormItem,
  NGrid,
  NGridItem,
  NInput,
  NInputNumber,
  NModal,
  NProgress,
  NSelect,
  NSpace,
  NStatistic,
  NSwitch,
  NTable,
  NTabs,
  NTabPane,
  NTag,
  NTooltip,
  NInputGroup,
} from 'naive-ui'
import { storeToRefs } from 'pinia'

import { useAiModelSuiteStore } from '@/store'
import { createMailUser } from '@/api/aiModelSuite'

defineOptions({ name: 'AiJwtSimulation' })

// ==================== 配置持久化 ====================
const STORAGE_KEYS = {
  SINGLE_FORM: 'jwt_test_single_form_config',
  LOAD_FORM: 'jwt_test_load_form_config',
  MULTI_USER_FORM: 'jwt_test_multi_user_form_config',
}

// 默认配置
const DEFAULT_SINGLE_FORM = {
  prompt_id: null,
  endpoint_id: null,
  model: null,
  message: '',
  username: 'admin',
  skip_prompt: false,
}

const DEFAULT_LOAD_FORM = {
  prompt_id: null,
  endpoint_id: null,
  model: null,
  message: '',
  batch_size: 10,
  concurrency: 5,
  stop_on_error: false,
  username: 'admin',
  skip_prompt: false,
}

const DEFAULT_MULTI_USER_FORM = {
  user_count: 5,
  username_prefix: 'test-user-',
  password: '123456',
  prompt_id: null,
  endpoint_id: null,
  model: null,
  message: '',
  concurrency: 3,
  skip_prompt: false,
}

// 从 localStorage 加载配置
function loadFormConfig(key, defaultConfig) {
  try {
    const saved = localStorage.getItem(key)
    if (saved) {
      return { ...defaultConfig, ...JSON.parse(saved) }
    }
  } catch (error) {
    console.warn('加载配置失败:', error)
  }
  return { ...defaultConfig }
}

// 保存配置到 localStorage
function saveFormConfig(key, config) {
  try {
    localStorage.setItem(key, JSON.stringify(config))
  } catch (error) {
    console.warn('保存配置失败:', error)
  }
}

const store = useAiModelSuiteStore()
const { models, prompts, latestRun, latestRunSummary, latestRunLoading } = storeToRefs(store)

// 表单配置（从 localStorage 加载）
const singleForm = reactive(loadFormConfig(STORAGE_KEYS.SINGLE_FORM, DEFAULT_SINGLE_FORM))
const loadForm = reactive(loadFormConfig(STORAGE_KEYS.LOAD_FORM, DEFAULT_LOAD_FORM))
const multiUserForm = reactive(
  loadFormConfig(STORAGE_KEYS.MULTI_USER_FORM, DEFAULT_MULTI_USER_FORM)
)

// 状态管理
const singleResult = ref(null)
const singleError = ref(null)
const pollingTimer = ref(null)
const isPolling = ref(false)
const expandedTestRows = ref(new Set())
const singleLoading = ref(false)
const loadTestLoading = ref(false)
const multiUserLoading = ref(false)
const jwtToken = ref(null)

// 弹窗控制
const showSingleDetailModal = ref(false)
const showLoadDetailModal = ref(false)
const showMultiUserDetailModal = ref(false)

// 多用户测试结果
const multiUserResults = ref([])
const multiUserSummary = ref(null)

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

/**
 * 获取真实的 Supabase JWT Token
 */
async function fetchRealJWT(username) {
  try {
    const { request } = await import('@/utils')
    const response = await request.post('/base/access_token', {
      username: username || 'admin',
      password: '123456', // 测试账号密码
    })
    return response.data?.access_token || null
  } catch (error) {
    window.$message?.error('获取 JWT Token 失败: ' + (error.message || '未知错误'))
    throw error
  }
}

// ==================== 工具函数 ====================
/**
 * 重置表单为默认值
 */
function resetSingleForm() {
  Object.assign(singleForm, DEFAULT_SINGLE_FORM)
  localStorage.removeItem(STORAGE_KEYS.SINGLE_FORM)
  window.$message?.success('已重置为默认配置')
}

function resetLoadForm() {
  Object.assign(loadForm, DEFAULT_LOAD_FORM)
  localStorage.removeItem(STORAGE_KEYS.LOAD_FORM)
  window.$message?.success('已重置为默认配置')
}

function resetMultiUserForm() {
  Object.assign(multiUserForm, DEFAULT_MULTI_USER_FORM)
  localStorage.removeItem(STORAGE_KEYS.MULTI_USER_FORM)
  window.$message?.success('已重置为默认配置')
}

/**
 * 复制到剪贴板
 */
function copyToClipboard(text) {
  if (!text) {
    window.$message?.warning('无内容可复制')
    return
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      window.$message?.success('已复制到剪贴板')
    })
  } else {
    // 降级方案
    const textarea = document.createElement('textarea')
    textarea.value = text
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    window.$message?.success('已复制到剪贴板')
  }
}

/**
 * 导出 JSON 数据
 */
function exportJSON(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
  window.$message?.success('导出成功')
}

// ==================== 业务逻辑 ====================
const generatingUser = ref(false)
async function handleGenerateMailUser() {
  generatingUser.value = true
  try {
    const { data } = await createMailUser({
      mail_api_key: store.mailApiKey || undefined,
      username_prefix: 'auto-user',
    })
    
    if (data) {
      singleForm.username = data.username
      jwtToken.value = data.access_token
      window.$message.success(`用户 ${data.username} 创建成功`)
    }
  } catch (error) {
    window.$message.error('创建用户失败: ' + (error.message || '未知错误'))
  } finally {
    generatingUser.value = false
  }
}

async function runSingle() {
  singleError.value = null
  singleResult.value = null
  singleLoading.value = true

  try {
    // 保存配置
    saveFormConfig(STORAGE_KEYS.SINGLE_FORM, singleForm)

    // 1. 获取 JWT Token
    let token = jwtToken.value
    
    // 如果是 admin，总是刷新 token 为最新的
    // 如果不是 admin，且没有 token，尝试获取或报错
    if (singleForm.username === 'admin') {
         window.$message?.info('正在获取 admin Token...')
         token = await fetchRealJWT('admin')
    } else if (!token) {
         // 尝试检查是否有缓存或者抛错
         throw new Error("非 admin 用户请先生成用户或手动填入 Token")
    }
    
    jwtToken.value = token

    // 2. 使用真实 JWT 执行对话模拟
    window.$message?.info('正在执行对话模拟...')
    const payload = {
      prompt_id: singleForm.prompt_id,
      endpoint_id: singleForm.endpoint_id,
      message: singleForm.message,
      model: singleForm.model,
      username: singleForm.username,
      skip_prompt: singleForm.skip_prompt,
    }
    const { data } = await store.simulateDialog(payload)
    singleResult.value = {
      ...data,
      jwt_token: token,
      timestamp: new Date().toISOString(),
    }
    window.$message?.success('模拟完成')
    showSingleDetailModal.value = true // 自动打开详情弹窗
  } catch (error) {
    singleError.value = error?.message || String(error)
    window.$message?.error('模拟失败: ' + singleError.value)
  } finally {
    singleLoading.value = false
  }
}

async function runLoadTest() {
  loadTestLoading.value = true

  try {
    // 保存配置
    saveFormConfig(STORAGE_KEYS.LOAD_FORM, loadForm)

    // 1. 先获取真实的 Supabase JWT
    window.$message?.info('正在获取 JWT Token...')
    const token = await fetchRealJWT(loadForm.username)
    jwtToken.value = token

    // 2. 使用真实 JWT 执行压测
    window.$message?.info('正在启动压测...')
    const payload = {
      prompt_id: loadForm.prompt_id,
      endpoint_id: loadForm.endpoint_id,
      message: loadForm.message,
      batch_size: loadForm.batch_size,
      concurrency: loadForm.concurrency,
      stop_on_error: loadForm.stop_on_error,
      model: loadForm.model,
      username: loadForm.username,
      skip_prompt: loadForm.skip_prompt,
    }

    const result = await store.triggerLoadTest(payload)
    // 开始轮询进度
    const runId = result?.summary?.id
    if (runId) {
      startPolling(runId)
    }
    window.$message?.success('压测已启动，正在后台执行...')
  } catch (error) {
    window.$message?.error('压测启动失败: ' + (error?.message || '未知错误'))
  } finally {
    loadTestLoading.value = false
  }
}

/**
 * 多用户并发测试
 * 注意：由于后端仅支持 admin/123456，这里使用单个 JWT Token 模拟多个并发请求
 */
async function runMultiUserTest() {
  multiUserLoading.value = true
  multiUserResults.value = []
  multiUserSummary.value = null

  try {
    // 保存配置
    saveFormConfig(STORAGE_KEYS.MULTI_USER_FORM, multiUserForm)

    window.$message?.info('正在启动多用户并发测试...')

    const startTime = Date.now()

    // 1. 使用 admin 账号获取一个 JWT Token
    window.$message?.info('正在获取 JWT Token (admin 账号)...')
    let sharedToken = null
    try {
      sharedToken = await fetchRealJWT('admin')
      window.$message?.success('JWT Token 获取成功')
    } catch (error) {
      window.$message?.error('JWT Token 获取失败: ' + error.message)
      multiUserSummary.value = {
        total_users: multiUserForm.user_count,
        success_users: 0,
        failed_users: multiUserForm.user_count,
        success_tests: 0,
        failed_tests: 0,
        total_time_ms: Date.now() - startTime,
        avg_time_ms: 0,
      }
      return
    }

    // 2. 生成虚拟用户列表（用于标识不同的并发请求）
    const virtualUsers = []
    for (let i = 1; i <= multiUserForm.user_count; i++) {
      virtualUsers.push({
        username: `${multiUserForm.username_prefix}${i}`,
        index: i,
        token: sharedToken, // 所有用户共享同一个 Token
      })
    }

    window.$message?.info(`开始并发执行 ${virtualUsers.length} 个 AI 对话测试...`)

    // 3. 并发执行 AI 对话测试（使用共享的 JWT Token）
    const testPromises = virtualUsers.map(async (user) => {
      const testStartTime = Date.now()
      try {
        const payload = {
          prompt_id: multiUserForm.prompt_id,
          endpoint_id: multiUserForm.endpoint_id,
          message: multiUserForm.message,
          model: multiUserForm.model,
          username: 'admin', // 实际使用 admin 账号
          skip_prompt: multiUserForm.skip_prompt,
        }
        const { data } = await store.simulateDialog(payload)
        const testLatency = Date.now() - testStartTime
        return {
          ...user,
          jwt_success: true,
          test_success: true,
          test_result: data,
          test_error: null,
          latency_ms: testLatency,
        }
      } catch (error) {
        const testLatency = Date.now() - testStartTime
        return {
          ...user,
          jwt_success: true, // JWT 获取成功
          test_success: false, // 但 AI 对话测试失败
          test_result: null,
          test_error: error.message,
          latency_ms: testLatency,
        }
      }
    })

    const testResults = await Promise.all(testPromises)
    multiUserResults.value = testResults

    const totalTime = Date.now() - startTime
    const successTests = testResults.filter((r) => r.test_success).length
    const avgLatency = testResults.reduce((sum, r) => sum + r.latency_ms, 0) / testResults.length

    multiUserSummary.value = {
      total_users: virtualUsers.length,
      success_users: virtualUsers.length, // 所有用户都成功获取 JWT（共享 Token）
      failed_users: 0,
      success_tests: successTests,
      failed_tests: virtualUsers.length - successTests,
      total_time_ms: totalTime,
      avg_time_ms: avgLatency,
    }

    window.$message?.success(`多用户测试完成: ${successTests}/${virtualUsers.length} 成功`)
    showMultiUserDetailModal.value = true // 自动打开详情弹窗
  } catch (error) {
    window.$message?.error('多用户测试失败: ' + (error?.message || '未知错误'))
  } finally {
    multiUserLoading.value = false
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

/**
 * 切换测试行展开状态
 */
function toggleTestRow(index) {
  if (expandedTestRows.value.has(index)) {
    expandedTestRows.value.delete(index)
  } else {
    expandedTestRows.value.add(index)
  }
}

// ==================== 生命周期钩子 ====================
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
    <!-- 单次对话模拟 -->
    <NCard title="🎯 单次对话模拟" size="small">
      <template #header-extra>
        <NButton text size="small" @click="resetSingleForm">重置配置</NButton>
      </template>

      <NForm :model="singleForm" label-placement="left" label-width="90">
        <NGrid :cols="24" :x-gap="12">
          <NGridItem :span="12">
            <NFormItem label="Prompt" path="prompt_id">
              <NSelect v-model:value="singleForm.prompt_id" :options="promptOptions" filterable />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="12">
            <NFormItem label="模型接口" path="endpoint_id">
              <NSelect
                v-model:value="singleForm.endpoint_id"
                :options="endpointOptions"
                filterable
              />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="12">
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
          </NGridItem>

          <NGridItem :span="12">
            <NFormItem label="用户名" path="username">
              <NInputGroup>
                <NInput
                  v-model:value="singleForm.username"
                  placeholder="admin 或 生成的用户"
                  :disabled="singleLoading"
                />
                <NButton type="info" ghost @click="handleGenerateMailUser" :loading="generatingUser">
                   生成测试用户
                </NButton>
              </NInputGroup>
            </NFormItem>
          </NGridItem>
          <NGridItem :span="12">
            <NFormItem label="跳过Prompt" path="skip_prompt">
              <NSwitch v-model:value="singleForm.skip_prompt">
                <template #checked>跳过</template>
                <template #unchecked>注入</template>
              </NSwitch>
              <NTooltip trigger="hover">
                <template #trigger>
                  <span class="ml-2 text-gray-400 cursor-help">ℹ️</span>
                </template>
                开启后，将不向模型发送 Prompt (System Message)，仅发送用户消息。
              </NTooltip>
            </NFormItem>
          </NGridItem>
        </NGrid>

        <NFormItem label="对话内容" path="message">
          <NInput
            v-model:value="singleForm.message"
            type="textarea"
            rows="4"
            placeholder="请输入用户消息"
            :disabled="singleLoading"
          />
        </NFormItem>

        <NSpace justify="space-between">
          <NSpace>
            <NTag v-if="singleResult" type="success" size="small"> ✅ 上次执行成功 </NTag>
            <NTag v-else-if="singleError" type="error" size="small"> ❌ 上次执行失败 </NTag>
          </NSpace>
          <NSpace>
            <NButton
              v-if="singleResult"
              secondary
              size="small"
              @click="showSingleDetailModal = true"
            >
              查看详情
            </NButton>
            <NButton type="primary" :loading="singleLoading" @click="runSingle">
              {{ singleLoading ? '执行中...' : '执行模拟' }}
            </NButton>
          </NSpace>
        </NSpace>
      </NForm>


      <!-- 简要结果摘要 -->
      <div v-if="singleResult && !singleLoading" class="mt-4">
        <NDivider />
        <NSpace vertical size="small">
          <NStatistic label="JWT Token" :value="jwtToken?.substring(0, 20) + '...'">
            <template #suffix>
              <NButton text size="tiny" @click="copyToClipboard(jwtToken)">复制</NButton>
            </template>
          </NStatistic>
          <NStatistic
            label="执行耗时"
            :value="singleResult.result?.latency_ms?.toFixed?.(0) || '--'"
            suffix="ms"
          />
        </NSpace>
      </div>
    </NCard>
    <!-- 并发压测 -->
    <NCard title="⚡ 并发压测" size="small" :loading="latestRunLoading">
      <template #header-extra>
        <NButton text size="small" @click="resetLoadForm">重置配置</NButton>
      </template>
      <NForm :model="loadForm" label-placement="left" label-width="90">
        <NGrid :cols="24" :x-gap="12">
          <NGridItem :span="8">
            <NFormItem label="Prompt" path="prompt_id">
              <NSelect
                v-model:value="loadForm.prompt_id"
                :options="promptOptions"
                filterable
                :disabled="loadTestLoading"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="8">
            <NFormItem label="模型接口" path="endpoint_id">
              <NSelect
                v-model:value="loadForm.endpoint_id"
                :options="endpointOptions"
                filterable
                :disabled="loadTestLoading"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="8">
            <NFormItem label="模型名称" path="model">
              <NSelect
                v-model:value="loadForm.model"
                :options="loadModelOptions.length ? loadModelOptions : globalModelOptions"
                filterable
                clearable
                tag
                placeholder="选择或输入模型名称"
                :disabled="loadTestLoading"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="8">
            <NFormItem label="批次数" path="batch_size">
              <NInputNumber
                v-model:value="loadForm.batch_size"
                :min="1"
                :max="1000"
                :disabled="loadTestLoading"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="8">
            <NFormItem label="并发数" path="concurrency">
              <NInputNumber
                v-model:value="loadForm.concurrency"
                :min="1"
                :max="1000"
                :disabled="loadTestLoading"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="8">
            <NFormItem label="出错即停" path="stop_on_error">
              <NSwitch v-model:value="loadForm.stop_on_error" :disabled="loadTestLoading" />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="8">
            <NFormItem label="跳过Prompt" path="skip_prompt">
              <NSwitch v-model:value="loadForm.skip_prompt" :disabled="loadTestLoading">
                <template #checked>跳过</template>
                <template #unchecked>注入</template>
              </NSwitch>
            </NFormItem>
          </NGridItem>
        </NGrid>

        <NFormItem label="压测消息" path="message">
          <NInput
            v-model:value="loadForm.message"
            type="textarea"
            rows="3"
            placeholder="请输入压测消息"
            :disabled="loadTestLoading"
          />
        </NFormItem>

        <NSpace justify="space-between">
          <NSpace>
            <NTag v-if="isPolling" type="info" size="small"> 🔄 压测进行中... </NTag>
            <NTag v-else-if="loadSummary.id" type="success" size="small"> ✅ 压测已完成 </NTag>
          </NSpace>
          <NSpace>
            <NButton
              v-if="loadSummary.id"
              secondary
              size="small"
              @click="showLoadDetailModal = true"
            >
              查看详细报告
            </NButton>
            <NButton tertiary :disabled="!loadSummary.id || isPolling" @click="refreshRun">
              刷新结果
            </NButton>
            <NButton type="primary" :loading="loadTestLoading" @click="runLoadTest">
              {{ loadTestLoading ? '启动中...' : '执行压测' }}
            </NButton>
          </NSpace>
        </NSpace>
      </NForm>

      <!-- 压测结果摘要 -->
      <div v-if="loadSummary.id" class="mt-4">
        <NDivider />

        <!-- 进度条 -->
        <div v-if="isPolling || loadSummary.status === 'running'" class="mb-4">
          <NProgress
            type="line"
            :percentage="loadProgress"
            :status="loadSummary.failure_count > 0 ? 'warning' : 'success'"
            :show-indicator="true"
          />
          <div class="mt-2 text-sm text-gray-500">
            进度: {{ loadSummary.completed_count || 0 }} / {{ loadSummary.batch_size || 0 }} (成功:
            {{ loadSummary.success_count || 0 }}, 失败: {{ loadSummary.failure_count || 0 }})
          </div>
        </div>

        <!-- 关键指标卡片 -->
        <NGrid :cols="4" :x-gap="12" class="mb-4">
          <NGridItem>
            <NStatistic label="总请求数" :value="loadSummary.batch_size || 0" />
          </NGridItem>
          <NGridItem>
            <NStatistic label="成功数" :value="loadSummary.success_count || 0">
              <template #suffix>
                <NTag type="success" size="small">
                  {{ ((loadSummary.success_count / loadSummary.batch_size) * 100).toFixed(1) }}%
                </NTag>
              </template>
            </NStatistic>
          </NGridItem>
          <NGridItem>
            <NStatistic label="失败数" :value="loadSummary.failure_count || 0">
              <template #suffix>
                <NTag v-if="loadSummary.failure_count > 0" type="error" size="small">
                  {{ ((loadSummary.failure_count / loadSummary.batch_size) * 100).toFixed(1) }}%
                </NTag>
              </template>
            </NStatistic>
          </NGridItem>
          <NGridItem>
            <NStatistic label="状态" :value="loadSummary.status || '--'">
              <template #suffix>
                <NTag :type="loadSummary.status === 'completed' ? 'success' : 'info'" size="small">
                  {{ loadSummary.status === 'completed' ? '已完成' : '进行中' }}
                </NTag>
              </template>
            </NStatistic>
          </NGridItem>
        </NGrid>
      </div>
    </NCard>

    <!-- 多用户并发测试 -->
    <NCard title="👥 多用户并发测试" size="small">
      <template #header-extra>
        <NSpace>
          <NTag type="warning" size="small">实验性功能</NTag>
          <NButton text size="small" @click="resetMultiUserForm">重置配置</NButton>
        </NSpace>
      </template>

      <NCollapse>
        <NCollapseItem title="💡 功能说明" name="info">
          <div class="text-sm text-gray-600">
            <p class="mb-2">
              <strong>测试目的</strong>：模拟多个并发用户同时执行 AI
              对话测试，用于压力测试和性能评估。
            </p>
            <p class="mb-2"><strong>工作原理</strong>：</p>
            <ul class="mb-2 ml-2 list-disc list-inside">
              <li>使用 <code>admin/123456</code> 账号获取一个 JWT Token</li>
              <li>
                生成 N 个虚拟用户（如 <code>test-user-1</code>, <code>test-user-2</code>, ...）
              </li>
              <li>所有虚拟用户共享同一个 JWT Token</li>
              <li>并发执行 N 个 AI 对话请求（模拟多用户场景）</li>
            </ul>
            <p class="mb-2">
              ⚠️ <strong>注意</strong>：由于后端仅支持
              <code>admin/123456</code> 账号，虚拟用户名仅用于标识不同的并发请求，实际都使用 admin
              的 JWT Token。
            </p>
            <p>
              <strong>适用场景</strong>：测试 AI 接口在高并发下的性能表现、响应时间分布、错误率等。
            </p>
          </div>
        </NCollapseItem>
      </NCollapse>

      <NForm :model="multiUserForm" label-placement="left" label-width="110" class="mt-4">
        <NGrid :cols="24" :x-gap="12">
          <NGridItem :span="8">
            <NFormItem label="用户数量" path="user_count">
              <NInputNumber
                v-model:value="multiUserForm.user_count"
                :min="1"
                :max="50"
                :disabled="multiUserLoading"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="8">
            <NFormItem label="用户名前缀" path="username_prefix">
              <NInput
                v-model:value="multiUserForm.username_prefix"
                placeholder="test-user-"
                :disabled="multiUserLoading"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="8">
            <NFormItem label="并发数" path="concurrency">
              <NInputNumber
                v-model:value="multiUserForm.concurrency"
                :min="1"
                :max="20"
                :disabled="multiUserLoading"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="8">
            <NFormItem label="Prompt" path="prompt_id">
              <NSelect
                v-model:value="multiUserForm.prompt_id"
                :options="promptOptions"
                filterable
                :disabled="multiUserLoading"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="8">
            <NFormItem label="模型接口" path="endpoint_id">
              <NSelect
                v-model:value="multiUserForm.endpoint_id"
                :options="endpointOptions"
                filterable
                :disabled="multiUserLoading"
              />
            </NFormItem>
          </NGridItem>
          <NGridItem :span="8">
            <NFormItem label="模型名称" path="model">
              <NSelect
                v-model:value="multiUserForm.model"
                :options="globalModelOptions"
                filterable
                clearable
                tag
                :disabled="multiUserLoading"
              />
            </NFormItem>
          </NGridItem>
        </NGrid>

        <NFormItem label="测试消息" path="message">
          <NInput
            v-model:value="multiUserForm.message"
            type="textarea"
            rows="3"
            placeholder="请输入测试消息"
            :disabled="multiUserLoading"
          />
        </NFormItem>

        <NSpace justify="space-between">
          <NSpace>
            <NTag v-if="multiUserSummary" type="success" size="small"> ✅ 上次测试完成 </NTag>
          </NSpace>
          <NSpace>
            <NButton
              v-if="multiUserSummary"
              secondary
              size="small"
              @click="showMultiUserDetailModal = true"
            >
              查看详细结果
            </NButton>
            <NButton type="primary" :loading="multiUserLoading" @click="runMultiUserTest">
              {{ multiUserLoading ? '测试中...' : '开始测试' }}
            </NButton>
          </NSpace>
        </NSpace>
      </NForm>

      <!-- 多用户测试结果摘要 -->
      <div v-if="multiUserSummary && !multiUserLoading" class="mt-4">
        <NDivider />
        <NGrid :cols="4" :x-gap="12">
          <NGridItem>
            <NStatistic label="并发请求数" :value="multiUserSummary.total_users" />
          </NGridItem>
          <NGridItem>
            <NStatistic label="成功数" :value="multiUserSummary.success_tests">
              <template #suffix>
                <NTag type="success" size="small">
                  {{
                    ((multiUserSummary.success_tests / multiUserSummary.total_users) * 100).toFixed(
                      1
                    )
                  }}%
                </NTag>
              </template>
            </NStatistic>
          </NGridItem>
          <NGridItem>
            <NStatistic label="失败数" :value="multiUserSummary.failed_tests">
              <template #suffix>
                <NTag v-if="multiUserSummary.failed_tests > 0" type="error" size="small">
                  {{
                    ((multiUserSummary.failed_tests / multiUserSummary.total_users) * 100).toFixed(
                      1
                    )
                  }}%
                </NTag>
              </template>
            </NStatistic>
          </NGridItem>
          <NGridItem>
            <NStatistic
              label="平均耗时"
              :value="multiUserSummary.avg_time_ms?.toFixed?.(0) || '--'"
              suffix="ms"
            />
          </NGridItem>
        </NGrid>
      </div>
    </NCard>
  </NSpace>

  <!-- ==================== 弹窗组件 ==================== -->

  <!-- 单次测试详情弹窗 -->
  <NModal
    v-model:show="showSingleDetailModal"
    preset="card"
    title="🎯 单次对话模拟 - 详细结果"
    style="width: 80%; max-width: 1200px"
    :segmented="{ content: 'soft', footer: 'soft' }"
  >
    <NTabs type="line" animated>
      <NTabPane name="summary" tab="📊 结果摘要">
        <NSpace vertical size="large">
          <!-- JWT Token 信息 -->
          <div>
            <div class="mb-2 text-sm font-semibold">🔐 JWT Token</div>
            <NCode :code="jwtToken || '无'" language="text" />
            <NButton size="small" class="mt-2" @click="copyToClipboard(jwtToken)">
              复制 Token
            </NButton>
          </div>

          <!-- 关键指标 -->
          <div v-if="singleResult?.result">
            <div class="mb-2 text-sm font-semibold">⏱️ 性能指标</div>
            <NGrid :cols="3" :x-gap="12">
              <NGridItem>
                <NStatistic
                  label="响应延迟"
                  :value="singleResult.result.latency_ms?.toFixed?.(0) || '--'"
                  suffix="ms"
                />
              </NGridItem>
              <NGridItem v-if="singleResult.result.usage">
                <NStatistic
                  label="Prompt Tokens"
                  :value="singleResult.result.usage.prompt_tokens || 0"
                />
              </NGridItem>
              <NGridItem v-if="singleResult.result.usage">
                <NStatistic
                  label="Completion Tokens"
                  :value="singleResult.result.usage.completion_tokens || 0"
                />
              </NGridItem>
            </NGrid>
          </div>

          <!-- AI 回复 -->
          <div v-if="singleResult?.result?.response">
            <div class="mb-2 text-sm font-semibold">💬 AI 回复</div>
            <NCard size="small">
              <pre class="whitespace-pre-wrap">{{ singleResult.result.response }}</pre>
            </NCard>
          </div>
        </NSpace>
      </NTabPane>

      <NTabPane name="raw" tab="🔍 Raw 数据">
        <NCode :code="JSON.stringify(singleResult, null, 2)" language="json" />
        <NSpace class="mt-4">
          <NButton @click="copyToClipboard(JSON.stringify(singleResult, null, 2))">
            复制 JSON
          </NButton>
          <NButton @click="exportJSON(singleResult, 'single-test-result.json')">
            导出 JSON
          </NButton>
        </NSpace>
      </NTabPane>
    </NTabs>
  </NModal>

  <!-- 并发压测详情弹窗 -->
  <NModal
    v-model:show="showLoadDetailModal"
    preset="card"
    title="⚡ 并发压测 - 详细报告"
    style="width: 90%; max-width: 1400px"
    :segmented="{ content: 'soft', footer: 'soft' }"
  >
    <NTabs type="line" animated>
      <NTabPane name="summary" tab="📊 压测摘要">
        <NSpace vertical size="large">
          <!-- 关键指标 -->
          <NGrid :cols="4" :x-gap="12">
            <NGridItem>
              <NStatistic label="运行 ID" :value="loadSummary.id || '--'" />
            </NGridItem>
            <NGridItem>
              <NStatistic label="总请求数" :value="loadSummary.batch_size || 0" />
            </NGridItem>
            <NGridItem>
              <NStatistic label="成功数" :value="loadSummary.success_count || 0">
                <template #suffix>
                  <NTag type="success" size="small">
                    {{ ((loadSummary.success_count / loadSummary.batch_size) * 100).toFixed(1) }}%
                  </NTag>
                </template>
              </NStatistic>
            </NGridItem>
            <NGridItem>
              <NStatistic label="失败数" :value="loadSummary.failure_count || 0">
                <template #suffix>
                  <NTag v-if="loadSummary.failure_count > 0" type="error" size="small">
                    {{ ((loadSummary.failure_count / loadSummary.batch_size) * 100).toFixed(1) }}%
                  </NTag>
                </template>
              </NStatistic>
            </NGridItem>
          </NGrid>

          <!-- 时间信息 -->
          <div>
            <div class="mb-2 text-sm font-semibold">⏰ 时间信息</div>
            <NSpace>
              <span>开始时间: {{ loadSummary.started_at || '--' }}</span>
              <span>结束时间: {{ loadSummary.finished_at || '--' }}</span>
              <span>状态: {{ loadSummary.status || '--' }}</span>
            </NSpace>
          </div>
        </NSpace>
      </NTabPane>

      <NTabPane name="details" tab="📋 详细记录">
        <NTable :single-line="false" size="small" striped>
          <thead>
            <tr>
              <th style="width: 60px">展开</th>
              <th style="width: 80px">序号</th>
              <th>请求摘要</th>
              <th style="width: 100px">JWT 验证</th>
              <th style="width: 100px">成功</th>
              <th style="width: 100px">耗时(ms)</th>
              <th>错误</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!loadTests.length">
              <td colspan="7" class="py-4 text-center text-gray-500">暂无压测记录</td>
            </tr>
            <template v-for="(item, index) in loadTests" :key="item.id || index">
              <tr>
                <td>
                  <NButton text size="tiny" @click="toggleTestRow(index)">
                    {{ expandedTestRows.has(index) ? '▼' : '▶' }}
                  </NButton>
                </td>
                <td>{{ index + 1 }}</td>
                <td>
                  <NTooltip>
                    <template #trigger>
                      <span class="cursor-pointer text-primary">
                        {{ (item.request_message || '').substring(0, 30) }}...
                      </span>
                    </template>
                    <template #default>
                      <div class="max-w-xs whitespace-pre-wrap">{{ item.request_message }}</div>
                    </template>
                  </NTooltip>
                </td>
                <td>
                  <NTag
                    :type="
                      item.jwt_valid ? 'success' : item.jwt_valid === false ? 'error' : 'default'
                    "
                    size="small"
                    :bordered="false"
                  >
                    {{ item.jwt_valid ? '有效' : item.jwt_valid === false ? '无效' : '未验证' }}
                  </NTag>
                </td>
                <td>
                  <NTag :type="item.success ? 'success' : 'error'" size="small" :bordered="false">
                    {{ item.success ? '成功' : '失败' }}
                  </NTag>
                </td>
                <td>{{ item.latency_ms ? item.latency_ms.toFixed?.(0) : '--' }}</td>
                <td>{{ item.error || '--' }}</td>
              </tr>
              <!-- 展开的 Raw 数据行 -->
              <tr v-if="expandedTestRows.has(index)" class="expanded-row">
                <td colspan="7">
                  <div class="bg-gray-50 p-4 dark:bg-gray-800">
                    <!-- Token 使用统计 -->
                    <div v-if="item.usage" class="mb-3 rounded bg-blue-50 p-3">
                      <div class="mb-2 text-sm font-semibold">📊 Token 使用统计</div>
                      <div class="grid grid-cols-4 gap-2 text-xs">
                        <div>
                          <span class="text-gray-600">Prompt:</span>
                          <span class="ml-1 font-mono">{{ item.usage.prompt_tokens || 0 }}</span>
                        </div>
                        <div>
                          <span class="text-gray-600">Completion:</span>
                          <span class="ml-1 font-mono">{{
                            item.usage.completion_tokens || 0
                          }}</span>
                        </div>
                        <div>
                          <span class="text-gray-600">Total:</span>
                          <span class="ml-1 font-mono">{{ item.usage.total_tokens || 0 }}</span>
                        </div>
                        <div>
                          <span class="text-gray-600">⏱️ 延迟:</span>
                          <span class="ml-1 font-mono"
                            >{{ item.latency_ms?.toFixed?.(0) || '--' }} ms</span
                          >
                        </div>
                      </div>
                    </div>

                    <!-- 请求与响应 -->
                    <div class="mb-2">
                      <strong>📤 请求消息:</strong>
                      <pre class="raw-data mt-1">{{ item.request_message }}</pre>
                    </div>
                    <div v-if="item.response" class="mb-2">
                      <strong>📥 AI 回复:</strong>
                      <pre class="raw-data mt-1">{{ item.response }}</pre>
                    </div>

                    <!-- 完整 Raw 数据 -->
                    <div class="mb-2">
                      <strong>🔍 完整 Raw 数据:</strong>
                      <pre class="raw-data mt-1">{{ JSON.stringify(item, null, 2) }}</pre>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </NTable>
      </NTabPane>

      <NTabPane name="export" tab="📥 导出数据">
        <NSpace vertical>
          <div class="text-sm text-gray-600">导出完整的压测数据，包括所有请求和响应详情。</div>
          <NSpace>
            <NButton @click="exportJSON(latestRun, `load-test-${loadSummary.id}.json`)">
              导出完整数据
            </NButton>
            <NButton @click="exportJSON(loadSummary, `load-test-summary-${loadSummary.id}.json`)">
              仅导出摘要
            </NButton>
          </NSpace>
        </NSpace>
      </NTabPane>
    </NTabs>
  </NModal>

  <!-- 多用户测试详情弹窗 -->
  <NModal
    v-model:show="showMultiUserDetailModal"
    preset="card"
    title="👥 多用户并发测试 - 详细结果"
    style="width: 90%; max-width: 1400px"
    :segmented="{ content: 'soft', footer: 'soft' }"
  >
    <NTabs type="line" animated>
      <NTabPane name="summary" tab="📊 测试摘要">
        <NSpace vertical size="large">
          <!-- 关键指标 -->
          <NGrid :cols="4" :x-gap="12">
            <NGridItem>
              <NStatistic label="并发请求数" :value="multiUserSummary?.total_users || 0" />
            </NGridItem>
            <NGridItem>
              <NStatistic label="成功数" :value="multiUserSummary?.success_tests || 0">
                <template #suffix>
                  <NTag type="success" size="small">
                    {{
                      (
                        (multiUserSummary?.success_tests / multiUserSummary?.total_users) *
                        100
                      ).toFixed(1)
                    }}%
                  </NTag>
                </template>
              </NStatistic>
            </NGridItem>
            <NGridItem>
              <NStatistic label="失败数" :value="multiUserSummary?.failed_tests || 0">
                <template #suffix>
                  <NTag v-if="multiUserSummary?.failed_tests > 0" type="error" size="small">
                    {{
                      (
                        (multiUserSummary?.failed_tests / multiUserSummary?.total_users) *
                        100
                      ).toFixed(1)
                    }}%
                  </NTag>
                </template>
              </NStatistic>
            </NGridItem>
            <NGridItem>
              <NStatistic
                label="平均耗时"
                :value="multiUserSummary?.avg_time_ms?.toFixed?.(0) || '--'"
                suffix="ms"
              />
            </NGridItem>
          </NGrid>

          <!-- 时间信息 -->
          <div>
            <div class="mb-2 text-sm font-semibold">⏰ 时间信息</div>
            <NSpace>
              <span>总耗时: {{ multiUserSummary?.total_time_ms || '--' }} ms</span>
              <span>平均耗时: {{ multiUserSummary?.avg_time_ms?.toFixed?.(0) || '--' }} ms</span>
            </NSpace>
          </div>
        </NSpace>
      </NTabPane>

      <NTabPane name="details" tab="📋 用户详情">
        <div class="mb-4 rounded bg-blue-50 p-3">
          <div class="text-sm text-gray-600">
            💡 <strong>说明</strong>：所有虚拟用户共享同一个 JWT Token（admin
            账号），用于模拟并发请求场景。
          </div>
        </div>
        <NTable :single-line="false" size="small" striped>
          <thead>
            <tr>
              <th style="width: 80px">序号</th>
              <th>虚拟用户名</th>
              <th style="width: 120px">测试状态</th>
              <th style="width: 120px">耗时 (ms)</th>
              <th>错误信息</th>
              <th style="width: 100px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!multiUserResults.length">
              <td colspan="6" class="py-4 text-center text-gray-500">暂无测试结果</td>
            </tr>
            <tr v-for="(user, index) in multiUserResults" :key="index">
              <td>{{ user.index }}</td>
              <td>{{ user.username }}</td>
              <td>
                <NTag :type="user.test_success ? 'success' : 'error'" size="small">
                  {{ user.test_success ? '✅ 成功' : '❌ 失败' }}
                </NTag>
              </td>
              <td>{{ user.latency_ms?.toFixed?.(0) || '--' }}</td>
              <td>{{ user.test_error || '--' }}</td>
              <td>
                <NButton
                  v-if="user.test_result"
                  text
                  size="tiny"
                  @click="copyToClipboard(JSON.stringify(user.test_result, null, 2))"
                >
                  复制结果
                </NButton>
              </td>
            </tr>
          </tbody>
        </NTable>
      </NTabPane>

      <NTabPane name="export" tab="📥 导出数据">
        <NSpace vertical>
          <div class="text-sm text-gray-600">
            导出多用户测试的完整数据，包括所有用户的 JWT 获取和 AI 对话测试结果。
          </div>
          <NSpace>
            <NButton
              @click="
                exportJSON(
                  { summary: multiUserSummary, results: multiUserResults },
                  'multi-user-test-results.json'
                )
              "
            >
              导出完整数据
            </NButton>
            <NButton @click="exportJSON(multiUserSummary, 'multi-user-test-summary.json')">
              仅导出摘要
            </NButton>
          </NSpace>
        </NSpace>
      </NTabPane>
    </NTabs>
  </NModal>
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
.raw-data {
  background-color: #f5f5f5;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  padding: 12px;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  overflow-x: auto;
  max-height: 400px;
  overflow-y: auto;
}
.expanded-row {
  background-color: #fafafa;
}
.bg-blue-50 {
  background-color: #eff6ff;
}
.bg-green-50 {
  background-color: #f0fdf4;
}
.grid {
  display: grid;
}
.grid-cols-3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.grid-cols-4 {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}
.gap-2 {
  gap: 0.5rem;
}
.rounded {
  border-radius: 0.375rem;
}
.font-mono {
  font-family: 'Courier New', monospace;
}
.text-gray-600 {
  color: #6b7280;
}
.flex {
  display: flex;
}
.items-center {
  align-items: center;
}
.flex-1 {
  flex: 1 1 0%;
}
.overflow-hidden {
  overflow: hidden;
}
.text-ellipsis {
  text-overflow: ellipsis;
}
.border {
  border: 1px solid #e5e7eb;
}
</style>
