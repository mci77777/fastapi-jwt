# Dashboard 重构 - 实施规格说明

**文档版本**: v1.0  
**创建时间**: 2025-01-11  
**状态**: 待实施  
**目标方案**: 方案 A（左侧 Log 小窗布局）

---

## 📋 文档目的

本文档提供 Dashboard 重构的详细技术规格，基于架构设计文档（`ARCHITECTURE_OVERVIEW.md`）。

---

## 🏗️ 后端实施规格

### 1. 核心服务层

#### 1.1 MetricsCollector - 统计数据聚合服务

**职责**: 聚合所有统计数据，提供统一接口

**实现位置**: `app/services/metrics_collector.py`

**核心方法**:
```python
class MetricsCollector:
    def __init__(self, db_manager, endpoint_monitor):
        self.db = db_manager
        self.monitor = endpoint_monitor
    
    async def aggregate_stats(self, time_window: str = "24h") -> dict:
        """聚合所有统计数据"""
        return {
            "daily_active_users": await self._get_daily_active_users(time_window),
            "ai_requests": await self._get_ai_requests(time_window),
            "token_usage": None,  # 后续追加
            "api_connectivity": await self._get_api_connectivity(),
            "jwt_availability": await self._get_jwt_availability()
        }
    
    async def _get_daily_active_users(self, time_window: str) -> int:
        """查询日活用户数"""
        start_time = self._calculate_start_time(time_window)
        result = await self.db.fetch_one("""
            SELECT COUNT(DISTINCT user_id) as total
            FROM user_activity_stats
            WHERE activity_date >= ?
        """, [start_time.date().isoformat()])
        return result['total']
```

---

#### 1.2 LogCollector - 日志收集服务

**职责**: 收集后端 Python logger 输出，提供最近日志查询

**实现位置**: `app/services/log_collector.py`

**核心方法**:
```python
from collections import deque
import logging

class LogCollector:
    def __init__(self, max_size=100):
        self.logs = deque(maxlen=max_size)
        self.handler = LogHandler(self.logs)
        logging.getLogger().addHandler(self.handler)
    
    def get_recent_logs(self, level='WARNING', limit=100):
        """获取最近日志"""
        level_map = {'ERROR': 40, 'WARNING': 30, 'INFO': 20}
        min_level = level_map.get(level, 30)
        
        filtered = [
            log for log in self.logs 
            if log['level_num'] >= min_level
        ]
        return filtered[:limit]

class LogHandler(logging.Handler):
    def __init__(self, logs_deque):
        super().__init__()
        self.logs = logs_deque
    
    def emit(self, record):
        self.logs.append({
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'level_num': record.levelno,
            'user_id': getattr(record, 'user_id', None),
            'message': record.getMessage()
        })
```

---

#### 1.3 DashboardBroker - WebSocket 推送服务

**职责**: 管理 WebSocket 连接，定时推送统计数据

**实现位置**: `app/services/dashboard_broker.py`

**核心方法**:
```python
class DashboardBroker:
    def __init__(self, metrics_collector):
        self.collector = metrics_collector
        self.connections = {}  # {user_id: WebSocket}
    
    async def add_connection(self, user_id: str, websocket: WebSocket):
        """添加连接"""
        self.connections[user_id] = websocket
    
    async def remove_connection(self, user_id: str):
        """移除连接"""
        self.connections.pop(user_id, None)
    
    async def get_dashboard_stats(self) -> dict:
        """获取 Dashboard 统计数据"""
        return await self.collector.aggregate_stats()
```

---

#### 1.4 SyncService - 数据同步服务

**职责**: 定时同步 SQLite 数据到 Supabase

**实现位置**: `app/services/sync_service.py`

**核心方法**:
```python
class SyncService:
    def __init__(self, sqlite_manager, supabase_client):
        self.sqlite = sqlite_manager
        self.supabase = supabase_client
        self.last_sync_time = None
    
    async def sync_dashboard_stats(self):
        """同步 dashboard_stats 表"""
        # 1. 查询最近 1 小时数据
        data = await self.sqlite.fetch_all("""
            SELECT * FROM dashboard_stats
            WHERE updated_at > ?
        """, [self.last_sync_time or datetime.now() - timedelta(hours=1)])
        
        # 2. 批量插入 Supabase
        if data:
            await self.supabase.table('dashboard_stats').insert([
                {
                    'stat_type': row['stat_type'],
                    'stat_value': row['stat_value'],
                    'stat_metadata': row['stat_metadata'],
                    'time_window': row['time_window'],
                    'source': 'local_sqlite',
                    'created_at': row['created_at']
                }
                for row in data
            ]).execute()
        
        # 3. 更新同步时间
        self.last_sync_time = datetime.now()
```

---

### 2. API 端点设计

#### 2.1 WebSocket 端点

**路径**: `/ws/dashboard`  
**文件**: `app/api/v1/dashboard.py`

