# Dashboard 模型管理与监控功能增强 - 交接文档

## 📋 任务概述

**目标**：完善 Dashboard 页面，新增模型映射管理、优化模型切换器联动逻辑、增强 Prompt 选择器分类功能。

**完成时间**：2025-01-14  
**状态**：✅ 已完成

---

## 🎯 核心功能

### 1. Model Mapping 管理模块（新增）

**组件路径**：`web/src/components/dashboard/ModelMappingCard.vue`

**功能说明**：
- 展示 API 供应商到标准模型名称的映射关系
- 支持新增、查看、删除映射配置
- 映射关系：`API 供应商模型名称` → `标准模型名称（自定义）`
- 示例：`gpt-4-turbo` → `GPT-5`, `claude-3-opus` → `Claude`

**后端 API**：
- `GET /api/v1/llm/model-groups` - 获取所有映射
- `POST /api/v1/llm/model-groups` - 创建映射
- `POST /api/v1/llm/model-groups/{id}/activate` - 激活默认模型

**前端实现**：
- 使用 Naive UI 的 `n-data-table` 展示映射列表
- 支持弹窗新增映射（业务域类型、标识、名称、默认模型、候选模型）
- 显示字段：业务域、对象、默认模型、候选模型、操作按钮

**使用示例**：
```vue
<ModelMappingCard @mapping-change="handleMappingChange" />
```

**数据结构**：
```javascript
{
  id: "prompt_123",
  scope_type: "tenant",
  scope_key: "1",
  name: "GPT-5",
  default_model: "gpt-4-turbo",
  candidates: ["gpt-4-turbo", "gpt-4-fast-reasoning"],
  is_active: true,
  updated_at: "2025-01-14T12:00:00Z",
  source: "supabase"
}
```

---

### 2. Model Switcher 优化（修改现有组件）

**组件路径**：`web/src/components/dashboard/ModelSwitcher.vue`

**优化内容**：
1. **联动 Model Mapping 数据**：
   - 从 `mappings` 数据生成标准模型名称选项
   - 显示格式：`标准模型名称 (API 供应商模型名称)`
   - 示例：`GPT-5 (gpt-4-turbo)`

2. **实时匹配**：
   - 使用 `watch` 监听 `mappings` 数据变化
   - 自动刷新 Model Switcher 选项
   - 如果当前选中的模型不在新选项中，自动重置为默认模型

3. **回退机制**：
   - 如果 Model Mapping 数据为空，回退到原始模型列表
   - 确保组件在任何情况下都能正常工作

**关键代码**：
```javascript
// 标准模型名称映射（从 Model Mapping 数据生成）
const standardModelMap = computed(() => {
  const map = new Map()
  
  mappings.value.forEach((mapping) => {
    if (mapping.default_model && mapping.candidates && mapping.candidates.length > 0) {
      const standardName = mapping.name || mapping.default_model
      const apiModel = mapping.default_model
      
      const modelObj = models.value.find((m) => m.model === apiModel || m.name === apiModel)
      if (modelObj) {
        map.set(standardName, {
          standardName,
          apiModel,
          modelId: modelObj.id,
          modelObj,
        })
      }
    }
  })
  
  return map
})

// 模型选项（优先使用标准模型名称）
const modelOptions = computed(() => {
  if (standardModelMap.value.size > 0) {
    return Array.from(standardModelMap.value.values()).map((item) => ({
      label: `${item.standardName} (${item.apiModel})`,
      value: item.modelId,
      disabled: !item.modelObj.is_active,
    }))
  }
  
  // 回退到原始模型列表
  return models.value.map((model) => ({
    label: `${model.model || model.name} (${model.provider || 'Unknown'})`,
    value: model.id,
    disabled: !model.is_active,
  }))
})
```

---

### 3. Prompt Selector 增强（修改现有组件）

**组件路径**：`web/src/components/dashboard/PromptSelector.vue`

**增强内容**：
1. **添加 Tabs 分类**：
   - System Prompts：系统级提示词模板
   - Tools Prompts：工具调用提示词模板

2. **分类逻辑**：
   - 基于 `tools_json` 字段判断类型
   - 如果 `tools_json` 存在且非空，认为是 Tools Prompt
   - 否则认为是 System Prompt

3. **UI 改进**：
   - 使用 `n-tabs` 组件分隔两个类别
   - 每个 Tab 内独立的 `n-select` 选择器
   - 显示当前 Prompt 的类型标签

**关键代码**：
```javascript
function getPromptType(prompt) {
  if (!prompt) return null
  if (prompt.tools_json && Object.keys(prompt.tools_json).length > 0) {
    return 'tools'
  }
  return 'system'
}

const systemPromptOptions = computed(() => {
  return prompts.value
    .filter((p) => getPromptType(p) === 'system')
    .map((prompt) => ({
      label: prompt.name,
      value: prompt.id,
    }))
})

const toolsPromptOptions = computed(() => {
  return prompts.value
    .filter((p) => getPromptType(p) === 'tools')
    .map((prompt) => ({
      label: prompt.name,
      value: prompt.id,
    }))
})
```

