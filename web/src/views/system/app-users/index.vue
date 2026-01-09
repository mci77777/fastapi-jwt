<script setup>
import { computed, h, onMounted, reactive, ref } from 'vue'
import {
  NAlert,
  NButton,
  NCard,
  NCheckbox,
  NDataTable,
  NDatePicker,
  NDropdown,
  NDrawer,
  NDrawerContent,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NTag,
  useDialog,
  useMessage,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'SystemAppUsers' })

const message = useMessage()
const dialog = useDialog()

const bootLoading = ref(false)
const boot = ref(null)

const listLoading = ref(false)
const listRows = ref([])

const keyword = ref('')
const activeOnly = ref(true)

const pagination = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page) => {
    pagination.page = page
    loadList()
  },
  onUpdatePageSize: (pageSize) => {
    pagination.pageSize = pageSize
    pagination.page = 1
    loadList()
  },
})

const config = computed(() => boot.value?.config || {})
const tierPresets = computed(() => (Array.isArray(boot.value?.tier_presets) ? boot.value.tier_presets : []))
const stats = computed(() => boot.value?.stats || null)
const supabaseReady = computed(() => Boolean(boot.value?.supabase_ready))
const canDisableUser = computed(() => Boolean(config.value?.allow_disable_user))
const canResetPassword = computed(() => Boolean(config.value?.allow_reset_password))
const canEditEntitlements = computed(() => Boolean(config.value?.allow_edit_entitlements))
const canManagePermissions = computed(() => Boolean(config.value?.allow_manage_permissions))

const tierOptions = computed(() => {
  const defaults = [
    { label: 'free', value: 'free' },
    { label: 'pro', value: 'pro' },
  ]
  const map = new Map(defaults.map((opt) => [opt.value, opt]))
  tierPresets.value.forEach((item) => {
    const tier = String(item?.tier || '').trim().toLowerCase()
    if (!tier || tier === 'other') return
    map.set(tier, { label: tier, value: tier })
  })
  return Array.from(map.values())
})

const statsText = computed(() => {
  const data = stats.value || {}
  return {
    total: Number(data.total_users || 0),
    anon: Number(data.anonymous_users || 0),
    active: Number(data.active_users || 0),
  }
})

const columns = [
  {
    title: '邮箱',
    key: 'email',
    width: 240,
    ellipsis: { tooltip: true },
  },
  {
    title: '昵称',
    key: 'username',
    width: 160,
    ellipsis: { tooltip: true },
  },
  {
    title: '订阅',
    key: 'tier',
    width: 120,
    render: (row) => h(NTag, { type: row.tier === 'pro' ? 'success' : 'default' }, { default: () => row.tier || 'free' }),
  },
  {
    title: '状态',
    key: 'isactive',
    width: 120,
    render: (row) =>
      h(NTag, { type: Number(row.isactive) === 1 ? 'success' : 'error' }, { default: () => (Number(row.isactive) === 1 ? '正常' : '禁用') }),
  },
  {
    title: '最近登录',
    key: 'last_sign_in_at',
    width: 180,
    render: (row) => String(row.last_sign_in_at || ''),
  },
]

const selected = ref(null)
const drawerVisible = computed({
  get: () => Boolean(selected.value),
  set: (v) => {
    if (!v) selected.value = null
  },
})

const subscriptionSaving = ref(false)
const subscriptionForm = reactive({
  user_id: '',
  email: '',
  tier: 'free',
  expires_at: null,
})

const permissionsVisible = ref(false)
const permissionsLoading = ref(false)
const permissionsSaving = ref(false)
const permissionsAdvanced = ref(false)
const permissionsForm = reactive({
  user_id: '',
  role: '',
  permissionsText: '',
})
const permissionsError = ref('')

const resetPasswordResult = ref(null)
const showResetPasswordResult = ref(false)

const actionOptions = computed(() => {
  const options = []
  if (canManagePermissions.value) options.push({ label: '权限', key: 'permissions' })
  if (canDisableUser.value) options.push({ label: Number(selected.value?.isactive) === 1 ? '禁用' : '解禁', key: 'toggle' })
  if (canResetPassword.value) options.push({ label: '重置密码', key: 'reset_password' })
  return options
})

