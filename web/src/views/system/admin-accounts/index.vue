<script setup>
import { computed, h, onMounted, reactive, ref, resolveDirective, withDirectives } from 'vue'
import {
  NButton,
  NCard,
  NDataTable,
  NForm,
  NFormItem,
  NInput,
  NModal,
  NSelect,
  NSpace,
  NSwitch,
  NTag,
  useMessage,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'SystemAdminAccounts' })

const message = useMessage()
const vPermission = resolveDirective('permission')

const loading = ref(false)
const rows = ref([])

const roleOptions = [
  { label: '1 admin', value: 'admin' },
  { label: '2 高级管理权限', value: 'manager' },
  { label: '3 普通权限', value: 'user' },
]

function roleTagType(role) {
  const r = String(role || '').trim().toLowerCase()
  if (r === 'admin' || r === 'super_admin') return 'warning'
  if (r === 'manager' || r === 'llm_admin' || r === 'app_user_admin' || r === 'exercise_admin') return 'info'
  return 'default'
}

async function loadList() {
  loading.value = true
  try {
    const res = await api.listDashboardUsers()
    rows.value = Array.isArray(res?.data) ? res.data : []
  } catch (error) {
    rows.value = []
    message.error(error?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadList()
})

// ---------------- Create ----------------
const createVisible = ref(false)
const createSaving = ref(false)
const createForm = reactive({
  username: '',
  password: '',
  role: 'user',
  is_active: true,
})

function openCreate() {
  createForm.username = ''
  createForm.password = ''
  createForm.role = 'user'
  createForm.is_active = true
  createVisible.value = true
}

async function submitCreate() {
  const username = String(createForm.username || '').trim()
  const password = String(createForm.password || '').trim()
  if (!username) {
    message.error('请输入用户名')
    return
  }
  if (username.length < 3) {
    message.error('用户名至少 3 位')
    return
  }
  if (!password || password.length < 6) {
    message.error('密码至少 6 位')
    return
  }

  createSaving.value = true
  try {
    await api.createDashboardUser({
      username,
      password,
      role: String(createForm.role || 'user'),
      is_active: Boolean(createForm.is_active),
    })
    message.success('已创建')
    createVisible.value = false
    await loadList()
  } catch (error) {
    message.error(error?.message || '创建失败')
  } finally {
    createSaving.value = false
  }
}

// ---------------- Update Role ----------------
const roleVisible = ref(false)
const roleSaving = ref(false)
const roleForm = reactive({
  username: '',
  role: 'user',
  confirm_username: '',
})

const roleConfirmOk = computed(
  () => String(roleForm.confirm_username || '').trim() === String(roleForm.username || '').trim()
)

function openRole(row) {
  const username = String(row?.username || '').trim()
  if (!username) return
  roleForm.username = username
  roleForm.role = String(row?.role || 'user').trim() || 'user'
  roleForm.confirm_username = ''
  roleVisible.value = true
}

async function submitRole() {
  if (!roleConfirmOk.value) {
    message.error('请输入确认用户名')
    return
  }
  roleSaving.value = true
  try {
    await api.updateDashboardUserRole(roleForm.username, {
      role: String(roleForm.role || 'user'),
      confirm_username: String(roleForm.confirm_username || '').trim(),
    })
    message.success('已更新')
    roleVisible.value = false
    await loadList()
  } catch (error) {
    message.error(error?.message || '更新失败')
  } finally {
    roleSaving.value = false
  }
}

// ---------------- Toggle Active ----------------
const toggleVisible = ref(false)
const toggleSaving = ref(false)
const toggleAction = ref('disable') // disable | enable
const toggleForm = reactive({
  username: '',
  confirm_username: '',
})

const toggleConfirmOk = computed(
  () => String(toggleForm.confirm_username || '').trim() === String(toggleForm.username || '').trim()
)

function openToggle(row) {
  const username = String(row?.username || '').trim()
  if (!username) return
  toggleForm.username = username
  toggleForm.confirm_username = ''
  toggleAction.value = Number(row?.is_active) ? 'disable' : 'enable'
  toggleVisible.value = true
}

async function submitToggle() {
  if (!toggleConfirmOk.value) {
    message.error('请输入确认用户名')
    return
  }
  toggleSaving.value = true
  try {
    const payload = { confirm_username: String(toggleForm.confirm_username || '').trim() }
    if (toggleAction.value === 'disable') {
      await api.disableDashboardUser(toggleForm.username, payload)
      message.success('已禁用')
    } else {
      await api.enableDashboardUser(toggleForm.username, payload)
      message.success('已启用')
    }
    toggleVisible.value = false
    await loadList()
  } catch (error) {
    message.error(error?.message || '操作失败')
  } finally {
    toggleSaving.value = false
  }
}

// ---------------- Reset Password ----------------
const resetVisible = ref(false)
const resetSaving = ref(false)
const resetForm = reactive({
  username: '',
  confirm_username: '',
  password_length: 16,
})
const resetConfirmOk = computed(
  () => String(resetForm.confirm_username || '').trim() === String(resetForm.username || '').trim()
)
const resetResultVisible = ref(false)
const resetResult = ref(null)

function openReset(row) {
  const username = String(row?.username || '').trim()
  if (!username) return
  resetForm.username = username
  resetForm.confirm_username = ''
  resetForm.password_length = 16
  resetVisible.value = true
}

async function submitReset() {
  if (!resetConfirmOk.value) {
    message.error('请输入确认用户名')
    return
  }
  resetSaving.value = true
  try {
    const res = await api.resetDashboardUserPassword(resetForm.username, {
      confirm_username: String(resetForm.confirm_username || '').trim(),
      password_length: Number(resetForm.password_length || 16),
    })
    resetResult.value = res?.data || null
    resetVisible.value = false
    resetResultVisible.value = true
    await loadList()
  } catch (error) {
    message.error(error?.message || '重置失败')
  } finally {
    resetSaving.value = false
  }
}

function copyResetPassword() {
  const pwd = String(resetResult.value?.password || '')
  if (!pwd) return
  navigator.clipboard.writeText(pwd)
  message.success('已复制')
}

const columns = [
  {
    title: '用户名',
    key: 'username',
    width: 160,
    ellipsis: { tooltip: true },
  },
  {
    title: '角色',
    key: 'role',
    width: 140,
    render: (row) =>
      h(NTag, { size: 'small', type: roleTagType(row?.role) }, { default: () => String(row?.role || 'user') }),
  },
  {
    title: '状态',
    key: 'is_active',
    width: 100,
    render: (row) =>
      h(
        NTag,
        { size: 'small', type: Number(row?.is_active) ? 'success' : 'error' },
        { default: () => (Number(row?.is_active) ? '启用' : '禁用') }
      ),
  },
  {
    title: '最近登录',
    key: 'last_login_at',
    width: 200,
    ellipsis: { tooltip: true },
    render: (row) => String(row?.last_login_at || '--'),
  },
  {
    title: '更新时间',
    key: 'updated_at',
    width: 200,
    ellipsis: { tooltip: true },
    render: (row) => String(row?.updated_at || '--'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 320,
    fixed: 'right',
    render: (row) =>
      h(
        NSpace,
        { size: 'small' },
        {
          default: () => [
            withDirectives(
              h(
                NButton,
                { size: 'small', secondary: true, onClick: () => openRole(row) },
                { default: () => '角色' }
              ),
              [[vPermission, 'post/api/v1/admin/dashboard-users/role']]
            ),
            withDirectives(
              h(
                NButton,
                { size: 'small', secondary: true, onClick: () => openToggle(row) },
                { default: () => (Number(row?.is_active) ? '禁用' : '启用') }
              ),
              [[vPermission, Number(row?.is_active) ? 'post/api/v1/admin/dashboard-users/disable' : 'post/api/v1/admin/dashboard-users/enable']]
            ),
            withDirectives(
              h(
                NButton,
                { size: 'small', type: 'warning', secondary: true, onClick: () => openReset(row) },
                { default: () => '重置密码' }
              ),
              [[vPermission, 'post/api/v1/admin/dashboard-users/reset-password']]
            ),
          ],
        }
      ),
  },
]
</script>

<template>
  <CommonPage title="后台账号管理">
    <NSpace vertical size="large">
      <NCard size="small" title="账号列表">
        <NSpace align="center" justify="space-between">
          <NSpace>
            <NButton
              v-permission="'get/api/v1/admin/dashboard-users/list'"
              :loading="loading"
              @click="loadList"
            >
              刷新
            </NButton>
            <NButton v-permission="'post/api/v1/admin/dashboard-users/create'" type="primary" @click="openCreate">
              创建账号
            </NButton>
          </NSpace>
          <div />
        </NSpace>
        <div class="mt-12">
          <NDataTable :columns="columns" :data="rows" :loading="loading" :row-key="(row) => row.username" />
        </div>
      </NCard>
    </NSpace>

    <NModal v-model:show="createVisible" preset="card" title="创建账号" style="width: 520px">
      <NForm label-width="120">
        <NFormItem label="用户名">
          <NInput v-model:value="createForm.username" placeholder="3-32 位，例如：ops_01" />
        </NFormItem>
        <NFormItem label="初始密码">
          <NInput v-model:value="createForm.password" type="password" show-password-on="mousedown" placeholder="至少 6 位" />
        </NFormItem>
        <NFormItem label="角色">
          <NSelect v-model:value="createForm.role" :options="roleOptions" />
        </NFormItem>
        <NFormItem label="启用">
          <NSwitch v-model:value="createForm.is_active" />
        </NFormItem>
      </NForm>
      <NSpace justify="end">
        <NButton @click="createVisible = false">取消</NButton>
        <NButton type="primary" :loading="createSaving" @click="submitCreate">创建</NButton>
      </NSpace>
    </NModal>

    <NModal v-model:show="roleVisible" preset="card" title="更新角色（二次确认）" style="width: 520px">
      <NForm label-width="160">
        <NFormItem label="目标用户名">
          <NInput :value="roleForm.username" disabled />
        </NFormItem>
        <NFormItem label="新角色">
          <NSelect v-model:value="roleForm.role" :options="roleOptions" />
        </NFormItem>
        <NFormItem label="确认用户名">
          <NInput v-model:value="roleForm.confirm_username" placeholder="输入目标用户名以确认" />
        </NFormItem>
      </NForm>
      <NSpace justify="end">
        <NButton @click="roleVisible = false">取消</NButton>
        <NButton type="primary" :disabled="!roleConfirmOk" :loading="roleSaving" @click="submitRole">保存</NButton>
      </NSpace>
    </NModal>

    <NModal
      v-model:show="toggleVisible"
      preset="card"
      :title="toggleAction === 'disable' ? '禁用账号（二次确认）' : '启用账号（二次确认）'"
      style="width: 520px"
    >
      <NForm label-width="160">
        <NFormItem label="目标用户名">
          <NInput :value="toggleForm.username" disabled />
        </NFormItem>
        <NFormItem label="确认用户名">
          <NInput v-model:value="toggleForm.confirm_username" placeholder="输入目标用户名以确认" />
        </NFormItem>
      </NForm>
      <NSpace justify="end">
        <NButton @click="toggleVisible = false">取消</NButton>
        <NButton
          :type="toggleAction === 'disable' ? 'error' : 'primary'"
          :disabled="!toggleConfirmOk"
          :loading="toggleSaving"
          @click="submitToggle"
        >
          {{ toggleAction === 'disable' ? '禁用' : '启用' }}
        </NButton>
      </NSpace>
    </NModal>

    <NModal v-model:show="resetVisible" preset="card" title="重置密码（二次确认）" style="width: 520px">
      <NForm label-width="160">
        <NFormItem label="目标用户名">
          <NInput :value="resetForm.username" disabled />
        </NFormItem>
        <NFormItem label="密码长度">
          <NInput v-model:value="resetForm.password_length" placeholder="默认 16（8-64）" />
        </NFormItem>
        <NFormItem label="确认用户名">
          <NInput v-model:value="resetForm.confirm_username" placeholder="输入目标用户名以确认" />
        </NFormItem>
      </NForm>
      <NSpace justify="end">
        <NButton @click="resetVisible = false">取消</NButton>
        <NButton type="warning" :disabled="!resetConfirmOk" :loading="resetSaving" @click="submitReset">
          重置
        </NButton>
      </NSpace>
    </NModal>

    <NModal v-model:show="resetResultVisible" preset="card" title="重置结果（仅本次展示）" style="width: 520px">
      <NForm label-width="160">
        <NFormItem label="用户名">
          <NInput :value="String(resetResult?.username || '')" disabled />
        </NFormItem>
        <NFormItem label="新密码">
          <NInput :value="String(resetResult?.password || '')" type="password" show-password-on="mousedown" readonly />
        </NFormItem>
      </NForm>
      <NSpace justify="end">
        <NButton @click="resetResultVisible = false">关闭</NButton>
        <NButton type="primary" :disabled="!resetResult?.password" @click="copyResetPassword">复制密码</NButton>
      </NSpace>
    </NModal>
  </CommonPage>
</template>
