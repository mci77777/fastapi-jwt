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
            <span class="detail-label">统计周期</span>
            <span class="detail-value">最近 24 小时</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">数据来源</span>
            <span class="detail-value">对话日志 response_payload.usage</span>
          </div>
        </template>

        <template v-else-if="stat.id === 4">
          <!-- API 连通性详情 -->
          <div class="detail-item">
            <span class="detail-label">检测方式</span>
            <span class="detail-value">/v1/models 探针（启动时预热 + 可开启定时监控）</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">检测间隔</span>
            <span class="detail-value">可配置（默认 60 秒/轮）</span>
          </div>
        </template>

        <template v-else-if="stat.id === 5">
          <!-- JWT 可获取性详情 -->
          <div class="detail-item">
            <span class="detail-label">检测方式</span>
            <span class="detail-value">JWKS 探针（SUPABASE_JWKS_URL）</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">数据来源</span>
            <span class="detail-value">JWKS 探针 + JWT 验证指标（辅助）</span>
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
    default: false,
  },
  stat: {
    type: Object,
    default: null,
  },
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
/* ========== Claude 风格统计详情弹窗 ========== */
.stat-detail-content {
  padding: var(--spacing-sm) 0;
}

.stat-value-section {
  display: flex;
  align-items: center;
  gap: var(--spacing-2xl);
  padding: var(--spacing-lg) 0;
}

.stat-value-info {
  flex: 1;
}

.stat-value-large {
  /* Serif 字体 + 负字母间距 */
  font-family: var(--font-serif);
  font-size: 36px;
  font-weight: var(--font-weight-bold);
  line-height: 1.2;
  margin-bottom: var(--spacing-sm);
  color: var(--claude-terra-cotta);
  letter-spacing: var(--letter-spacing-tight);
}

.stat-trend-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.trend-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-semibold);
}

.trend-up {
  background-color: rgba(24, 160, 88, 0.1);
  color: var(--claude-success);
}

.trend-down {
  background-color: rgba(220, 38, 38, 0.1);
  color: var(--claude-error);
}

.trend-label {
  font-size: var(--font-size-sm);
  color: var(--claude-text-gray);
}

.stat-details {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--claude-border);
}

.detail-item:last-child {
  border-bottom: none;
}

.detail-label {
  font-family: var(--font-sans);
  font-size: var(--font-size-base);
  color: var(--claude-text-gray);
  font-weight: var(--font-weight-medium);
}

.detail-value {
  font-family: var(--font-sans);
  font-size: var(--font-size-base);
  color: var(--claude-text-dark);
  font-weight: var(--font-weight-semibold);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
}

/* Modal 背景色 */
:deep(.n-card.n-modal) {
  background-color: var(--claude-card-bg);
}
</style>
