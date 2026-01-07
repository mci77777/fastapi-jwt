<script setup>
import { computed, h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { NAlert, NButton, NCard, NDataTable, NForm, NFormItem, NInput, NInputNumber, NSpace, NTag, useMessage } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'SystemUserEntitlementsConfig' })

const message = useMessage()
const vPermission = resolveDirective('permission')

const loading = ref(false)
const saving = ref(false)
const rows = ref([])

const flagsError = ref('')

const form = ref({
  tier: '',
  default_expires_days: null,
  flagsText: '{}',
})

const normalizedTier = computed(() => String(form.value.tier || '').trim().toLowerCase())

function toJsonObjectText(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return '{}'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return '{}'
  }
}

function fillForm(row) {
  const data = row && typeof row === 'object' ? row : {}
  form.value.tier = String(data.tier || '')
  form.value.default_expires_days =
    Number.isFinite(Number(data.default_expires_days)) && Number(data.default_expires_days) >= 0
      ? Number(data.default_expires_days)
      : null
  form.value.flagsText = toJsonObjectText(data.flags)
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

async function loadPresets() {
  loading.value = true
  try {
    const res = await api.getUserEntitlementTierPresets()
    rows.value = Array.isArray(res?.data) ? res.data : []
  } finally {
    loading.value = false
  }
}

async function savePreset() {
  const tier = normalizedTier.value
  if (!tier) {
    message.error('请输入 tier')
    return
  }
  if (tier === 'other') {
    message.error("tier 'other' 为保留值")
    return
  }

  const flags = parseFlags()
  if (flags == null) {
    message.error(flagsError.value || 'flags 无效')
    return
  }

  saving.value = true
  try {
    await api.upsertUserEntitlementTierPreset({
      tier,
      default_expires_days: form.value.default_expires_days ?? null,
      flags,
    })
    message.success('已保存')
    await loadPresets()
  } finally {
    saving.value = false
  }
}

async function deletePreset(row) {
  const tier = String(row?.tier || '').trim().toLowerCase()
  if (!tier) return
  if (tier === 'other') {
    message.error("tier 'other' 为保留值")
    return
  }
  if (!window.confirm(`确认删除预设：${tier}？（free/pro 删除后会回退为默认预设）`)) return

  saving.value = true
  try {
    await api.deleteUserEntitlementTierPreset(tier)
    message.success('已删除')
    await loadPresets()
  } finally {
    saving.value = false
  }
}

const tableRows = computed(() => {
  const list = Array.isArray(rows.value) ? rows.value : []
  return list.map((item) => ({
    tier: String(item?.tier || '').trim(),
    default_expires_days: Number.isFinite(Number(item?.default_expires_days)) ? Number(item.default_expires_days) : null,
    flags: item?.flags && typeof item.flags === 'object' && !Array.isArray(item.flags) ? item.flags : {},
  }))
})

const columns = [
  {
    title: 'tier',
    key: 'tier',
    width: 120,
    render: (row) => h(NTag, { size: 'small', type: row.tier === 'pro' ? 'success' : 'default' }, { default: () => row.tier }),
  },
  {
    title: 'default_expires_days',
    key: 'default_expires_days',
    width: 180,
    render: (row) => (row.default_expires_days == null ? '--' : String(row.default_expires_days)),
  },
  {
    title: 'flags',
    key: 'flags',
    ellipsis: { tooltip: true },
    render: (row) => {
      const text = JSON.stringify(row.flags || {})
      return text.length > 120 ? `${text.slice(0, 120)}...` : text
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    render: (row) =>
      h(
        NSpace,
        { size: 'small' },
        {
          default: () => [
            withDirectives(
              h(
                NButton,
                {
                  size: 'small',
                  secondary: true,
                  onClick: () => fillForm(row),
                },
                { default: () => '编辑' }
              ),
              [[vPermission, 'get/api/v1/admin/user-entitlements/presets']]
            ),
            withDirectives(
              h(
                NButton,
                {
                  size: 'small',
                  type: 'error',
                  secondary: true,
                  onClick: () => deletePreset(row),
                },
                { default: () => '删除' }
              ),
              [[vPermission, 'delete/api/v1/admin/user-entitlements/presets']]
            ),
          ],
        }
      ),
  },
]

onMounted(() => {
  loadPresets()
})
</script>

<template>
  <CommonPage title="权益等级配置">
    <NSpace vertical size="large">
      <NAlert type="info" title="说明">
        这里配置的是「Dashboard 侧等级预设」：用于下拉选项与快捷升级；用户真实等级数据仍以 Supabase `user_entitlements` 为准。
      </NAlert>

      <NCard title="预设列表" size="small">
        <NSpace align="center" justify="space-between" wrap>
          <div />
          <NButton v-permission="'get/api/v1/admin/user-entitlements/presets'" :loading="loading" @click="loadPresets">刷新</NButton>
        </NSpace>
        <div class="mt-12">
          <NDataTable :columns="columns" :data="tableRows" :loading="loading" :row-key="(row) => row.tier" />
        </div>
      </NCard>

      <NCard title="新增 / 编辑" size="small">
        <NForm :label-width="160">
          <NFormItem label="tier">
            <NInput v-model:value="form.tier" placeholder="例如：free / pro / vip" />
          </NFormItem>
          <NFormItem label="default_expires_days">
            <NInputNumber v-model:value="form.default_expires_days" clearable :min="0" />
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
          <NButton
            v-permission="'post/api/v1/admin/user-entitlements/presets'"
            type="primary"
            :loading="saving"
            @click="savePreset"
          >
            保存
          </NButton>
        </NSpace>
      </NCard>
    </NSpace>
  </CommonPage>
</template>

