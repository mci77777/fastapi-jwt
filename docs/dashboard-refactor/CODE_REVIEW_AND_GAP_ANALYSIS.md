# Dashboard 重构 - 代码审查与差距分析

**文档版本**: v2.0  
**最后更新**: 2025-01-12 | **变更**: 基于核心功能缺失诊断重写  
**状态**: 待实施

---

## 📋 文档目的

本文档基于 **Dashboard 核心功能缺失诊断报告**，分析现有代码与目标功能的差距，包括：
- LSP 扫描清单（可复用组件）
- 缺失功能清单（5 大核心功能）
- 影响面扫描（新增/修改文件）
- 依赖层级图（4 层依赖关系）
- 潜在风险点

---

## 🔍 LSP 扫描清单（可复用组件）

### 1. 模型切换组件

**位置**：`web/src/views/ai/model-suite/catalog/index.vue`

**现有功能**：
- ✅ 模型列表展示（表格形式）
- ✅ 设为默认模型（`setDefaultModel()` 方法）
- ✅ 同步模型到 Supabase
- ✅ 状态管理（`useAiModelSuiteStore`）

**可复用逻辑**：
```vue
<!-- catalog/index.vue 第 120-135 行 -->
<n-button @click="handleSetDefault(row)">设为默认</n-button>

<script setup>
const store = useAiModelSuiteStore()

async function handleSetDefault(model) {
  await store.setDefaultModel(model)
  window.$message.success('已设为默认模型')
  await store.loadModels()
}
</script>
```

**提取方案**：
- 创建 `ModelSwitcher.vue` 组件
- 复用 `useAiModelSuiteStore` 状态管理
- 复用 `setDefaultModel()` 方法
- 简化 UI 为下拉选择器（而非表格）

---

### 2. Prompt 选择器

**位置**：`web/src/views/ai/model-suite/mapping/index.vue`

**现有功能**：
- ✅ Prompt 下拉选择（第 54-56 行）
- ✅ Prompt 列表获取（`fetchPrompts()` API）

**可复用逻辑**：
```vue
<!-- mapping/index.vue 第 54-56 行 -->
<n-select
  v-model:value="formData.prompt_id"
  :options="promptOptions"
  placeholder="选择 Prompt"
/>

<script setup>
const promptOptions = ref([])

async function loadPrompts() {
  const res = await fetchPrompts()
  promptOptions.value = res.data.map(p => ({
    label: p.name,
    value: p.id
  }))
}
</script>
```

**提取方案**：
- 创建 `PromptSelector.vue` 组件
- 复用 `fetchPrompts()` API
- 添加"设为激活"功能（调用 `PUT /api/v1/llm/prompts`）
- 添加 Tools 启用/禁用开关

---

### 3. Supabase 状态卡片

**位置**：`web/src/views/system/ai/index.vue`

**现有功能**：
- ✅ Supabase 连接状态显示（第 257-267 行）
- ✅ 状态轮询（`loadSupabaseStatus()` 方法）

**可复用逻辑**：
```vue
<!-- system/ai/index.vue 第 257-267 行 -->
<n-card title="Supabase 连接状态">
  <n-tag :type="supabaseStatus.connected ? 'success' : 'error'">
    {{ supabaseStatus.connected ? '在线' : '离线' }}
  </n-tag>
  <p>延迟: {{ supabaseStatus.latency_ms }} ms</p>
  <p>最近同步: {{ supabaseStatus.last_sync_at }}</p>
</n-card>

<script setup>
const supabaseStatus = ref({})

async function loadSupabaseStatus() {
  const res = await getSupabaseStatus()
  supabaseStatus.value = res.data
}
</script>
```

**提取方案**：
- 创建 `SupabaseStatusCard.vue` 组件
- 复用 `getSupabaseStatus()` API
- 添加自动刷新（每 30 秒）

---

### 4. 端点监控状态

**位置**：`web/src/views/system/ai/index.vue`

**现有功能**：
- ✅ 监控任务状态显示（第 269-287 行）
- ✅ 启动/停止监控按钮
- ✅ 端点列表展示

