<template>
  <div class="stats-banner">
    <NGrid :x-gap="16" :y-gap="16" :cols="gridCols" responsive="screen">
      <NGi v-for="stat in stats" :key="stat.id">
        <!-- 骨架屏加载状态 -->
        <NSkeleton v-if="loading" height="120px" :sharp="false" />

        <!-- 统计卡片 -->
        <NCard
          v-else
          :bordered="true"
          hoverable
          class="stat-card"
          @click="handleStatClick(stat)"
        >
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
    }
  },
  loading: {
    type: Boolean,
    default: false
  }
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
.stats-banner {
  width: 100%;
}

.stat-card {
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border-radius: 12px;
  overflow: hidden;
}

.stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
}

.stat-card:active {
  transform: translateY(-2px);
}

.stat-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.stat-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 64px;
  height: 64px;
  border-radius: 12px;
  flex-shrink: 0;
  transition: all 0.3s ease;
}

.stat-card:hover .stat-icon-wrapper {
  transform: scale(1.05);
}

.stat-info {
  flex: 1;
  min-width: 0;
}

.stat-label {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}

.stat-value-wrapper {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  color: #333;
}

.stat-trend {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: 4px;
}

.trend-up {
  background-color: rgba(24, 160, 88, 0.1);
  color: #18a058;
}

.trend-down {
  background-color: rgba(208, 48, 80, 0.1);
  color: #d03050;
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
    font-size: 24px;
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
    font-size: 13px;
  }

  .stat-value {
    font-size: 22px;
  }
}

/* 暗色模式适配 */
@media (prefers-color-scheme: dark) {
  .stat-label {
    color: #aaa;
  }

  .stat-value {
    color: #ddd;
  }
}
</style>