**实现**:
```python
@router.websocket("/ws/dashboard")
async def dashboard_websocket(
    websocket: WebSocket,
    token: str,
    request: Request
):
    # JWT 验证
    user = await get_current_user_ws(token)
    if not user or user.user_type == 'anonymous':
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    await websocket.accept()
    broker = request.app.state.dashboard_broker
    await broker.add_connection(user.user_id, websocket)
    
    try:
        while True:
            stats = await broker.get_dashboard_stats()
            await websocket.send_json({
                "type": "stats_update",
                "data": stats,
                "timestamp": datetime.utcnow().isoformat()
            })
            await asyncio.sleep(10)
    except WebSocketDisconnect:
        pass
    finally:
        await broker.remove_connection(user.user_id)
```

---

#### 2.2 REST API 端点

**文件**: `app/api/v1/stats.py`

**端点列表**:
1. `GET /api/v1/stats/dashboard` - 聚合统计数据
2. `GET /api/v1/stats/daily-active-users` - 日活用户数
3. `GET /api/v1/stats/ai-requests` - AI 请求统计
4. `GET /api/v1/stats/api-connectivity` - API 连通性
5. `GET /api/v1/stats/jwt-availability` - JWT 可获取性
6. `GET /api/v1/logs/recent` - 最近日志
7. `GET /api/v1/stats/config` - 配置查询
8. `PUT /api/v1/stats/config` - 配置更新

**详细设计见架构文档 `ARCHITECTURE_OVERVIEW.md`**

---

### 3. 数据库表结构

#### 3.1 SQLite 表（3 张）

1. **dashboard_stats** - 统计数据缓存表
2. **user_activity_stats** - 用户活跃度统计表
3. **ai_request_stats** - AI 请求统计表

**详细 SQL 见架构文档 `ARCHITECTURE_OVERVIEW.md`**

---

#### 3.2 Supabase 表（1 张）

**dashboard_stats** - 远端备份表

**详细 SQL 见架构文档 `ARCHITECTURE_OVERVIEW.md`**

---

### 4. 数据写入时机

#### 4.1 用户活跃度记录

**触发时机**: 每次 JWT 验证成功时

**实现位置**: `app/auth/dependencies.py::get_current_user()`

**代码**:
```python
async def get_current_user(request: Request, ...):
    # ... JWT 验证逻辑 ...
    
    # 记录用户活跃度
    await record_user_activity(
        user_id=user.user_id,
        user_type=user.user_type
    )
    
    return user

async def record_user_activity(user_id: str, user_type: str):
    """记录用户活跃度"""
    db = get_db()
    today = datetime.now().date().isoformat()
    
    await db.execute("""
        INSERT INTO user_activity_stats (user_id, user_type, activity_date, request_count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(user_id, activity_date) 
        DO UPDATE SET 
            request_count = request_count + 1,
            last_request_at = CURRENT_TIMESTAMP
    """, [user_id, user_type, today])
```

---

#### 4.2 AI 请求记录

**触发时机**: 每次 AI 请求完成时

**实现位置**: `app/api/v1/messages.py::create_message()`

**代码**:
```python
async def create_message(...):
    # ... AI 请求逻辑 ...
    
    # 记录 AI 请求统计
    await record_ai_request(
        user_id=user.user_id,
        endpoint_id=endpoint.id,
        model=model_name,
        latency_ms=latency,
        success=success
    )

async def record_ai_request(user_id, endpoint_id, model, latency_ms, success):
    """记录 AI 请求统计"""
    db = get_db()
    today = datetime.now().date().isoformat()
    
    await db.execute("""
        INSERT INTO ai_request_stats 
        (user_id, endpoint_id, model, request_date, count, total_latency_ms, success_count, error_count)
        VALUES (?, ?, ?, ?, 1, ?, ?, ?)
        ON CONFLICT(user_id, endpoint_id, model, request_date)
        DO UPDATE SET
            count = count + 1,
            total_latency_ms = total_latency_ms + ?,
            success_count = success_count + ?,
            error_count = error_count + ?,
            updated_at = CURRENT_TIMESTAMP
    """, [
        user_id, endpoint_id, model, today, latency_ms,
        1 if success else 0, 0 if success else 1,
        latency_ms, 1 if success else 0, 0 if success else 1
    ])
```

---

## 🎨 前端实施规格

### 5. Vue 组件设计

#### 5.1 组件列表

**新增组件（6 个）**:
1. `StatsBanner.vue` - 统计横幅
2. `LogWindow.vue` - Log 小窗
3. `UserActivityChart.vue` - 用户活跃度图表
4. `WebSocketClient.vue` - WebSocket 客户端封装
5. `PollingConfig.vue` - 轮询间隔配置
6. `RealTimeIndicator.vue` - 实时状态指示器

**修改组件（3 个）**:
1. `dashboard/index.vue` - 整合新组件
2. `layout/sidebar/index.vue` - 新增 Log 小窗入口
3. `api/index.js` - 新增统计 API 封装

---

#### 5.2 StatsBanner.vue - 统计横幅

**路径**: `web/src/components/dashboard/StatsBanner.vue`

**Props**:
```typescript
interface Stat {
  id: number
  icon: string
  label: string
  value: string | number
  trend: number
  color: string
  detail?: string
}

interface Props {
  stats: Stat[]
  loading?: boolean
}
```