**可复用逻辑**：
```vue
<!-- system/ai/index.vue 第 269-287 行 -->
<n-card title="端点监控">
  <n-space>
    <n-button @click="handleStartMonitor">启动监控</n-button>
    <n-button @click="handleStopMonitor">停止监控</n-button>
  </n-space>
  
  <n-table :data="endpoints">
    <n-table-column prop="name" label="名称" />
    <n-table-column prop="status" label="状态" />
    <n-table-column prop="latency_ms" label="延迟" />
  </n-table>
</n-card>

<script setup>
async function handleStartMonitor() {
  await startMonitor(60)
  window.$message.success('监控已启动')
}

async function handleStopMonitor() {
  await stopMonitor()
  window.$message.success('监控已停止')
}
</script>
```

**提取方案**：
- 创建 `ApiConnectivityModal.vue` 组件
- 复用 `startMonitor()` 和 `stopMonitor()` API
- 复用端点列表展示逻辑
- 改为 Modal 弹窗形式（而非内嵌卡片）

---

## 📊 缺失功能清单（5 大核心功能）

### 1. 导航枢纽功能

**状态**：❌ **未实现**

**现有代码**：
- 后端菜单配置：`app/api/v1/base.py` (第183-278行) ✅ 已有完整菜单结构
- 前端 Dashboard：`web/src/views/dashboard/index.vue` ✅ 组件存在

**缺失内容**：
- ❌ Dashboard 页面**没有任何跳转链接**到配置页面
- ❌ 缺少"快速访问"卡片或按钮组
- ❌ 缺少配置总览面板（应显示当前激活的模型、Prompt、API 供应商等）
- ❌ 缺少导航卡片（跳转到模型目录、模型映射、Prompt 管理、JWT 测试等）

**需要新增**：
- `web/src/components/dashboard/QuickAccessCard.vue` - 快速访问卡片组件
- 在 `web/src/views/dashboard/index.vue` 中集成卡片组

---

### 2. 模型切换功能

**状态**：⚠️ **部分实现（但未集成到 Dashboard）**

**现有代码**：
- 模型列表 API：`app/api/v1/llm_models.py` ✅ 完整 CRUD
- 模型切换 UI：`web/src/views/ai/model-suite/catalog/index.vue` ✅ 存在
- 状态管理：`web/src/store/modules/aiModelSuite.js` ✅ 包含 `setDefaultModel()` 方法

**缺失内容**：
- ❌ Dashboard 上**没有模型切换组件**
- ❌ 缺少"当前激活模型"显示
- ❌ 缺少快速切换下拉菜单或弹窗
- ❌ 切换后未在 Dashboard 上实时反馈

**需要新增**：
- `web/src/components/dashboard/ModelSwitcher.vue` - 模型切换器组件
- 在 `web/src/views/dashboard/index.vue` 中集成切换器

---

### 3. Prompt 与 Tools 管理功能

**状态**：⚠️ **部分实现（但未集成到 Dashboard）**

**现有代码**：
- Prompt CRUD API：`app/api/v1/llm_prompts.py` ✅ 完整实现
- Prompt 管理 UI：`web/src/views/system/ai/prompt/index.vue` ✅ 存在
- Tools JSON 字段：`ai_prompts.tools_json` ✅ 数据库支持

**缺失内容**：
- ❌ Dashboard 上**没有 Prompt 切换功能**
- ❌ 缺少"当前激活 Prompt"显示
- ❌ 缺少 Tools 启用/禁用控制
- ❌ 缺少 Prompt 预览面板

**需要新增**：
- `web/src/components/dashboard/PromptSelector.vue` - Prompt 选择器组件
- 在 `web/src/views/dashboard/index.vue` 中集成选择器

---

### 4. API 供应商与模型映射控制功能

**状态**：⚠️ **部分实现（但未集成到 Dashboard）**

