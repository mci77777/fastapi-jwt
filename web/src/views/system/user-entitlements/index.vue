<script setup>
import { NSpace, NAlert, NButton } from 'naive-ui'
import { useRouter } from 'vue-router'

import CommonPage from '@/components/page/CommonPage.vue'

defineOptions({ name: 'SystemUserEntitlements' })

const router = useRouter()

function goAppUsers() {
  router.push('/system/app-users')
}

function goTierPresets() {
  router.push('/system/user-entitlements/config')
}
</script>

<template>
  <CommonPage title="用户权益">
    <NSpace vertical size="large">
      <NAlert type="info" title="已合并到 App 用户管理">
        订阅编辑/权限/禁用/重置密码已统一放到「系统管理 → App 用户管理」的用户详情抽屉中。
      </NAlert>

      <NSpace>
        <NButton type="primary" @click="goAppUsers">打开 App 用户管理</NButton>
        <NButton @click="goTierPresets">订阅等级配置</NButton>
      </NSpace>
    </NSpace>
  </CommonPage>
</template>
