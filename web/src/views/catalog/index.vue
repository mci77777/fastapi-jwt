<template>
  <div class="catalog-container">
    <!-- 页面标题 -->
    <div class="page-header">
      <h1 class="page-title">目录管理</h1>
      <p class="page-description">管理内容分类和标签，组织您的资源</p>
    </div>

    <!-- 操作栏 -->
    <div class="action-bar">
      <div class="search-section">
        <NInput
          v-model:value="searchQuery"
          placeholder="搜索目录名称或描述..."
          clearable
          class="search-input"
        >
          <template #prefix>
            <HeroIcon name="magnifying-glass" :size="20" color="var(--claude-text-gray)" />
          </template>
        </NInput>
      </div>
      <div class="button-section">
        <NButton type="primary" @click="handleAddCatalog">
          <template #icon>
            <HeroIcon name="plus" :size="20" color="white" />
          </template>
          新建目录
        </NButton>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <NSpace>
        <NTag
          :type="filterType === 'all' ? 'primary' : 'default'"
          :bordered="false"
          class="filter-tag"
          @click="filterType = 'all'"
        >
          全部 ({{ catalogs.length }})
        </NTag>
        <NTag
          :type="filterType === 'active' ? 'primary' : 'default'"
          :bordered="false"
          class="filter-tag"
          @click="filterType = 'active'"
        >
          启用 ({{ activeCatalogs.length }})
        </NTag>
        <NTag
          :type="filterType === 'inactive' ? 'primary' : 'default'"
          :bordered="false"
          class="filter-tag"
          @click="filterType = 'inactive'"
        >
          禁用 ({{ inactiveCatalogs.length }})
        </NTag>
      </NSpace>
    </div>

    <!-- 目录列表（卡片形式） -->
    <div v-if="filteredCatalogs.length > 0" class="catalog-grid">
      <NCard v-for="catalog in filteredCatalogs" :key="catalog.id" class="catalog-card" hoverable>
        <div class="catalog-card-header">
          <div class="catalog-icon">
            <HeroIcon :name="catalog.icon" :size="28" :color="catalog.color" />
          </div>
          <div class="catalog-status">
            <NBadge
              :value="catalog.status === 'active' ? '启用' : '禁用'"
              :type="catalog.status === 'active' ? 'success' : 'default'"
            />
          </div>
        </div>
        <div class="catalog-content">
          <h3 class="catalog-title">{{ catalog.name }}</h3>
          <p class="catalog-description">{{ catalog.description }}</p>
          <div class="catalog-meta">
            <span class="meta-item">
              <HeroIcon name="document-text" :size="16" color="var(--claude-text-gray)" />
              {{ catalog.itemCount }} 项
            </span>
            <span class="meta-item">
              <HeroIcon name="clock" :size="16" color="var(--claude-text-gray)" />
              {{ formatDate(catalog.updatedAt) }}
            </span>
          </div>
        </div>
        <div class="catalog-actions">
          <NButton text @click="handleEditCatalog(catalog)">
            <template #icon>
              <HeroIcon name="pencil" :size="18" color="var(--claude-terra-cotta)" />
            </template>
            编辑
          </NButton>
          <NButton text @click="handleDeleteCatalog(catalog)">
            <template #icon>
              <HeroIcon name="trash" :size="18" color="var(--claude-error)" />
            </template>
            删除
          </NButton>
        </div>
      </NCard>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <HeroIcon name="folder-open" :size="64" color="var(--claude-text-gray)" />
      <p class="empty-text">暂无目录数据</p>
      <NButton type="primary" @click="handleAddCatalog">
        <template #icon>
          <HeroIcon name="plus" :size="20" color="white" />
        </template>
        创建第一个目录
      </NButton>
    </div>

    <!-- 新建/编辑目录弹窗 -->
    <NModal v-model:show="showCatalogModal" preset="card" :title="modalTitle" class="catalog-modal">
      <NForm
        ref="formRef"
        :model="formData"
        :rules="formRules"
        label-placement="left"
        label-width="80"
      >
        <NFormItem label="目录名称" path="name">
          <NInput v-model:value="formData.name" placeholder="请输入目录名称" />
        </NFormItem>
        <NFormItem label="描述" path="description">
          <NInput
            v-model:value="formData.description"
            type="textarea"
            placeholder="请输入目录描述"
            :rows="3"
          />
        </NFormItem>
        <NFormItem label="图标" path="icon">
          <NSelect v-model:value="formData.icon" :options="iconOptions" placeholder="选择图标" />
        </NFormItem>
        <NFormItem label="颜色" path="color">
          <NSelect v-model:value="formData.color" :options="colorOptions" placeholder="选择颜色" />
        </NFormItem>
        <NFormItem label="状态" path="status">
          <NSwitch v-model:value="formData.active">
            <template #checked>启用</template>
            <template #unchecked>禁用</template>
          </NSwitch>
        </NFormItem>
      </NForm>
      <template #footer>
        <NSpace justify="end">
          <NButton @click="showCatalogModal = false">取消</NButton>
          <NButton type="primary" @click="handleSubmit">确定</NButton>
        </NSpace>
      </template>
    </NModal>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import {
  NCard,
  NButton,
  NInput,
  NSpace,
  NTag,
  NBadge,
  NModal,
  NForm,
  NFormItem,
  NSelect,
  NSwitch,
  useMessage,
  useDialog,
} from 'naive-ui'
import HeroIcon from '@/components/common/HeroIcon.vue'

