# Dashboard 功能文档

> GymBro Dashboard 的功能实现和增强记录  
> 包含：API 监控、Supabase 状态、快速访问卡片

**文档来源**：合并自以下文档
- `API_MONITOR_HANDOVER.md` - API 端点健康监控功能（582 行）
- `DASHBOARD_ENHANCEMENTS_SUMMARY.md` - Dashboard 增强功能总结（283 行）

---

## 📋 目录

1. [功能概述](#1-功能概述)
2. [API 监控功能](#2-api-监控功能)
3. [Dashboard 增强功能](#3-dashboard-增强功能)
4. [技术实现](#4-技术实现)
5. [测试验证](#5-测试验证)
6. [故障排查](#6-故障排查)

---

## 1. 功能概述

### 1.1 核心功能

| 功能 | 状态 | 描述 |
|------|------|------|
| **API 监控** | ✅ 已完成 | 实时监控 API 端点健康状态 |
| **Supabase 状态** | ✅ 已完成 | 显示 Supabase 连接状态（Modal 弹窗） |
| **快速访问卡片** | ✅ 已完成 | Dashboard 快速访问入口 |
| **WebSocket 端点** | ✅ 已完成 | `/api/v1/agents` 多 Agent 对话 |
| **定时轮询** | ✅ 已完成 | 自动刷新 API 监控数据 |

### 1.2 页面结构

```
Dashboard (/dashboard)
├── 控制面板（横幅看板）
│   ├── 日活用户数
│   ├── AI 请求数
│   ├── Token 使用量
│   ├── API 连通性
│   └── JWT 连通性
├── 快速访问卡片
│   ├── API 监控
│   ├── Supabase 状态（Modal 触发按钮）
│   └── 服务器负载
└── API 监控页面 (/dashboard/api-monitor)
    ├── 端点列表
    ├── 健康状态
    ├── 响应时间
    └── 手动触发检测
```

---

## 2. API 监控功能

### 2.1 功能描述

**目标**: 实时监控所有 API 端点的健康状态，及时发现和定位问题。

**核心功能**:
- ✅ 显示所有 API 端点列表
- ✅ 实时检测端点健康状态（在线/离线）
- ✅ 显示响应时间（毫秒）
- ✅ 手动触发检测
- ✅ 定时自动刷新（30 秒）
- ✅ 支持 WebSocket 端点检测

### 2.2 监控端点清单

**配置文件**: `web/src/config/apiEndpoints.js`

```javascript
export const API_ENDPOINTS = [
  // 健康检查
  { name: 'Health Check', path: '/api/v1/healthz', method: 'GET', category: 'health' },
  { name: 'Liveness Probe', path: '/api/v1/livez', method: 'GET', category: 'health' },
  { name: 'Readiness Probe', path: '/api/v1/readyz', method: 'GET', category: 'health' },
  
  // AI 服务
  { name: 'AI Models', path: '/api/v1/llm/models', method: 'GET', category: 'ai' },
  { name: 'AI Messages', path: '/api/v1/messages', method: 'POST', category: 'ai' },
  
  // Dashboard 统计
  { name: 'Dashboard Stats', path: '/api/v1/stats/dashboard', method: 'GET', category: 'stats' },
  { name: 'Daily Active Users', path: '/api/v1/stats/daily-active-users', method: 'GET', category: 'stats' },
  { name: 'AI Requests', path: '/api/v1/stats/ai-requests', method: 'GET', category: 'stats' },
  
  // WebSocket
  { name: 'Dashboard WebSocket', path: '/api/v1/ws/dashboard', method: 'WS', category: 'websocket' },
  { name: 'Agents WebSocket', path: '/api/v1/agents', method: 'WS', category: 'websocket' },
]
```

### 2.3 页面组件

**文件**: `web/src/views/dashboard/ApiMonitor/index.vue`

**核心功能**:
```vue
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { API_ENDPOINTS } from '@/config/apiEndpoints'

const endpoints = ref([])
const loading = ref(false)
let timer = null

// 检测端点健康状态
async function checkEndpoints() {
  loading.value = true
  
  for (const endpoint of API_ENDPOINTS) {
    const startTime = Date.now()
    
    try {
      if (endpoint.method === 'WS') {
        // WebSocket 检测
        await checkWebSocket(endpoint.path)
      } else {
        // HTTP 检测
        await http.request({ url: endpoint.path, method: endpoint.method })
      }
      
      endpoints.value.push({
        ...endpoint,
        status: 'online',
        responseTime: Date.now() - startTime
      })
    } catch (error) {
      endpoints.value.push({
        ...endpoint,
        status: 'offline',
        responseTime: null,
        error: error.message
      })
    }
  }
  
  loading.value = false
}

// 定时刷新（30 秒）
onMounted(() => {
  checkEndpoints()
  timer = setInterval(checkEndpoints, 30000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div class="api-monitor">
    <n-card title="API 端点监控">
      <n-button @click="checkEndpoints" :loading="loading">
        手动检测
      </n-button>
      
      <n-data-table
        :columns="columns"
        :data="endpoints"
        :loading="loading"
      />
    </n-card>
  </div>
</template>
```

### 2.4 后端支持

**文件**: `app/api/v1/agents.py`

**WebSocket 端点**:
```python
@router.websocket("/agents")
async def agents_websocket(websocket: WebSocket):
    """多 Agent 对话 WebSocket 端点。
    
    支持：
    - 多个 Agent 同时对话
    - 实时消息推送
    - 连接状态管理
    """
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            # 处理消息
            response = await process_agent_message(data)
            await websocket.send_text(response)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
```

---

## 3. Dashboard 增强功能

### 3.1 Supabase 状态改为 Modal 弹窗

**问题**: Supabase 状态卡片占据控制面板 1/4 空间，始终显示，占用大量屏幕空间。

**解决方案**: 
- 控制面板只显示触发按钮
- 点击按钮弹出 Modal 显示详细状态
- 节省屏幕空间，提升用户体验

**实现**:
```vue
<script setup>
import { ref } from 'vue'

const showSupabaseModal = ref(false)

function openSupabaseModal() {
  showSupabaseModal.value = true
}
</script>

<template>
  <!-- 触发按钮 -->
  <n-button @click="openSupabaseModal">
    查看 Supabase 状态
  </n-button>
  
  <!-- Modal 弹窗 -->
  <n-modal v-model:show="showSupabaseModal" title="Supabase 连接状态">
    <n-card>
      <SupabaseStatusCard />
    </n-card>
  </n-modal>
</template>
```

### 3.2 快速访问卡片

**功能**: 在 Dashboard 主页添加快速访问入口，方便用户快速跳转到常用功能。

**卡片列表**:
| 卡片 | 跳转路径 | 描述 |
|------|----------|------|
| **API 监控** | `/dashboard/api-monitor` | 查看 API 端点健康状态 |
| **Supabase 状态** | Modal 弹窗 | 查看 Supabase 连接状态 |
| **服务器负载** | `/dashboard/server-load` | 查看服务器负载和性能 |

**实现**:
```vue
<template>
  <div class="quick-access-cards">
    <n-grid :cols="3" :x-gap="16">
      <!-- API 监控卡片 -->
      <n-grid-item>
        <n-card hoverable @click="$router.push('/dashboard/api-monitor')">
          <n-statistic label="API 监控" :value="onlineEndpoints">
            <template #suffix>/ {{ totalEndpoints }} 在线</template>
          </n-statistic>
        </n-card>
      </n-grid-item>
      
      <!-- Supabase 状态卡片 -->
      <n-grid-item>
        <n-card hoverable @click="openSupabaseModal">
          <n-statistic label="Supabase 状态" value="在线">
            <template #prefix>
              <n-icon :component="CheckCircle" color="green" />
            </template>
          </n-statistic>
        </n-card>
      </n-grid-item>
      
      <!-- 服务器负载卡片 -->
      <n-grid-item>
        <n-card hoverable @click="$router.push('/dashboard/server-load')">
          <n-statistic label="服务器负载" :value="serverLoad">
            <template #suffix>%</template>
          </n-statistic>
        </n-card>
      </n-grid-item>
    </n-grid>
  </div>
</template>
```

### 3.3 ServerLoadCard 集成 API 监控

**功能**: 在服务器负载卡片中集成 API 端点健康监控指标。

**显示内容**:
- 在线端点数 / 总端点数
- 平均响应时间
- "查看详情"按钮跳转到 API 监控页面

**实现**:
```vue
<script setup>
import { ref, computed } from 'vue'
import { API_ENDPOINTS } from '@/config/apiEndpoints'

const endpoints = ref([])

const onlineEndpoints = computed(() => 
  endpoints.value.filter(e => e.status === 'online').length
)

const avgResponseTime = computed(() => {
  const online = endpoints.value.filter(e => e.status === 'online')
  if (online.length === 0) return 0
  const total = online.reduce((sum, e) => sum + e.responseTime, 0)
  return Math.round(total / online.length)
})
</script>

<template>
  <n-card title="服务器负载">
    <n-statistic label="API 端点健康">
      <template #default>
        {{ onlineEndpoints }} / {{ API_ENDPOINTS.length }} 在线
      </template>
    </n-statistic>
    
    <n-statistic label="平均响应时间" :value="avgResponseTime">
      <template #suffix>ms</template>
    </n-statistic>
    
    <n-button @click="$router.push('/dashboard/api-monitor')">
      查看详情
    </n-button>
  </n-card>
</template>
```

---

## 4. 技术实现

### 4.1 新建文件清单

| 文件 | 行数 | 描述 |
|------|------|------|
| `app/api/v1/agents.py` | 200 | WebSocket 端点实现 |
| `web/src/views/dashboard/ApiMonitor/index.vue` | 457 | API 监控页面组件 |
| `web/src/config/apiEndpoints.js` | 245 | 端点配置清单 |
| `scripts/test_api_monitor.py` | 260 | 功能测试脚本 |

### 4.2 修改文件清单

| 文件 | 修改行数 | 描述 |
|------|----------|------|
| `app/api/v1/__init__.py` | +3 | 注册 agents 路由 |
| `app/api/v1/base.py` | +20 | 添加 Dashboard 子菜单 |
| `web/src/views/dashboard/index.vue` | +30 | Dashboard 增强 |
| `web/src/components/dashboard/ServerLoadCard.vue` | +100 | 集成 API 监控指标 |

### 4.3 路由配置

**后端路由**:
```python
# app/api/v1/base.py
@router.get("/getRouterList")
async def get_router_list():
    return {
        "code": 200,
        "data": [
            {
                "name": "Dashboard",
                "path": "/dashboard",
                "children": [
                    {
                        "name": "API 监控",
                        "path": "/dashboard/api-monitor",
                        "component": "dashboard/ApiMonitor/index"
                    }
                ]
            }
        ]
    }
```

**前端路由**:
```javascript
// web/src/router/index.js
{
  path: '/dashboard',
  name: 'Dashboard',
  component: () => import('@/views/dashboard/index.vue'),
  children: [
    {
      path: 'api-monitor',
      name: 'ApiMonitor',
      component: () => import('@/views/dashboard/ApiMonitor/index.vue')
    }
  ]
}
```

---

## 5. 测试验证

### 5.1 功能测试

**测试脚本**: `scripts/test_api_monitor.py`

```bash
python scripts/test_api_monitor.py
```

**测试结果**: 7/7 通过

| 测试项 | 状态 | 描述 |
|--------|------|------|
| 后端健康检查 | ✅ | `/api/v1/healthz` 返回 200 |
| API 监控页面访问 | ✅ | `/dashboard/api-monitor` 可访问 |
| WebSocket 连接 | ✅ | `/api/v1/agents` 连接成功 |
| 端点检测功能 | ✅ | 手动触发检测正常 |
| 定时刷新功能 | ✅ | 30 秒自动刷新正常 |
| Supabase Modal | ✅ | Modal 弹窗正常显示 |
| 快速访问卡片 | ✅ | 卡片跳转正常 |

### 5.2 性能测试

| 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|
| API 监控页面加载时间 | < 1s | 0.8s | ✅ |
| 端点检测时间 | < 5s | 3.2s | ✅ |
| WebSocket 连接时间 | < 500ms | 320ms | ✅ |
| 定时刷新性能影响 | < 5% CPU | 2% CPU | ✅ |

---

## 6. 故障排查

### 6.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| API 监控页面 404 | 路由配置错误 | 检查文件路径是否为 `ApiMonitor/index.vue` |
| WebSocket 连接失败 | Token 过期 | 刷新页面重新登录 |
| 端点检测超时 | 后端服务未启动 | 检查后端服务状态 |
| Supabase Modal 不显示 | 组件未正确导入 | 检查组件导入路径 |

### 6.2 调试命令

```bash
# 1. 测试 API 监控功能
python scripts/test_api_monitor.py

# 2. 测试 WebSocket 连接
# 在浏览器 Console 中执行
const ws = new WebSocket('ws://localhost:9999/api/v1/agents')
ws.onopen = () => console.log('Connected')
ws.onmessage = (e) => console.log('Message:', e.data)

# 3. 检查路由配置
curl http://localhost:9999/api/v1/base/getRouterList

# 4. 检查端点健康
curl http://localhost:9999/api/v1/healthz
```

---

## 📚 相关文档

- **项目概览**: [docs/PROJECT_OVERVIEW.md](../PROJECT_OVERVIEW.md)
- **调试指南**: [docs/guides/debugging/DEBUGGING_GUIDE.md](../guides/debugging/DEBUGGING_GUIDE.md)
- **Token 认证**: [docs/architecture/TOKEN_AUTHENTICATION.md](../architecture/TOKEN_AUTHENTICATION.md)

---

**最后更新**: 2025-10-17  
**维护者**: GymBro Team

