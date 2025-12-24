# JWT 压测页面优化完成报告

## 📋 任务概述

优化 JWT 压测页面（`/ai/jwt`）的 UI 和功能体验，提升用户操作便利性和数据可视化效果。

## ✅ 已完成功能

### 1. 配置持久化（localStorage）

**实现内容**：
- ✅ 单次对话模拟配置自动保存/恢复
- ✅ 并发压测配置自动保存/恢复
- ✅ 多用户测试配置自动保存/恢复
- ✅ 每个表单提供"重置为默认值"按钮

**存储键**：
```javascript
STORAGE_KEYS = {
  SINGLE_FORM: 'jwt_test_single_form_config',
  LOAD_FORM: 'jwt_test_load_form_config',
  MULTI_USER_FORM: 'jwt_test_multi_user_form_config',
}
```

**用户体验**：
- 刷新页面后自动填充上次使用的配置
- 执行测试前自动保存当前配置
- 点击"重置配置"按钮恢复默认值

---

### 2. 结果弹窗展示

**实现内容**：
- ✅ 单次测试结果在弹窗中展示（`<n-modal>`）
- ✅ 并发压测结果在弹窗中展示
- ✅ 多用户测试结果在弹窗中展示
- ✅ 主页面仅显示摘要信息和"查看详情"按钮

**弹窗功能**：
- **单次测试弹窗**：
  - 📊 结果摘要：JWT Token、性能指标、AI 回复
  - 🔍 Raw 数据：完整 JSON 数据展示
  - 复制/导出功能

- **并发压测弹窗**：
  - 📊 压测摘要：运行 ID、成功率、时间信息
  - 📋 详细记录：可展开的测试记录表格
  - 📥 导出数据：导出完整数据或仅摘要

- **多用户测试弹窗**：
  - 📊 测试摘要：总用户数、JWT 成功率、测试成功率
  - 📋 用户详情：每个用户的 JWT 和测试状态
  - 📥 导出数据：导出完整数据或仅摘要

---

### 3. 多用户并发测试

**实现内容**：
- ✅ 新增"多用户并发测试"卡片
- ✅ 批量生成虚拟用户（`test-user-1`, `test-user-2`, ...）
- ✅ 使用 admin 账号获取单个 JWT Token
- ✅ 所有虚拟用户共享同一个 JWT Token
- ✅ 并发执行 N 个 AI 对话测试
- ✅ 按虚拟用户分组展示结果

**配置参数**：
- 用户数量（1-50）：并发请求数
- 用户名前缀（默认 `test-user-`）：虚拟用户标识
- 并发数（1-20）：控制并发执行的请求数
- Prompt、模型接口、模型名称
- 测试消息

**工作原理**：
1. 使用 `admin/123456` 账号获取一个 JWT Token
2. 生成 N 个虚拟用户（仅用于标识不同的并发请求）
3. 所有虚拟用户共享同一个 JWT Token
4. 并发执行 N 个 AI 对话请求（模拟多用户场景）
5. 统计每个请求的成功/失败状态和耗时

**注意事项**：
⚠️ 由于后端仅支持 `admin/123456` 账号，虚拟用户名仅用于标识不同的并发请求，实际都使用 admin 的 JWT Token。此功能主要用于测试 AI 接口在高并发下的性能表现。

---

### 4. UI 美化和状态优化

**实现内容**：
- ✅ 使用 `<n-grid>` 实现响应式布局
- ✅ 使用 `<n-tag>` 显示状态（成功/失败/进行中）
- ✅ 使用 `<n-progress>` 显示实时进度
- ✅ 使用 `<n-statistic>` 显示关键指标
- ✅ 使用 `<n-collapse>` 实现可折叠的配置说明
- ✅ 使用 `<n-tabs>` 组织弹窗内容
- ✅ 所有异步操作显示加载状态
- ✅ 表单字段在加载时禁用

**视觉优化**：
- 卡片标题添加 Emoji 图标（🎯 🚀 👥）
- 状态标签使用颜色编码（绿色=成功、红色=失败、蓝色=进行中）
- 关键指标使用统计卡片展示
- 进度条实时更新（成功/失败状态颜色区分）

---

## 📂 修改文件清单

### 主要修改
- **`web/src/views/ai/model-suite/jwt/index.vue`**（1289 行）
  - 新增配置持久化逻辑（localStorage）
  - 新增 3 个弹窗组件（单次/并发/多用户）
  - 新增多用户并发测试功能
  - 优化 UI 布局和状态展示
  - 新增工具函数（复制、导出、重置）

### 新增组件导入
```javascript
import {
  NCode,        // 代码展示
  NCollapse,    // 可折叠面板
  NCollapseItem,
  NDivider,     // 分割线
  NGrid,        // 网格布局
  NGridItem,
  NModal,       // 弹窗
  NStatistic,   // 统计数字
  NTabs,        // 标签页
  NTabPane,
} from 'naive-ui'
```

---

## 🎯 验收标准检查

- [x] 刷新页面后表单自动填充上次配置
- [x] 详细结果在弹窗中展示，主页面保持简洁
- [x] 支持多用户并发测试（批量生成用户方式）
- [x] 页面使用 Naive UI 组件库统一风格
- [x] 所有异步操作有明确的加载状态指示
- [x] 错误信息友好且可操作（提供复制/导出按钮）

