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
/* ========== 黑白风格统计横幅 ========== */
.stats-banner {
  width: 100%;
}

.stat-card {
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  border-radius: 16px;
  overflow: hidden;
  background: #ffffff;
  color: #000000;
  border: 1px solid #e0e0e0;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.stat-card:hover {
  transform: translateY(-6px) scale(1.02);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.16);
  border-color: #000000;
}

.stat-card:active {
  transform: translateY(-4px) scale(1.01);
}

.stat-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 24px 20px;
  gap: 12px;
}

.stat-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: #f5f5f5;
  flex-shrink: 0;
  transition: all 0.3s ease;
}

.stat-card:hover .stat-icon-wrapper {
  transform: scale(1.1);
  background: #e0e0e0;
}

.stat-info {
  flex: 1;
  min-width: 0;
  width: 100%;
}

.stat-label {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 12px;
  color: #666666;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stat-value-wrapper {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 8px;
}

.stat-value {
  font-family: ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif;
  font-size: 32px;
  font-weight: 600;
  line-height: 1.2;
  letter-spacing: -0.02em;
  color: #000000;
}

.stat-trend {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 8px;
  border-radius: 12px;
  background: #f5f5f5;
  color: #666666;
}

.trend-up {
  background: #e8f5e9;
  color: #00aa00;
}

.trend-down {
  background: #ffebee;
  color: #cc0000;
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
