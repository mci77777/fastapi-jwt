# Dashboard 重构 Phase 2 Task 2.1 交接文档

**文档版本**: v1.0  
**完成日期**: 2025-10-12  
**实施人员**: AI Assistant  
**状态**: ✅ 已完成并验收

---

## 1. 实施摘要

### 1.1 完成的任务

**Phase 2 Task 2.1: PromptSelector.vue - Prompt 选择器** - ✅ 已完成

实施内容：
- ✅ 创建 `PromptSelector.vue` 组件（Prompt 下拉选择 + 实时切换 + 状态显示）
- ✅ 扩展 `useAiModelSuiteStore`：新增 `activatePrompt()` action
- ✅ 集成到 Dashboard 主页面（`web/src/views/dashboard/index.vue`）
- ✅ 代码格式化（Prettier）
- ✅ Chrome DevTools 端到端验证

### 1.2 创建/修改的文件清单

**新增文件（1 个组件）**:
1. `web/src/components/dashboard/PromptSelector.vue` - 88 行

**修改文件（2 个）**:
1. `web/src/store/modules/aiModelSuite.js` - 新增 `activatePrompt()` action（4 行）
2. `web/src/views/dashboard/index.vue` - 新增 PromptSelector 组件导入与使用（3 行）

### 1.3 验收标准达成情况

| 验收标准 | 状态 | 验证方法 |
|---------|------|---------|
| Prompt 选择器正确显示 | ✅ 通过 | Chrome DevTools 快照 |
| Prompt 列表从 API 加载 | ✅ 通过 | 网络请求验证（`GET /api/v1/llm/prompts`） |
| Prompt 切换功能正常 | ✅ 通过 | 下拉选择器可交互，成功切换到 "stander" |
| 激活 API 调用成功 | ✅ 通过 | `POST /api/v1/llm/prompts/1/activate` 返回 200 |
| 状态实时更新 | ✅ 通过 | 切换后 UI 显示 "stander" + "已激活" |
| 无编译错误 | ✅ 通过 | `diagnostics` 工具验证 |
| 无控制台错误 | ✅ 通过 | `list_console_messages` 验证 |
| 代码格式化 | ✅ 通过 | Prettier 格式化完成 |

---

## 2. 组件说明

### 2.1 PromptSelector.vue

**文件路径**: `web/src/components/dashboard/PromptSelector.vue`

**功能描述（WHY）**:  
解决 Dashboard 缺少 Prompt 快速切换功能的问题。用户需要在 Dashboard 上直接切换 AI Prompt 模板，而不是跳转到 Prompt 管理页面。

**Props API**:
```typescript
interface Props {
  compact?: boolean  // 紧凑模式（默认 false）
}
```

**Events API**:
```typescript
interface Emits {
  (e: 'change', promptId: number): void  // Prompt 切换时触发
}
```

**使用示例**:
```vue
<PromptSelector :compact="false" @change="handlePromptChange" />
```

**依赖的 Store/API**:
- Store: `useAiModelSuiteStore` (SSOT)
  - `prompts` - Prompt 列表
  - `promptsLoading` - 加载状态
  - `loadPrompts()` - 加载 Prompt 列表
  - `activatePrompt(promptId)` - 激活 Prompt（新增）
- API: `GET /api/v1/llm/prompts`, `POST /api/v1/llm/prompts/{id}/activate`

**关键特性**:
- 复用 Pinia store 作为唯一数据源（SSOT 合规）
- 支持加载状态显示
- 错误处理和自动回滚（切换失败时恢复到之前的选择）
- 显示 Prompt 详细信息（描述、激活状态、Tools 配置状态）
- 简化 Tools 开关：仅显示只读状态（YAGNI 原则）

---

## 3. 技术实现细节

### 3.1 SSOT 合规性

**复用现有状态**：
- ✅ 使用 `useAiModelSuiteStore` 的 `prompts` 状态（无新建状态）
- ✅ 使用 `promptsLoading` 状态（无重复加载逻辑）
- ✅ 新增 `activatePrompt()` action（符合 Store 职责）

**数据流**：
```
UI 交互 → Store Action → 后端 API → 状态更新 → UI 反馈
```

