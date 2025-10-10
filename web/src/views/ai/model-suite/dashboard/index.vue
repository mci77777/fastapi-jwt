<script setup>
import { computed, onMounted } from 'vue'
import {
  NButton,
  NCard,
  NDivider,
  NEmpty,
  NGrid,
  NGridItem,
  NSpace,
  NStatistic,
  NTable,
  NTag,
  NTooltip,
} from 'naive-ui'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'

import { useAiModelSuiteStore } from '@/store'

defineOptions({ name: 'AiModelDashboard' })

const store = useAiModelSuiteStore()
const { models, mappings, modelsLoading, mappingsLoading } = storeToRefs(store)
const router = useRouter()

const totalEndpoints = computed(() => models.value.length)
const defaultEndpoint = computed(() => models.value.find((item) => item.is_default))
const activeEndpoints = computed(() => models.value.filter((item) => item.is_active).length)
const syncedEndpoints = computed(
  () => models.value.filter((item) => item.sync_status === 'synced').length
)
const monitoredEndpoints = computed(
  () => models.value.filter((item) => item.status === 'online').length
)
const aggregatedModels = computed(() => store.modelCandidates.length)
const mappingScopeStats = computed(() => {
  const stats = new Map()
  mappings.value.forEach((item) => {
    const current = stats.get(item.scope_type) || 0
    stats.set(item.scope_type, current + 1)
  })
  return Array.from(stats.entries()).map(([scope, count]) => ({ scope, count }))
})

function goToCatalog() {
  router.push('/ai/model-suite/catalog')
}

function goToMapping() {
  router.push('/ai/model-suite/mapping')
}

function goToJwt() {
  router.push('/ai/model-suite/jwt')
}

const endpointRows = computed(() =>
  models.value.map((item) => ({
    ...item,
    candidateCount: Array.isArray(item.model_list) ? item.model_list.length : 0,
  }))
)

const mappingRows = computed(() =>
  mappings.value.map((item) => ({
    ...item,
    candidateCount: Array.isArray(item.candidates) ? item.candidates.length : 0,
  }))
)

onMounted(() => {
  if (!models.value.length) {
    store.loadModels()
  }
  if (!mappings.value.length) {
    store.loadMappings()
  }
  store.loadPrompts()
})
</script>

