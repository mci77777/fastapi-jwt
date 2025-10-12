# Dashboard 重构需求 - 需求澄清文档

**文档版本**: v1.0  
**创建时间**: 2025-01-11  
**状态**: 待用户确认

---

## 📋 文档目的

本文档基于用户提供的需求，梳理所有技术细节和实施方案，列出需要确认的关键问题。**用户确认后，将进入架构设计阶段**。

---

## ✅ 已明确的需求（无需确认）

### 1️⃣ Dashboard 横幅统计信息（P0）

**需要展示的 5 个核心指标**：

| 指标 | 定义 | 数据来源 | 刷新策略 |
|------|------|---------|---------|
| **日活监控** | JWT 活跃用户数（设计容量 1W/天） | 本地优先，远端备份 | 实时图表 + 时间窗口可调 |
| **AI 请求数量** | 所有 AI API 调用次数 | 本地优先，远端备份 | 实时图表 + 时间窗口可调 |
| **Token 使用量** | Token 消耗总量 + USD 换算 | 本地优先，远端备份 | 实时图表 + 时间窗口可调 |
| **API 连通性** | 用户填写的 API 供应商健康状态 + JWT 可访问性 | 本地优先，远端备份 | 实时图表 + 时间窗口可调 |
| **JWT 可获取性** | Supabase 认证签发状态（生产 36h/测试 1h） | 本地优先，远端备份 | 实时图表 + 时间窗口可调 |

**交互要求**：
- 支持实时图表渲染（折线图 + 仪表盘）
- 时间窗口可调整（最近 1 小时/24 小时/7 天）

---

### 2️⃣ 权限管理（P1）

**要求**：
- 需要可自定义权限配置
- 默认权限方案由 AI 设计并提供建议
- 合并现有的"角色管理"和"菜单管理"为统一的"权限管理"入口

---

### 3️⃣ 模型管理整合（P1）

**整合范围**：
- `/system/ai`（AI 配置 - 端点管理）
- `/ai/catalog`（模型目录）
- `/ai/mapping`（模型映射）
- **注意**：`/system/api`（API 权限）暂不整合，后续追加

**整合后的层级结构**：
```
模型管理
├── API 供应商选择（第 1 层）
│   └── 选择具体供应商（如 OpenAI、Supabase）
├── Models 选择（第 2 层）
│   └── 该供应商下的可用模型列表
└── 映射选择（第 3 层）
    └── 映射 = 最终用户看到的 models
```
- 所有层级均支持扩展

---

### 4️⃣ Log 左侧小窗（P1）

**位置与交互**：
- 放置在左下角侧边栏内
- 点击后扩展弹出详情窗口
- 支持复制日志内容
- 支持实时折叠和展开

**显示规则**：
- 默认只显示错误和警告信息
- 显示最近 100 条日志
- 实时更新

**数据来源**：
- App 用户 JWT 接入点
- App 用户消息发送点
- API 调用点
- 所有能接入的日志源都可以接入（展示与否由用户控制）

---

### 5️⃣ JWT 测试功能修复（P2）

**现状**：
- 基本功能已实现（`/ai/jwt` 页面）
- 当前处于失效状态，需要修复

**要求**：
- 测试结果需要保存到本地
- 恢复现有功能的正常运行

---

### 6️⃣ Prompt 管理增强（P2）

**功能要求**：
- 需要版本控制（记录修改历史）
- 管理内容包括：
  1. 系统提示词管理
  2. Tool 工具管理
- 可以复用现有 `/system/ai/prompt` 页面的代码

---

### 7️⃣ UI 设计要求

**菜单 UI**：
- 需要设计 2 套方案供用户选择
- 包含新的菜单结构和布局

**Dashboard UI**：
- 需要设计 2 套方案供用户选择
- 包含横幅、Log 小窗、用户管理中心等区域的布局

**原型要求**：
- 使用简单的 HTML 示例展示设计方案
- 用户确认满意后再进行正式开发

---

## ❓ 需要用户确认的技术细节

### 🔴 问题 1：数据统计实现方案（P0 - 核心）

**背景分析**：
- **现有数据源**：
  - ✅ Prometheus 指标（`/api/v1/metrics`）：`auth_requests_total`, `active_connections`, `rate_limit_blocks_total`
  - ✅ Supabase 数据库表：`users`, `chat_sessions`, `chat_raw`, `audit_logs`, `user_metrics`
  - ✅ SQLite 本地数据库：`ai_endpoints`, `ai_prompts`, `ai_prompt_tests`
  - ❌ **缺失**：Token 使用量统计、费用计算逻辑

**问题**：
1. **日活监控（JWT 活跃用户数）**：
   - 方案 A：从 Supabase `user_metrics` 表统计（需新增后端 API `/api/v1/stats/daily-active-users`）
   - 方案 B：从 Prometheus `auth_requests_total` 指标解析（需前端解析 Prometheus 文本格式）
   - 方案 C：新增本地 SQLite 表 `user_activity_stats`（每日定时聚合）
   - **请选择方案**：[ ] A [ ] B [ ] C [ ] 其他：___________

