<script setup>
import { computed, h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NDataTable,
  NDatePicker,
  NForm,
  NFormItem,
  NInput,
  NSelect,
  NSpace,
  NTag,
  useMessage,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'SystemUserEntitlements' })

const message = useMessage()
const vPermission = resolveDirective('permission')

const loading = ref(false)
const saving = ref(false)

const queryUserId = ref('')

const flagsError = ref('')

const statsLoading = ref(false)
const stats = ref(null)

const presetsLoading = ref(false)
const tierPresets = ref([])

const listLoading = ref(false)
const listRows = ref([])
const listTier = ref(null)
const listActiveOnly = ref(false)
const listUserId = ref('')

const tierOptions = computed(() => {
  const defaults = [
    { label: 'free', value: 'free' },
    { label: 'pro', value: 'pro' },
  ]
  const map = new Map(defaults.map((opt) => [opt.value, opt]))
  const list = Array.isArray(tierPresets.value) ? tierPresets.value : []
  list.forEach((item) => {
    const tier = String(item?.tier || '').trim().toLowerCase()
    if (!tier || tier === 'other') return
    map.set(tier, { label: tier, value: tier })
  })
  return Array.from(map.values())
})

const listTierOptions = computed(() => [{ label: '全部', value: null }, ...tierOptions.value])

const presetsByTier = computed(() => {
  const map = {}
  const list = Array.isArray(tierPresets.value) ? tierPresets.value : []
  list.forEach((item) => {
    const tier = String(item?.tier || '').trim().toLowerCase()
    if (!tier || tier === 'other') return
    map[tier] = item
  })
  return map
})

const form = ref({
  user_id: '',
  tier: 'free',
  expires_at: null,
  flagsText: '{}',
  last_updated: null,
  exists: false,
})

const pagination = ref({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page) => {
    pagination.value.page = page
    loadList()
  },
  onUpdatePageSize: (pageSize) => {
    pagination.value.pageSize = pageSize
    pagination.value.page = 1
    loadList()
  },
})

const lastUpdatedText = computed(() => {
  const ms = Number(form.value?.last_updated)
  if (!Number.isFinite(ms) || ms <= 0) return '--'
  return new Date(ms).toLocaleString()
})

const statsSummary = computed(() => {
  const data = stats.value && typeof stats.value === 'object' ? stats.value : {}
  const tiers = Array.isArray(data.tiers) ? data.tiers : []
  return {
    total_rows: Number(data.total_rows) || 0,
    tiers: tiers
      .map((item) => ({
        tier: String(item?.tier || '').trim(),
        count: Number(item?.count) || 0,
      }))
      .filter((item) => item.tier),
    pro_active: Number(data.pro_active) || 0,
    pro_expired: Number(data.pro_expired) || 0,
  }
})

function normalizeUserId(value) {
  return String(value || '').trim()
}

function formatMs(ms) {
  const v = Number(ms)
  if (!Number.isFinite(v) || v <= 0) return '--'
  return new Date(v).toLocaleString()
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
    await loadStats()
    await loadList()
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
    await loadStats()
    await loadList()
  } finally {
    saving.value = false
  }
}

async function loadStats() {
  statsLoading.value = true
  try {
    const res = await api.getUserEntitlementsStats()
    stats.value = res?.data || null
  } finally {
    statsLoading.value = false
  }
}

async function loadTierPresets() {
  presetsLoading.value = true
  try {
    const res = await api.getUserEntitlementTierPresets()
    tierPresets.value = Array.isArray(res?.data) ? res.data : []
  } finally {
    presetsLoading.value = false
  }
}

async function loadList() {
  listLoading.value = true
  try {
    const params = {
      page: pagination.value.page,
      page_size: pagination.value.pageSize,
      tier: listTier.value,
      active_only: listActiveOnly.value,
      user_id: normalizeUserId(listUserId.value) || undefined,
    }
    const res = await api.listUserEntitlements(params)
    const data = res?.data || {}
    listRows.value = Array.isArray(data.items) ? data.items : []
    pagination.value.itemCount = Number(data.total) || 0
  } finally {
    listLoading.value = false
  }
}

async function handleSearchList() {
  pagination.value.page = 1
  await loadList()
}

function resetListFilters() {
  listTier.value = null
  listActiveOnly.value = false
  listUserId.value = ''
  pagination.value.page = 1
  loadList()
}

async function quickSetTier(row, tier, expiresAt) {
  if (!row || !row.user_id) return
  const preset = presetsByTier.value[String(tier || '').trim().toLowerCase()] || {}
  const presetFlags = preset?.flags && typeof preset.flags === 'object' && !Array.isArray(preset.flags) ? preset.flags : {}
  const flags = Object.keys(presetFlags).length ? presetFlags : {}

  saving.value = true
  try {
    const res = await api.upsertUserEntitlements({
      user_id: String(row.user_id),
      tier: String(tier || 'free'),
      expires_at: expiresAt ?? null,
      flags,
    })
    fillForm(res?.data)
    queryUserId.value = String(row.user_id)
    message.success('已更新')
    await loadStats()
    await loadList()
  } finally {
    saving.value = false
  }
}

