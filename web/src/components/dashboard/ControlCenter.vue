<script setup>
import { NCard, NSpace, NButton, NText, NDivider, NList, NListItem } from 'naive-ui'
import HeroIcon from '@/components/common/HeroIcon.vue'
import ModelSwitcher from '@/components/dashboard/ModelSwitcher.vue'
import PromptSelector from '@/components/dashboard/PromptSelector.vue'
import draggable from 'vuedraggable'
import { ref, onMounted } from 'vue'
import { useMessage } from 'naive-ui'
import { useRouter } from 'vue-router'

const props = defineProps({
  quickAccessCards: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:quickAccessCards', 'reset-layout', 'show-supabase-modal'])

const message = useMessage()
const router = useRouter()

// Local state for draggable to avoid mutating prop directly (though v-model on component works if set up right, 
// usually it's better to manage list state in parent or use a computed setter)
// For simplicity, we'll emit changes.
const internalCards = computed({
  get: () => props.quickAccessCards,
  set: (value) => emit('update:quickAccessCards', value)
})

import { computed } from 'vue'

const handleQuickAccessClick = (path) => {
  router.push(path)
}

const handleReset = () => {
  emit('reset-layout')
}

const handleModelChange = (modelId) => {
    // Handled in parent or global store usually, but we log for now
    console.log('Model changed:', modelId)
}

const handlePromptChange = (promptId) => {
    console.log('Prompt changed:', promptId)
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

    <!-- AI Configuration Section -->
    <div class="section mb-6">
      <h3 class="text-sm font-semibold opacity-70 uppercase tracking-wider mb-3">AI 配置</h3>
      <div class="space-y-4">
        <ModelSwitcher :compact="false" @change="handleModelChange" />
        <PromptSelector :compact="false" @change="handlePromptChange" />
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
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 20px;
  border: 1px solid rgba(255, 255, 255, 0.3);
  padding: 24px;
  height: 100%;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); 
}

.quick-access-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.5);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}

.quick-access-item:hover {
  background: white;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
  transform: translateY(-1px);
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
  background: #f0f0f0;
  border: 1px dashed #ccc;
}

.system-action-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: white;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid rgba(0,0,0,0.05);
}

.system-action-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
  transform: translateY(-2px);
}
</style>