---

## 🚀 使用指南

### 1. 单次对话模拟
1. 填写 Prompt、模型接口、模型名称、对话内容
2. 点击"执行模拟"按钮
3. 等待执行完成后，点击"查看详情"按钮打开弹窗
4. 在弹窗中查看 JWT Token、性能指标、AI 回复
5. 可复制 Token 或导出 JSON 数据

### 2. 并发压测
1. 填写 Prompt、模型接口、模型名称、批次数、并发数
2. 点击"执行压测"按钮
3. 观察实时进度条和关键指标卡片
4. 压测完成后，点击"查看详细报告"按钮
5. 在弹窗中查看压测摘要、详细记录、导出数据

### 3. 多用户并发测试
1. 配置用户数量、用户名前缀、并发数
2. 填写 Prompt、模型接口、模型名称、测试消息
3. 点击"开始测试"按钮
4. 等待测试完成后，点击"查看详细结果"按钮
5. 在弹窗中查看测试摘要、用户详情、导出数据

---

## 🔧 技术实现细节

### 配置持久化
```javascript
// 保存配置
function saveFormConfig(key, config) {
  localStorage.setItem(key, JSON.stringify(config))
}

// 加载配置
function loadFormConfig(key, defaultConfig) {
  const saved = localStorage.getItem(key)
  return saved ? { ...defaultConfig, ...JSON.parse(saved) } : { ...defaultConfig }
}
```

### 弹窗控制
```javascript
const showSingleDetailModal = ref(false)
const showLoadDetailModal = ref(false)
const showMultiUserDetailModal = ref(false)

// 执行成功后自动打开弹窗
async function runSingle() {
  // ... 执行逻辑
  showSingleDetailModal.value = true
}
```

### 多用户并发测试
```javascript
async function runMultiUserTest() {
  // 1. 使用 admin 账号获取一个 JWT Token
  const sharedToken = await fetchRealJWT('admin')

  // 2. 生成虚拟用户列表（共享同一个 Token）
  const virtualUsers = Array.from({ length: multiUserForm.user_count }, (_, i) => ({
    username: `${multiUserForm.username_prefix}${i + 1}`,
    index: i + 1,
    token: sharedToken,
  }))

  // 3. 并发执行 AI 对话测试（所有请求使用相同的 JWT Token）
  const testResults = await Promise.all(virtualUsers.map(async (user) => {
    const { data } = await store.simulateDialog({
      prompt_id: multiUserForm.prompt_id,
      endpoint_id: multiUserForm.endpoint_id,
      message: multiUserForm.message,
      model: multiUserForm.model,
      username: 'admin', // 实际使用 admin 账号
    })
    return { ...user, test_result: data }
  }))

  // 4. 汇总结果
  multiUserSummary.value = {
    total_users: virtualUsers.length,
    success_tests: testResults.filter(r => r.test_success).length,
    avg_time_ms: /* 平均耗时 */,
  }
}
```

---

## 📊 性能优化

- **懒加载弹窗**：弹窗内容仅在打开时渲染
- **响应式布局**：使用 `<n-grid>` 自适应不同屏幕尺寸
- **异步操作优化**：使用 `Promise.all()` 并发执行多用户测试
- **状态管理**：使用 `ref()` 和 `reactive()` 管理组件状态

---

## 🐛 已知限制

1. **后端账号限制**：当前后端仅支持 `admin/123456` 账号
   - 多用户测试实际使用相同的 JWT Token（所有虚拟用户共享）
   - 虚拟用户名仅用于标识不同的并发请求，不代表真实的多用户认证
   - 未来需要后端支持多用户注册功能才能实现真正的多用户测试

补充（真实环境建议）：
- 实际联调请优先使用 Supabase 真实用户 Token（ES256），并配合 Mail API 生成临时邮箱完成注册/验证流程（见 `docs/mail-api.txt`）。

2. **并发数限制**：建议并发数不超过 20，避免浏览器性能问题

3. **数据导出格式**：仅支持 JSON 格式导出

4. **并发压测轮询**：并发压测结果需要通过轮询获取，初始响应中 `tests` 为空是正常现象

---

## 🔄 后续优化建议

1. **CSV 文件导入**：支持从 CSV 文件导入用户列表
2. **手动数组输入**：支持手动输入用户名/密码数组
3. **图表可视化**：使用 ECharts 展示压测结果趋势图
4. **实时日志流**：显示测试执行的实时日志
5. **测试历史记录**：保存历史测试结果，支持对比分析

---

## 📝 提交信息

```
feat(jwt-test): 优化 JWT 压测页面 UI 和功能体验

- 新增配置持久化（localStorage）
- 新增结果弹窗展示（单次/并发/多用户）
- 新增多用户并发测试功能
- 优化 UI 布局和状态展示
- 新增工具函数（复制、导出、重置）

验收标准：
✅ 配置持久化
✅ 弹窗展示详细结果
✅ 多用户并发测试
✅ Naive UI 统一风格
✅ 加载状态指示
✅ 友好错误提示
```

---

**优化完成时间**：2025-10-18  
**文件修改数**：1  
**新增代码行数**：约 400 行  
**删除代码行数**：约 100 行  
**净增代码行数**：约 300 行
