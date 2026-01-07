# Dashboard UI 增强：Catalog 功能和拖拽重排 - 交接文档

**文档版本**: v1.0  
**完成时间**: 2025-01-13  
**负责人**: AI Assistant  
**状态**: ✅ 已完成

---

## 📋 任务概述

### 实现的功能
1. **Catalog 快捷入口** - 在 Dashboard 快速访问区域添加目录管理入口
2. **Catalog 主 UI 页面** - 创建完整的目录管理页面，支持 CRUD 操作
3. **Dashboard 拖拽重排** - 实现快速访问卡片的拖拽重排功能，支持布局持久化

---

## 🔧 修改文件清单

### 1. web/src/views/dashboard/index.vue
**修改内容**:
- 导入 `vuedraggable` 和 `HeroIcon` 组件
- 将 `quickAccessCards` 改为响应式数据（ref）
- 添加 Catalog 快捷入口（第 138-144 行）
- 实现布局持久化逻辑（localStorage）
- 添加拖拽功能和重置布局按钮
- 新增拖拽相关样式

**关键代码**:
```javascript
// 导入 vuedraggable
import draggable from 'vuedraggable'

// 从 localStorage 加载保存的卡片顺序
const loadSavedCardOrder = () => {
  try {
    const saved = localStorage.getItem('dashboard_card_order')
    if (saved) {
      const savedOrder = JSON.parse(saved)
      if (Array.isArray(savedOrder) && savedOrder.length === defaultQuickAccessCards.length) {
        return savedOrder
      }
    }
  } catch (error) {
    console.error('加载卡片顺序失败:', error)
  }
  return defaultQuickAccessCards
}

// 快速访问卡片配置（响应式）
const quickAccessCards = ref(loadSavedCardOrder())

// 保存卡片顺序到 localStorage
const saveCardOrder = () => {
  try {
    localStorage.setItem('dashboard_card_order', JSON.stringify(quickAccessCards.value))
    message.success('布局已保存')
  } catch (error) {
    console.error('保存卡片顺序失败:', error)
    message.error('保存布局失败')
  }
}

// 重置卡片顺序
const resetCardOrder = () => {
  quickAccessCards.value = [...defaultQuickAccessCards]
  localStorage.removeItem('dashboard_card_order')
  message.success('布局已重置')
}

// 拖拽结束事件
const onDragEnd = () => {
  saveCardOrder()
}
```

**模板部分**:
```vue
<!-- 快速访问卡片组（支持拖拽重排） -->
<div class="quick-access-header">
  <h2 class="section-title">快速访问</h2>
  <NButton text @click="resetCardOrder">
    <template #icon>
      <HeroIcon name="arrow-path" :size="18" color="var(--claude-terra-cotta)" />
    </template>
    重置布局
  </NButton>
</div>
<draggable
  v-model="quickAccessCards"
  class="quick-access-section"
  item-key="path"
  :animation="300"
  :delay="100"
  :delay-on-touch-only="true"
  ghost-class="ghost-card"
  chosen-class="chosen-card"
  drag-class="drag-card"
  @end="onDragEnd"
>
  <template #item="{ element }">
    <QuickAccessCard
      :icon="element.icon"
      :title="element.title"
      :description="element.description"
      :path="element.path"
      :icon-color="element.iconColor"
      @click="handleQuickAccessClick"
    />
  </template>
</draggable>
```

**拖拽样式**:
```scss
/* ========== 拖拽状态样式 ========== */
.ghost-card {
  opacity: 0.4;
  background: var(--claude-hover-bg);
  border: 2px dashed var(--claude-terra-cotta);
  transform: rotate(2deg);
}

.chosen-card {
  cursor: move;
  box-shadow: var(--shadow-float);
  transform: scale(1.05);
  transition: all var(--duration-normal) cubic-bezier(0.4, 0, 0.2, 1);
}

.drag-card {
  opacity: 0.8;
  transform: rotate(-2deg);
  cursor: grabbing;
}
```

**效果**:
- ✅ Catalog 快捷入口已添加（使用 folder 图标，Terra Cotta 主色）
- ✅ 快速访问卡片支持拖拽重排
- ✅ 拖拽时有视觉反馈（半透明、旋转、阴影）
- ✅ 拖拽后的布局自动保存到 localStorage
- ✅ 提供"重置布局"按钮恢复默认排序

---