defineOptions({ name: 'CatalogIndex' })

const message = useMessage()
const dialog = useDialog()

// 响应式状态
const searchQuery = ref('')
const filterType = ref('all')
const showCatalogModal = ref(false)
const formRef = ref(null)

// 模拟目录数据
const catalogs = ref([
  {
    id: 1,
    name: 'AI 模型',
    description: 'AI 模型相关资源分类',
    icon: 'cpu-chip',
    color: '#667eea',
    status: 'active',
    itemCount: 24,
    updatedAt: '2025-01-13T10:30:00Z',
  },
  {
    id: 2,
    name: '提示词模板',
    description: 'Prompt 模板库',
    icon: 'document-text',
    color: '#18a058',
    status: 'active',
    itemCount: 56,
    updatedAt: '2025-01-12T15:20:00Z',
  },
  {
    id: 3,
    name: '用户数据',
    description: '用户相关数据分类',
    icon: 'user-group',
    color: '#2080f0',
    status: 'active',
    itemCount: 128,
    updatedAt: '2025-01-11T09:15:00Z',
  },
  {
    id: 4,
    name: '系统配置',
    description: '系统配置项分类',
    icon: 'cog-6-tooth',
    color: '#f0a020',
    status: 'inactive',
    itemCount: 12,
    updatedAt: '2025-01-10T14:45:00Z',
  },
])

// 表单数据
const formData = ref({
  name: '',
  description: '',
  icon: 'folder',
  color: '#da7756',
  active: true,
})

// 表单验证规则
const formRules = {
  name: [{ required: true, message: '请输入目录名称', trigger: 'blur' }],
  description: [{ required: true, message: '请输入目录描述', trigger: 'blur' }],
}

// 图标选项
const iconOptions = [
  { label: '文件夹', value: 'folder' },
  { label: 'CPU 芯片', value: 'cpu-chip' },
  { label: '文档', value: 'document-text' },
  { label: '用户组', value: 'user-group' },
  { label: '设置', value: 'cog-6-tooth' },
  { label: '标签', value: 'tag' },
  { label: '书签', value: 'bookmark' },
  { label: '星标', value: 'star' },
]

// 颜色选项
const colorOptions = [
  { label: 'Terra Cotta', value: '#da7756' },
  { label: '紫色', value: '#667eea' },
  { label: '绿色', value: '#18a058' },
  { label: '蓝色', value: '#2080f0' },
  { label: '橙色', value: '#f0a020' },
  { label: '红色', value: '#d03050' },
]

// 计算属性
const modalTitle = computed(() => (formData.value.id ? '编辑目录' : '新建目录'))

const activeCatalogs = computed(() => catalogs.value.filter((c) => c.status === 'active'))
const inactiveCatalogs = computed(() => catalogs.value.filter((c) => c.status === 'inactive'))

const filteredCatalogs = computed(() => {
  let result = catalogs.value

  // 按状态筛选
  if (filterType.value === 'active') {
    result = result.filter((c) => c.status === 'active')
  } else if (filterType.value === 'inactive') {
    result = result.filter((c) => c.status === 'inactive')
  }

  // 按搜索关键词筛选
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter(
      (c) => c.name.toLowerCase().includes(query) || c.description.toLowerCase().includes(query)
    )
  }

  return result
})

