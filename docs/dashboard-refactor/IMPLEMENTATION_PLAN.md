# Dashboard 重构 - 分阶段实施计划

**文档版本**: v2.0（基于代码审查调整）
**创建时间**: 2025-01-11
**更新时间**: 2025-01-XX
**状态**: 待执行
**目标方案**: 方案 A（左侧 Log 小窗布局）

---

## 📋 总体规划

### 实施周期

**总工期**: 8-10 个工作日（基于代码审查优化，原 10-12 天）
**团队规模**: 1-2 人
**风险缓冲**: 2 个工作日

**调整说明**:
- 原计划 10-12 天 → 调整为 8-10 天
- **原因**: 大量现有模块可复用（`MessageEventBroker`、`SSEConcurrencyGuard`、`EndpointMonitor` 等），减少开发时间

---

### 阶段划分

| 阶段 | 名称 | 工期 | 优先级 | 依赖 | 调整说明 |
|------|------|------|--------|------|---------|
| 阶段 1 | 数据库与服务层 | 1.5-2 天 | P0 | 无 | ⬇️ 减少 1 天（复用 SQLiteManager 模式）|
| 阶段 2 | 后端 API 实现 | 1.5-2 天 | P0 | 阶段 1 | ⬇️ 减少 1 天（复用 llm_models.py 模式）|
| 阶段 3 | 前端组件开发 | 3-4 天 | P0 | 阶段 2 | ⏸️ 保持不变 |
| 阶段 4 | 集成测试与优化 | 1.5 天 | P0 | 阶段 3 | ⬇️ 减少 0.5 天 |
| 阶段 5 | 部署与监控 | 0.5 天 | P1 | 阶段 4 | ⬇️ 减少 0.5 天（复用现有部署流程）|

---

## 🔧 阶段 1：数据库与服务层（1.5-2 天）

### 目标

- ✅ 创建 SQLite 表结构（复用 `SQLiteManager._ensure_columns()` 模式）
- ✅ 创建 Supabase 表结构
- ✅ 实现核心服务层（复用现有服务模式）
- ✅ 实现数据写入逻辑

---

### 任务清单

#### 1.1 数据库表创建（0.5 天）

**文件**: `app/db/sqlite_manager.py`

**任务**:
- [ ] 在 `INIT_SCRIPT` 中新增 3 张表（复用现有模式）
- [ ] 创建 Supabase 表 `dashboard_stats`（手动执行 SQL）
- [ ] 验证表结构和索引

**代码示例**（复用现有模式）:
```python
# app/db/sqlite_manager.py（在 INIT_SCRIPT 中新增）

CREATE TABLE IF NOT EXISTS dashboard_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_date TEXT NOT NULL,
    daily_active_users INTEGER DEFAULT 0,
    ai_request_count INTEGER DEFAULT 0,
    token_usage INTEGER DEFAULT 0,
    api_connectivity_rate REAL DEFAULT 0.0,
    jwt_availability_rate REAL DEFAULT 0.0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dashboard_stats_date ON dashboard_stats(stat_date);

CREATE TABLE IF NOT EXISTS user_activity_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_hour TEXT NOT NULL,
    active_user_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_activity_stats_hour ON user_activity_stats(stat_hour);

CREATE TABLE IF NOT EXISTS ai_request_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stat_hour TEXT NOT NULL,
    request_count INTEGER DEFAULT 0,
    avg_latency_ms REAL DEFAULT 0.0,
    error_count INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_request_stats_hour ON ai_request_stats(stat_hour);
```

**验收标准**:
```bash
# 验证表创建成功
sqlite3 db.sqlite3 ".schema dashboard_stats"
sqlite3 db.sqlite3 ".schema user_activity_stats"
sqlite3 db.sqlite3 ".schema ai_request_stats"
```
  - `user_activity_stats`
  - `ai_request_stats`
- [ ] 创建 Supabase 表 `dashboard_stats`（手动执行 SQL）
- [ ] 验证表结构和索引

**验收标准**:
```bash
# 运行迁移脚本
python scripts/migrate_dashboard_tables.py

# 验证表创建成功
sqlite3 db.sqlite3 ".schema dashboard_stats"
sqlite3 db.sqlite3 ".schema user_activity_stats"
sqlite3 db.sqlite3 ".schema ai_request_stats"
```

---

#### 1.2 MetricsCollector 实现（0.5 天）