**现有代码**：
- API 供应商监控：`app/services/monitor_service.py::EndpointMonitor` ✅ 完整实现
- 模型映射 API：`app/api/v1/llm_mappings.py` ✅ 完整 CRUD
- 映射管理 UI：`web/src/views/ai/model-suite/mapping/index.vue` ✅ 存在
- API 连通性统计：`app/api/v1/dashboard.py::get_api_connectivity()` ✅ 已实现

**缺失内容**：
- ❌ Dashboard 上**只显示连通性数字**（如 "3/5"），但**无法查看详情**
- ❌ 缺少 API 供应商列表（在线/离线、延迟、配额）
- ❌ 缺少模型映射关系的可视化展示
- ❌ 缺少映射编辑入口

**需要新增**：
- `web/src/components/dashboard/ApiConnectivityModal.vue` - API 连通性详情弹窗
- 在 `web/src/views/dashboard/index.vue` 中集成弹窗触发器

---

### 5. 系统状态监控功能

#### 5.1 Supabase 连接状态

**状态**：⚠️ **部分实现（但未集成到 Dashboard）**

**现有代码**：
- Supabase 健康检查：`app/services/ai_config_service.py::supabase_status()` ✅ 已实现
- API 端点：`app/api/v1/llm_models.py::get_supabase_status()` ✅ 已实现

**缺失内容**：
- ❌ Dashboard 上**没有 Supabase 状态显示**
- ❌ 缺少连接健康度指示器（在线/离线、延迟）
- ❌ 缺少最近同步时间显示

**需要新增**：
- `web/src/components/dashboard/SupabaseStatusCard.vue` - Supabase 状态卡片
- 在 `web/src/views/dashboard/index.vue` 中集成卡片

#### 5.2 服务器负载监控

**状态**：❌ **未实现**

**现有代码**：
- Prometheus 指标：`app/api/v1/metrics.py` ✅ 导出指标
- 指标类型：`auth_requests_total`, `active_connections`, `rate_limit_blocks_total` ✅ 已采集

**缺失内容**：
- ❌ Dashboard 上**没有服务器负载显示**
- ❌ 缺少 CPU、内存使用率监控
- ❌ 缺少请求数/QPS 图表
- ❌ 缺少 Prometheus 指标解析和展示

**需要新增**：
- `web/src/components/dashboard/ServerLoadCard.vue` - 服务器负载卡片
- `web/src/api/dashboard.js::parsePrometheusMetrics()` - Prometheus 指标解析函数
- 在 `web/src/views/dashboard/index.vue` 中集成卡片

---

## 📁 影响面扫描（新增/修改文件）

### 新增文件（6 个组件 + 1 个 API 文件）

#### 前端组件（P0 优先级）
1. `web/src/components/dashboard/QuickAccessCard.vue` - 快速访问卡片
2. `web/src/components/dashboard/ModelSwitcher.vue` - 模型切换器
3. `web/src/components/dashboard/ApiConnectivityModal.vue` - API 连通性详情弹窗

#### 前端组件（P1 优先级）
4. `web/src/components/dashboard/PromptSelector.vue` - Prompt 选择器
5. `web/src/components/dashboard/SupabaseStatusCard.vue` - Supabase 状态卡片
6. `web/src/components/dashboard/ServerLoadCard.vue` - 服务器负载卡片

#### API 封装
7. `web/src/api/dashboard.js` - Dashboard 专用 API 封装（如果不存在）

---

### 修改文件（1 个）

#### 主 Dashboard 页面
- `web/src/views/dashboard/index.vue` - 集成所有新增组件

