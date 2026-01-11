<script setup>
import { computed } from 'vue'
import { NButton, NDivider } from 'naive-ui'
import draggable from 'vuedraggable'
import { useRouter } from 'vue-router'
import HeroIcon from '@/components/common/HeroIcon.vue'

const props = defineProps({
  quickAccessCards: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:quickAccessCards', 'reset-layout', 'show-supabase-modal'])

const router = useRouter()

// Local state for draggable to avoid mutating prop directly (though v-model on component works if set up right, 
// usually it's better to manage list state in parent or use a computed setter)
// For simplicity, we'll emit changes.
const internalCards = computed({
  get: () => props.quickAccessCards,
  set: (value) => emit('update:quickAccessCards', value)
})

const handleQuickAccessClick = (path) => {
  router.push(path)
}

const handleReset = () => {
  emit('reset-layout')
}

</script>

<template>
  <div class="control-center">
    <!-- Quick Access Section -->
    <div class="section mb-6">
      <div class="flex justify-between items-center mb-3">
        <h3 class="text-sm font-semibold opacity-70 uppercase tracking-wider">快捷访问</h3>
        <NButton text size="tiny" @click="handleReset">
          <template #icon><HeroIcon name="arrow-path" size="14" /></template>
        </NButton>
      </div>
      
      <div class="quick-access-list">
        <draggable
          v-model="internalCards"
          item-key="path"
          :animation="200"
          ghost-class="ghost-item"
          class="space-y-2"
        >
          <template #item="{ element }">
             <div 
               class="quick-access-item group" 
               @click="handleQuickAccessClick(element.path)"
             >
                <div class="icon-box" :style="{ backgroundColor: element.iconColor + '20', color: element.iconColor }">
                  <HeroIcon :name="element.icon" size="18" />
                </div>
                <div class="flex-1 min-w-0">
                  <div class="font-medium truncate">{{ element.title }}</div>
                  <div class="text-xs opacity-60 truncate">{{ element.description }}</div>
                </div>
                <div class="opacity-0 group-hover:opacity-100 transition-opacity">
                   <HeroIcon name="chevron-right" size="16" class="text-gray-400" />
                </div>
             </div>
          </template>
        </draggable>
      </div>
    </div>

    <NDivider />

    <!-- System Status Actions -->
    <div class="section">
       <h3 class="text-sm font-semibold opacity-70 uppercase tracking-wider mb-3">系统状态</h3>
       <div class="grid grid-cols-2 gap-3">
         <div class="system-action-card" @click="emit('show-supabase-modal')">
            <HeroIcon name="circle-stack" size="20" class="mb-2 text-green-600" />
            <span class="text-xs font-medium">Supabase</span>
            <span class="text-[10px] opacity-60">正常运行</span>
         </div>
         <!-- Add more system quick checks here if needed -->
       </div>
    </div>

  </div>
</template>

<style scoped>
.control-center {
  background: var(--dash-surface);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: var(--dash-radius);
  border: 1px solid var(--dash-border);
  padding: 24px;
  height: 100%;
  box-shadow: var(--dash-shadow);
}

.quick-access-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  border-radius: 12px;
  background: var(--dash-item-bg);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}

.quick-access-item:hover {
  background: var(--dash-item-hover-bg);
  transform: translateY(-1px);
  border-color: var(--dash-divider);
}

.icon-box {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ghost-item {
  opacity: 0.5;
  background: var(--dash-item-bg);
  border: 1px dashed var(--dash-border);
}

.system-action-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: var(--dash-surface-solid);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid var(--dash-border);
}

.system-action-card:hover {
  box-shadow: var(--dash-shadow);
  transform: translateY(-1px);
}
</style>
