# Dashboard 重构 - 分阶段实施计划

**文档版本**: v2.0
**最后更新**: 2025-01-12 | **变更**: 基于核心功能缺失诊断重写
**状态**: 待实施

---

## 📋 总体规划

### 实施周期

**总工期**: 3-4 个工作日
**团队规模**: 1 人
**风险缓冲**: 1 个工作日

**调整说明**:
- 原计划 8-10 天 → 调整为 3-4 天
- **原因**: 无需新增后端 API 和数据库表，只需前端组件开发和集成

---

### 阶段划分

| 阶段 | 名称 | 工期 | 优先级 | 依赖 |
|------|------|------|--------|------|
| Phase 1 | 核心控制功能（P0） | 1.5-2 天 | P0 | 无 |
| Phase 2 | 增强功能（P1） | 1-1.5 天 | P1 | Phase 1 |
| Phase 3 | 可选优化（P2） | 0.5-1 天 | P2 | Phase 2 |

---

## 🔧 Phase 1：核心控制功能（P0 优先级）

### 目标

- ✅ 实现导航枢纽（快速访问卡片）
- ✅ 实现模型切换控制
- ✅ 实现 API 连通性详情面板

**工期**: 1.5-2 天

---

### 任务 1.1：QuickAccessCard.vue - 导航枢纽

**工作量**: 0.5 天

**文件路径**: `web/src/components/dashboard/QuickAccessCard.vue`

**任务清单**:
- [ ] 创建 QuickAccessCard 组件
- [ ] 定义 Props（icon, title, description, path, badge）
- [ ] 实现点击跳转逻辑（使用 Vue Router）
- [ ] 添加 hover 效果和过渡动画
- [ ] 集成到 Dashboard 主页面

**Props 定义**:
```typescript
interface Props {
  icon: string        // Heroicons 图标名称（如 'mdi:robot'）
  title: string       // 卡片标题
  description: string // 卡片描述
  path: string        // 跳转路由路径
  badge?: number      // 可选徽章数字
}
```

**使用示例**:
```vue
<QuickAccessCard
  icon="mdi:robot"
  title="模型目录"
  description="查看和管理 AI 模型"
  path="/ai/catalog"
/>
```

**验收标准**:
- ✅ 点击卡片跳转到对应页面
- ✅ 卡片显示图标、标题、描述
- ✅ hover 时显示阴影效果
- ✅ 支持徽章显示（可选）

**依赖关系**: 无

---

### 任务 1.2：ModelSwitcher.vue - 模型切换器

**工作量**: 0.5 天

**文件路径**: `web/src/components/dashboard/ModelSwitcher.vue`

**任务清单**:
- [ ] 创建 ModelSwitcher 组件
- [ ] 复用 `useAiModelSuiteStore` 状态管理
- [ ] 实现模型列表加载（调用 `loadModels()`）
- [ ] 实现模型切换（调用 `setDefaultModel()`）
- [ ] 添加加载状态和错误处理
- [ ] 集成到 Dashboard 主页面

**复用逻辑**:
```javascript
// 从 catalog/index.vue 提取
import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'

const store = useAiModelSuiteStore()

async function handleModelChange(modelId) {
  await store.setDefaultModel({ id: modelId, is_default: true })
  window.$message.success('模型已切换')
  await store.loadModels()
}
```

**验收标准**:
- ✅ 显示当前激活模型
- ✅ 下拉选择其他模型
- ✅ 切换后 Dashboard 实时更新
- ✅ 显示加载状态和错误提示

**依赖关系**:
- 依赖 `useAiModelSuiteStore`
- 依赖 API: `GET /api/v1/llm/models`, `PUT /api/v1/llm/models`

---

### 任务 1.3：ApiConnectivityModal.vue - API 连通性详情弹窗

**工作量**: 0.5-1 天

**文件路径**: `web/src/components/dashboard/ApiConnectivityModal.vue`

