# 模型管理能力实现说明

## 概览
- **后端重构**：`app/api/v1/llm.py` 拆分为 `llm_models.py` / `llm_prompts.py` / `llm_mappings.py` / `llm_tests.py`，共用 `llm_common`。
- **服务层**：
  - `ModelMappingService`：复用 `ai_prompts.tools_json` 与 `storage/ai_runtime/model_mappings.json` 维护映射。
  - `JWTTestService`：封装单次对话与并发压测，结果写入 `ai_prompt_tests` + `storage/ai_runtime/jwt_runs.json`。
  - `AIConfigService`：新增本地/远端备份目录 `storage/ai_runtime/backups/`（保留 `*-latest.json` + 最近 3 个时间戳归档），推送/拉取前自动快照，并支持覆盖写入与缺失项删除开关。
- **SQLite**：仍只使用现有表；映射信息写入 JSON 字段；压测明细保存在 `ai_prompt_tests`。
- **前端**：新增 `web/src/views/ai/model-suite/` 四个页面与 Pinia store，支撑模型 Dashboard、模型目录、映射管理与 JWT 对话压测；同步弹窗支持方向/覆盖/删除选项。

## API 变更
| 路径 | 方法 | 描述 |
| --- | --- | --- |
| `/llm/model-groups` | GET/POST | 查询或保存模型映射（scope_type: prompt/module/tenant）。|
| `/llm/model-groups/{id}/activate` | POST | 切换映射默认模型。|
| `/llm/tests/dialog` | POST | 单次 JWT 对话模拟，返回 token + 模型响应。|
| `/llm/tests/load` | POST | 发起 1~1000 批并发压测，落地 SQLite/JSON。|
| `/llm/models/sync` | POST | 批量同步端点，支持覆盖、删除缺失控制。|
| `/llm/tests/runs/{id}` | GET | 查询压测批次摘要及测试样本。|

> `SyncRequest.overwrite`：当推送时为 False 且远端更新时间不早于本地，将跳过覆盖并标记 `skipped:overwrite_disabled`；拉取时保持原有“仅当远端更新更晚才覆盖”行为。`delete_missing` 在推送/拉取均可触发目标端缺失项清理。

> 兼容性：原 `/llm/models`、`/llm/prompts`、`/llm/prompts/test` 行为保持不变。

## 运行时依赖
- FastAPI lifespan 中新增：
  - `app.state.model_mapping_service`（目录：`storage/ai_runtime/model_mappings.json`）
  - `app.state.jwt_test_service`（目录：`storage/ai_runtime/jwt_runs.json`）
- `storage/ai_runtime/.gitkeep` 保证目录存在；新增 `storage/ai_runtime/backups/` 使用 `name-latest.json` + `name-YYYYMMDDTHHMMSSZ.json` 形式存放最近 3 次快照，便于回滚。

## 前端结构

### Dashboard作为系统首页
- **路径**: `/dashboard`（系统登录后默认首页）
- **组件**: `web/src/views/dashboard/index.vue`（原workbench重命名）
- **菜单位置**: 左侧菜单最顶部（order: 0）
- **功能**: 全局Dashboard，展示系统状态、快速访问各模块入口、AI统计信息

### AI模型管理子模块
- `web/src/api/aiModelSuite.js`：封装新增 API，含单端点及全量同步选项。
- `web/src/store/modules/aiModelSuite.js`：集中加载模型/映射/压测结果，提供候选模型/端点选项与同步状态响应式数据。
- 视图组件：
  - `dashboard/index.vue`：模型 Dashboard，展示端点状态与映射覆盖并提供跳转入口。
  - `catalog/index.vue`：模型列表、设为默认、同步。
  - `mapping/index.vue`：映射 CRUD，Prompt 选择、候选模型管理、默认模型弹窗。
  - `jwt/index.vue`：单次对话 & 压测面板，展示摘要/测试结果，模型选择支持端点候选列表。
- 菜单入口通过 `/base/usermenu` 动态注入。

## 备份机制

### 存储路径
- **备份目录**: `storage/ai_runtime/backups/`
- **文件命名规则**:
  - 最新版本: `{name}-latest.json`
  - 历史归档: `{name}-YYYYMMDDTHHMMSSfZ.json`
