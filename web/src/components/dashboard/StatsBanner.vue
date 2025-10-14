<template>
  <div class="stats-banner">
    <NGrid :x-gap="16" :y-gap="16" :cols="gridCols" responsive="screen">
      <NGi v-for="stat in stats" :key="stat.id">
        <!-- 骨架屏加载状态 -->
        <NSkeleton v-if="loading" height="120px" :sharp="false" />

        <!-- 统计卡片 -->
        <NCard v-else :bordered="true" hoverable class="stat-card" @click="handleStatClick(stat)">
          <div class="stat-content">
            <div class="stat-icon-wrapper" :style="{ backgroundColor: `${stat.color}15` }">
              <HeroIcon :name="stat.icon" :size="32" :color="stat.color" />
            </div>
            <div class="stat-info">
              <div class="stat-label">{{ stat.label }}</div>
              <div class="stat-value-wrapper">
                <span class="stat-value">
                  <NNumberAnimation
                    :from="0"
                    :to="parseStatValue(stat.value)"
                    :duration="800"
                    :active="true"
                    :precision="0"
                  />
                </span>
                <template v-if="stat.trend !== undefined && stat.trend !== 0">
                  <span class="stat-trend" :class="trendClass(stat.trend)">
                    {{ formatTrend(stat.trend) }}
                  </span>
                </template>
              </div>
            </div>
          </div>
        </NCard>
      </NGi>
    </NGrid>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { NCard, NGrid, NGi, NSkeleton, NNumberAnimation } from 'naive-ui'
import HeroIcon from '@/components/common/HeroIcon.vue'

defineOptions({ name: 'StatsBanner' })

const props = defineProps({
  stats: {
    type: Array,
    default: () => [],
    validator: (value) => {
      return value.every(
        (stat) =>
          stat.id !== undefined &&
          stat.icon !== undefined &&
          stat.label !== undefined &&
          stat.value !== undefined
      )
    },
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['stat-click'])

// 响应式网格列数
const gridCols = computed(() => {
  const count = props.stats.length
  if (count <= 3) return count
  if (count === 4) return 4
  return 5 // 默认 5 列
})

/**
 * 解析统计值（用于数字动画）
 */
function parseStatValue(value) {
  if (typeof value === 'number') return value
  if (typeof value === 'string') {
    // 尝试提取数字（如 "3/5" 提取 3）
    const match = value.match(/^(\d+)/)
    return match ? parseInt(match[1], 10) : 0
  }
  return 0
}

/**
 * 格式化趋势值
 */
function formatTrend(trend) {
  const sign = trend > 0 ? '+' : ''
  return `${sign}${trend.toFixed(1)}%`
}

/**
 * 趋势样式类
 */
function trendClass(trend) {
  if (trend > 0) return 'trend-up'
  if (trend < 0) return 'trend-down'
  return ''
}

/**
 * 点击统计卡片
 */
function handleStatClick(stat) {
  emit('stat-click', stat)
}
</script>

<style scoped>
/* ========== Claude 风格统计横幅 ========== */
.stats-banner {
  width: 100%;
}

.stat-card {
  cursor: pointer;
  transition: all var(--duration-slow) var(--ease-smooth);
  border-radius: var(--radius-lg);
  overflow: hidden;
  /* Claude 渐变背景：Terra Cotta → Button Orange */
  background: var(--gradient-terra-cotta);
  color: white;
  border: none;
  box-shadow: var(--shadow-soft);
}

.stat-card:hover {
  /* 更大的悬停位移 + 缩放 + 浮空阴影 */
  transform: translateY(-6px) scale(1.02);
  box-shadow: var(--shadow-float);
}

.stat-card:active {
  transform: translateY(-4px) scale(1.01);
}

.stat-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--spacing-2xl) var(--spacing-xl);
  gap: var(--spacing-md);
}

.stat-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  /* 半透明白色背景 */
  background: rgba(255, 255, 255, 0.2);
  flex-shrink: 0;
  transition: all var(--duration-slow) ease;
}

.stat-card:hover .stat-icon-wrapper {
  transform: scale(1.1);
  background: rgba(255, 255, 255, 0.3);
}

.stat-info {
  flex: 1;
  min-width: 0;
  width: 100%;
}

.stat-label {
  /* Sans-serif 字体 + 大写 + 字母间距 */
  font-family: var(--font-sans);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--spacing-md);
  color: white;
  text-transform: uppercase;
  letter-spacing: var(--letter-spacing-wide);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stat-value-wrapper {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: var(--spacing-sm);
}

.stat-value {
  /* Serif 字体 + 负字母间距 */
  font-family: var(--font-serif);
  font-size: var(--font-size-4xl);
  font-weight: var(--font-weight-semibold);
  line-height: 1.2;
  letter-spacing: var(--letter-spacing-tight);
  color: white;
}

.stat-trend {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
  padding: 4px 8px;
  border-radius: var(--radius-md);
  background: rgba(255, 255, 255, 0.2);
  color: white;
}

.trend-up {
  background: rgba(255, 255, 255, 0.25);
  color: white;
}

.trend-down {
  background: rgba(255, 255, 255, 0.25);
  color: white;
}

/* 响应式布局 */
@media (max-width: 1400px) {
  .stats-banner :deep(.n-grid) {
    grid-template-columns: repeat(3, 1fr) !important;
  }
}

@media (max-width: 1200px) {
  .stats-banner :deep(.n-grid) {
    grid-template-columns: repeat(2, 1fr) !important;
  }

  .stat-icon-wrapper {
    width: 56px;
    height: 56px;
  }

  .stat-value {
    font-size: var(--font-size-2xl);
  }
}

@media (max-width: 768px) {
  .stats-banner :deep(.n-grid) {
    grid-template-columns: 1fr !important;
  }

  .stat-icon-wrapper {
    width: 48px;
    height: 48px;
  }

  .stat-label {
    font-size: var(--font-size-sm);
  }

  .stat-value {
    font-size: var(--font-size-xl);
  }
}
</style>
