<script setup>
import { computed, ref } from 'vue'
import { NAlert, NButton, NCard, NDatePicker, NForm, NFormItem, NInput, NSelect, NSpace, NTag, useMessage } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'SystemUserEntitlements' })

const message = useMessage()

const loading = ref(false)
const saving = ref(false)

const queryUserId = ref('')

const flagsError = ref('')

const tierOptions = [
  { label: 'free', value: 'free' },
  { label: 'pro', value: 'pro' },
]

const form = ref({
  user_id: '',
  tier: 'free',
  expires_at: null,
  flagsText: '{}',
  last_updated: null,
  exists: false,
})

const lastUpdatedText = computed(() => {
  const ms = Number(form.value?.last_updated)
  if (!Number.isFinite(ms) || ms <= 0) return '--'
  return new Date(ms).toLocaleString()
})

function normalizeUserId(value) {
  return String(value || '').trim()
}

function toJsonObjectText(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return '{}'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return '{}'
  }
}

function fillForm(snapshot) {
  const data = snapshot && typeof snapshot === 'object' ? snapshot : {}
  form.value.user_id = normalizeUserId(data.user_id)
  form.value.tier = String(data.tier || 'free')
  form.value.expires_at = Number.isFinite(Number(data.expires_at)) ? Number(data.expires_at) : null
  form.value.flagsText = toJsonObjectText(data.flags)
  form.value.last_updated = Number.isFinite(Number(data.last_updated)) ? Number(data.last_updated) : null
  form.value.exists = Boolean(data.exists)
  flagsError.value = ''
}

function parseFlags() {
  flagsError.value = ''
  const raw = String(form.value.flagsText || '').trim()
  if (!raw) return {}

  let parsed
  try {
    parsed = JSON.parse(raw)
  } catch (err) {
    flagsError.value = `JSON 解析失败：${err?.message || String(err)}`
    return null
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    flagsError.value = 'flags 必须是 JSON 对象'
    return null
  }
  return parsed
}

async function fetchEntitlements() {
  const userId = normalizeUserId(queryUserId.value)
  if (!userId) {
    message.error('请输入 user_id')
    return
  }

  loading.value = true
  try {
    const res = await api.getUserEntitlements({ user_id: userId })
    fillForm(res?.data)
  } finally {
    loading.value = false
  }
}

async function saveEntitlements() {
  const userId = normalizeUserId(form.value.user_id)
  if (!userId) {
    message.error('请先查询 user_id')
    return
  }

  const flags = parseFlags()
  if (flags == null) {
    message.error(flagsError.value || 'flags 无效')
    return
  }

  saving.value = true
  try {
    const res = await api.upsertUserEntitlements({
      user_id: userId,
      tier: String(form.value.tier || 'free'),
      expires_at: form.value.expires_at ?? null,
      flags,
    })
    fillForm(res?.data)
    message.success('已保存')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <CommonPage title="用户权益">
    <NSpace vertical size="large">
      <NCard title="查询" size="small">
        <NForm :label-width="90" :show-feedback="false">
          <NFormItem label="user_id">
            <NInput v-model:value="queryUserId" placeholder="Supabase auth.users.id（UUID）" />
          </NFormItem>
        </NForm>
        <NSpace>
          <NButton v-permission="'get/api/v1/admin/user-entitlements'" type="primary" :loading="loading" @click="fetchEntitlements">
            查询
          </NButton>
        </NSpace>
      </NCard>

      <NCard title="结果 / 编辑" size="small">
        <NAlert v-if="!form.user_id" type="info" title="提示">
          请输入 user_id 并点击“查询”。
        </NAlert>

        <template v-else>
          <NSpace vertical size="small">
            <NSpace>
              <NTag :type="form.exists ? 'success' : 'warning'">
                {{ form.exists ? '已存在' : '不存在（保存将创建）' }}
              </NTag>
              <NTag type="info">last_updated: {{ lastUpdatedText }}</NTag>
            </NSpace>

            <NForm :label-width="90">
              <NFormItem label="tier">
                <NSelect v-model:value="form.tier" :options="tierOptions" />
              </NFormItem>
              <NFormItem label="expires_at">
                <NDatePicker v-model:value="form.expires_at" type="datetime" clearable />
              </NFormItem>
              <NFormItem label="flags(JSON)" :validation-status="flagsError ? 'error' : undefined" :feedback="flagsError">
                <NInput
                  v-model:value="form.flagsText"
                  type="textarea"
                  :autosize="{ minRows: 6, maxRows: 14 }"
                  placeholder='{"skip_prompt": true}'
                />
              </NFormItem>
            </NForm>

            <NSpace>
              <NButton v-permission="'post/api/v1/admin/user-entitlements'" type="primary" :loading="saving" @click="saveEntitlements">
                保存
              </NButton>
            </NSpace>
          </NSpace>
        </template>
      </NCard>
    </NSpace>
  </CommonPage>
</template>
