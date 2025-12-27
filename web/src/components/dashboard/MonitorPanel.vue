<script setup>
import { NGrid, NGridItem, NCard } from 'naive-ui'
import UserActivityChart from '@/components/dashboard/UserActivityChart.vue'
import LogWindow from '@/components/dashboard/LogWindow.vue'
import ServerLoadCard from '@/components/dashboard/ServerLoadCard.vue'
import EndpointConnectivityCard from '@/components/dashboard/EndpointConnectivityCard.vue'

const props = defineProps({
  chartData: Array,
  chartTimeRange: String,
  statsLoading: Boolean,
  logs: Array,
  logsLoading: Boolean,
  dashboardConfig: Object
})

const emit = defineEmits([
  'time-range-change',
  'log-click',
  'log-filter-change',
  'log-refresh',
  'metrics-update'
])

// Forwarding events
const handleTimeRangeChange = (val) => emit('time-range-change', val)
const handleLogClick = (val) => emit('log-click', val)
const handleLogFilterChange = (val) => emit('log-filter-change', val)
const handleLogRefresh = () => emit('log-refresh')
const handleMetricsUpdate = (val) => emit('metrics-update', val)
</script>

<template>
  <div class="monitor-panel space-y-6">
    <!-- Top Row: Charts & Server Load -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div class="lg:col-span-2 chart-container glass-panel">
        <UserActivityChart
          :time-range="chartTimeRange"
          :data="chartData"
          :loading="statsLoading"
          @time-range-change="handleTimeRangeChange"
        />
      </div>
      <div class="server-stat-container glass-panel">
         <ServerLoadCard
           :auto-refresh="true"
           :refresh-interval="60"
           @metrics-update="handleMetricsUpdate"
         />
      </div>
    </div>

    <!-- Middle Row: Connectivity -->
    <div class="glass-panel p-4">
        <EndpointConnectivityCard />
    </div>

    <!-- Bottom Row: Logs -->
    <div class="logs-container glass-panel">
       <LogWindow
          :logs="logs"
          :loading="logsLoading"
          @log-click="handleLogClick"
          @filter-change="handleLogFilterChange"
          @refresh="handleLogRefresh"
        />
    </div>
  </div>
</template>

<style scoped>
.glass-panel {
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05);
  overflow: hidden;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.glass-panel:hover {
    box-shadow: 0 8px 25px -5px rgba(0, 0, 0, 0.08); 
}

.chart-container {
    min-height: 400px;
    padding: 20px;
}

.server-stat-container {
    min-height: 400px;
    padding: 10px; /* Internal padding of card handles spacing usually */
}

/* Adjustments for nested components to fit glass theme if possible, 
   otherwise the panel background provides the effect */
:deep(.n-card) {
    background: transparent !important;
    border: none !important;
}

:deep(.n-card-header) {
    padding-bottom: 0;
}
</style>
