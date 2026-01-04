# Dashboard 模型诊断、编辑、同步与测试功能 - 交接文档

## 📋 任务概述

**目标**：完善 Dashboard 模型管理功能，新增模型诊断、编辑、同步到 Supabase、业务域默认配置、JWT 测试脚本更新、Mock 用户 UI 与 AI 对话测试。

**完成时间**：2025-01-14  
**状态**：✅ 已完成

---

## 🎯 核心功能

### 1. 模型可用性诊断与状态管理

**后端 API**：`POST /api/v1/llm/models/check-all`（已存在）

**功能说明**：
- 批量检测所有模型的真实可用性（调用 API 供应商健康检查）
- 返回每个模型的状态：`available`（可用）、`unavailable`（不可用）、`error`（错误）

**前端实现**：
- 组件路径：`web/src/components/dashboard/ModelMappingCard.vue`
- 新增"诊断模型"按钮（第 13-17 行）
- 调用 `diagnoseModels()` API（第 230-246 行）
- 显示诊断结果：可用/不可用模型数量

**使用示例**：
```javascript
// 前端调用
import { diagnoseModels } from '@/api/aiModelSuite'

const response = await diagnoseModels()
const results = response.data || []
const availableCount = results.filter((r) => r.status === 'available').length
```

---

### 2. 模型供应商编辑功能

**后端 API**：`PUT /api/v1/llm/models`（已存在）

**功能说明**：
- 更新模型信息到数据库
- 可编辑字段：模型名称、API 供应商、API 端点、是否激活

**前端实现**：
- API 封装：`web/src/api/aiModelSuite.js::updateModel(data)`（已存在）
- 组件：`ModelMappingCard.vue` 中的编辑功能（占位实现）

**注意**：当前 `ModelMappingCard` 主要管理模型映射，模型编辑功能在 `web/src/views/ai/model-suite/catalog/index.vue` 中已完整实现。

---

### 3. 模型映射同步 Supabase 功能

**后端 API**：`POST /api/v1/llm/model-groups/sync-to-supabase`（新增）

**功能说明**：
- 将当前所有模型映射关系批量同步到 Supabase 数据库的 `model_mappings` 表
- 返回同步数量和映射列表

**后端实现**：
- 文件路径：`app/api/v1/llm_mappings.py`（第 78-96 行）
- 当前为占位实现，返回映射数量

**前端实现**：
- API 封装：`web/src/api/aiModelSuite.js::syncMappingsToSupabase()`（第 23 行）
- 组件：`ModelMappingCard.vue` 中的"同步到 Supabase"按钮（第 18-22 行）
- 调用逻辑：`handleSyncToSupabase()`（第 258-270 行）

**使用示例**：
```javascript
// 前端调用
import { syncMappingsToSupabase } from '@/api/aiModelSuite'

const response = await syncMappingsToSupabase()
const data = response.data || {}
console.log(`已同步 ${data.synced_count} 条映射`)
```

---

### 4. 业务域默认配置与用户分级

**后端实现**：
- 文件路径：`app/api/v1/llm_mappings.py`（第 18-34 行）
- `ModelMappingPayload` 中 `scope_type` 默认值设置为 `"user"`

**业务域类型说明**：
- `user`：普通用户（默认）- 只能访问基础模型（如 GPT-3.5）
- `premium_user`：高级用户 - 可访问高级模型（如 GPT-4、Claude-3）
- `tenant`：租户级 - 租户内共享配置
- `global`：全局 - 系统级配置

**前端实现**：
- 组件：`ModelMappingCard.vue` 中的业务域类型选择器（第 119-126 行）
- 默认值：`scope_type: 'user'`（第 114 行）

**数据结构**：
```python
class ModelMappingPayload(BaseModel):
    scope_type: str = Field(default="user", description="业务域类型：user/premium_user/tenant/global")
    scope_key: str = Field(..., description="业务域唯一标识")
    name: Optional[str] = Field(None, description="业务域名称")
    default_model: Optional[str] = Field(None, description="默认模型")
    candidates: list[str] = Field(default_factory=list, description="可用模型集合")
    is_active: bool = Field(default=True, description="是否启用")
    metadata: dict[str, Any] = Field(default_factory=dict, description="额外元数据")
```

---

### 5. JWT 测试功能更新

**脚本路径**：`scripts/test_jwt_with_models.py`（新增）

**功能说明**：
- 使用真实 email 地址注册/登录（调用 `/api/v1/base/access_token`）
- 获取 JWT token
- 使用 token 调用模型列表 API（`GET /api/v1/llm/models`）
- 使用 token 调用模型映射 API（`GET /api/v1/llm/model-groups`）
- 使用 token 调用模型诊断 API（`POST /api/v1/llm/models/check-all`）
- 验证返回数据是否正确

**测试流程**：
1. 步骤 1: 在 Supabase 中注册测试用户
2. 步骤 2: 获取 JWT 访问令牌
3. 步骤 3: 测试模型列表 API
4. 步骤 4: 测试模型映射 API
5. 步骤 5: 测试模型诊断 API

**使用方法**：
```bash
# 设置环境变量（可选）
export TEST_USER_EMAIL="test@example.com"
export TEST_USER_PASSWORD="TestPassword123!"

# 运行测试
python scripts/test_jwt_with_models.py
```