function onSelectAction(key) {
  if (key === 'permissions') return openPermissions()
  if (key === 'toggle') return disableOrEnable()
  if (key === 'reset_password') return resetPassword()
}

async function loadBootstrap() {
  bootLoading.value = true
  try {
    const res = await api.getAppUsersBootstrap({ page: 1, page_size: 0, include_anonymous: false })
    boot.value = res.data || null
    const list = res.data?.list || {}
    listRows.value = Array.isArray(list.items) ? list.items : []
    pagination.page = Number(list.page || 1)
    pagination.pageSize = Number(list.page_size || config.value?.default_page_size || 20)
    pagination.itemCount = Number(list.total || 0)
    if (typeof config.value?.default_active_only === 'boolean') {
      activeOnly.value = config.value.default_active_only
    }
  } catch (err) {
    message.error('初始化失败')
  } finally {
    bootLoading.value = false
  }
}

async function loadList() {
  listLoading.value = true
  try {
    const res = await api.listAppUsers({
      page: pagination.page,
      page_size: pagination.pageSize,
      keyword: String(keyword.value || '').trim() || undefined,
      active_only: Boolean(activeOnly.value),
      include_anonymous: false,
    })
    const payload = res.data || {}
    listRows.value = Array.isArray(payload.items) ? payload.items : []
    pagination.itemCount = Number(payload.total || 0)
  } catch (err) {
    listRows.value = []
    pagination.itemCount = 0
    message.error('加载失败')
  } finally {
    listLoading.value = false
  }
}

function openUser(row) {
  const userId = String(row?.user_id || '').trim()
  if (!userId) return
  selected.value = row
  subscriptionForm.user_id = userId
  subscriptionForm.email = String(row?.email || '').trim()
  subscriptionForm.tier = String(row?.tier || 'free').trim() || 'free'
  subscriptionForm.expires_at = row?.expires_at ?? null
}

async function saveSubscription() {
  const userId = String(subscriptionForm.user_id || '').trim()
  if (!userId) return
  if (!canEditEntitlements.value) {
    message.warning('当前配置禁止修改订阅')
    return
  }
  subscriptionSaving.value = true
  try {
    await api.upsertAppUserEntitlements(userId, {
      tier: subscriptionForm.tier,
      expires_at: subscriptionForm.expires_at,
      flags: {},
    })
    message.success('已保存')
    // refresh current page (keep filters)
    await loadList()
    // keep drawer selected row updated
    const updated = listRows.value.find((x) => String(x?.user_id || '').trim() === userId)
    if (updated) selected.value = updated
  } catch (err) {
    // interceptor shows message
  } finally {
    subscriptionSaving.value = false
  }
}

async function openPermissions() {
  const userId = String(subscriptionForm.user_id || '').trim()
  if (!userId) return
  if (!canManagePermissions.value) {
    message.warning('当前配置禁止权限管理')
    return
  }
  permissionsError.value = ''
  permissionsForm.user_id = userId
  permissionsForm.role = ''
  permissionsForm.permissionsText = ''
  permissionsAdvanced.value = false
  permissionsVisible.value = true
  permissionsLoading.value = true
  try {
    const res = await api.getAppUserSnapshot(userId)
    const authUser = res.data?.auth_user || null
    const appMeta = authUser?.app_metadata || {}
    permissionsForm.role = String(appMeta?.app_role || '')
    permissionsForm.permissionsText = JSON.stringify(appMeta?.app_permissions ?? [], null, 2)
  } catch (err) {
    permissionsForm.permissionsText = '[]'
  } finally {
    permissionsLoading.value = false
  }
}