**文件**: `app/services/metrics_collector.py`

**任务**:
- [ ] 实现 `MetricsCollector` 类
- [ ] 实现 `aggregate_stats()` 方法
- [ ] 实现 `_get_daily_active_users()` 方法
- [ ] 实现 `_get_ai_requests()` 方法
- [ ] 实现 `_get_api_connectivity()` 方法
- [ ] 实现 `_get_jwt_availability()` 方法

**验收标准**:
```python
# 单元测试
pytest tests/test_metrics_collector.py -v
```

---

#### 1.3 LogCollector 实现（0.5 天）

**文件**: `app/services/log_collector.py`

**任务**:
- [ ] 实现 `LogCollector` 类
- [ ] 实现 `LogHandler` 类
- [ ] 实现 `get_recent_logs()` 方法
- [ ] 集成到 Python logging 系统

**验收标准**:
```python
# 单元测试
pytest tests/test_log_collector.py -v

# 手动测试
import logging
logging.error("Test error message")
# 验证日志被收集
```

---

#### 1.4 DashboardBroker 实现（0.5 天）

**文件**: `app/services/dashboard_broker.py`

**任务**:
- [ ] 实现 `DashboardBroker` 类
- [ ] 实现 `add_connection()` 方法
- [ ] 实现 `remove_connection()` 方法
- [ ] 实现 `get_dashboard_stats()` 方法

**验收标准**:
```python
# 单元测试
pytest tests/test_dashboard_broker.py -v
```

---

#### 1.5 SyncService 实现（0.5 天）

**文件**: `app/services/sync_service.py`

**任务**:
- [ ] 实现 `SyncService` 类
- [ ] 实现 `sync_dashboard_stats()` 方法
- [ ] 实现定时任务调度（使用 APScheduler）

**验收标准**:
```python
# 单元测试（Mock Supabase）
pytest tests/test_sync_service.py -v

# 集成测试
python scripts/test_sync_service.py
```

---

#### 1.6 数据写入逻辑集成（0.5 天）

**任务**:
- [ ] 在 `app/auth/dependencies.py::get_current_user()` 中添加 `record_user_activity()`
- [ ] 在 `app/api/v1/messages.py::create_message()` 中添加 `record_ai_request()`
- [ ] 验证数据写入成功

**验收标准**:
```bash
# 启动服务
python run.py

# 发起 JWT 请求
curl -H "Authorization: Bearer <token>" http://localhost:9999/api/v1/healthz

# 验证数据写入
sqlite3 db.sqlite3 "SELECT * FROM user_activity_stats ORDER BY created_at DESC LIMIT 5;"

# 发起 AI 请求
curl -X POST -H "Authorization: Bearer <token>" \
  http://localhost:9999/api/v1/messages \
  -d '{"content": "Hello"}'

# 验证数据写入
sqlite3 db.sqlite3 "SELECT * FROM ai_request_stats ORDER BY created_at DESC LIMIT 5;"
```

---

## 🌐 阶段 2：后端 API 实现（2-3 天）

### 目标

- ✅ 实现 WebSocket 端点
- ✅ 实现 8 个 REST API 端点
- ✅ 集成到应用生命周期
- ✅ 编写 API 测试

---

### 任务清单

#### 2.1 WebSocket 端点实现（1 天）

**文件**: `app/api/v1/dashboard.py`

**任务**:
- [ ] 实现 `/ws/dashboard` 端点
- [ ] 实现 JWT 验证（`get_current_user_ws()`）
- [ ] 实现连接管理（add/remove connection）
- [ ] 实现数据推送循环（10 秒间隔）
- [ ] 实现错误处理（断线重连、超时）

**验收标准**:
```python
# 集成测试
pytest tests/test_dashboard_websocket.py -v

# 手动测试（使用 wscat）
wscat -c "ws://localhost:9999/ws/dashboard?token=<token>"
# 验证每 10 秒收到一次数据推送
```

---

#### 2.2 REST API 端点实现（1 天）

**文件**: `app/api/v1/stats.py`

**任务**:
- [ ] 实现 `GET /api/v1/stats/dashboard`
- [ ] 实现 `GET /api/v1/stats/daily-active-users`
- [ ] 实现 `GET /api/v1/stats/ai-requests`
- [ ] 实现 `GET /api/v1/stats/api-connectivity`
- [ ] 实现 `GET /api/v1/stats/jwt-availability`
- [ ] 实现 `GET /api/v1/logs/recent`
- [ ] 实现 `GET /api/v1/stats/config`
- [ ] 实现 `PUT /api/v1/stats/config`

