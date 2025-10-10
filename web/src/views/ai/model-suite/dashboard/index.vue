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
const syncedEndpoints = computed(() =>
  models.value.filter((item) => item.sync_status === 'synced').length
)
const monitoredEndpoints = computed(() =>
  models.value.filter((item) => item.status === 'online').length
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
  <NSpace vertical size="large">
    <NCard title="模型能力概览" size="small">
      <NGrid cols="1 640:2 960:4" responsive="screen" x-gap="12" y-gap="12">
        <NGridItem>
          <NStatistic label="端点数量" :value="totalEndpoints" />
        </NGridItem>
        <NGridItem>
          <NStatistic label="已启用端点" :value="activeEndpoints" />
        </NGridItem>
        <NGridItem>
          <NStatistic label="同步完成" :value="syncedEndpoints" />
        </NGridItem>
        <NGridItem>
          <NStatistic label="在线监控" :value="monitoredEndpoints" />
        </NGridItem>
        <NGridItem>
          <NStatistic v-if="aggregatedModels" label="候选模型" :value="aggregatedModels" />
        </NGridItem>
        <NGridItem v-if="defaultEndpoint">
          <NStatistic
            label="默认端点"
            :value="defaultEndpoint.name || defaultEndpoint.base_url"
          />
        </NGridItem>
      </NGrid>
      <NDivider />
      <NSpace wrap>
        <NButton type="primary" @click="goToCatalog">管理端点</NButton>
        <NButton type="info" @click="goToMapping">维护映射</NButton>
        <NButton type="success" @click="goToJwt">JWT 压测</NButton>
      </NSpace>
    </NCard>

    <NCard title="端点状态" size="small" :loading="modelsLoading">
      <template v-if="endpointRows.length">
        <NTable :single-line="false" size="small" striped>
          <thead>
            <tr>
              <th style="width: 220px">名称</th>
              <th>基础地址</th>
              <th style="width: 120px">候选模型</th>
              <th style="width: 120px">状态</th>
              <th style="width: 160px">最后检测</th>
              <th style="width: 160px">同步状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="endpoint in endpointRows" :key="endpoint.id">
              <td>
                <div class="flex items-center gap-2">
                  <span>{{ endpoint.name }}</span>
                  <NTag v-if="endpoint.is_default" type="primary" size="tiny" bordered={false}>默认</NTag>
                  <NTag v-if="endpoint.is_active" type="success" size="tiny" bordered={false}>启用</NTag>
                </div>
                <div class="text-xs text-gray-500 mt-1">{{ endpoint.model || '未指定模型' }}</div>
              </td>
              <td>
                <NTooltip trigger="hover">
                  <template #trigger>
                    <span class="text-primary cursor-pointer">{{ endpoint.base_url }}</span>
                  </template>
                  <template #default>
                    <div v-for="(url, key) in endpoint.resolved_endpoints" :key="key">
                      {{ key }}：{{ url }}
                    </div>
                  </template>
                </NTooltip>
              </td>
              <td>
                <span v-if="endpoint.candidateCount">{{ endpoint.candidateCount }} 个</span>
                <span v-else class="text-gray-400">--</span>
              </td>
              <td>
                <NTag
                  :type="
                    endpoint.status === 'online'
                      ? 'success'
                      : endpoint.status === 'offline'
                        ? 'error'
                        : 'warning'
                  "
                  size="small"
                  bordered={false}
                >
                  {{ endpoint.status || '未知' }}
                </NTag>
              </td>
              <td>{{ endpoint.last_checked_at || '--' }}</td>
              <td>
                <NTag
                  :type="endpoint.sync_status === 'synced' ? 'success' : 'warning'"
                  size="small"
                  bordered={false}
                >
                  {{ endpoint.sync_status || '未同步' }}
                </NTag>
              </td>
            </tr>
          </tbody>
        </NTable>
      </template>
      <NEmpty v-else description="暂无端点信息" />
    </NCard>

    <NCard title="映射覆盖" size="small" :loading="mappingsLoading">
      <div class="text-sm text-gray-500 mb-3" v-if="mappingScopeStats.length">
        <span class="mr-2">按业务域统计：</span>
        <NSpace wrap>
          <NTag v-for="item in mappingScopeStats" :key="item.scope" type="info" bordered={false}>
            {{ item.scope }}：{{ item.count }}
          </NTag>
        </NSpace>
      </div>
      <template v-if="mappingRows.length">
        <NTable :single-line="false" size="small" striped>
          <thead>
            <tr>
              <th style="width: 140px">业务域</th>
              <th style="width: 200px">对象名称</th>
              <th style="width: 160px">默认模型</th>
              <th>候选模型</th>
              <th style="width: 160px">更新时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="mapping in mappingRows" :key="mapping.id">
              <td>
                <NTag type="info" size="small" bordered={false}>{{ mapping.scope_type }}</NTag>
              </td>
              <td>{{ mapping.name || mapping.scope_key }}</td>
              <td>{{ mapping.default_model || '--' }}</td>
              <td>
                <NSpace wrap>
                  <NTag
                    v-for="model in mapping.candidates"
                    :key="model"
                    size="small"
                    bordered={false}
                  >
                    {{ model }}
                  </NTag>
                </NSpace>
              </td>
              <td>{{ mapping.updated_at || '--' }}</td>
            </tr>
          </tbody>
        </NTable>
      </template>
      <NEmpty v-else description="暂无映射记录" />
    </NCard>
  </NSpace>
</template>

<style scoped>
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

