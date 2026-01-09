<script setup>
import { computed, onMounted, ref, resolveDirective } from 'vue'
import { NAlert, NButton, NCard, NCheckbox, NForm, NFormItem, NInputNumber, NSpace, useMessage } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'

defineOptions({ name: 'SystemAppUsersConfig' })

const message = useMessage()
const vPermission = resolveDirective('permission')

const loading = ref(false)
const saving = ref(false)

const config = ref(null)

const form = ref({
  default_page_size: 20,
  default_active_only: true,
  allow_edit_entitlements: true,
  allow_manage_permissions: true,
  allow_disable_user: true,
  allow_reset_password: false,
  require_confirm_user_id_for_dangerous_actions: true,
  reset_password_length: 16,
})

const canSave = computed(() => !saving.value && !loading.value)

async function loadConfig() {
  loading.value = true
  try {
    const res = await api.getAppUserAdminConfig()
    config.value = res.data || null
    const data = res.data || {}
    form.value.default_page_size = Number(data.default_page_size || 20)
    form.value.default_active_only = Boolean(data.default_active_only)
    form.value.allow_edit_entitlements = Boolean(data.allow_edit_entitlements)
    form.value.allow_manage_permissions = Boolean(data.allow_manage_permissions)
    form.value.allow_disable_user = Boolean(data.allow_disable_user)
    form.value.allow_reset_password = Boolean(data.allow_reset_password)
    form.value.require_confirm_user_id_for_dangerous_actions = Boolean(data.require_confirm_user_id_for_dangerous_actions)
    form.value.reset_password_length = Number(data.reset_password_length || 16)
  } catch (err) {
    message.error('加载配置失败')
  } finally {
    loading.value = false
  }
}

async function saveConfig() {
  saving.value = true
  try {
    await api.upsertAppUserAdminConfig({
      default_page_size: form.value.default_page_size,
      default_active_only: form.value.default_active_only,
      allow_edit_entitlements: form.value.allow_edit_entitlements,
      allow_manage_permissions: form.value.allow_manage_permissions,
      allow_disable_user: form.value.allow_disable_user,
      allow_reset_password: form.value.allow_reset_password,
      require_confirm_user_id_for_dangerous_actions: form.value.require_confirm_user_id_for_dangerous_actions,
      reset_password_length: form.value.reset_password_length,
    })
    message.success('已保存')
    await loadConfig()
  } catch (err) {
    message.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadConfig()
})
</script>

<template>
  <CommonPage title="用户管理配置">
    <NSpace vertical size="large">
      <NCard title="基础能力" size="small" :loading="loading">
        <NForm :label-width="220" :show-feedback="false">
          <NFormItem label="允许修改订阅">
            <NCheckbox v-model:checked="form.allow_edit_entitlements">启用</NCheckbox>
          </NFormItem>
          <NFormItem label="允许管理权限">
            <NCheckbox v-model:checked="form.allow_manage_permissions">启用</NCheckbox>
          </NFormItem>
        </NForm>
      </NCard>

      <NCard title="危险操作" size="small" :loading="loading">
        <NForm :label-width="220" :show-feedback="false">
          <NFormItem label="允许禁用/解禁">
            <NCheckbox v-model:checked="form.allow_disable_user">启用</NCheckbox>
          </NFormItem>
          <NFormItem label="允许管理员重置密码">
            <NCheckbox v-model:checked="form.allow_reset_password">启用（高风险）</NCheckbox>
          </NFormItem>
          <NFormItem label="危险操作强制二次确认">
            <NCheckbox v-model:checked="form.require_confirm_user_id_for_dangerous_actions">需要输入邮箱确认</NCheckbox>
          </NFormItem>
          <NFormItem label="重置密码长度">
            <NInputNumber v-model:value="form.reset_password_length" :min="8" :max="64" />
          </NFormItem>
        </NForm>
        <NAlert class="mt-12" type="warning" title="说明">
          重置密码会直接覆盖 Supabase Auth 账号密码，仅一次性返回明文，请确保流程与审计符合你的运营要求。
        </NAlert>
      </NCard>

      <NCard title="默认列表行为" size="small" :loading="loading">
        <NForm :label-width="220" :show-feedback="false">
          <NFormItem label="默认 page_size">
            <NInputNumber v-model:value="form.default_page_size" :min="1" :max="100" />
          </NFormItem>
          <NFormItem label="默认仅 active">
            <NCheckbox v-model:checked="form.default_active_only">仅显示未禁用用户</NCheckbox>
          </NFormItem>
        </NForm>
      </NCard>

      <NSpace justify="end">
        <NButton :disabled="!canSave" @click="loadConfig">刷新</NButton>
        <NButton v-permission="'post/api/v1/admin/app-users/config'" type="primary" :loading="saving" :disabled="!canSave" @click="saveConfig">
          保存
        </NButton>
      </NSpace>
    </NSpace>
  </CommonPage>
</template>
