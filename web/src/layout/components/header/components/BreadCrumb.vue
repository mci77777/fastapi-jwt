<template>
  <n-breadcrumb>
    <n-breadcrumb-item
      v-for="item in breadcrumbItems"
      :key="item.path"
      @click="handleBreadClick(item.path)"
    >
      <component :is="getIcon(item.meta)" />
      {{ item.meta.title }}
    </n-breadcrumb-item>
  </n-breadcrumb>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { renderCustomIcon, renderIcon } from '@/utils'

const router = useRouter()
const route = useRoute()

const breadcrumbItems = computed(() => {
  const matched = route.matched.filter((item) => !!item.meta?.title)
  return matched.filter(
    (item, index) => matched.findIndex((target) => target.path === item.path) === index
  )
})

function handleBreadClick(path) {
  if (path === route.path) return
  router.push(path)
}

function getIcon(meta) {
  if (meta?.customIcon) return renderCustomIcon(meta.customIcon, { size: 18 })
  if (meta?.icon) return renderIcon(meta.icon, { size: 18 })
  return null
}
</script>