**验收标准**:
```bash
# API 测试
pytest tests/test_stats_api.py -v

# 手动测试
curl -H "Authorization: Bearer <token>" \
  "http://localhost:9999/api/v1/stats/dashboard?time_window=24h"
```

---

#### 2.3 应用生命周期集成（0.5 天）

**文件**: `app/core/application.py`

**任务**:
- [ ] 在 `create_app()` 中初始化服务层
- [ ] 注册 WebSocket 路由
- [ ] 注册 REST API 路由
- [ ] 启动定时任务（SyncService）

**代码**:
```python
# app/core/application.py
from app.services import MetricsCollector, LogCollector, DashboardBroker, SyncService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化
    app.state.metrics_collector = MetricsCollector(
        db_manager=app.state.sqlite_manager,
        endpoint_monitor=app.state.endpoint_monitor
    )
    app.state.log_collector = LogCollector(max_size=100)
    app.state.dashboard_broker = DashboardBroker(
        metrics_collector=app.state.metrics_collector
    )
    app.state.sync_service = SyncService(
        sqlite_manager=app.state.sqlite_manager,
        supabase_client=app.state.supabase_client
    )
    
    # 启动定时任务（每小时同步一次）
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        app.state.sync_service.sync_dashboard_stats,
        'interval',
        hours=1
    )
    scheduler.start()
    
    yield
    
    # 关闭时清理
    scheduler.shutdown()
```

**验收标准**:
```bash
# 启动服务
python run.py

# 验证服务初始化成功
curl http://localhost:9999/api/v1/healthz
```

---

## 🎨 阶段 3：前端组件开发（3-4 天）

### 目标

- ✅ 实现 6 个新增组件
- ✅ 修改 3 个现有组件
- ✅ 实现 WebSocket 客户端
- ✅ 实现 API 调用封装
- ✅ 实现 Dashboard 主页面

---

### 任务清单

#### 3.1 基础组件实现（1.5 天）

**任务**:
- [ ] 实现 `StatsBanner.vue`（0.5 天）
- [ ] 实现 `LogWindow.vue`（0.5 天）
- [ ] 实现 `RealTimeIndicator.vue`（0.25 天）
- [ ] 实现 `PollingConfig.vue`（0.25 天）

**验收标准**:
```bash
# 组件单元测试
cd web && pnpm test:unit
```

---

#### 3.2 图表组件实现（1 天）

**任务**:
- [ ] 实现 `UserActivityChart.vue`
- [ ] 集成 ECharts
- [ ] 实现时间范围切换（1h/24h/7d）
- [ ] 实现数据自动更新

**验收标准**:
```bash
# 组件单元测试
cd web && pnpm test:unit

# 手动测试
cd web && pnpm dev
# 访问 http://localhost:3101/dashboard
```

---

#### 3.3 WebSocket 客户端实现（0.5 天）

**任务**:
- [ ] 实现 `WebSocketClient.vue`
- [ ] 实现自动重连逻辑（最多 3 次）
- [ ] 实现降级为 HTTP 轮询

**验收标准**:
```javascript
// 手动测试
const ws = new WebSocket('ws://localhost:9999/ws/dashboard?token=<token>')
ws.onmessage = (event) => console.log(JSON.parse(event.data))
```

---

#### 3.4 API 调用封装（0.5 天）

**文件**: `web/src/api/dashboard.js`

**任务**:
- [ ] 封装 8 个 API 调用函数
- [ ] 添加错误处理
- [ ] 添加 TypeScript 类型定义

**验收标准**:
```javascript
// 手动测试
import { getDashboardStats } from '@/api/dashboard'
const stats = await getDashboardStats({ time_window: '24h' })
console.log(stats)
```

---

#### 3.5 Dashboard 主页面实现（1 天）

**文件**: `web/src/views/dashboard/index.vue`

**任务**:
- [ ] 实现方案 A 布局（Grid 两列）
- [ ] 集成所有组件
- [ ] 实现 WebSocket 连接
- [ ] 实现 HTTP 轮询降级
- [ ] 实现响应式布局（1200px、768px 断点）