**任务清单**:
- [ ] 创建 ApiConnectivityModal 组件
- [ ] 实现端点列表展示（表格形式）
- [ ] 实现监控控制（启动/停止按钮）
- [ ] 添加实时状态刷新（每 30 秒）
- [ ] 集成到 Dashboard 主页面

**Props 定义**:
```typescript
interface Props {
  show: boolean  // 控制弹窗显示
}

interface Emits {
  (e: 'update:show', value: boolean): void
}
```

**API 调用**:
```javascript
import { getMonitorStatus, startMonitor, stopMonitor } from '@/api/dashboard'

async function handleStartMonitor() {
  await startMonitor(60)  // 60 秒间隔
  window.$message.success('监控已启动')
  await loadMonitorStatus()
}

async function handleStopMonitor() {
  await stopMonitor()
  window.$message.success('监控已停止')
  await loadMonitorStatus()
}
```

**验收标准**:
- ✅ 点击统计卡片弹出详情弹窗
- ✅ 显示所有 API 供应商列表（在线/离线、延迟、最近检测时间）
- ✅ 提供"启动监控"/"停止监控"按钮
- ✅ 监控状态实时更新

**依赖关系**:
- 依赖 API: `GET /api/v1/llm/monitor/status`, `POST /api/v1/llm/monitor/start`, `POST /api/v1/llm/monitor/stop`


---

## 🔧 Phase 2：增强功能（P1 优先级）

### 目标

- ✅ 实现 Prompt 管理控制
- ✅ 实现 Supabase 连接状态显示
- ✅ 实现服务器负载监控

**工期**: 1-1.5 天

---

### 任务 2.1：PromptSelector.vue - Prompt 选择器

**工作量**: 0.5 天

**文件路径**: `web/src/components/dashboard/PromptSelector.vue`

**任务清单**:
- [ ] 创建 PromptSelector 组件
- [ ] 实现 Prompt 列表加载（调用 `fetchPrompts()`）
- [ ] 实现 Prompt 切换（调用 `PUT /api/v1/llm/prompts`）
- [ ] 添加 Tools 启用/禁用开关
- [ ] 集成到 Dashboard 主页面

**API 调用**:
```javascript
import { getPrompts, setActivePrompt } from '@/api/dashboard'

async function handlePromptChange(promptId) {
  await setActivePrompt(promptId)
  window.$message.success('Prompt 已切换')
  await loadPrompts()
}
```

**验收标准**:
- ✅ 显示当前激活 Prompt
- ✅ 下拉选择其他 Prompt
- ✅ 切换后 Dashboard 实时更新
- ✅ 显示 Tools 启用/禁用开关

**依赖关系**:
- 依赖 API: `GET /api/v1/llm/prompts`, `PUT /api/v1/llm/prompts`

---

### 任务 2.2：SupabaseStatusCard.vue - Supabase 状态卡片

**工作量**: 0.25 天

**文件路径**: `web/src/components/dashboard/SupabaseStatusCard.vue`

**任务清单**:
- [ ] 创建 SupabaseStatusCard 组件
- [ ] 实现状态加载（调用 `getSupabaseStatus()`）
- [ ] 添加自动刷新（每 30 秒）
- [ ] 显示连接状态、延迟、最近同步时间
- [ ] 集成到 Dashboard 主页面

**API 调用**:
```javascript
import { getSupabaseStatus } from '@/api/dashboard'

async function loadSupabaseStatus() {
  const res = await getSupabaseStatus()
  supabaseStatus.value = res.data
}

// 自动刷新
onMounted(() => {
  loadSupabaseStatus()
  setInterval(loadSupabaseStatus, 30000)  // 30 秒
})
```

**验收标准**:
- ✅ 显示 Supabase 连接状态（在线/离线）
- ✅ 显示延迟（ms）
- ✅ 显示最近同步时间
- ✅ 每 30 秒自动刷新

**依赖关系**:
- 依赖 API: `GET /api/v1/llm/status/supabase`

---