async function savePermissions() {
  const userId = String(permissionsForm.user_id || '').trim()
  if (!userId) return
  permissionsError.value = ''

  let permissions = null
  if (permissionsAdvanced.value) {
    const text = String(permissionsForm.permissionsText || '').trim()
    if (text) {
      try {
        permissions = JSON.parse(text)
      } catch (err) {
        permissionsError.value = 'permissions JSON 解析失败'
        return
      }
    }
  }

  permissionsSaving.value = true
  try {
    await api.upsertAppUserPermissions(userId, {
      role: String(permissionsForm.role || '').trim() || null,
      permissions: permissionsAdvanced.value ? permissions : null,
    })
    message.success('已保存')
    permissionsVisible.value = false
  } catch (err) {
    // interceptor shows message
  } finally {
    permissionsSaving.value = false
  }
}

function promptConfirmByEmail(expectedEmail) {
  return new Promise((resolve) => {
    const input = ref('')
    const expected = String(expectedEmail || '').trim()
    dialog.create({
      title: '二次确认',
      content: () =>
        h('div', null, [
          h('div', { style: 'margin-bottom: 8px' }, '请输入该用户 email 以确认操作'),
          h(NInput, {
            value: input.value,
            'onUpdate:value': (v) => (input.value = v),
            placeholder: expected || 'email',
          }),
        ]),
      positiveText: '确认',
      negativeText: '取消',
      onPositiveClick: () => resolve(String(input.value || '').trim()),
      onNegativeClick: () => resolve(null),
      onClose: () => resolve(null),
    })
  })
}

async function disableOrEnable() {
  const row = selected.value
  const userId = String(row?.user_id || '').trim()
  if (!userId) return
  if (!canDisableUser.value) {
    message.warning('当前配置禁止禁用/解禁')
    return
  }
  const email = String(row?.email || '').trim()
  const confirm = await promptConfirmByEmail(email)
  if (!confirm) return

  const isActive = Number(row?.isactive) === 1
  try {
    if (isActive) {
      await api.disableAppUser(userId, { confirm })
      message.success('已禁用')
    } else {
      await api.enableAppUser(userId, { confirm })
      message.success('已解禁')
    }
    await loadList()
    const updated = listRows.value.find((x) => String(x?.user_id || '').trim() === userId)
    if (updated) selected.value = updated
  } catch (err) {
    // interceptor shows message
  }
}

async function resetPassword() {
  const row = selected.value
  const userId = String(row?.user_id || '').trim()
  if (!userId) return
  if (!canResetPassword.value) {
    message.warning('当前配置禁止重置密码（可在「用户管理配置」开启）')
    return
  }
  const email = String(row?.email || '').trim()
  const confirm = await promptConfirmByEmail(email)
  if (!confirm) return
  try {
    const res = await api.resetAppUserPassword(userId, { confirm })
    resetPasswordResult.value = res.data || null
    showResetPasswordResult.value = true
  } catch (err) {
    // interceptor shows message
  }
}

function handleSearch() {
  pagination.page = 1
  loadList()
}

onMounted(async () => {
  await loadBootstrap()
})
</script>