**验收标准**:
```bash
# 启动前端
cd web && pnpm dev

# 访问 http://localhost:3101/dashboard
# 验证：
# 1. 统计横幅显示正确
# 2. Log 小窗在左侧（300px）
# 3. 用户活跃度图表在右侧
# 4. WebSocket 连接成功（实时状态指示器显示"已连接"）
# 5. 响应式布局正常（调整浏览器窗口大小）
```

---

## 🧪 阶段 4：集成测试与优化（2 天）

### 目标

- ✅ 编写端到端测试
- ✅ 性能优化
- ✅ 错误处理完善
- ✅ 用户体验优化

---

### 任务清单

#### 4.1 端到端测试（1 天）

**任务**:
- [ ] 编写 Playwright 测试脚本
- [ ] 测试 Dashboard 加载
- [ ] 测试 WebSocket 实时更新
- [ ] 测试 HTTP 轮询降级
- [ ] 测试 Log 小窗交互
- [ ] 测试图表时间范围切换

**验收标准**:
```bash
# 运行 E2E 测试
cd web && pnpm test:e2e
```

---

#### 4.2 性能优化（0.5 天）

**任务**:
- [ ] 优化 WebSocket 推送频率（可配置）
- [ ] 优化日志查询性能（添加索引）
- [ ] 优化图表渲染性能（防抖）
- [ ] 优化 API 响应时间（缓存）

**验收标准**:
```bash
# 性能测试
python scripts/performance_test.py

# 验证指标：
# - WebSocket 连接延迟 < 100ms
# - 统计数据查询延迟 < 200ms
# - 日志查询延迟 < 100ms
```

---

#### 4.3 错误处理完善（0.5 天）

**任务**:
- [ ] WebSocket 断线重连
- [ ] API 调用失败处理
- [ ] 数据同步失败处理
- [ ] 日志内存溢出处理

**验收标准**:
```bash
# 错误场景测试
# 1. 断开网络 → 验证自动重连
# 2. 后端服务停止 → 验证错误提示
# 3. Supabase 连接失败 → 验证降级为本地存储
```

---

## 🚀 阶段 5：部署与监控（1 天）

### 目标

- ✅ 部署到生产环境
- ✅ 配置监控告警
- ✅ 编写运维文档

---

### 任务清单

#### 5.1 部署（0.5 天）

**任务**:
- [ ] 构建 Docker 镜像
- [ ] 部署到生产环境
- [ ] 配置环境变量
- [ ] 执行数据库迁移

**验收标准**:
```bash
# 构建 Docker 镜像
docker build -t vue-fastapi-admin:dashboard-v1 .

# 部署
docker-compose up -d

# 验证
curl https://your-domain.com/api/v1/healthz
```

---

#### 5.2 监控配置（0.5 天）

**任务**:
- [ ] 配置 Prometheus 指标收集
- [ ] 配置 Grafana 仪表盘
- [ ] 配置告警规则

**验收标准**:
```bash
# 访问 Grafana
# 验证 Dashboard 指标正常显示
```

---

## 📋 验收标准总结

### 功能验收

- [ ] 统计横幅显示 5 个指标（日活、AI 请求数、Token 使用量、API 连通性、JWT 可获取性）
- [ ] Log 小窗显示最近 100 条日志，支持级别过滤
- [ ] 用户活跃度图表支持时间范围切换（1h/24h/7d）
- [ ] WebSocket 实时推送统计数据（10 秒间隔）
- [ ] HTTP 轮询降级（WebSocket 失败时自动切换）
- [ ] 响应式布局（桌面端、平板端、移动端）

---

### 性能验收

- [ ] WebSocket 连接延迟 < 100ms
- [ ] 统计数据查询延迟 < 200ms
- [ ] 日志查询延迟 < 100ms
- [ ] 并发 WebSocket 连接数 ≥ 1000
- [ ] 数据同步延迟 < 5s

---

### 安全验收

- [ ] 匿名用户禁止访问 Dashboard
- [ ] 仅 admin 角色可查看日志
- [ ] JWT 验证正常工作
- [ ] WebSocket 连接需要 token 认证

---

## 🎯 下一步行动

**请确认以上实施计划，我将：**
1. 开始执行阶段 1（数据库与服务层）
2. 逐步完成所有阶段
3. 每个阶段完成后向您汇报进度

**请回复确认，我将立即开始代码实施。** 🚀