### 3.2 端到端链路

**完整流程**：
1. **组件挂载** → `onMounted()` → `store.loadPrompts()` → `GET /api/v1/llm/prompts`
2. **用户选择** → `handlePromptChange(promptId)` → `store.activatePrompt(promptId)`
3. **Store Action** → `api.activateAIPrompt(promptId)` → `POST /api/v1/llm/prompts/{id}/activate`
4. **后端处理** → 更新数据库 `is_active` 字段 → 返回更新后的 Prompt
5. **重新加载** → `store.loadPrompts()` → `GET /api/v1/llm/prompts`
6. **UI 更新** → 选择器显示新 Prompt + 状态标签更新

### 3.3 错误处理

**失败回滚**：
```javascript
catch (error) {
  window.$message?.error('Prompt 切换失败')
  // 回滚到之前的选择
  const activePrompt = prompts.value.find((p) => p.is_active)
  if (activePrompt) {
    selectedPromptId.value = activePrompt.id
  }
}
```

---

## 4. Chrome DevTools 验证结果

### 4.1 组件渲染验证

**快照结果**：
```
uid=11_53 heading "当前 Prompt" level="2"
uid=11_54 generic ""
  uid=11_55 StaticText "GymBro Assistant"
  uid=11_56 image "loading"
uid=11_57 StaticText "默认健身助手 Prompt"
uid=11_58 StaticText "已激活"
```

**验证通过**：
- ✅ 组件正确渲染
- ✅ 显示当前激活 Prompt 名称
- ✅ 显示描述信息
- ✅ 显示激活状态标签

### 4.2 网络请求验证

**初始加载**：
```
GET /api/v1/llm/prompts → 200 OK
Response: {
  "data": [
    {"id": 2, "name": "GymBro Assistant", "is_active": true, ...},
    {"id": 1, "name": "stander", "is_active": false, ...}
  ]
}
```

**切换 Prompt**：
```
POST /api/v1/llm/prompts/1/activate → 200 OK
GET /api/v1/llm/prompts → 200 OK (重新加载)
```

**验证通过**：
- ✅ API 调用成功
- ✅ 状态正确更新
- ✅ 无网络错误

### 4.3 控制台日志验证

**成功日志**：
```
[Dashboard] Prompt 已切换，新 Prompt ID: 1
```

**验证通过**：
- ✅ 无 JavaScript 错误
- ✅ 无 Vue 警告
- ✅ 事件正确触发

---

## 5. 与 Phase 1 的对比

| 特性 | Phase 1 (ModelSwitcher) | Phase 2 (PromptSelector) |
|------|------------------------|-------------------------|
| 组件复杂度 | 中等（155 行） | 简单（88 行） |
| Store Action | 复用 `setDefaultModel()` | 新增 `activatePrompt()` |
| API 端点 | `PUT /api/v1/llm/models` | `POST /api/v1/llm/prompts/{id}/activate` |
| 状态显示 | Base URL + 状态标签 | 描述 + 激活状态 + Tools 配置 |
| 错误处理 | 消息提示 | 消息提示 + 自动回滚 |

---

## 6. 下一步计划

**Phase 2 剩余任务**：
- Task 2.2: SupabaseStatusCard.vue（Supabase 状态卡片）
- Task 2.3: ServerLoadCard.vue（服务器负载卡片）

**依赖关系**：
- Task 2.1 ✅ → Task 2.2 ⏳ → Task 2.3 ⏳

---

## 7. 回滚方案

**如需回滚**：
```bash
# 1. 删除新增组件
rm web/src/components/dashboard/PromptSelector.vue

# 2. 恢复 Store 文件
git checkout HEAD -- web/src/store/modules/aiModelSuite.js

# 3. 恢复 Dashboard 文件
git checkout HEAD -- web/src/views/dashboard/index.vue

# 4. 重启前端服务
cd web && pnpm dev
```

**影响范围**：
- ✅ 无数据库变更
- ✅ 无后端 API 变更
- ✅ 仅前端组件变更，回滚安全

---

**文档版本**: v1.0  
**最后更新**: 2025-10-12  
**状态**: ✅ 已完成并验收

