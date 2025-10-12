# Dashboard 重构 - 部署运维指南

**文档版本**: v2.0
**最后更新**: 2025-01-12 | **变更**: 基于核心功能缺失诊断重写
**状态**: 待实施

---

## 📋 目录

1. [前置检查](#1-前置检查)
2. [组件部署顺序](#2-组件部署顺序)
3. [端到端验证](#3-端到端验证)
4. [回滚程序](#4-回滚程序)
5. [故障排查](#5-故障排查)

---

## 1. 前置检查

### 1.1 API 端点可用性验证

**目的**: 确保所有必需的后端 API 端点已实现并可用

**检查清单**:

```bash
# 1. 模型管理 API
curl -X GET http://localhost:9999/api/v1/llm/models \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
# 预期: 返回模型列表，状态码 200

# 2. Prompt 管理 API
curl -X GET http://localhost:9999/api/v1/llm/prompts \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
# 预期: 返回 Prompt 列表，状态码 200

# 3. 监控状态 API
curl -X GET http://localhost:9999/api/v1/llm/monitor/status \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
# 预期: 返回监控状态，状态码 200

# 4. Supabase 状态 API
curl -X GET http://localhost:9999/api/v1/llm/status/supabase \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
# 预期: 返回 Supabase 连接状态，状态码 200

# 5. Prometheus 指标 API
curl -X GET http://localhost:9999/api/v1/metrics
# 预期: 返回 Prometheus 文本格式指标，状态码 200
```

**验收标准**:
- ✅ 所有 API 端点返回状态码 200
- ✅ 响应数据格式符合预期
- ✅ 无 500 或 404 错误

---

### 1.2 前端依赖检查

**目的**: 确保前端项目已安装所有必需的依赖

**检查清单**:

```bash
cd web

# 1. 检查 package.json 中的依赖
cat package.json | grep -E "naive-ui|vue-router|pinia"

# 预期输出:
# "naive-ui": "^2.x.x"
# "vue-router": "^4.x.x"
# "pinia": "^2.x.x"

# 2. 验证依赖已安装
pnpm list naive-ui vue-router pinia

# 预期: 显示已安装的版本号
```

**验收标准**:
- ✅ Naive UI 2.x 已安装
- ✅ Vue Router 4.x 已安装
- ✅ Pinia 2.x 已安装

---

### 1.3 现有组件检查

**目的**: 确保 Dashboard 现有组件正常工作

**检查清单**:

```bash
# 1. 检查现有组件文件是否存在
ls web/src/components/dashboard/StatsBanner.vue
ls web/src/components/dashboard/LogWindow.vue
ls web/src/components/dashboard/UserActivityChart.vue
ls web/src/components/dashboard/WebSocketClient.vue

# 2. 检查 Dashboard 主页面
ls web/src/views/dashboard/index.vue
```

**验收标准**:
- ✅ 所有现有组件文件存在
- ✅ Dashboard 主页面存在
- ✅ 现有组件无编译错误

---

## 2. 组件部署顺序

### 步骤 1：创建 API 封装文件

**文件路径**: `web/src/api/dashboard.js`

**操作**:

```bash
# 创建文件
touch web/src/api/dashboard.js
```

**文件内容**: 参考 `IMPLEMENTATION_SPEC.md` 中的 API 封装规格

**验证**:

```bash
# 检查文件是否创建成功
ls web/src/api/dashboard.js

# 检查语法错误
cd web && pnpm lint web/src/api/dashboard.js
```

**验收标准**:
- ✅ 文件创建成功
- ✅ 无语法错误
- ✅ 导出所有必需的 API 函数

---

### 步骤 2：部署 QuickAccessCard.vue（P0）

**文件路径**: `web/src/components/dashboard/QuickAccessCard.vue`

**操作**:

```bash
# 创建文件
touch web/src/components/dashboard/QuickAccessCard.vue
```

**文件内容**: 参考 `IMPLEMENTATION_SPEC.md` 中的组件规格

**验证**:

```bash
# 检查语法错误
cd web && pnpm lint web/src/components/dashboard/QuickAccessCard.vue

# 启动开发服务器测试
pnpm dev
```

**验收标准**:
- ✅ 组件创建成功
- ✅ 无编译错误
- ✅ 组件可独立渲染

---

### 步骤 3：部署 ModelSwitcher.vue（P0）

**文件路径**: `web/src/components/dashboard/ModelSwitcher.vue`

**操作**:

```bash
# 创建文件
touch web/src/components/dashboard/ModelSwitcher.vue
```

**文件内容**: 参考 `IMPLEMENTATION_SPEC.md` 中的组件规格

**验证**:

```bash
# 检查语法错误
cd web && pnpm lint web/src/components/dashboard/ModelSwitcher.vue
```

**验收标准**:
- ✅ 组件创建成功
- ✅ 无编译错误
- ✅ 可成功调用 `getModels()` API
- ✅ 可成功调用 `setDefaultModel()` API

---

### 步骤 4：部署 ApiConnectivityModal.vue（P0）

**文件路径**: `web/src/components/dashboard/ApiConnectivityModal.vue`

**操作**:

```bash
# 创建文件
touch web/src/components/dashboard/ApiConnectivityModal.vue
```

**文件内容**: 参考 `IMPLEMENTATION_SPEC.md` 中的组件规格

**验证**:

```bash
# 检查语法错误
cd web && pnpm lint web/src/components/dashboard/ApiConnectivityModal.vue
```

**验收标准**:
- ✅ 组件创建成功
- ✅ 无编译错误
- ✅ 可成功调用监控 API
- ✅ 弹窗可正常打开/关闭

---

### 步骤 5-7：部署 P1 组件

**组件清单**:
- `PromptSelector.vue`
- `SupabaseStatusCard.vue`
- `ServerLoadCard.vue`

**操作**: 重复步骤 2-4 的流程

**验收标准**: 参考各组件的 `IMPLEMENTATION_SPEC.md` 规格

---

### 步骤 8：集成到 Dashboard 主页面

**文件路径**: `web/src/views/dashboard/index.vue`

**操作**:

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
        v-bind="card"
      />
    </div>

    <!-- 新增：当前配置面板 -->
    <div class="config-panel">
      <ModelSwitcher />
      <PromptSelector />
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

**验证**:

```bash
# 检查语法错误
cd web && pnpm lint web/src/views/dashboard/index.vue

# 启动开发服务器
pnpm dev

# 访问 http://localhost:3101/dashboard
```

**验收标准**:
- ✅ 所有新增组件正常渲染
- ✅ 无编译错误
- ✅ 无运行时错误

---

## 3. 端到端验证

### 3.1 导航枢纽链路验证

**测试步骤**:

1. 访问 Dashboard 页面：`http://localhost:3101/dashboard`
2. 点击"模型目录"快速访问卡片
3. 验证跳转到 `/ai/catalog` 页面
4. 返回 Dashboard
5. 重复测试其他 5 个快速访问卡片

**验收标准**:
- ✅ 所有卡片可点击
- ✅ 跳转路由正确
- ✅ 无 404 错误

---

### 3.2 模型切换链路验证

**测试步骤**:

1. 在 Dashboard 上找到 ModelSwitcher 组件
2. 打开模型下拉列表
3. 选择一个非默认模型
4. 观察切换结果

**验收标准**:
- ✅ 下拉列表显示所有模型
- ✅ 切换后显示成功提示
- ✅ Dashboard 实时更新显示新模型
- ✅ 后端数据库已更新（`is_default` 字段）

**验证命令**:

```bash
# 查询数据库验证
sqlite3 db.sqlite3 "SELECT id, model, is_default FROM ai_endpoints;"
```

---

### 3.3 API 监控链路验证

**测试步骤**:

1. 点击统计横幅中的"API 连通性"卡片
2. 验证弹窗打开
3. 点击"启动监控"按钮
4. 观察端点列表状态更新
5. 点击"停止监控"按钮

**验收标准**:
- ✅ 弹窗正常打开/关闭
- ✅ 端点列表显示所有 API 供应商
- ✅ 监控启动/停止功能正常
- ✅ 状态实时更新

---

### 3.4 Prompt 切换链路验证

**测试步骤**:

1. 在 Dashboard 上找到 PromptSelector 组件
2. 打开 Prompt 下拉列表
3. 选择一个非激活 Prompt
4. 观察切换结果

**验收标准**:
- ✅ 下拉列表显示所有 Prompt
- ✅ 切换后显示成功提示
- ✅ Dashboard 实时更新显示新 Prompt

---

### 3.5 Supabase 状态验证

**测试步骤**:

1. 在 Dashboard 上找到 SupabaseStatusCard 组件
2. 观察连接状态（在线/离线）
3. 等待 30 秒观察自动刷新

**验收标准**:
- ✅ 显示连接状态
- ✅ 显示延迟（ms）
- ✅ 显示最近同步时间
- ✅ 每 30 秒自动刷新

---

### 3.6 服务器负载验证

**测试步骤**:

1. 在 Dashboard 上找到 ServerLoadCard 组件
2. 观察显示的指标
3. 点击"刷新"按钮
4. 验证数据更新

**验收标准**:
- ✅ 显示总请求数
- ✅ 显示错误率
- ✅ 显示活跃连接数
- ✅ 显示限流阻止数
- ✅ 手动刷新功能正常

---

## 4. 回滚程序


### 4.1 撤销组件集成

**场景**: 新增组件导致 Dashboard 出现问题，需要快速回滚

**操作步骤**:

```bash
# 1. 备份当前 Dashboard 主页面
cp web/src/views/dashboard/index.vue web/src/views/dashboard/index.vue.backup

# 2. 使用 Git 恢复到上一个版本
git checkout HEAD~1 -- web/src/views/dashboard/index.vue

# 3. 重启开发服务器
cd web && pnpm dev
```

**验证**:

```bash
# 访问 Dashboard 验证功能正常
curl http://localhost:3101/dashboard
```

**验收标准**:
- ✅ Dashboard 恢复到旧版本
- ✅ 现有功能正常工作
- ✅ 无编译错误

---

### 4.2 删除新增组件

**场景**: 需要完全移除新增的组件文件

**操作步骤**:

```bash
# 1. 删除新增组件文件
rm web/src/components/dashboard/QuickAccessCard.vue
rm web/src/components/dashboard/ModelSwitcher.vue
rm web/src/components/dashboard/PromptSelector.vue
rm web/src/components/dashboard/ApiConnectivityModal.vue
rm web/src/components/dashboard/SupabaseStatusCard.vue
rm web/src/components/dashboard/ServerLoadCard.vue

# 2. 删除 API 封装文件
rm web/src/api/dashboard.js

# 3. 清理 node_modules 缓存
cd web && rm -rf node_modules/.vite

# 4. 重启开发服务器
pnpm dev
```

**验证**:

```bash
# 检查文件是否已删除
ls web/src/components/dashboard/QuickAccessCard.vue
# 预期: No such file or directory
```

**验收标准**:
- ✅ 所有新增文件已删除
- ✅ Dashboard 恢复到旧版本
- ✅ 无编译错误

---

### 4.3 Git 回滚

**场景**: 使用 Git 回滚到指定提交

**操作步骤**:

```bash
# 1. 查看提交历史
git log --oneline

# 2. 回滚到指定提交（假设提交 hash 为 abc123）
git revert abc123

# 3. 推送回滚提交
git push origin main
```

**验收标准**:
- ✅ 代码回滚到指定版本
- ✅ Git 历史记录清晰
- ✅ 无冲突

---

### 4.4 回滚验证清单

**验证步骤**:

- [ ] Dashboard 页面可正常访问
- [ ] 现有组件（StatsBanner、LogWindow、UserActivityChart）正常工作
- [ ] WebSocket 连接正常
- [ ] 无 JavaScript 错误
- [ ] 无 API 调用失败

---

## 5. 故障排查

### 5.1 组件无法渲染

**症状**: 新增组件在 Dashboard 上不显示

**可能原因**:
1. 组件未正确导入
2. 组件 Props 传递错误
3. 组件内部错误

**排查步骤**:

```bash
# 1. 检查浏览器控制台错误
# 打开浏览器开发者工具 → Console

# 2. 检查组件导入
grep -r "import.*QuickAccessCard" web/src/views/dashboard/index.vue

# 3. 检查组件注册
grep -r "components.*QuickAccessCard" web/src/views/dashboard/index.vue

# 4. 检查 Props 传递
# 在浏览器控制台执行:
# document.querySelector('.quick-access-card')
```

**解决方案**:
- 确保组件正确导入：`import QuickAccessCard from '@/components/dashboard/QuickAccessCard.vue'`
- 确保组件在 `<script setup>` 中可用（Composition API 自动注册）
- 检查 Props 是否正确传递

---

### 5.2 API 调用失败

**症状**: 组件加载时显示错误提示

**可能原因**:
1. API 端点不存在
2. JWT Token 过期
3. 网络请求失败

**排查步骤**:

```bash
# 1. 检查 API 端点是否可用
curl -X GET http://localhost:9999/api/v1/llm/models \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# 2. 检查浏览器 Network 面板
# 打开浏览器开发者工具 → Network → 查看失败的请求

# 3. 检查 JWT Token
# 在浏览器控制台执行:
# localStorage.getItem('token')
```

**解决方案**:
- 确保后端服务正在运行：`python run.py`
- 确保 JWT Token 有效（重新登录获取新 Token）
- 检查 API 路径是否正确

---

### 5.3 组件状态不更新

**症状**: 切换模型/Prompt 后 Dashboard 未更新

**可能原因**:
1. 响应式数据未正确设置
2. 组件未监听状态变化
3. Pinia Store 未正确更新

**排查步骤**:

```bash
# 1. 检查 Pinia Store 状态
# 在浏览器控制台执行:
# import { useAiModelSuiteStore } from '@/store/modules/aiModelSuite'
# const store = useAiModelSuiteStore()
# console.log(store.models)

# 2. 检查组件是否使用 storeToRefs
grep -r "storeToRefs" web/src/components/dashboard/ModelSwitcher.vue
```

**解决方案**:
- 使用 `storeToRefs()` 解构 Store 状态以保持响应性
- 确保组件使用 `ref()` 或 `reactive()` 包装数据
- 在状态变化后手动触发刷新：`await store.loadModels()`

---

### 5.4 Prometheus 指标解析失败

**症状**: ServerLoadCard 显示 0 或错误数据

**可能原因**:
1. Prometheus 指标格式不正确
2. `parsePrometheusMetrics()` 函数有 bug
3. 指标名称不匹配

**排查步骤**:

```bash
# 1. 检查 Prometheus 指标原始数据
curl http://localhost:9999/api/v1/metrics

# 2. 在浏览器控制台测试解析函数
# import { getSystemMetrics, parsePrometheusMetrics } from '@/api/dashboard'
# const text = await getSystemMetrics()
# console.log(parsePrometheusMetrics(text))
```

**解决方案**:
- 确保 Prometheus 指标格式正确（`metric_name value`）
- 检查正则表达式是否匹配指标格式
- 验证指标名称是否正确（如 `auth_requests_total`）

---

### 5.5 自动刷新不工作

**症状**: SupabaseStatusCard 或 ServerLoadCard 不自动刷新

**可能原因**:
1. `setInterval` 未正确设置
2. 组件卸载时未清理定时器
3. `autoRefresh` Props 为 false

**排查步骤**:

```bash
# 1. 检查组件 Props
# 在浏览器控制台执行:
# document.querySelector('.supabase-status-card').__vueParentComponent.props

# 2. 检查定时器是否运行
# 在组件内部添加 console.log
```

**解决方案**:
- 确保 `autoRefresh` Props 为 `true`
- 确保在 `onMounted` 中设置 `setInterval`
- 确保在 `onUnmounted` 中清理定时器：`clearInterval(refreshTimer)`

---

**文档版本**: v2.0
**最后更新**: 2025-01-12
**变更**: 基于核心功能缺失诊断重写
**状态**: 待实施