// 方法
function formatDate(dateString) {
  const date = new Date(dateString)
  const now = new Date()
  const diff = now - date
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))

  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days} 天前`
  return date.toLocaleDateString('zh-CN')
}

function handleAddCatalog() {
  formData.value = {
    name: '',
    description: '',
    icon: 'folder',
    color: '#da7756',
    active: true,
  }
  showCatalogModal.value = true
}

function handleEditCatalog(catalog) {
  formData.value = {
    id: catalog.id,
    name: catalog.name,
    description: catalog.description,
    icon: catalog.icon,
    color: catalog.color,
    active: catalog.status === 'active',
  }
  showCatalogModal.value = true
}

function handleDeleteCatalog(catalog) {
  dialog.warning({
    title: '确认删除',
    content: `确定要删除目录"${catalog.name}"吗？此操作不可恢复。`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: () => {
      const index = catalogs.value.findIndex((c) => c.id === catalog.id)
      if (index > -1) {
        catalogs.value.splice(index, 1)
        message.success('删除成功')
      }
    },
  })
}

function handleSubmit() {
  formRef.value?.validate((errors) => {
    if (!errors) {
      if (formData.value.id) {
        // 编辑
        const index = catalogs.value.findIndex((c) => c.id === formData.value.id)
        if (index > -1) {
          catalogs.value[index] = {
            ...catalogs.value[index],
            name: formData.value.name,
            description: formData.value.description,
            icon: formData.value.icon,
            color: formData.value.color,
            status: formData.value.active ? 'active' : 'inactive',
            updatedAt: new Date().toISOString(),
          }
          message.success('更新成功')
        }
      } else {
        // 新建
        const newCatalog = {
          id: Date.now(),
          name: formData.value.name,
          description: formData.value.description,
          icon: formData.value.icon,
          color: formData.value.color,
          status: formData.value.active ? 'active' : 'inactive',
          itemCount: 0,
          updatedAt: new Date().toISOString(),
        }
        catalogs.value.unshift(newCatalog)
        message.success('创建成功')
      }
      showCatalogModal.value = false
    }
  })
}
</script>

<style scoped>
/* ========== Claude 设计系统 ========== */
.catalog-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2xl);
  padding: var(--spacing-2xl);
  background: var(--claude-bg-warm);
  min-height: 100%;
}

/* ========== 页面标题 ========== */
.page-header {
  margin-bottom: var(--spacing-md);
}

.page-title {
  font-family: var(--font-serif);
  font-size: 32px;
  font-weight: var(--font-weight-bold);
  color: var(--claude-black);
  margin: 0 0 var(--spacing-sm) 0;
  letter-spacing: -0.02em;
}

.page-description {
  font-family: var(--font-sans);
  font-size: var(--font-size-md);
  color: var(--claude-text-gray);
  margin: 0;
}

/* ========== 操作栏 ========== */
.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--spacing-lg);
}

.search-section {
  flex: 1;
  max-width: 400px;
}

.search-input {
  width: 100%;
}

.button-section {
  display: flex;
  gap: var(--spacing-md);
}

/* ========== 筛选栏 ========== */
.filter-bar {
  padding: var(--spacing-md) 0;
}

.filter-tag {
  cursor: pointer;
  transition: all var(--duration-fast);
}

.filter-tag:hover {
  transform: translateY(-2px);
}

/* ========== 目录网格 ========== */
.catalog-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--spacing-lg);
}

/* ========== 目录卡片 ========== */
.catalog-card {
  background: var(--claude-card-bg);
  border: 1px solid var(--claude-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-soft);
  transition: all var(--duration-normal);
}

.catalog-card:hover {
  border-color: var(--claude-terra-cotta);
  box-shadow: var(--shadow-hover);
  transform: translateY(-4px);
}

.catalog-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
}

.catalog-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  background: var(--claude-bg-warm);
  border-radius: var(--radius-md);
}

.catalog-content {
  margin-bottom: var(--spacing-lg);
}

.catalog-title {
  font-family: var(--font-sans);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--claude-black);
  margin: 0 0 var(--spacing-sm) 0;
}

.catalog-description {
  font-family: var(--font-sans);
  font-size: var(--font-size-sm);
  color: var(--claude-text-gray);
  margin: 0 0 var(--spacing-md) 0;
  line-height: 1.5;
}

.catalog-meta {
  display: flex;
  gap: var(--spacing-lg);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-family: var(--font-sans);
  font-size: var(--font-size-xs);
  color: var(--claude-text-gray);
}

.catalog-actions {
  display: flex;
  gap: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--claude-border);
}

/* ========== 空状态 ========== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-4xl) var(--spacing-2xl);
  background: var(--claude-card-bg);
  border: 1px solid var(--claude-border);
  border-radius: var(--radius-lg);
  gap: var(--spacing-lg);
}

.empty-text {
  font-family: var(--font-sans);
  font-size: var(--font-size-md);
  color: var(--claude-text-gray);
  margin: 0;
}

/* ========== 响应式 ========== */
@media (max-width: 768px) {
  .catalog-container {
    padding: var(--spacing-lg);
  }

  .action-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .search-section {
    max-width: 100%;
  }

  .catalog-grid {
    grid-template-columns: 1fr;
  }
}
</style>