- **备份类型**:
  - `sqlite_endpoints-*.json`: SQLite 本地端点备份
  - `supabase_endpoints-*.json`: Supabase 远端端点备份

### 轮转策略
- 每次备份操作生成两个文件:
  1. 覆盖 `-latest.json` 为当前最新快照
  2. 新建时间戳归档文件 (精确到微秒)
- 自动清理机制: 保留最近 **3 个**时间戳归档 (通过 `keep=3` 参数控制)
- 触发时机:
  - 推送前: 备份 Supabase 远端数据
  - 拉取前: 备份 SQLite 本地数据

### 备份内容示例
```json
{
  "exported_at": "2025-10-10T08:30:00Z",
  "items": [
    {
      "id": 1,
      "name": "OpenAI GPT-4",
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-4o-mini",
      "is_default": true
    }
  ]
}
```

## API 参数说明

### `/llm/models/sync` 请求参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `overwrite` | `bool` | `true` | 控制推送时的覆盖行为 |
| `delete_missing` | `bool` | `false` | 是否删除目标端缺失的项 |

#### `overwrite` 参数详解
**推送场景 (push)**:
- `overwrite=true`: 无条件覆盖远端数据
- `overwrite=false`: 仅当本地 `updated_at` 晚于远端时才覆盖
  - 若远端更新时间 `>=` 本地,跳过推送并标记 `sync_status: "skipped:overwrite_disabled"`

**拉取场景 (pull)**:
- `overwrite=true`: 无条件覆盖本地数据
- `overwrite=false`: 仅当远端 `updated_at` 晚于本地时才覆盖
  - 若本地更新时间 `>=` 远端,保持本地数据不变

#### `delete_missing` 参数详解
**推送场景 (push)**:
- `delete_missing=true`: 删除 Supabase 中不存在于本地的端点
- `delete_missing=false`: 保留 Supabase 现有数据

**拉取场景 (pull)**:
- `delete_missing=true`: 删除 SQLite 中不存在于 Supabase 的端点
- `delete_missing=false`: 保留 SQLite 现有数据

**使用示例**:
```bash
# 推送并覆盖远端,删除远端多余项
POST /llm/models/sync
{
  "direction": "push",
  "overwrite": true,
  "delete_missing": true
}

# 拉取但不覆盖本地新数据,保留本地独有项
POST /llm/models/sync
{
  "direction": "pull",
  "overwrite": false,
  "delete_missing": false
}
```

## 已知问题修复

### JWT类型错误修复（2025-01-11）
**文件**: `app/api/v1/base.py`（第73-85行）
**问题**: `settings.supabase_jwt_secret`可能为`None`，导致类型检查错误
**修复**: 添加空值检查，抛出500错误而非类型错误
```python
jwt_secret = settings.supabase_jwt_secret
if not jwt_secret:
    raise HTTPException(status_code=500, detail="JWT secret is not configured")
token = jwt.encode(payload, jwt_secret, algorithm="HS256")
```

### 登录后404问题修复（2025-01-11）
**问题**: 登录成功后跳转`/dashboard`返回404
**根因**: 登录时token刚保存，auth-guard立即跳转，但动态路由尚未加载
**修复**: `web/src/router/guard/auth-guard.js`
- 检测`permissionStore.accessRoutes`是否为空
- 为空时先调用`addDynamicRoutes()`加载路由
- 然后用`replace: true`重新导航到目标路由

### 静态路由冲突清理（2025-01-11）
**删除文件**:
- `web/src/views/dashboard/route.js`（静态路由，已删除）
- `web/src/views/ai/route.js`（静态路由，已删除）
**原因**: 这些静态route.js会与动态路由冲突，导致组件加载失败

## 兼容与回滚
- 回滚仅需删除新路由、服务文件与前端子包，恢复 `llm.py` 旧实现。
- 本地 JSON fallback 可在回滚前备份或直接清空（不会影响 Supabase 主数据）。
- Dashboard首页功能可通过修改`base.py`菜单配置降级回AI模型概览。