<template>
  <CommonPage title="App 用户管理">
    <NSpace vertical size="large">
      <NCard size="small" :bordered="false">
        <NSpace align="center" justify="space-between" wrap>
          <NSpace align="center" wrap>
            <NTag type="info">用户：{{ statsText.total }}</NTag>
            <NTag type="warning">匿名：{{ statsText.anon }}</NTag>
            <NTag type="success">活跃：{{ statsText.active }}</NTag>
            <NTag v-if="!supabaseReady" type="error">Supabase 未就绪</NTag>
          </NSpace>
          <NButton v-permission="'get/api/v1/admin/app-users/bootstrap'" :loading="bootLoading" @click="loadBootstrap">刷新</NButton>
        </NSpace>
      </NCard>

      <NAlert v-if="!supabaseReady" type="warning" title="提示">
        用户数据源未就绪：{{ boot?.supabase_hint || '请检查 Supabase 视图/权限' }}
      </NAlert>

      <NCard title="用户" size="small">
        <NSpace align="center" wrap>
          <NInput v-model:value="keyword" placeholder="搜索邮箱 / 昵称" style="width: 240px" />
          <NCheckbox v-model:checked="activeOnly">仅显示未禁用</NCheckbox>
          <NButton v-permission="'get/api/v1/admin/app-users/list'" type="primary" :loading="listLoading" @click="handleSearch">
            查询
          </NButton>
        </NSpace>
        <div class="mt-12">
          <NDataTable
            :columns="columns"
            :data="listRows"
            :loading="listLoading"
            :pagination="pagination"
            :row-key="(row) => row.user_id"
            :row-props="(row) => ({ style: 'cursor: pointer', onClick: () => openUser(row) })"
          />
        </div>
      </NCard>
    </NSpace>

    <NDrawer v-model:show="drawerVisible" width="520">
      <NDrawerContent title="用户" :native-scrollbar="false">
        <template v-if="selected">
          <NSpace vertical size="large">
            <NSpace align="center" wrap>
              <NTag type="info">{{ selected.email || '-' }}</NTag>
              <NTag type="default">{{ selected.username || '-' }}</NTag>
              <NTag :type="selected.tier === 'pro' ? 'success' : 'default'">{{ selected.tier || 'free' }}</NTag>
              <NTag :type="Number(selected.isactive) === 1 ? 'success' : 'error'">{{ Number(selected.isactive) === 1 ? '正常' : '禁用' }}</NTag>
            </NSpace>

            <NCard size="small" title="订阅">
              <NForm :label-width="90" :show-feedback="false">
                <NFormItem label="等级">
                  <NSelect v-model:value="subscriptionForm.tier" :options="tierOptions" style="width: 180px" :disabled="!canEditEntitlements" />
                </NFormItem>
                <NFormItem label="到期">
                  <NDatePicker v-model:value="subscriptionForm.expires_at" type="datetime" clearable :disabled="!canEditEntitlements" />
                </NFormItem>
              </NForm>
              <NSpace justify="end">
                <NButton
                  v-permission="'post/api/v1/admin/app-users/entitlements'"
                  type="primary"
                  :loading="subscriptionSaving"
                  :disabled="!canEditEntitlements"
                  @click="saveSubscription"
                >
                  保存
                </NButton>
              </NSpace>
            </NCard>

            <NCard size="small" title="操作">
              <NDropdown :options="actionOptions" trigger="click" placement="bottom-start" @select="onSelectAction">
                <NButton secondary :disabled="actionOptions.length === 0">更多操作</NButton>
              </NDropdown>
            </NCard>
          </NSpace>
        </template>
      </NDrawerContent>
    </NDrawer>

    <NModal v-model:show="permissionsVisible" preset="card" title="权限" style="width: 560px">
      <NForm :label-width="110" :show-feedback="false">
        <NFormItem label="Role">
          <NInput v-model:value="permissionsForm.role" placeholder="例如 user / admin" :disabled="permissionsLoading" />
        </NFormItem>
        <NFormItem label="高级">
          <NCheckbox v-model:checked="permissionsAdvanced">编辑 permissions(JSON)</NCheckbox>
        </NFormItem>
        <NFormItem
          v-if="permissionsAdvanced"
          label="Permissions(JSON)"
          :validation-status="permissionsError ? 'error' : undefined"
          :feedback="permissionsError"
        >
          <NInput v-model:value="permissionsForm.permissionsText" type="textarea" :disabled="permissionsLoading" :autosize="{ minRows: 6, maxRows: 12 }" placeholder="[]" />
        </NFormItem>
      </NForm>
      <NSpace justify="end">
        <NButton :disabled="permissionsSaving" @click="permissionsVisible = false">取消</NButton>
        <NButton v-permission="'post/api/v1/admin/app-users/permissions'" type="primary" :loading="permissionsSaving" @click="savePermissions">保存</NButton>
      </NSpace>
    </NModal>

    <NModal v-model:show="showResetPasswordResult" preset="card" title="一次性密码" style="width: 520px">
      <NAlert type="warning" title="注意">此密码只展示一次，请立即复制并安全转交。</NAlert>
      <div class="mt-12">
        <NInput :value="resetPasswordResult?.temporary_password || ''" readonly />
      </div>
      <NSpace justify="end" class="mt-12">
        <NButton type="primary" @click="showResetPasswordResult = false">我已复制</NButton>
      </NSpace>
    </NModal>
  </CommonPage>
</template>