---

### 4. API 监控状态模块（已存在，无需修改）

**组件路径**：
- `web/src/components/dashboard/SupabaseStatusCard.vue`
- `web/src/components/dashboard/ServerLoadCard.vue`

**功能说明**：
- Supabase 连接状态：显示在线/离线状态、延迟、最近同步时间
- 服务器负载：显示总请求数、错误率、活跃连接、限流阻止

**后端 API**：
- `GET /api/v1/llm/status/supabase` - Supabase 状态
- `GET /api/v1/llm/monitor/status` - 监控状态
- `GET /api/v1/metrics` - Prometheus 指标

---

## 📐 技术实现细节

### 依赖关系

**Model Switcher** ← **Model Mapping**：
- Model Switcher 的选项来源于 Model Mapping 的数据
- Model Mapping 数据变化时，Model Switcher 自动刷新选项

**数据流**：
1. 用户在 Model Mapping 模块中配置：`gpt-4-turbo` → `GPT-5`
2. Model Switcher 自动显示选项 `GPT-5 (gpt-4-turbo)`
3. 用户选择 `GPT-5` 后，实际调用的是 `gpt-4-turbo` API

### Store 使用

**Pinia Store**：`useAiModelSuiteStore`

**State**：
- `models` - 模型列表
- `modelsLoading` - 模型加载状态
- `mappings` - 模型映射列表
- `mappingsLoading` - 映射加载状态
- `prompts` - Prompt 列表
- `promptsLoading` - Prompt 加载状态

**Actions**：
- `loadModels()` - 加载模型列表
- `loadMappings()` - 加载映射列表
- `saveMapping(payload)` - 保存映射
- `activateMapping(mappingId, defaultModel)` - 激活默认模型
- `loadPrompts()` - 加载 Prompt 列表
- `activatePrompt(promptId)` - 激活 Prompt

---

## 🔗 集成到 Dashboard

**文件路径**：`web/src/views/dashboard/index.vue`

**修改内容**：
1. 导入 `ModelMappingCard` 组件
2. 在模板中添加 `<ModelMappingCard>` 标签
3. 添加 `handleMappingChange` 事件处理函数
4. 添加 CSS 样式 `.dashboard-mapping`

**代码片段**：
```vue
<template>
  <div class="dashboard-container">
    <!-- 现有组件 -->
    <StatsBanner />
    <QuickAccessCard />
    
    <!-- 控制面板 -->
    <div class="dashboard-controls">
      <ModelSwitcher @change="handleModelChange" />
      <PromptSelector @change="handlePromptChange" />
      <SupabaseStatusCard />
      <ServerLoadCard />
    </div>
    
    <!-- 新增：模型映射管理 -->
    <div class="dashboard-mapping">
      <ModelMappingCard @mapping-change="handleMappingChange" />
    </div>
    
    <!-- 现有组件 -->
    <LogWindow />
    <UserActivityChart />
  </div>
</template>

<script setup>
function handleMappingChange(mappings) {
  console.log('[Dashboard] 模型映射已更新，共', mappings.length, '条映射')
  // 映射变化后，ModelSwitcher 会自动刷新选项（通过 watch）
}
</script>

<style scoped>
.dashboard-mapping {
  margin: var(--spacing-md) 0;
}
</style>
```

---

## ✅ 验证清单

- [x] **编译通过**：`pnpm build` 无错误
- [x] **组件导入**：所有新增组件已正确导入
- [x] **API 调用**：使用 `web/src/api/aiModelSuite.js` 封装函数
- [x] **响应式更新**：Model Switcher 监听 mappings 变化
- [x] **错误处理**：API 调用失败时显示友好提示
- [x] **代码规范**：遵循 Vue 3 Composition API 规范（`<script setup>`）
- [x] **样式一致**：使用 Claude 设计系统变量

---

## 🚀 后续优化建议

1. **Model Mapping 删除功能**：
   - 后端需新增 `DELETE /api/v1/llm/model-groups/{id}` API
   - 前端 `ModelMappingCard` 中的删除按钮当前仅为占位

2. **Prompt 类型自动识别**：
   - 当前基于 `tools_json` 字段判断类型
   - 可考虑在后端添加 `prompt_type` 字段，明确标识类型

3. **Model Switcher 性能优化**：
   - 当 mappings 数据量大时，考虑使用虚拟滚动
   - 添加搜索过滤功能

4. **缓存机制**：
   - Model Mapping 数据可缓存到 localStorage
   - 减少频繁 API 调用

---

## 📚 相关文档

- **架构总览**：`docs/archive/dashboard-refactor/ARCHITECTURE_OVERVIEW.md`
- **实现规范**：`docs/archive/dashboard-refactor/IMPLEMENTATION_SPEC.md`
- **Model Mapping 后端实现**：`docs/features/model_management/implementation.md`
- **Vue 最佳实践**：`docs/coding-standards/vue-best-practices.md`

---

**交接完成**  
**文档版本**：v1.0  
**最后更新**：2025-01-14