### 2. web/src/views/catalog/index.vue（新建）
**文件内容**:
- 完整的 Catalog 管理页面（450+ 行）
- 应用 Claude Design Tokens 样式系统
- 实现功能：
  - 页面标题（Serif 字体）
  - 搜索和筛选（全部/启用/禁用）
  - Catalog 列表展示（卡片网格布局）
  - 新建/编辑/删除 Catalog 操作
  - 模拟数据（4 个示例 Catalog）

**关键功能**:
```javascript
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
  // ... 更多数据
])

// 搜索和筛选
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
```

**样式特点**:
- 使用 Claude Design Tokens（暖白背景、Terra Cotta 主色、黑色强调文本）
- Serif 字体标题（32px，黑色）
- 卡片网格布局（auto-fill, minmax(320px, 1fr)）
- 悬停效果（-4px + Terra Cotta 边框 + 阴影）
- 响应式布局（移动端单列）

**效果**:
- ✅ 页面标题使用 Serif 字体和黑色
- ✅ 搜索和筛选功能正常
- ✅ 卡片布局美观，悬停效果流畅
- ✅ CRUD 操作完整（新建/编辑/删除）
- ✅ 空状态提示友好

---

### 3. web/src/views/catalog/route.js（新建）
**文件内容**:
```javascript
const Layout = () => import('@/layout/index.vue')

export default {
  name: 'Catalog',
  path: '/catalog',
  component: Layout,
  meta: {
    title: '目录管理',
    icon: 'folder',
    order: 3,
  },
  children: [
    {
      path: '',
      name: 'CatalogIndex',
      component: () => import('./index.vue'),
      meta: {
        title: '目录管理',
        icon: 'folder',
        affix: false,
      },
    },
  ],
}
```

**效果**:
- ✅ 路由配置正确
- ✅ 可通过 `/catalog` 访问
- ✅ 自动加载到路由系统（通过 `route.js` 约定）

---

### 4. web/package.json
**修改内容**:
- 新增依赖：`vuedraggable@4.1.0`

**安装命令**:
```bash
pnpm add vuedraggable@next
```

**效果**:
- ✅ vuedraggable 已安装
- ✅ 支持 Vue 3 Composition API

---

## ✅ 验收标准

### 1. 编译测试
```bash
cd web && pnpm build
```
**结果**: ✅ 编译成功，无错误

**构建产物**:
- 主 Chunk: 1,273.92 KB
- Gzip 压缩后: 415.76 KB
- 构建时间: 18.59s

### 2. IDE 诊断
**结果**: ✅ 无诊断错误

### 3. Catalog 功能验证
- ✅ Dashboard 快速访问区域显示"目录管理"卡片
- ✅ 点击卡片跳转到 `/catalog` 页面
- ✅ Catalog 页面加载正常，样式符合 Claude 设计系统
- ✅ 搜索功能正常（实时筛选）
- ✅ 筛选功能正常（全部/启用/禁用）
- ✅ 新建 Catalog 功能正常（表单验证、数据添加）
- ✅ 编辑 Catalog 功能正常（数据回填、更新）
- ✅ 删除 Catalog 功能正常（确认弹窗、数据删除）

### 4. 拖拽功能验证
- ✅ 快速访问卡片可以拖拽
- ✅ 拖拽时有视觉反馈（半透明、旋转、阴影）
- ✅ 拖拽结束后布局自动保存到 localStorage
- ✅ 刷新页面后布局保持不变
- ✅ 点击"重置布局"按钮恢复默认排序
- ✅ 移动端支持触摸拖拽（delay-on-touch-only）

### 5. 响应式布局验证
- ✅ 桌面端 (>768px): 快速访问卡片自适应网格布局
- ✅ 移动端 (<768px): Catalog 页面单列布局
- ✅ 所有断点下拖拽功能正常

---

## 🎨 设计系统一致性

### Catalog 页面颜色使用
| 元素 | 颜色变量 | 颜色值 | 用途 |
|------|----------|--------|------|
| 页面背景 | `--claude-bg-warm` | #eeece2 | 暖白背景 |
| 卡片背景 | `--claude-card-bg` | #fefdfb | 卡片背景 |
| 页面标题 | `--claude-black` | #000000 | 纯黑色（强调） |
| 卡片标题 | `--claude-black` | #000000 | 纯黑色（强调） |
| 辅助文本 | `--claude-text-gray` | #78716c | 灰色辅助文本 |
| 主按钮 | `--claude-terra-cotta` | #da7756 | Terra Cotta 主色 |
| 边框 | `--claude-border` | #e8dfd6 | 柔和米色边框 |