**Events**:
- `stat-click(stat: Stat)` - 点击统计卡片

---

#### 5.3 LogWindow.vue - Log 小窗

**路径**: `web/src/components/dashboard/LogWindow.vue`

**Props**:
```typescript
interface Log {
  id: number
  timestamp: string
  level: 'ERROR' | 'WARNING' | 'INFO'
  message: string
  user_id?: string
}

interface Props {
  logs: Log[]
  loading?: boolean
}
```

**Events**:
- `log-click(log: Log)` - 点击日志（复制到剪贴板）
- `filter-change(level: string)` - 切换日志级别过滤

---

#### 5.4 UserActivityChart.vue - 用户活跃度图表

**路径**: `web/src/components/dashboard/UserActivityChart.vue`

**Props**:
```typescript
interface Props {
  timeRange: '1h' | '24h' | '7d'
  loading?: boolean
}
```

**Events**:
- `time-range-change(range: string)` - 切换时间范围

**实现**:
```vue
<script setup>
import { ref, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<Props>()
const emit = defineEmits(['time-range-change'])

const chartRef = ref(null)
let chart = null

onMounted(() => {
  chart = echarts.init(chartRef.value)
  updateChart()
})

watch(() => props.timeRange, () => {
  updateChart()
})

function updateChart() {
  // ECharts 配置...
}
</script>
```

---

#### 5.5 WebSocketClient.vue - WebSocket 客户端

**路径**: `web/src/components/dashboard/WebSocketClient.vue`

**Props**:
```typescript
interface Props {
  url: string
  token: string
  autoReconnect?: boolean
  maxReconnectAttempts?: number
}
```

**Events**:
- `message(data: any)` - 收到消息
- `connected()` - 连接成功
- `disconnected()` - 连接断开
- `error(error: Error)` - 连接错误

**实现**:
```vue
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = withDefaults(defineProps<Props>(), {
  autoReconnect: true,
  maxReconnectAttempts: 3
})

const emit = defineEmits(['message', 'connected', 'disconnected', 'error'])

let ws = null
let reconnectAttempts = 0

function connect() {
  ws = new WebSocket(`${props.url}?token=${props.token}`)
  
  ws.onopen = () => {
    reconnectAttempts = 0
    emit('connected')
  }
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    emit('message', data)
  }
  
  ws.onerror = (error) => {
    emit('error', error)
  }
  
  ws.onclose = () => {
    emit('disconnected')
    
    if (props.autoReconnect && reconnectAttempts < props.maxReconnectAttempts) {
      reconnectAttempts++
      setTimeout(connect, 2000 * reconnectAttempts)
    }
  }
}

onMounted(() => {
  connect()
})

onBeforeUnmount(() => {
  if (ws) {
    ws.close()
  }
})
</script>
```

---

### 6. API 调用封装

**文件**: `web/src/api/dashboard.js`

```javascript
import http from '@/utils/http'

export function getDashboardStats(params) {
  return http.get('/api/v1/stats/dashboard', { params })
}

export function getDailyActiveUsers(params) {
  return http.get('/api/v1/stats/daily-active-users', { params })
}

export function getAiRequests(params) {
  return http.get('/api/v1/stats/ai-requests', { params })
}

export function getApiConnectivity() {
  return http.get('/api/v1/stats/api-connectivity')
}

export function getJwtAvailability() {
  return http.get('/api/v1/stats/jwt-availability')
}

export function getRecentLogs(params) {
  return http.get('/api/v1/logs/recent', { params })
}

export function getStatsConfig() {
  return http.get('/api/v1/stats/config')
}

export function updateStatsConfig(data) {
  return http.put('/api/v1/stats/config', data)
}
```

---

### 7. Dashboard 主页面实现

**文件**: `web/src/views/dashboard/index.vue`

**布局结构（方案 A）**:
```vue
<template>
  <div class="dashboard-container">
    <!-- 实时状态指示器 -->
    <RealTimeIndicator :status="connectionStatus" />
    
    <!-- 统计横幅 -->
    <StatsBanner :stats="stats" :loading="statsLoading" @stat-click="handleStatClick" />
    
    <!-- 主内容区（Grid 两列布局）-->
    <div class="main-content">
      <!-- Log 小窗（左侧，300px）-->
      <LogWindow 
        :logs="logs" 
        :loading="logsLoading"
        @log-click="handleLogClick"
        @filter-change="handleLogFilterChange"
      />
      
      <!-- 用户管理中心（右侧，剩余空间）-->
      <div class="user-center">
        <UserActivityChart 
          :time-range="timeRange"
          @time-range-change="handleTimeRangeChange"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.main-content {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 20px;
  height: calc(100vh - 240px);
}

@media (max-width: 1200px) {
  .main-content {
    grid-template-columns: 250px 1fr;
  }
}

@media (max-width: 768px) {
  .main-content {
    grid-template-columns: 1fr;
    height: auto;
  }
}
</style>
```

---

## 📋 下一步

请查看 `IMPLEMENTATION_PLAN.md` 了解分阶段实施计划。

