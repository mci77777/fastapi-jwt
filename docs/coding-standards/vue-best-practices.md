# Vue 3 + Naive UI 编码规范和最佳实践

## 目录

1. [概述](#概述)
2. [模板语法规范](#模板语法规范)
3. [组件开发规范](#组件开发规范)
4. [响应式数据管理](#响应式数据管理)
5. [生命周期管理](#生命周期管理)
6. [常见陷阱和反模式](#常见陷阱和反模式)
7. [Naive UI 组件使用规范](#naive-ui-组件使用规范)
8. [代码审查检查清单](#代码审查检查清单)

---

## 概述

本文档定义了 GymBro 项目中 Vue 3 + Naive UI 的编码规范，旨在防止常见错误（如 JSX 语法混入 Vue 模板），提升代码质量和开发效率。

**核心原则**：
- **严格区分 Vue 模板语法和 JSX** - .vue 文件中禁止使用 JSX 语法
- **使用 Composition API** - 优先使用 `<script setup>` 语法
- **组件按需导入** - 支持 tree-shaking，减少打包体积
- **响应式数据最佳实践** - 正确使用 `ref`、`reactive`、`computed`

---

## 模板语法规范

### ✅ 正确的 Vue 模板语法

Vue 3 使用 **基于 HTML 的模板语法**，与 JSX 有本质区别。

#### 属性绑定

```vue
<!-- ✅ 正确 - Vue 模板语法 -->
<template>
  <NButton type="primary" @click="handleClick">
    点击我
  </NButton>

  <NInput v-model:value="formData.username" placeholder="请输入用户名" />

  <NCheckbox v-model:checked="formData.agree">
    同意条款
  </NCheckbox>
</template>

<!-- ❌ 错误 - JSX 语法（禁止在 .vue 文件中使用） -->
<template>
  <NButton type="primary" onClick={handleClick}>
    点击我
  </NButton>

  <NInput value={formData.username} onUpdateValue={handleInput} />

  <NCheckbox checked={formData.agree} onUpdateChecked={handleCheck}>
    同意条款
  </NCheckbox>
</template>
```

#### 类名绑定

```vue
<!-- ✅ 正确 - Vue 模板语法 -->
<template>
  <div class="static-class">静态类名</div>
  <div :class="dynamicClass">动态类名</div>
  <div :class="{ active: isActive, disabled: isDisabled }">对象语法</div>
  <div :class="[class1, class2]">数组语法</div>
</template>

<!-- ❌ 错误 - JSX 语法 -->
<template>
  <div className="static-class">静态类名</div>
  <div className={dynamicClass}>动态类名</div>
</template>
```

#### 条件渲染

```vue
<!-- ✅ 正确 - Vue 模板语法 -->
<template>
  <div v-if="isVisible">显示内容</div>
  <div v-else-if="isAlternative">备选内容</div>
  <div v-else>默认内容</div>

  <div v-show="isToggled">切换显示</div>
</template>

<!-- ❌ 错误 - JSX 语法 -->
<template>
  <div>{isVisible && <div>显示内容</div>}</div>
  <div>{isVisible ? <div>是</div> : <div>否</div>}</div>
</template>
```

#### 列表渲染

```vue
<!-- ✅ 正确 - Vue 模板语法 -->
<template>
  <div v-for="item in items" :key="item.id">
    {{ item.name }}
  </div>

  <tr v-for="(row, index) in tableData" :key="row.id">
    <td>{{ index + 1 }}</td>
    <td>{{ row.name }}</td>
  </tr>
</template>

<!-- ❌ 错误 - JSX 语法 -->
<template>
  {items.map(item => (
    <div key={item.id}>{item.name}</div>
  ))}
</template>
```

#### 插槽使用

```vue
<!-- ✅ 正确 - Vue 模板语法 -->
<template>
  <NButton type="primary">
    <template #icon>
      <span>📦</span>
    </template>
    按钮文字
  </NButton>

  <NTooltip>
    <template #trigger>
      <span>悬停查看</span>
    </template>
    <template #default>
      <div>提示内容</div>
    </template>
  </NTooltip>
</template>

<!-- ❌ 错误 - JSX 语法 -->
<template>
  <NButton type="primary" v-slots={{
    icon: () => <span>📦</span>
  }}>
    按钮文字
  </NButton>
</template>
```

---

## 组件开发规范

### 组件结构

使用 `<script setup>` 语法，代码更简洁：

```vue
<script setup>
import { ref, computed, onMounted } from 'vue'
import { NButton, NCard } from 'naive-ui'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useAiModelSuiteStore } from '@/store'

// 定义组件选项
defineOptions({ name: 'AiModelDashboard' })

// 状态管理
const store = useAiModelSuiteStore()
const { models, loading } = storeToRefs(store)
const router = useRouter()

// 响应式数据
const formData = reactive({
  username: '',
  password: ''
})

// 计算属性
const totalCount = computed(() => models.value.length)

// 方法
function handleClick() {
  router.push('/path')
}

// 生命周期
onMounted(() => {
  store.loadModels()
})
</script>

<template>
  <NCard title="标题">
    <!-- 模板内容 -->
  </NCard>
</template>

<style scoped>
/* 样式 */
</style>
```

### 组件命名

```vue
<script setup>
// ✅ 正确 - 使用 defineOptions 定义组件名
defineOptions({ name: 'AiModelDashboard' })
</script>

<!-- ❌ 错误 - 不使用 export default -->
<script>
export default {
  name: 'ai-model-dashboard' // 错误命名格式
}
</script>
```

### 组件导入

```vue
<script setup>
// ✅ 正确 - 按需导入
import {
  NButton,
  NCard,
  NTable,
  NTag
} from 'naive-ui'

// ❌ 错误 - 全量导入
import naive from 'naive-ui'
</script>
```

---

## 响应式数据管理

### ref vs reactive

```vue
<script setup>
import { ref, reactive, computed } from 'vue'

// ✅ 正确 - ref 用于基础类型
const count = ref(0)
const message = ref('Hello')
const isActive = ref(false)

// ✅ 正确 - reactive 用于对象
const formData = reactive({
  username: '',
  email: '',
  age: 0
})

// ✅ 正确 - computed 用于派生状态
const doubleCount = computed(() => count.value * 2)
const isValid = computed(() => formData.username.length > 0)

// ❌ 错误 - 对基础类型使用 reactive
const count = reactive(0) // 会失去响应性

// ❌ 错误 - 解构 reactive 对象
const { username } = formData // 失去响应性
const { username } = toRefs(formData) // ✅ 正确
</script>
```

### storeToRefs 使用

```vue
<script setup>
import { storeToRefs } from 'pinia'
import { useAiModelSuiteStore } from '@/store'

const store = useAiModelSuiteStore()

// ✅ 正确 - 使用 storeToRefs 解构响应式状态
const { models, loading } = storeToRefs(store)

// ✅ 正确 - 直接解构 actions
const { loadModels, syncModel } = store

// ❌ 错误 - 直接解构 state 会失去响应性
const { models, loading } = store
</script>
```

### computed 最佳实践

```vue
<script setup>
// ✅ 正确 - computed 只用于计算，无副作用
const totalEndpoints = computed(() => models.value.length)
const activeCount = computed(() =>
  models.value.filter(item => item.is_active).length
)

// ❌ 错误 - 在 computed 中产生副作用
const totalEndpoints = computed(() => {
  console.log('计算中...') // 副作用
  store.updateCount(models.value.length) // 副作用
  return models.value.length
})

// ✅ 正确 - 使用 watch 处理副作用
watch(() => models.value.length, (newCount) => {
  console.log('数量变化:', newCount)
  store.updateCount(newCount)
})
</script>
```

---

## 生命周期管理

### 资源清理

```vue
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

// ✅ 正确 - 及时清理定时器、监听器
const timer = ref(null)

onMounted(() => {
  timer.value = setInterval(() => {
    console.log('轮询中...')
  }, 5000)

  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  // 清理定时器
  if (timer.value) {
    clearInterval(timer.value)
    timer.value = null
  }

  // 移除事件监听
  window.removeEventListener('resize', handleResize)
})

// ❌ 错误 - 不清理资源
onMounted(() => {
  setInterval(() => {
    console.log('轮询中...') // 内存泄漏
  }, 5000)
})
</script>
```

### 数据加载最佳实践

```vue
<script setup>
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'

const store = useAiModelSuiteStore()
const { models, loading } = storeToRefs(store)

// ✅ 正确 - 避免重复加载
onMounted(() => {
  if (!models.value.length) {
    store.loadModels()
  }
})

// ❌ 错误 - 每次挂载都加载
onMounted(() => {
  store.loadModels() // 可能重复请求
})
</script>
```

---

## 常见陷阱和反模式

### 1. JSX 语法混入 Vue 模板

**问题**: 在 `.vue` 文件的 `<template>` 中使用 JSX 语法会导致编译错误。

```vue
<!-- ❌ 错误 - JSX 语法 -->
<template>
  <NButton onClick={handleClick}>点击</NButton>
  <div className="container">内容</div>
</template>

<!-- ✅ 正确 - Vue 模板语法 -->
<template>
  <NButton @click="handleClick">点击</NButton>
  <div class="container">内容</div>
</template>
```

### 2. v-if 和 v-for 同时使用

```vue
<!-- ❌ 错误 - v-if 和 v-for 同级 -->
<div v-for="item in items" :key="item.id" v-if="item.isActive">
  {{ item.name }}
</div>

<!-- ✅ 正确 - 使用 computed 过滤 -->
<script setup>
const activeItems = computed(() =>
  items.value.filter(item => item.isActive)
)
</script>

<template>
  <div v-for="item in activeItems" :key="item.id">
    {{ item.name }}
  </div>
</template>

<!-- ✅ 正确 - 使用嵌套 template -->
<template v-for="item in items" :key="item.id">
  <div v-if="item.isActive">
    {{ item.name }}
  </div>
</template>
```

### 3. 直接修改 props

```vue
<script setup>
const props = defineProps({
  modelValue: String
})

// ❌ 错误 - 直接修改 props
function updateValue(val) {
  props.modelValue = val // 警告：不应修改 props
}

// ✅ 正确 - 使用 emit
const emit = defineEmits(['update:modelValue'])

function updateValue(val) {
  emit('update:modelValue', val)
}
</script>
```

### 4. 异步操作缺少错误处理

```vue
<script setup>
// ❌ 错误 - 无错误处理
async function loadData() {
  const data = await api.fetchData()
  state.data = data
}

// ✅ 正确 - 完整错误处理
async function loadData() {
  try {
    loading.value = true
    const data = await api.fetchData()
    state.data = data
  } catch (error) {
    console.error('加载失败:', error)
    window.$message?.error(error.message || '加载失败')
  } finally {
    loading.value = false
  }
}
</script>
```

### 5. watch 使用不当

```vue
<script setup>
// ❌ 错误 - 监听整个 reactive 对象
watch(formData, (newVal) => {
  console.log('变化了', newVal)
})

// ✅ 正确 - 监听特定属性
watch(() => formData.username, (newVal, oldVal) => {
  console.log('用户名变化:', oldVal, '->', newVal)
})

// ✅ 正确 - 深度监听对象
watch(formData, (newVal) => {
  console.log('formData 变化了')
}, { deep: true })

// ✅ 正确 - 立即执行
watch(() => route.params.id, (id) => {
  loadData(id)
}, { immediate: true })
</script>
```

---

## Naive UI 组件使用规范

### 属性绑定

Naive UI 组件使用 `v-model:[prop]` 格式进行双向绑定：

```vue
<template>
  <!-- ✅ 正确 - v-model 绑定 -->
  <NInput v-model:value="formData.username" />
  <NCheckbox v-model:checked="formData.agree" />
  <NSelect v-model:value="formData.category" :options="options" />
  <NSwitch v-model:value="formData.enabled" />

  <!-- ❌ 错误 - JSX 风格 -->
  <NInput value={formData.username} onUpdateValue={handleUpdate} />
  <NCheckbox checked={formData.agree} onUpdateChecked={handleCheck} />
</template>
```

### 事件处理

```vue
<template>
  <!-- ✅ 正确 - @ 符号绑定事件 -->
  <NButton @click="handleClick">点击</NButton>
  <NInput @update:value="handleInput" />
  <NSelect @update:value="handleSelect" />

  <!-- ❌ 错误 - JSX 风格 -->
  <NButton onClick={handleClick}>点击</NButton>
  <NInput onUpdateValue={handleInput} />
</template>
```

### 插槽使用

```vue
<template>
  <!-- ✅ 正确 - template 标签定义插槽 -->
  <NButton type="primary">
    <template #icon>
      <span>📦</span>
    </template>
    按钮文字
  </NButton>

  <NTooltip>
    <template #trigger>
      <span>悬停查看</span>
    </template>
    <div>提示内容</div>
  </NTooltip>

  <NTable>
    <template #empty>
      <NEmpty description="暂无数据" />
    </template>
  </NTable>
</template>
```

### 条件属性绑定

```vue
<template>
  <!-- ✅ 正确 - 三元表达式 -->
  <NTag :type="item.status === 'online' ? 'success' : 'error'">
    {{ item.status }}
  </NTag>

  <!-- ✅ 正确 - 复杂逻辑使用 computed -->
  <NTag :type="getStatusType(item.status)">
    {{ item.status }}
  </NTag>
</template>

<script setup>
const getStatusType = (status) => {
  const typeMap = {
    online: 'success',
    offline: 'error',
    checking: 'warning'
  }
  return typeMap[status] || 'default'
}
</script>
```

### 表格渲染

```vue
<template>
  <NTable :single-line="false" size="small" striped>
    <thead>
      <tr>
        <th>ID</th>
        <th>名称</th>
        <th>状态</th>
      </tr>
    </thead>
    <tbody>
      <!-- ✅ 正确 - v-for 渲染行 -->
      <tr v-for="item in tableData" :key="item.id">
        <td>{{ item.id }}</td>
        <td>{{ item.name }}</td>
        <td>
          <NTag :type="item.status === 'active' ? 'success' : 'default'">
            {{ item.status }}
          </NTag>
        </td>
      </tr>

      <!-- ✅ 正确 - 空状态处理 -->
      <tr v-if="!tableData.length">
        <td colspan="3" class="text-center">
          <NEmpty description="暂无数据" />
        </td>
      </tr>
    </tbody>
  </NTable>
</template>
```

---

## 代码审查检查清单

### 模板语法检查

- [ ] 确认没有使用 JSX 语法（`className`、`onClick`、`{}`）
- [ ] 正确使用 `v-model:value` 而非 `value={}`
- [ ] 事件使用 `@click` 而非 `onClick`
- [ ] 插槽使用 `<template #name>` 而非 JSX 插槽
- [ ] 条件渲染使用 `v-if` 而非 `{condition && <div>}`
- [ ] 列表渲染使用 `v-for` 而非 `.map()`

### 组件开发检查

- [ ] 使用 `<script setup>` 语法
- [ ] 使用 `defineOptions` 定义组件名（PascalCase）
- [ ] 按需导入 Naive UI 组件
- [ ] 正确使用 `ref`（基础类型）和 `reactive`（对象）
- [ ] 使用 `storeToRefs` 解构 Pinia state
- [ ] `computed` 无副作用
- [ ] 避免 `v-if` 和 `v-for` 同级使用

### 生命周期检查

- [ ] 定时器在 `onBeforeUnmount` 中清理
- [ ] 事件监听器在组件卸载时移除
- [ ] 避免重复加载数据（检查缓存）
- [ ] 异步操作有完整的 try-catch 错误处理

### 性能和可维护性

- [ ] 复杂逻辑提取为 computed 或方法
- [ ] 避免在模板中使用复杂表达式
- [ ] 使用 `:key` 优化列表渲染
- [ ] 大列表考虑虚拟滚动
- [ ] 合理使用 `v-show`（频繁切换）和 `v-if`（条件渲染）

---

## 参考资源

- [Vue 3 官方文档 - 模板语法](https://vuejs.org/guide/essentials/template-syntax.html)
- [Vue 3 官方文档 - Composition API](https://vuejs.org/guide/extras/composition-api-faq.html)
- [Naive UI 官方文档](https://www.naiveui.com/)
- [Vue 3 风格指南](https://vuejs.org/style-guide/)
- [Pinia 官方文档](https://pinia.vuejs.org/)

---

**最后更新**: 2025-01-10
**维护者**: GymBro 开发团队