const listColumns = [
  {
    title: 'user_id',
    key: 'user_id',
    width: 260,
    ellipsis: { tooltip: true },
  },
  {
    title: 'tier',
    key: 'tier',
    width: 90,
    render: (row) => {
      const tier = String(row?.tier || 'free')
      const type = tier === 'pro' ? 'success' : tier === 'free' ? 'default' : 'warning'
      return h(NTag, { type, size: 'small' }, { default: () => tier })
    },
  },
  {
    title: 'expires_at',
    key: 'expires_at',
    width: 180,
    render: (row) => formatMs(row?.expires_at),
  },
  {
    title: 'last_updated',
    key: 'last_updated',
    width: 180,
    render: (row) => formatMs(row?.last_updated),
  },
  {
    title: '操作',
    key: 'actions',
    width: 260,
    render: (row) => {
      const now = Date.now()
      const proPreset = presetsByTier.value.pro || {}
      const rawDays = proPreset?.default_expires_days
      const proDays = typeof rawDays === 'number' && Number.isFinite(rawDays) ? rawDays : null
      const expiresPro = proDays == null ? null : now + proDays * 24 * 60 * 60 * 1000
      return h(
        NSpace,
        { size: 'small' },
        {
          default: () => [
            h(
              NButton,
              {
                size: 'small',
                secondary: true,
                onClick: () => {
                  queryUserId.value = String(row?.user_id || '')
                  fillForm({
                    user_id: String(row?.user_id || ''),
                    tier: String(row?.tier || 'free'),
                    expires_at: Number.isFinite(Number(row?.expires_at)) ? Number(row?.expires_at) : null,
                    flags: row?.flags,
                    last_updated: row?.last_updated,
                    exists: true,
                  })
                },
              },
              { default: () => '编辑' }
            ),
            withDirectives(
              h(
                NButton,
                {
                  size: 'small',
                  type: 'success',
                  secondary: true,
                  onClick: () => quickSetTier(row, 'pro', expiresPro),
                },
                { default: () => (proDays == null ? 'Pro' : `Pro ${proDays}天`) }
              ),
              [[vPermission, 'post/api/v1/admin/user-entitlements']]
            ),
            withDirectives(
              h(
                NButton,
                {
                  size: 'small',
                  type: 'default',
                  secondary: true,
                  onClick: () => quickSetTier(row, 'free', null),
                },
                { default: () => 'Free' }
              ),
              [[vPermission, 'post/api/v1/admin/user-entitlements']]
            ),
          ],
        }
      )
    },
  },
]

onMounted(() => {
  loadTierPresets()
  loadStats()
  loadList()
})
</script>

<template>
  <CommonPage title="用户权益">
    <NSpace vertical size="large">
      <NCard title="等级统计" size="small" :loading="statsLoading">
        <NSpace align="center" justify="space-between" wrap>
          <NSpace align="center" wrap>
            <NTag type="info">total_rows: {{ statsSummary.total_rows }}</NTag>
            <NTag
              v-for="item in statsSummary.tiers"
              :key="item.tier"
              :type="item.tier === 'pro' ? 'success' : item.tier === 'other' ? 'warning' : 'default'"
            >
              {{ item.tier }}: {{ item.count }}
            </NTag>
            <NTag type="success">pro_active: {{ statsSummary.pro_active }}</NTag>
            <NTag type="error">pro_expired: {{ statsSummary.pro_expired }}</NTag>
          </NSpace>
          <NButton v-permission="'get/api/v1/admin/user-entitlements/stats'" :loading="statsLoading" @click="loadStats">
            刷新
          </NButton>
        </NSpace>
        <NAlert class="mt-12" type="warning" title="说明">
          统计基于 Supabase `user_entitlements` 表行数；未创建 entitlements 行的用户默认视为 free，但此处不会计入。
        </NAlert>
      </NCard>

      <NCard title="用户列表" size="small">
        <NSpace align="center" wrap>
          <NSelect v-model:value="listTier" :options="listTierOptions" style="width: 140px" />
          <NCheckbox v-model:checked="listActiveOnly">仅活跃</NCheckbox>
          <NInput v-model:value="listUserId" placeholder="user_id（可选）" style="width: 320px" />
          <NButton
            v-permission="'get/api/v1/admin/user-entitlements/list'"
            type="primary"
            :loading="listLoading"
            @click="handleSearchList"
          >
            查询
          </NButton>
          <NButton :disabled="listLoading" @click="resetListFilters">重置</NButton>
        </NSpace>
        <div class="mt-12">
          <NDataTable
            :columns="listColumns"
            :data="listRows"
            :loading="listLoading"
            :pagination="pagination"
            :row-key="(row) => row.user_id"
          />
        </div>
      </NCard>

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