<template>
  <div class="dashboard-container">
    <NCard title="模型能力概览" size="small" class="overview-card">
      <NGrid cols="2 640:3 960:6" responsive="screen" x-gap="16" y-gap="16">
        <NGridItem>
          <div class="stat-card">
            <NStatistic label="端点数量" :value="totalEndpoints">
              <template #prefix>
                <span class="stat-icon">📊</span>
              </template>
            </NStatistic>
          </div>
        </NGridItem>
        <NGridItem>
          <div class="stat-card">
            <NStatistic label="已启用" :value="activeEndpoints">
              <template #prefix>
                <span class="stat-icon">✅</span>
              </template>
            </NStatistic>
          </div>
        </NGridItem>
        <NGridItem>
          <div class="stat-card">
            <NStatistic label="已同步" :value="syncedEndpoints">
              <template #prefix>
                <span class="stat-icon">🔄</span>
              </template>
            </NStatistic>
          </div>
        </NGridItem>
        <NGridItem>
          <div class="stat-card">
            <NStatistic label="在线" :value="monitoredEndpoints">
              <template #prefix>
                <span class="stat-icon">🟢</span>
              </template>
            </NStatistic>
          </div>
        </NGridItem>
        <NGridItem v-if="aggregatedModels">
          <div class="stat-card">
            <NStatistic label="候选模型" :value="aggregatedModels">
              <template #prefix>
                <span class="stat-icon">🤖</span>
              </template>
            </NStatistic>
          </div>
        </NGridItem>
        <NGridItem v-if="defaultEndpoint">
          <div class="stat-card">
            <NStatistic
              label="默认端点"
              :value="defaultEndpoint.name || defaultEndpoint.base_url"
            />
          </div>
        </NGridItem>
      </NGrid>
      <NDivider style="margin: 20px 0" />
      <NSpace wrap size="large">
        <NButton type="primary" size="medium" @click="goToCatalog">
          <template #icon>
            <span>📦</span>
          </template>
          管理端点
        </NButton>
        <NButton type="info" size="medium" @click="goToMapping">
          <template #icon>
            <span>🗺️</span>
          </template>
          维护映射
        </NButton>
        <NButton type="success" size="medium" @click="goToJwt">
          <template #icon>
            <span>🔬</span>
          </template>
          JWT 压测
        </NButton>
      </NSpace>
    </NCard>

    <NCard title="端点状态" size="small" :loading="modelsLoading" class="status-card">
      <template v-if="endpointRows.length">
        <div class="table-wrapper">
          <NTable :single-line="false" size="small" striped>
            <thead>
              <tr>
                <th style="min-width: 180px">名称</th>
                <th style="min-width: 200px">基础地址</th>
                <th style="width: 100px; text-align: center">候选模型</th>
                <th style="width: 100px; text-align: center">状态</th>
                <th style="width: 140px">最后检测</th>
                <th style="width: 100px; text-align: center">同步</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="endpoint in endpointRows" :key="endpoint.id">
                <td>
                  <div class="endpoint-name">
                    <div class="name-row">
                      <span class="name-text">{{ endpoint.name }}</span>
                      <NSpace :size="4" style="margin-left: 8px">
                        <NTag
                          v-if="endpoint.is_default"
                          type="primary"
                          size="tiny"
                          :bordered="false"
                        >
                          默认
                        </NTag>
                        <NTag
                          v-if="endpoint.is_active"
                          type="success"
                          size="tiny"
                          :bordered="false"
                        >
                          启用
                        </NTag>
                      </NSpace>
                    </div>
                    <div class="model-text">{{ endpoint.model || '未指定模型' }}</div>
                  </div>
                </td>
                <td>
                  <NTooltip trigger="hover">
                    <template #trigger>
                      <span class="url-text">{{ endpoint.base_url }}</span>
                    </template>
                    <template #default>
                      <div
                        v-for="(url, key) in endpoint.resolved_endpoints"
                        :key="key"
                        class="tooltip-line"
                      >
                        <strong>{{ key }}</strong
                        >：{{ url }}
                      </div>
                    </template>
                  </NTooltip>
                </td>
                <td style="text-align: center">
                  <span v-if="endpoint.candidateCount" class="count-badge">
                    {{ endpoint.candidateCount }}
                  </span>
                  <span v-else class="text-gray-400">--</span>
                </td>
                <td style="text-align: center">
                  <NTag
                    :type="
                      endpoint.status === 'online'
                        ? 'success'
                        : endpoint.status === 'offline'
                        ? 'error'
                        : 'warning'
                    "
                    size="small"
                    :bordered="false"
                  >
                    {{ endpoint.status || '未知' }}
                  </NTag>
                </td>
                <td>
                  <span class="time-text">{{ endpoint.last_checked_at || '--' }}</span>
                </td>
                <td style="text-align: center">
                  <NTag
                    :type="endpoint.sync_status === 'synced' ? 'success' : 'warning'"
                    size="small"
                    :bordered="false"
                  >
                    {{ endpoint.sync_status || '未同步' }}
                  </NTag>
                </td>
              </tr>
            </tbody>
          </NTable>
        </div>
      </template>
      <NEmpty v-else description="暂无端点信息" />
    </NCard>

    <NCard title="映射覆盖" size="small" :loading="mappingsLoading" class="mapping-card">
      <div v-if="mappingScopeStats.length" class="scope-stats">
        <span class="stats-label">按业务域统计：</span>
        <NSpace wrap :size="8">
          <NTag
            v-for="item in mappingScopeStats"
            :key="item.scope"
            type="info"
            :bordered="false"
            size="small"
          >
            {{ item.scope }}：{{ item.count }}
          </NTag>
        </NSpace>
      </div>
      <template v-if="mappingRows.length">
        <div class="table-wrapper">
          <NTable :single-line="false" size="small" striped>
            <thead>
              <tr>
                <th style="width: 120px; text-align: center">业务域</th>
                <th style="min-width: 160px">对象名称</th>
                <th style="min-width: 140px">默认模型</th>
                <th>候选模型</th>
                <th style="width: 140px">更新时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="mapping in mappingRows" :key="mapping.id">
                <td style="text-align: center">
                  <NTag type="info" size="small" :bordered="false">
                    {{ mapping.scope_type }}
                  </NTag>
                </td>
                <td>
                  <span class="name-text">{{ mapping.name || mapping.scope_key }}</span>
                </td>
                <td>
                  <span class="model-text">{{ mapping.default_model || '--' }}</span>
                </td>
                <td>
                  <NSpace wrap :size="6">
                    <NTag
                      v-for="model in mapping.candidates"
                      :key="model"
                      size="small"
                      :bordered="false"
                      type="default"
                    >
                      {{ model }}
                    </NTag>
                  </NSpace>
                </td>
                <td>
                  <span class="time-text">{{ mapping.updated_at || '--' }}</span>
                </td>
              </tr>
            </tbody>
          </NTable>
        </div>
      </template>
      <NEmpty v-else description="暂无映射记录" />
    </NCard>
  </div>
</template>

<style scoped>
.dashboard-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 4px;
}

.overview-card,
.status-card,
.mapping-card {
  margin-bottom: 0;
}

.stat-card {
  padding: 8px;
  border-radius: 6px;
  background-color: rgba(var(--primary-color-rgb, 24, 160, 88), 0.05);
  transition: all 0.2s ease;
}

.stat-card:hover {
  background-color: rgba(var(--primary-color-rgb, 24, 160, 88), 0.1);
  transform: translateY(-2px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.stat-icon {
  font-size: 20px;
  margin-right: 6px;
}

.table-wrapper {
  overflow-x: auto;
}

.endpoint-name {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.name-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
}

.name-text {
  font-weight: 500;
  color: #333;
}

.model-text {
  font-size: 12px;
  color: #6b7280;
}

.url-text {
  color: #2080f0;
  cursor: pointer;
  text-decoration: underline;
  text-decoration-style: dotted;
}

.url-text:hover {
  color: #4098fc;
}

.count-badge {
  display: inline-block;
  padding: 2px 8px;
  background-color: #f0f0f0;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
}

.time-text {
  font-size: 12px;
  color: #666;
}

.tooltip-line {
  padding: 2px 0;
  line-height: 1.6;
}

.tooltip-line strong {
  color: #2080f0;
}

.scope-stats {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  padding: 12px;
  background-color: #fafafa;
  border-radius: 6px;
}

.stats-label {
  font-size: 13px;
  font-weight: 500;
  color: #6b7280;
}

.text-gray-400 {
  color: #9ca3af;
}
.text-gray-500 {
  color: #6b7280;
}
.text-primary {
  color: #2080f0;
}
.cursor-pointer {
  cursor: pointer;
}
.mt-1 {
  margin-top: 4px;
}
.mr-2 {
  margin-right: 8px;
}
.flex {
  display: flex;
}
.items-center {
  align-items: center;
}
.gap-2 {
  gap: 8px;
}
</style>