### 任务 2.3：ServerLoadCard.vue - 服务器负载卡片

**工作量**: 0.5 天

**文件路径**: `web/src/components/dashboard/ServerLoadCard.vue`

**任务清单**:
- [ ] 创建 ServerLoadCard 组件
- [ ] 实现 Prometheus 指标解析（`parsePrometheusMetrics()`）
- [ ] 显示关键指标（总请求数、错误率、活跃连接数、限流阻止数）
- [ ] 使用 NStatistic 或 ECharts 展示
- [ ] 集成到 Dashboard 主页面

**API 调用**:
```javascript
import { getSystemMetrics, parsePrometheusMetrics } from '@/api/dashboard'

async function loadServerLoad() {
  const text = await getSystemMetrics()
  const metrics = parsePrometheusMetrics(text)

  serverLoad.value = {
    totalRequests: metrics['auth_requests_total'] || 0,
    errorRate: calculateErrorRate(metrics),
    activeConnections: metrics['active_connections'] || 0,
    rateLimitBlocks: metrics['rate_limit_blocks_total'] || 0
  }
}

function calculateErrorRate(metrics) {
  const total = metrics['auth_requests_total'] || 0
  const errors = metrics['jwt_validation_errors_total'] || 0
  return total > 0 ? (errors / total * 100).toFixed(2) : 0
}
```

**验收标准**:
- ✅ 解析 Prometheus 指标（`GET /api/v1/metrics`）
- ✅ 显示总请求数、错误率、活跃连接数、限流阻止数
- ✅ 使用 NStatistic 或 ECharts 展示

**依赖关系**:
- 依赖 API: `GET /api/v1/metrics`
- 需要新增 `parsePrometheusMetrics()` 函数

---

## 🔧 Phase 3：可选优化（P2 优先级）

### 目标

- ✅ 实现配置总览面板
- ✅ 实现快速操作栏

**工期**: 0.5-1 天

**状态**: 可选，根据时间和需求决定是否实施

---

### 任务 3.1：ConfigSummaryPanel.vue - 配置总览面板

**工作量**: 0.25 天

**文件路径**: `web/src/components/dashboard/ConfigSummaryPanel.vue`

**功能**: 显示当前系统配置摘要（当前模型、Prompt、API 供应商数量等）

**验收标准**:
- ✅ 显示当前激活模型
- ✅ 显示当前激活 Prompt
- ✅ 显示 API 供应商数量（在线/总数）

---

### 任务 3.2：QuickActionsBar.vue - 快速操作栏

**工作量**: 0.25 天

**文件路径**: `web/src/components/dashboard/QuickActionsBar.vue`

**功能**: 提供常用操作按钮（刷新数据、导出报告、清除缓存等）

**验收标准**:
- ✅ 提供"刷新数据"按钮
- ✅ 提供"导出报告"按钮（可选）
- ✅ 提供"清除缓存"按钮（可选）

---

## 📋 总体验收标准

### Phase 1（P0）验收清单

- [ ] QuickAccessCard 组件完成并集成
- [ ] ModelSwitcher 组件完成并集成
- [ ] ApiConnectivityModal 组件完成并集成
- [ ] Dashboard 主页面集成所有 P0 组件
- [ ] 端到端链路验证（导航、模型切换、API 详情）

### Phase 2（P1）验收清单

- [ ] PromptSelector 组件完成并集成
- [ ] SupabaseStatusCard 组件完成并集成
- [ ] ServerLoadCard 组件完成并集成
- [ ] Dashboard 主页面集成所有 P1 组件
- [ ] 端到端链路验证（Prompt 切换、Supabase 状态、服务器负载）

### Phase 3（P2）验收清单

- [ ] ConfigSummaryPanel 组件完成并集成（可选）
- [ ] QuickActionsBar 组件完成并集成（可选）

---

**文档版本**: v2.0
**最后更新**: 2025-01-12
**变更**: 基于核心功能缺失诊断重写
**状态**: 待实施