2. **AI 请求数量**：
   - 方案 A：从 Supabase `chat_sessions` 表统计 `message_count`
   - 方案 B：从 Prometheus `auth_requests_total` 指标解析
   - 方案 C：新增本地 SQLite 表 `ai_request_stats`
   - **请选择方案**：[ ] A [ ] B [ ] C [ ] 其他：___________

3. **Token 使用量 + USD 换算**：
   - **当前系统未实现 Token 统计**，需要新增功能：
     - 在 `chat_raw` 表新增字段：`prompt_tokens`, `completion_tokens`, `total_tokens`
     - 在 AI 响应后调用 OpenAI API 获取 Token 使用量
     - 新增费用计算逻辑（不同模型价格不同）
   - **是否需要立即实现**：[ ] 是（P0） [ ] 否（后续追加）
   - **如果是，请提供**：
     - 各模型的 Token 价格表（如 gpt-4o-mini: $0.15/1M input tokens）
     - 费用计算公式

4. **API 连通性**：
   - 方案 A：复用现有 `/api/v1/llm/monitor/status`（已有端点健康检测）
   - 方案 B：新增 `/api/v1/stats/api-connectivity`（聚合多个供应商状态）
   - **请选择方案**：[ ] A [ ] B [ ] 其他：___________

5. **JWT 可获取性**：
   - 方案 A：从 Prometheus `auth_requests_total` 计算成功率
   - 方案 B：新增 `/api/v1/stats/jwt-availability`（查询 Supabase Auth 状态）
   - 方案 C：定时任务测试 JWT 签发（生产 36h/测试 1h）并记录结果
   - **请选择方案**：[ ] A [ ] B [ ] C [ ] 其他：___________

---

### 🟡 问题 2：数据存储策略（P0 - 核心）

**背景**：用户要求"本地优先，远端备份"

**问题**：
1. **本地存储**：
   - 方案 A：SQLite 新增表 `dashboard_stats`（存储聚合后的统计数据）
   - 方案 B：JSON 文件 `storage/dashboard_stats.json`（类似现有 `jwt_runs.json`）
   - 方案 C：内存缓存 + 定时持久化到 SQLite
   - **请选择方案**：[ ] A [ ] B [ ] C [ ] 其他：___________

2. **远端备份**：
   - 方案 A：定时推送到 Supabase 新表 `dashboard_stats`
   - 方案 B：定时推送到 Supabase 现有表（如 `audit_logs` 扩展字段）
   - 方案 C：不做远端备份（仅本地存储）
   - **请选择方案**：[ ] A [ ] B [ ] C [ ] 其他：___________

3. **数据保留策略**：
   - 本地保留多久？[ ] 7 天 [ ] 30 天 [ ] 90 天 [ ] 永久
   - 远端保留多久？[ ] 30 天 [ ] 90 天 [ ] 1 年 [ ] 永久

---

### 🟡 问题 3：实时更新机制（P0 - 核心）

**背景**：用户要求"实时图表渲染"

**问题**：
1. **前端轮询间隔**：
   - [ ] 5 秒
   - [ ] 10 秒（推荐，与现有 Dashboard 一致）
   - [ ] 30 秒
   - [ ] 可配置（用户可调整）

2. **是否需要 WebSocket/SSE 实时推送**：
   - [ ] 是（需新增 WebSocket 端点）
   - [ ] 否（使用轮询即可）

---

### 🟡 问题 4：Log 小窗数据来源（P1 - 重要）

**背景**：用户要求"App 用户 JWT 接入点、消息发送点、API 调用点"

**问题**：
1. **日志来源**：
   - [ ] Supabase `audit_logs` 表（已有用户操作记录）
   - [ ] 后端 Python logger 输出（需新增日志收集 API）
   - [ ] Prometheus 日志（需解析）
   - [ ] 混合来源（需聚合多个数据源）

2. **日志级别过滤**：
   - 默认显示：[ ] ERROR + WARNING [ ] ERROR only [ ] 可配置

3. **日志格式**：
   - 需要显示哪些字段？
     - [ ] 时间戳
     - [ ] 日志级别（ERROR/WARNING/INFO）
     - [ ] 用户 ID
     - [ ] 操作类型（JWT 接入/消息发送/API 调用）
     - [ ] 详细信息
     - [ ] Trace ID
     - [ ] 其他：___________

---

### 🟢 问题 5：JWT 测试失效原因（P2 - 次要）

**背景**：用户提到"当前处于失效状态"

**问题**：
1. **失效表现**：
   - [ ] 无法发起测试请求
   - [ ] 测试结果不显示
   - [ ] 测试结果不保存
   - [ ] 其他：___________

