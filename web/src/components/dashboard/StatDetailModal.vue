<template>
  <NModal
    v-model:show="visible"
    preset="card"
    :title="modalTitle"
    :bordered="false"
    size="medium"
    :segmented="{ content: 'soft', footer: 'soft' }"
    style="width: 600px; max-width: 90vw"
  >
    <div v-if="stat" class="stat-detail-content">
      <!-- 统计值展示 -->
      <div class="stat-value-section">
        <HeroIcon :name="stat.icon" :size="48" :color="stat.color" />
        <div class="stat-value-info">
          <div class="stat-value-large">{{ stat.value }}</div>
          <div v-if="stat.trend !== undefined && stat.trend !== 0" class="stat-trend-info">
            <span :class="['trend-badge', stat.trend > 0 ? 'trend-up' : 'trend-down']">
              {{ formatTrend(stat.trend) }}
            </span>
            <span class="trend-label">较上期</span>
          </div>
        </div>
      </div>

      <!-- 详细信息 -->
      <NDivider />

      <div class="stat-details">
        <div v-if="stat.detail" class="detail-item">
          <span class="detail-label">说明</span>
          <span class="detail-value">{{ stat.detail }}</span>
        </div>

        <!-- 根据不同统计类型显示不同详情 -->
        <template v-if="stat.id === 1">
          <!-- 日活用户数详情 -->
          <div class="detail-item">
            <span class="detail-label">统计周期</span>
            <span class="detail-value">最近 24 小时</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">数据来源</span>
            <span class="detail-value">JWT 认证记录</span>
          </div>
        </template>

        <template v-else-if="stat.id === 2">
          <!-- AI 请求数详情 -->
          <div class="detail-item">
            <span class="detail-label">统计周期</span>
            <span class="detail-value">最近 24 小时</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">数据来源</span>
            <span class="detail-value">AI 请求日志</span>
          </div>
        </template>

        <template v-else-if="stat.id === 3">
          <!-- Token 使用量详情 -->
          <div class="detail-item">
            <span class="detail-label">功能状态</span>
            <span class="detail-value">即将上线</span>
          </div>
        </template>

        <template v-else-if="stat.id === 4">
          <!-- API 连通性详情 -->
          <div class="detail-item">
            <span class="detail-label">检测方式</span>
            <span class="detail-value">定时健康检查</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">检测间隔</span>
            <span class="detail-value">每 5 分钟</span>
          </div>
        </template>

        <template v-else-if="stat.id === 5">
          <!-- JWT 可获取性详情 -->
          <div class="detail-item">
            <span class="detail-label">统计周期</span>
            <span class="detail-value">最近 24 小时</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">数据来源</span>
            <span class="detail-value">Prometheus 指标</span>
          </div>
        </template>
      </div>
    </div>

    <template #footer>
      <div class="modal-footer">
        <NButton @click="handleClose">关闭</NButton>
      </div>
    </template>
  </NModal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { NModal, NButton, NDivider } from 'naive-ui'
import HeroIcon from '@/components/common/HeroIcon.vue'

defineOptions({ name: 'StatDetailModal' })

const props = defineProps({
  show: {
    type: Boolean,
    default: false
  },
  stat: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:show'])

const visible = ref(props.show)

// 弹窗标题
const modalTitle = computed(() => {
  return props.stat ? props.stat.label : '统计详情'
})

/**
 * 格式化趋势值
 */
function formatTrend(trend) {
  const sign = trend > 0 ? '+' : ''
  return `${sign}${trend.toFixed(1)}%`
}

/**
 * 关闭弹窗
 */
function handleClose() {
  visible.value = false
}

// 监听 props 变化
watch(
  () => props.show,
  (newValue) => {
    visible.value = newValue
  }
)

// 监听 visible 变化，同步到父组件
watch(visible, (newValue) => {
  emit('update:show', newValue)
})
</script>

<style scoped>
.stat-detail-content {
  padding: 8px 0;
}

.stat-value-section {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 16px 0;
}

.stat-value-info {
  flex: 1;
}

.stat-value-large {
  font-size: 36px;
  font-weight: 700;
  line-height: 1.2;
  margin-bottom: 8px;
}

.stat-trend-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.trend-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 600;
}

.trend-up {
  background-color: rgba(24, 160, 88, 0.1);
  color: #18a058;
}

.trend-down {
  background-color: rgba(208, 48, 80, 0.1);
  color: #d03050;
}

.trend-label {
  font-size: 13px;
  color: #999;
}

.stat-details {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
}

.detail-label {
  font-size: 14px;
  color: #666;
  font-weight: 500;
}

.detail-value {
  font-size: 14px;
  color: #333;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
}

/* 暗色模式适配 */
:deep(.n-card.n-modal) {
  background-color: var(--n-color);
}

@media (prefers-color-scheme: dark) {
  .detail-label {
    color: #aaa;
  }

  .detail-value {
    color: #ddd;
  }
}
</style>

