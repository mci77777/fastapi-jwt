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
/* ========== Claude 风格快速访问卡片 ========== */
.quick-access-card {
  cursor: pointer;
  transition: all var(--duration-slow) var(--ease-smooth);
  height: 100%;
  /* Claude 暖白卡片背景 */
  background: var(--claude-card-bg);
  border: 1px solid var(--claude-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-soft);
}

.quick-access-card:hover {
  /* 悬停效果：位移 + 缩放 + 阴影加深 + 边框变色 */
  transform: translateY(-4px) scale(1.02);
  box-shadow: var(--shadow-hover);
  border-color: var(--claude-terra-cotta);
}

.card-content {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--spacing-md);
  padding: var(--spacing-sm);
}

.icon-wrapper {
  position: relative;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  /* Claude 暖白背景 */
  background: var(--claude-bg-warm);
  border-radius: var(--radius-md);
  transition: all var(--duration-slow) ease;
}

.quick-access-card:hover .icon-wrapper {
  /* 悬停时背景变为淡橙色 */
  background: var(--claude-hover-bg);
  transform: scale(1.1);
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
  /* Sans-serif 字体 + 黑色强调 */
  font-family: var(--font-sans);
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--claude-black); /* 使用纯黑色提高对比度 */
  line-height: 1.4;
}

.description {
  margin: 0;
  /* Sans-serif 字体 + 灰色辅助文本 */
  font-family: var(--font-sans);
  font-size: var(--font-size-sm);
  color: var(--claude-text-gray);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

/* 响应式布局 */
@media (max-width: 768px) {
  .icon-wrapper {
    width: 40px;
    height: 40px;
  }

  .title {
    font-size: var(--font-size-base);
  }

  .description {
    font-size: var(--font-size-xs);
  }
}
</style>