2. **是否需要先修复再重构**：
   - [ ] 是（先修复，再整合到新 Dashboard）
   - [ ] 否（直接在重构中修复）

---

### 🟢 问题 6：Prompt 版本控制实现（P2 - 次要）

**问题**：
1. **版本控制方式**：
   - 方案 A：SQLite 新增表 `ai_prompt_versions`（存储历史版本）
   - 方案 B：在 `ai_prompts` 表新增字段 `version_history` (JSON)
   - 方案 C：Git 风格版本控制（每次修改生成新记录，保留旧记录）
   - **请选择方案**：[ ] A [ ] B [ ] C [ ] 其他：___________

2. **版本回滚**：
   - 是否需要一键回滚到历史版本？[ ] 是 [ ] 否

---

## 📐 技术实施建议（待用户确认）

### 建议 1：新增后端 API 端点

基于以上需求，建议新增以下 API：

| 端点 | 方法 | 功能 | 优先级 |
|------|------|------|--------|
| `/api/v1/stats/dashboard` | GET | 返回 Dashboard 所有统计数据（聚合接口） | P0 |
| `/api/v1/stats/daily-active-users` | GET | 日活用户数（支持时间窗口参数） | P0 |
| `/api/v1/stats/ai-requests` | GET | AI 请求数量统计 | P0 |
| `/api/v1/stats/token-usage` | GET | Token 使用量 + 费用 | P0（如需要） |
| `/api/v1/stats/api-connectivity` | GET | API 连通性状态 | P0 |
| `/api/v1/stats/jwt-availability` | GET | JWT 可获取性状态 | P0 |
| `/api/v1/logs/recent` | GET | 最近日志（支持过滤） | P1 |
| `/api/v1/prompts/{id}/versions` | GET | Prompt 版本历史 | P2 |

**是否同意以上 API 设计**：[ ] 是 [ ] 否（请说明修改意见）

---

### 建议 2：SQLite 数据库扩展

建议新增以下表：

```sql
-- Dashboard 统计数据缓存表
CREATE TABLE dashboard_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_type TEXT NOT NULL,  -- 'daily_active_users', 'ai_requests', 'token_usage', etc.
    stat_value REAL NOT NULL,
    stat_metadata TEXT,  -- JSON 格式，存储额外信息
    time_window TEXT,  -- '1h', '24h', '7d'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Prompt 版本历史表
CREATE TABLE ai_prompt_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    version TEXT NOT NULL,
    content TEXT NOT NULL,
    tools_json TEXT,
    created_by TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(prompt_id) REFERENCES ai_prompts(id) ON DELETE CASCADE
);

-- 日志聚合表（可选，如果不使用 Supabase audit_logs）
CREATE TABLE system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    level TEXT NOT NULL,  -- 'ERROR', 'WARNING', 'INFO'
    source TEXT NOT NULL,  -- 'jwt_auth', 'ai_message', 'api_call'
    user_id TEXT,
    message TEXT NOT NULL,
    trace_id TEXT,
    metadata TEXT,  -- JSON
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**是否同意以上表结构**：[ ] 是 [ ] 否（请说明修改意见）

---

## 🎨 UI 设计方案预览（下一阶段）

**说明**：用户确认以上技术细节后，将生成 2 套 HTML 原型方案：

### 方案 A：经典三栏布局
```
+----------+---------------------------+
| 侧边栏   | 横幅（5 个指标卡片）      |
| (15%)    +---------------------------+
|          | 主控监视面板（快捷入口）  |
| Log 小窗 | (70%)                     |
| (折叠)   +---------------------------+
|          | 用户管理中心（图表）      |
+----------+---------------------------+
```

### 方案 B：现代化卡片布局
```
+----------+---------------------------+
| 侧边栏   | 横幅（5 个指标 + 趋势图） |
| (15%)    +---------------------------+
|          | 主控监视面板（卡片网格）  |
|          | +-------+-------+-------+ |
|          | | 用户  | 模型  | JWT   | |
|          | +-------+-------+-------+ |
|          | | Log 小窗（内嵌）      | |
+----------+---------------------------+
```

**用户将在下一阶段选择满意的方案**。

---

## 📋 下一步行动

**请用户逐条确认以上问题后，我将：**

1. ✅ 生成 `ARCHITECTURE_OVERVIEW.md`（顶层架构设计）
2. ✅ 生成 `UI_DESIGN_V1.md` 和 `UI_DESIGN_V2.md`（2 套 HTML 原型）
3. ✅ 生成 `IMPLEMENTATION_SPEC.md`（实施规格说明）
4. ✅ 生成 `IMPLEMENTATION_PLAN.md`（分阶段实施计划）

**严格遵循 YAGNI → SSOT → KISS 原则，确保每个决策都有明确的业务价值。**

---

**请回复确认以上所有问题，我将立即开始架构设计阶段。**