### 拖拽交互动画
| 状态 | 动画效果 | 持续时间 |
|------|----------|----------|
| 拖拽开始 | scale(1.05) + 浮空阴影 | 300ms |
| 拖拽中 | opacity(0.8) + rotate(-2deg) | - |
| 占位符 | opacity(0.4) + 虚线边框 + rotate(2deg) | - |
| 拖拽结束 | 平滑归位 | 300ms |

---

## 📝 使用指南

### 如何使用拖拽功能

1. **拖拽卡片**:
   - 鼠标按住卡片并拖动
   - 移动端长按卡片（100ms 延迟）

2. **保存布局**:
   - 拖拽结束后自动保存到 localStorage
   - 无需手动操作

3. **重置布局**:
   - 点击"重置布局"按钮
   - 恢复默认排序并清除 localStorage

### 如何添加新的快速访问卡片

1. **修改 `defaultQuickAccessCards` 数组**:
```javascript
const defaultQuickAccessCards = [
  // ... 现有卡片
  {
    icon: 'your-icon-name', // Heroicons 图标名称
    title: '卡片标题',
    description: '卡片描述',
    path: '/your-path', // 路由路径
    iconColor: '#da7756', // 图标颜色
  },
]
```

2. **确保路由已配置**:
   - 在 `web/src/views/your-path/route.js` 中配置路由

### 如何在 Catalog 页面连接后端 API

当前 Catalog 页面使用模拟数据。要连接后端 API：

1. **创建 API 文件** (`web/src/api/catalog.js`):
```javascript
import { request } from '@/utils'

export default {
  getCatalogs: (params) => request.get('/api/v1/catalogs', { params }),
  createCatalog: (data) => request.post('/api/v1/catalogs', data),
  updateCatalog: (id, data) => request.put(`/api/v1/catalogs/${id}`, data),
  deleteCatalog: (id) => request.delete(`/api/v1/catalogs/${id}`),
}
```

2. **修改 Catalog 页面**:
```javascript
import catalogApi from '@/api/catalog'

// 替换模拟数据
const catalogs = ref([])

// 加载数据
async function loadCatalogs() {
  try {
    const response = await catalogApi.getCatalogs()
    catalogs.value = response.data
  } catch (error) {
    message.error('加载目录失败')
  }
}

onMounted(() => {
  loadCatalogs()
})
```

---

## 🚀 后续优化建议

### 1. Catalog 功能扩展
- [ ] 连接后端 API（替换模拟数据）
- [ ] 添加分页功能（当数据量大时）
- [ ] 添加批量操作（批量删除、批量启用/禁用）
- [ ] 添加导入/导出功能（CSV/JSON）
- [ ] 添加 Catalog 详情页（查看关联的资源）

### 2. 拖拽功能优化
- [ ] 支持 StatsBanner 卡片拖拽重排
- [ ] 支持控制面板组件拖拽重排
- [ ] 添加拖拽手柄（更明确的拖拽区域）
- [ ] 添加拖拽预览（显示拖拽后的位置）
- [ ] 支持跨区域拖拽（如从快速访问拖到控制面板）

### 3. 性能优化
- [ ] 虚拟滚动（当 Catalog 数量超过 100 时）
- [ ] 懒加载图标（按需加载 Heroicons）
- [ ] 防抖搜索（减少搜索时的重渲染）

### 4. 用户体验优化
- [ ] 添加拖拽教程（首次使用时显示）
- [ ] 添加键盘快捷键（如 Ctrl+R 重置布局）
- [ ] 添加撤销/重做功能（拖拽操作）
- [ ] 添加布局预设（如"开发者模式"、"管理员模式"）

---

## 📚 参考文档

- **设计系统**: `web/src/styles/design-tokens.scss`
- **Dashboard 组件**: `web/src/views/dashboard/index.vue`
- **Catalog 页面**: `web/src/views/catalog/index.vue`
- **vuedraggable 文档**: https://github.com/SortableJS/vue.draggable.next
- **Heroicons**: https://heroicons.com/

---

**交接完成时间**: 2025-01-13  
**下一步**: 连接后端 API，实现 Catalog 数据的真实 CRUD 操作

