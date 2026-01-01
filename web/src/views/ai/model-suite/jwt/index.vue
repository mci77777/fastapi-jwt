<template>
  <RealUserSseTest />
</template>

<script setup>
import RealUserSseTest from '@/views/test/real-user-sse.vue'

// 保持旧路由/菜单 name（后端动态路由可能依赖）
defineOptions({ name: 'AiJwtSimulation' })
</script>

