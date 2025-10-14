<template>
  <component :is="iconComponent" :class="iconClass" :style="iconStyle" />
</template>

<script setup>
import { computed } from 'vue'
import {
  ChartBarIcon,
  CpuChipIcon,
  CurrencyDollarIcon,
  SignalIcon,
  KeyIcon,
  ArrowPathIcon,
  Cog6ToothIcon,
  UserGroupIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XCircleIcon,
  RectangleStackIcon,
  MapIcon,
  DocumentTextIcon,
  WrenchScrewdriverIcon,
  ClipboardDocumentListIcon,
  FolderIcon,
  FolderOpenIcon,
  MagnifyingGlassIcon,
  PencilIcon,
  PlusIcon,
  TrashIcon,
} from '@heroicons/vue/24/outline'

// 图标映射表（SSOT）
const iconMap = {
  'chart-bar': ChartBarIcon,
  'cpu-chip': CpuChipIcon,
  'currency-dollar': CurrencyDollarIcon,
  signal: SignalIcon,
  key: KeyIcon,
  'arrow-path': ArrowPathIcon,
  'cog-6-tooth': Cog6ToothIcon,
  'user-group': UserGroupIcon,
  clock: ClockIcon,
  'exclamation-triangle': ExclamationTriangleIcon,
  'information-circle': InformationCircleIcon,
  'x-circle': XCircleIcon,
  'rectangle-stack': RectangleStackIcon,
  map: MapIcon,
  'document-text': DocumentTextIcon,
  'wrench-screwdriver': WrenchScrewdriverIcon,
  'clipboard-document-list': ClipboardDocumentListIcon,
  folder: FolderIcon,
  'folder-open': FolderOpenIcon,
  'magnifying-glass': MagnifyingGlassIcon,
  pencil: PencilIcon,
  plus: PlusIcon,
  trash: TrashIcon,
}

defineOptions({ name: 'HeroIcon' })

const props = defineProps({
  name: {
    type: String,
    required: true,
    validator: (value) => {
      const validIcons = [
        'chart-bar',
        'cpu-chip',
        'currency-dollar',
        'signal',
        'key',
        'arrow-path',
        'cog-6-tooth',
        'user-group',
        'clock',
        'exclamation-triangle',
        'information-circle',
        'x-circle',
        'rectangle-stack',
        'map',
        'document-text',
        'wrench-screwdriver',
        'clipboard-document-list',
        'folder',
        'folder-open',
        'magnifying-glass',
        'pencil',
        'plus',
        'trash',
      ]
      return validIcons.includes(value)
    },
  },
  size: {
    type: [String, Number],
    default: 24,
  },
  color: {
    type: String,
    default: 'currentColor',
  },
})

// 动态获取图标组件
const iconComponent = computed(() => {
  return iconMap[props.name] || ChartBarIcon
})

// 图标样式类
const iconClass = computed(() => {
  return 'hero-icon'
})

// 图标内联样式
const iconStyle = computed(() => {
  return {
    width: typeof props.size === 'number' ? `${props.size}px` : props.size,
    height: typeof props.size === 'number' ? `${props.size}px` : props.size,
    color: props.color,
  }
})
</script>

<style scoped>
.hero-icon {
  display: inline-block;
  flex-shrink: 0;
  vertical-align: middle;
}
</style>