**修改内容**：
```vue
<template>
  <div class="dashboard-container">
    <!-- 现有组件 -->
    <StatsBanner :stats="stats" :loading="statsLoading" @stat-click="handleStatClick" />

    <!-- 新增：快速访问卡片组 -->
    <div class="quick-access-section">
      <QuickAccessCard
        v-for="card in quickAccessCards"
        :key="card.path"
        :icon="card.icon"
        :title="card.title"
        :description="card.description"
        :path="card.path"
        :badge="card.badge"
      />
    </div>

    <!-- 新增：当前配置面板 -->
    <div class="config-panel">
      <ModelSwitcher :compact="false" />
      <PromptSelector :compact="false" />
      <SupabaseStatusCard />
    </div>

    <!-- 现有组件 -->
    <div class="dashboard-main">
      <LogWindow :logs="logs" :loading="logsLoading" />
      <UserActivityChart :time-range="chartTimeRange" :data="chartData" />
    </div>

    <!-- 新增：服务器负载卡片 -->
    <ServerLoadCard />

    <!-- 新增：API 连通性详情弹窗 -->
    <ApiConnectivityModal v-model:show="showApiModal" />
  </div>
</template>

<script setup>
import QuickAccessCard from '@/components/dashboard/QuickAccessCard.vue'
import ModelSwitcher from '@/components/dashboard/ModelSwitcher.vue'
import PromptSelector from '@/components/dashboard/PromptSelector.vue'
import ApiConnectivityModal from '@/components/dashboard/ApiConnectivityModal.vue'
import SupabaseStatusCard from '@/components/dashboard/SupabaseStatusCard.vue'
import ServerLoadCard from '@/components/dashboard/ServerLoadCard.vue'

const quickAccessCards = [
  { icon: 'mdi:robot', title: '模型目录', description: '查看和管理 AI 模型', path: '/ai/catalog' },
  { icon: 'mdi:map', title: '模型映射', description: '配置模型映射关系', path: '/ai/mapping' },
  { icon: 'mdi:text-box', title: 'Prompt 管理', description: '管理 Prompt 模板', path: '/system/ai/prompt' },
  { icon: 'mdi:key', title: 'JWT 测试', description: '测试 JWT 认证', path: '/ai/jwt' },
  { icon: 'mdi:cog', title: 'API 配置', description: '配置 API 供应商', path: '/system/ai' },
  { icon: 'mdi:file-document', title: '审计日志', description: '查看系统日志', path: '/dashboard/logs' }
]

const showApiModal = ref(false)

function handleStatClick(statType) {
  if (statType === 'api_connectivity') {
    showApiModal.value = true
  }
}
</script>
```

---

## 🌲 依赖层级图（4 层依赖关系）

### 第 1 层：Dashboard 主页面
```
web/src/views/dashboard/index.vue
  ├─ 集成所有新增组件
  ├─ 处理组件间交互（如点击统计卡片弹出详情）
  └─ 管理全局状态（如弹窗显示/隐藏）
```

### 第 2 层：Dashboard 组件
```
web/src/components/dashboard/
  ├─ QuickAccessCard.vue（导航卡片）
  ├─ ModelSwitcher.vue（模型切换器）
  ├─ PromptSelector.vue（Prompt 选择器）
  ├─ ApiConnectivityModal.vue（API 详情弹窗）
  ├─ SupabaseStatusCard.vue（Supabase 状态卡片）
  └─ ServerLoadCard.vue（服务器负载卡片）
```

### 第 3 层：API 调用与状态管理
```
web/src/api/dashboard.js
  ├─ getModels() → 调用 /api/v1/llm/models
  ├─ setDefaultModel() → 调用 PUT /api/v1/llm/models
  ├─ getPrompts() → 调用 /api/v1/llm/prompts
  ├─ setActivePrompt() → 调用 PUT /api/v1/llm/prompts
  ├─ getMonitorStatus() → 调用 /api/v1/llm/monitor/status
  ├─ startMonitor() → 调用 POST /api/v1/llm/monitor/start
  ├─ stopMonitor() → 调用 POST /api/v1/llm/monitor/stop
  ├─ getSupabaseStatus() → 调用 /api/v1/llm/status/supabase
  └─ getSystemMetrics() → 调用 /api/v1/metrics

web/src/store/modules/aiModelSuite.js
  ├─ loadModels() - 加载模型列表
  ├─ setDefaultModel() - 设置默认模型
  └─ syncAll() - 同步所有模型
```

