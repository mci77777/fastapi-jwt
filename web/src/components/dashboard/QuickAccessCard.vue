<template>
  <NCard class="quick-access-card" hoverable @click="handleClick">
    <div class="card-content">
      <div class="icon-wrapper">
        <HeroIcon :name="icon" :size="32" :color="iconColor" />
        <NBadge v-if="badge !== undefined" :value="badge" class="badge" />
      </div>
      <div class="text-content">
        <h3 class="title">{{ title }}</h3>
        <p class="description">{{ description }}</p>
      </div>
    </div>
  </NCard>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { NCard, NBadge } from 'naive-ui'
import HeroIcon from '@/components/common/HeroIcon.vue'

defineOptions({ name: 'QuickAccessCard' })

const props = defineProps({
  icon: {
    type: String,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    required: true,
  },
  path: {
    type: String,
    required: true,
  },
  badge: {
    type: Number,
    default: undefined,
  },
  iconColor: {
    type: String,
    default: '#667eea',
  },
})

const emit = defineEmits(['click'])
const router = useRouter()

function handleClick() {
  emit('click', props.path)
  router.push(props.path)
}
</script>

<style scoped>
/* ========== 黑白风格快速访问卡片 ========== */
.quick-access-card {
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  height: 100%;
  background: #ffffff;
  border: 1px solid #e0e0e0;
  border-radius: 16px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.quick-access-card:hover {
  transform: translateY(-4px) scale(1.02);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  border-color: #000000;
}

.card-content {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
  padding: 4px;
}

.icon-wrapper {
  position: relative;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  background: #f5f5f5;
  border-radius: 12px;
  transition: all 0.3s ease;
}

.quick-access-card:hover .icon-wrapper {
  background: #e0e0e0;
  transform: scale(1.05);
}

.badge {
  position: absolute;
  top: -8px;
  right: -8px;
}

.text-content {
  flex: 1;
  min-width: 0;
  width: 100%;
}

.title {
  margin: 0 0 6px 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 15px;
  font-weight: 600;
  color: #000000;
  line-height: 1.4;
}

.description {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 13px;
  color: #666666;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
</style>