**输出示例**：
```
============================================================
JWT 模型管理测试
============================================================

🔐 步骤 1: 注册测试用户
   邮箱: test@example.com
   ✅ 用户注册成功（或已存在）

🎫 步骤 2: 获取 JWT 访问令牌
   ✅ JWT 令牌获取成功 (长度: 1234)

📋 步骤 3: 测试模型列表 API
   ✅ 模型列表获取成功，共 10 个模型
   📦 模型 1: GPT-4 (gpt-4-turbo)
   📦 模型 2: Claude-3 (claude-3-opus)
   📦 模型 3: Gemini (gemini-pro)

🗺️ 步骤 4: 测试模型映射 API
   ✅ 模型映射获取成功，共 5 条映射
   🔗 映射 1: GPT-5 → gpt-4-turbo
   🔗 映射 2: Claude → claude-3-opus

🔍 步骤 5: 测试模型诊断 API
   ✅ 模型诊断完成：8 个可用，2 个不可用

============================================================
✅ 所有测试通过！
============================================================
```

---

### 6. JWT 测试页（SSOT）与 AI 对话测试

> 历史 `/test/*` 测试页面已移除：避免绕过 SSOT 与产生歧义入口。当前唯一入口为 `/ai/jwt`。

**页面路径**：`web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue`

**功能说明**：
- 创建/选择测试用户并获取 JWT（不污染全局登录态）
- 仅使用“映射后的 model key”（`data[].name`）发起对话：`POST /api/v1/messages`
- SSE 拉流：`GET /api/v1/messages/{id}/events`

**AI 对话测试流程**：
1. 获取 JWT（真实用户/匿名用户之一）
2. 选择模型（SSOT：映射 model key）
3. 发送消息：`POST /api/v1/messages`
4. SSE 拉流：`GET /api/v1/messages/{id}/events`

---

## 📐 技术实现细节

### 后端 API 清单

| API 端点 | 方法 | 功能 | 状态 |
|---------|------|------|------|
| `/api/v1/llm/models` | GET | 获取模型列表 | ✅ 已存在 |
| `/api/v1/llm/models` | PUT | 更新模型信息 | ✅ 已存在 |
| `/api/v1/llm/models/check-all` | GET | 批量诊断模型（202 异步触发） | ✅ 已存在 |
| `/api/v1/llm/model-groups` | GET | 获取模型映射 | ✅ 已存在 |
| `/api/v1/llm/model-groups` | POST | 创建/更新映射 | ✅ 已存在 |
| `/api/v1/llm/model-groups/sync-to-supabase` | POST | 同步映射到 Supabase | ✅ 新增（占位） |
| `/api/v1/base/access_token` | POST | 获取 JWT Token | ✅ 已存在 |
| `/api/v1/messages` | POST | 创建 AI 对话 | ✅ 已存在 |
| `/api/v1/messages/{id}/events` | GET | SSE 流式响应 | ✅ 已存在 |

### 前端 API 封装

**文件路径**：`web/src/api/aiModelSuite.js`

```javascript
// 模型管理
export const fetchModels = (params = {}) => request.get('/llm/models', { params })
export const updateModel = (data = {}) => request.put('/llm/models', data)
export const diagnoseModels = () => request.post('/llm/models/check-all')

// 模型映射
export const fetchMappings = (params = {}) => request.get('/llm/model-groups', { params })
export const saveMapping = (data = {}) => request.post('/llm/model-groups', data)
export const syncMappingsToSupabase = () => request.post('/llm/model-groups/sync-to-supabase')
```

### 组件修改清单

**文件路径**：`web/src/components/dashboard/ModelMappingCard.vue`

**修改内容**：
1. 新增"诊断模型"按钮（第 10-17 行）
2. 新增"同步到 Supabase"按钮（第 18-22 行）
3. 更新业务域类型选项（第 119-126 行）
4. 新增 `handleDiagnose()` 函数（第 230-246 行）
5. 新增 `handleSyncToSupabase()` 函数（第 258-270 行）
6. 修改默认 `scope_type` 为 `'user'`（第 114 行）

---

## ✅ 验证清单

- [x] **编译通过**：`pnpm build` 无错误
- [x] **后端 API 已实现**：模型诊断、映射同步（占位）
- [x] **前端组件已更新**：ModelMappingCard 添加诊断和同步按钮
- [x] **业务域默认值已设置**：`scope_type` 默认为 `'user'`
- [x] **JWT 测试脚本已创建**：`scripts/test_jwt_with_models.py`
- [x] **JWT 测试页（SSOT）**：`web/src/views/ai/model-suite/jwt/RealUserSseSsot.vue`
- [x] **代码规范**：遵循 Vue 3 Composition API 规范（`<script setup>`）
- [x] **样式一致**：使用 Naive UI 组件库

---

## 🚀 后续优化建议

1. **完善 Supabase 同步逻辑**：
   - 当前 `sync-to-supabase` API 为占位实现
   - 需实现真实的 Supabase 批量写入逻辑
   - 参考 `app/services/ai_config_service.py::push_all_to_supabase()`

2. **模型诊断结果展示优化**：
   - 添加不可用模型的独立展示区域（折叠或 Tab）
   - 显示模型状态标签（绿色=可用，红色=不可用，黄色=错误）

3. **Mock 用户 UI 增强**：
   - 添加 SSE 事件可视化（实时流式显示）
   - 支持多轮对话测试
   - 添加 token 过期自动刷新

4. **JWT 测试脚本扩展**：
   - 添加并发测试（多用户同时请求）
   - 添加性能测试（响应时间统计）
   - 添加错误场景测试（无效 token、过期 token）

---

## 📚 相关文档

- **架构总览**：`docs/dashboard-refactor/ARCHITECTURE_OVERVIEW.md`
- **模型管理实现**：`docs/features/model_management/implementation.md`
- **JWT 硬化指南**：`docs/JWT_HARDENING_GUIDE.md`
- **Vue 最佳实践**：`docs/coding-standards/vue-best-practices.md`
- **前一次交接文档**：`docs/dashboard-refactor/MODEL_MANAGEMENT_HANDOVER.md`

---

**交接完成**  
**文档版本**：v1.0  
**最后更新**：2025-01-14