### 第 4 层：后端 API 端点（已实现，无需变更）
```
app/api/v1/
  ├─ llm_models.py
  │   ├─ GET /llm/models - 获取模型列表
  │   ├─ PUT /llm/models - 更新模型（设置默认）
  │   ├─ GET /llm/monitor/status - 监控状态
  │   ├─ POST /llm/monitor/start - 启动监控
  │   ├─ POST /llm/monitor/stop - 停止监控
  │   └─ GET /llm/status/supabase - Supabase 状态
  ├─ llm_prompts.py
  │   ├─ GET /llm/prompts - 获取 Prompt 列表
  │   └─ PUT /llm/prompts - 更新 Prompt（设置激活）
  └─ metrics.py
      └─ GET /metrics - Prometheus 指标导出
```

**停止条件**：第 4 层已触达稳定接口（FastAPI 路由 + 服务层），无需继续展开。

**总展开符号**：约 42 个（未超过 60 个限制）。

---

## ⚠️ 潜在风险点

### 风险 1：组件提取失败

**风险等级**：低
**影响**：无法复用现有逻辑，需要重新实现

**缓释方案**：
- 逐步提取，先复制后重构
- 保留原有组件，新组件独立开发
- 使用 Composition API 提取可复用逻辑（如 `useModelSwitcher.js`）

---

### 风险 2：API 调用失败

**风险等级**：低
**影响**：组件无法获取数据

**缓释方案**：
- 复用现有 API，已验证可用
- 添加错误处理和重试机制
- 使用 Mock 数据进行开发和测试

---

### 风险 3：状态同步问题

**风险等级**：低
**影响**：模型切换后 Dashboard 未更新

**缓释方案**：
- 使用 Pinia store 统一管理状态
- 组件间通过 `watch` 监听状态变化
- 切换后手动触发 Dashboard 刷新

---

### 风险 4：性能问题

**风险等级**：低
**影响**：Dashboard 加载缓慢

**缓释方案**：
- 复用现有 WebSocket 推送，无额外负载
- 使用懒加载（Lazy Load）加载非关键组件
- 使用虚拟滚动（Virtual Scroll）优化长列表

---

### 风险 5：UI 一致性问题

**风险等级**：低
**影响**：新组件与现有组件风格不一致

**缓释方案**：
- 严格遵循 Naive UI 设计规范
- 复用现有组件的样式变量（如颜色、间距）
- 使用 `CommonPage.vue` 作为容器，保持布局一致

---

## 📋 总结

### 核心发现

**问题本质**：Dashboard 不是数据展示问题，而是**缺少核心控制功能**。

**现有实现**：
- ✅ 统计数据采集（日活、AI 请求、API 连通性、JWT 可获取性）
- ✅ WebSocket 实时推送
- ✅ Log 小窗
- ✅ 用户活跃度图表
- ✅ 后端 API 端点（模型、Prompt、监控、Supabase 状态、Prometheus 指标）

**缺失功能**：
- ❌ 导航枢纽（快速访问卡片）
- ❌ 模型切换控制
- ❌ Prompt/Tools 管理
- ❌ API 供应商详情面板
- ❌ Supabase 连接状态显示
- ❌ 服务器负载监控

---

### 实施路径

#### 阶段 1（P0）：核心控制功能
1. **QuickAccessCard.vue** - 导航枢纽
2. **ModelSwitcher.vue** - 模型切换
3. **ApiConnectivityModal.vue** - API 详情面板

**验收标准**：
- ✅ 点击卡片跳转到配置页面
- ✅ 模型切换后 Dashboard 实时更新
- ✅ API 详情弹窗显示所有端点状态

#### 阶段 2（P1）：增强功能
4. **PromptSelector.vue** - Prompt 管理
5. **SupabaseStatusCard.vue** - Supabase 状态
6. **ServerLoadCard.vue** - 服务器负载

**验收标准**：
- ✅ Prompt 切换后 Dashboard 实时更新
- ✅ Supabase 状态显示在线/离线、延迟
- ✅ 服务器负载显示请求数、错误率、连接数

---

**文档版本**: v2.0
**最后更新**: 2025-01-12
**变更**: 基于核心功能缺失诊断重写
**状态**: 待实施

