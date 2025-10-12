# GymBro 前端调试指南 - Chrome DevTools 使用手册

> 全栈 RBAC 管理平台的前端调试完整指南  
> 技术栈: Vue 3.3 + Vite 4 + Naive UI 2.x + Pinia + Vue Router

---

## 📋 目录

1. [工具概览](#1-工具概览)
2. [快速开始](#2-快速开始)
3. [常见调试场景](#3-常见调试场景)
4. [工具参考](#4-工具参考)
5. [最佳实践](#5-最佳实践)
6. [故障排查](#6-故障排查)

---

## 1. 工具概览

### 1.1 Chrome DevTools 核心面板

| 面板 | 用途 | 快捷键 |
|------|------|--------|
| **Elements** | 检查 DOM 结构、CSS 样式、事件监听器 | `Ctrl+Shift+C` |
| **Console** | 查看日志、执行 JavaScript、调试错误 | `Ctrl+Shift+J` |
| **Sources** | 断点调试、查看源代码、本地覆盖 | `Ctrl+Shift+I` |
| **Network** | 监控 HTTP 请求、查看响应、分析性能 | `Ctrl+Shift+I` → Network |
| **Performance** | 记录页面加载、分析渲染性能、查找瓶颈 | `Ctrl+Shift+I` → Performance |
| **Application** | 查看 LocalStorage、Cookie、IndexedDB | `Ctrl+Shift+I` → Application |
| **Vue DevTools** | 检查 Vue 组件树、Pinia 状态、路由 | 需安装扩展 |

### 1.2 项目特定调试工具

| 工具 | 路径 | 用途 |
|------|------|------|
| **测试 JWT 生成器** | `scripts/create_test_jwt.py` | 生成测试用户 token |
| **API 测试脚本** | `scripts/test_phase2_api.py` | 测试后端 API 端点 |
| **路由检查脚本** | `scripts/check_routes.py` | 验证路由注册 |
| **健康检查** | `http://localhost:9999/api/v1/healthz` | 后端服务状态 |
| **API 文档** | `http://localhost:9999/docs` | Swagger UI |

---

## 2. 快速开始

### 2.1 启动开发环境

```powershell
# 方式 1: 一键启动（推荐）
.\start-dev.ps1

# 方式 2: 手动启动
# 终端 1 - 后端
python run.py

# 终端 2 - 前端
cd web
pnpm dev
```

**预期输出**:
```
========================================
 Development Environment Ready!
========================================

Access URLs:
  Frontend:  http://localhost:3101
  Backend:   http://localhost:9999
  API Docs:  http://localhost:9999/docs
```

### 2.2 打开 Chrome DevTools

1. 访问 `http://localhost:3101`
2. 按 `F12` 或 `Ctrl+Shift+I` 打开 DevTools
3. 推荐布局: 右侧停靠（Dock side: right）

### 2.3 安装 Vue DevTools 扩展

```bash
# Chrome 扩展商店搜索: "Vue.js devtools"
# 或访问: https://chrome.google.com/webstore/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd
```

---

## 3. 常见调试场景

### 场景 1: 调试登录失败问题

#### 问题描述
用户点击登录按钮后，页面无响应或显示错误提示。

#### 调试步骤

**步骤 1: 检查网络请求**

1. 打开 **Network** 面板
2. 勾选 **Preserve log**（保留日志）
3. 过滤器输入: `access_token`
4. 点击登录按钮
5. 查看 `POST /api/v1/base/access_token` 请求

**预期正常响应**:
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer"
  }
}
```

**常见错误**:
- **401 Unauthorized**: 用户名或密码错误
- **500 Internal Server Error**: 后端服务异常
- **CORS Error**: 跨域配置问题（检查 `web/vite.config.js` 的 proxy 配置）

**步骤 2: 检查控制台错误**

打开 **Console** 面板，查找红色错误信息：

```javascript
// 示例错误 1: API 调用失败
Error: Request failed with status code 401
  at createError (axios.js:123)
  at settle (axios.js:456)

// 示例错误 2: Pinia store 未初始化
Uncaught TypeError: Cannot read properties of undefined (reading 'userInfo')
  at useUserStore (user.js:45)
```

**步骤 3: 检查 Pinia 状态**

使用 **Vue DevTools** → **Pinia** 面板：

1. 查看 `user` store 的 `userInfo` 状态
2. 检查 `token` 是否正确存储
3. 验证 `isLogin` 计算属性

**步骤 4: 使用脚本调试**

在 **Console** 中执行：

```javascript
// 检查 token 存储
localStorage.getItem('token')

// 检查 Pinia store
const userStore = window.__PINIA__.state.value.user
console.log('User Info:', userStore.userInfo)
console.log('Token:', userStore.token)

// 手动调用登录 API
const response = await fetch('http://localhost:9999/api/v1/base/access_token', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'admin', password: 'admin123' })
})
console.log(await response.json())
```

#### 解决方案

**问题 1: Token 未存储**
```javascript
// 检查 web/src/store/modules/user.js
async login(userInfo) {
  const res = await fetchLogin(userInfo)
  if (res.code === 200) {
    this.token = res.data.access_token  // ✅ 确保赋值
    localStorage.setItem('token', this.token)  // ✅ 持久化
  }
}
```

**问题 2: 请求拦截器未添加 token**
```javascript
// 检查 web/src/utils/http/index.js
request.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`  // ✅ 添加 header
  }
  return config
})
```

---

### 场景 2: 调试页面加载缓慢

#### 问题描述
首次访问页面或路由切换时，加载时间超过 3 秒。

#### 调试步骤

**步骤 1: 记录性能分析**

1. 打开 **Performance** 面板
2. 点击 **Record** 按钮（圆形图标）
3. 刷新页面 (`Ctrl+R`)
4. 等待页面完全加载后，点击 **Stop**

**步骤 2: 分析性能报告**

查看关键指标：
- **FCP (First Contentful Paint)**: 首次内容绘制 < 1.8s
- **LCP (Largest Contentful Paint)**: 最大内容绘制 < 2.5s
- **TTI (Time to Interactive)**: 可交互时间 < 3.8s

**步骤 3: 查看网络瀑布图**

打开 **Network** 面板：

1. 按 **Size** 列排序，找出大文件
2. 按 **Time** 列排序，找出慢请求
3. 查看 **Waterfall** 列，识别阻塞资源

**常见瓶颈**:
```
vendor.js (2.5 MB)  ← 第三方库过大
main.css (500 KB)   ← CSS 未压缩
/api/v1/user/info (3.2s)  ← 后端响应慢
```

**步骤 4: 使用 Coverage 工具**

1. 打开 **Coverage** 面板 (`Ctrl+Shift+P` → "Show Coverage")
2. 点击 **Record**
3. 刷新页面
4. 查看未使用的 CSS/JS 代码百分比

#### 解决方案

**优化 1: 代码分割**
```javascript
// web/src/router/index.js
const routes = [
  {
    path: '/dashboard',
    component: () => import('@/views/dashboard/index.vue')  // ✅ 懒加载
  }
]
```

**优化 2: 压缩资源**
```javascript
// web/vite.config.js
export default defineConfig({
  build: {
    minify: 'terser',  // ✅ 启用压缩
    terserOptions: {
      compress: { drop_console: true }  // ✅ 移除 console
    }
  }
})
```

**优化 3: 使用 CDN**
```html
<!-- web/index.html -->
<script src="https://cdn.jsdelivr.net/npm/vue@3.3.4/dist/vue.global.prod.js"></script>
```

---

### 场景 3: 调试 Vue 组件状态

#### 问题描述
组件数据未正确更新，或响应式失效。

#### 调试步骤

**步骤 1: 使用 Vue DevTools**

1. 打开 **Vue DevTools** 扩展
2. 选择 **Components** 面板
3. 在组件树中找到目标组件
4. 查看 **data**、**computed**、**props** 值

**步骤 2: 检查响应式丢失**

在 **Console** 中执行：

```javascript
// 检查组件实例
const app = document.querySelector('#app').__vueParentComponent
console.log(app.ctx)

// 检查 ref 是否正确解包
import { toRaw } from 'vue'
const rawData = toRaw(yourReactiveObject)
console.log(rawData)
```

**步骤 3: 监听数据变化**

```javascript
// 在组件中添加 watch
watch(() => userStore.userInfo, (newVal, oldVal) => {
  console.log('User info changed:', { newVal, oldVal })
}, { deep: true })
```

**步骤 4: 检查 Pinia store**

使用 **Vue DevTools** → **Pinia** 面板：

1. 查看 store 状态树
2. 点击 **Timeline** 查看状态变更历史
3. 使用 **Edit** 按钮手动修改状态测试

#### 解决方案

**问题 1: 直接修改 props**
```vue
<!-- ❌ 错误 -->
<script setup>
const props = defineProps(['user'])
props.user.name = 'New Name'  // 不允许
</script>

<!-- ✅ 正确 -->
<script setup>
import { ref, watch } from 'vue'
const props = defineProps(['user'])
const localUser = ref({ ...props.user })
watch(() => props.user, (newVal) => {
  localUser.value = { ...newVal }
})
</script>
```

**问题 2: 响应式丢失**
```javascript
// ❌ 错误: 解构丢失响应式
const { userInfo } = useUserStore()

// ✅ 正确: 使用 storeToRefs
import { storeToRefs } from 'pinia'
const { userInfo } = storeToRefs(useUserStore())
```

---

### 场景 4: 调试 API 调用失败

#### 问题描述
前端调用后端 API 时返回 401/403/500 错误。

#### 调试步骤

**步骤 1: 检查请求详情**

1. 打开 **Network** 面板
2. 点击失败的请求
3. 查看 **Headers** 标签页

**检查项**:
```
Request URL: http://localhost:9999/api/v1/stats/dashboard
Request Method: GET
Status Code: 401 Unauthorized

Request Headers:
  Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  ← 检查 token
  Content-Type: application/json

Response Headers:
  X-Trace-ID: abc123-def456  ← 用于后端日志追踪
```

**步骤 2: 查看响应体**

点击 **Response** 标签页：

```json
{
  "status": 401,
  "code": "token_expired",
  "message": "Token has expired",
  "trace_id": "abc123-def456",
  "hint": "Please login again"
}
```

**步骤 3: 使用 cURL 复现**

复制为 cURL 命令（右键 → Copy → Copy as cURL）：

```bash
curl 'http://localhost:9999/api/v1/stats/dashboard' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' \
  -H 'Content-Type: application/json'
```

**步骤 4: 检查后端日志**

使用 `trace_id` 在后端日志中搜索：

```bash
# 后端终端输出
2025-10-12 08:45:23 - ERROR - [abc123-def456] JWT token expired
```

#### 解决方案

**问题 1: Token 过期**
```javascript
// web/src/utils/http/index.js
response.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      const userStore = useUserStore()
      userStore.logout()  // ✅ 清除状态
      router.push('/login')  // ✅ 跳转登录
    }
    return Promise.reject(error)
  }
)
```

**问题 2: CORS 错误**
```javascript
// web/vite.config.js
export default defineConfig({
  server: {
    proxy: {
      '/api/v1': {
        target: 'http://localhost:9999',
        changeOrigin: true,  // ✅ 修改 Origin header
        rewrite: path => path  // ✅ 不重写路径
      }
    }
  }
})
```

**问题 3: 请求体格式错误**
```javascript
// ❌ 错误: 发送字符串
fetch('/api/v1/login', {
  body: '{"username":"admin"}'
})

// ✅ 正确: 使用 JSON.stringify
fetch('/api/v1/login', {
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'admin' })
})
```

---

## 4. 工具参考

### 4.1 Network 面板常用功能

| 功能 | 操作 | 用途 |
|------|------|------|
| **过滤请求** | 输入框输入关键词 | 只显示匹配的请求 |
| **保留日志** | 勾选 Preserve log | 页面跳转后保留请求记录 |
| **禁用缓存** | 勾选 Disable cache | 强制重新加载资源 |
| **限速模拟** | Throttling 下拉菜单 | 模拟慢速网络（Slow 3G/Fast 3G） |
| **复制请求** | 右键 → Copy | 复制为 cURL/Fetch/PowerShell |
| **重放请求** | 右键 → Replay XHR | 重新发送请求 |

### 4.2 Console 面板常用命令

```javascript
// 1. 查看全局对象
console.log(window.__PINIA__)  // Pinia store
console.log(window.$router)    // Vue Router
console.log(window.$message)   // Naive UI message

// 2. 清除控制台
console.clear()

// 3. 分组日志
console.group('API Calls')
console.log('Request 1')
console.log('Request 2')
console.groupEnd()

// 4. 表格显示
console.table([
  { name: 'Alice', age: 25 },
  { name: 'Bob', age: 30 }
])

// 5. 性能计时
console.time('API Call')
await fetch('/api/v1/data')
console.timeEnd('API Call')  // API Call: 123.45ms
```

### 4.3 Sources 面板断点调试

| 断点类型 | 设置方法 | 用途 |
|----------|----------|------|
| **行断点** | 点击行号 | 在特定代码行暂停 |
| **条件断点** | 右键行号 → Add conditional breakpoint | 满足条件时暂停 |
| **DOM 断点** | Elements 面板右键元素 → Break on | DOM 变化时暂停 |
| **XHR 断点** | Sources 面板 → XHR Breakpoints | 特定 URL 请求时暂停 |
| **事件监听器断点** | Sources 面板 → Event Listener Breakpoints | 特定事件触发时暂停 |

---

## 5. 最佳实践

### 5.1 调试前的准备

1. **启用 Source Maps**: 确保 `vite.config.js` 中 `build.sourcemap = true`
2. **禁用浏览器扩展**: 避免扩展干扰（使用无痕模式）
3. **清除缓存**: `Ctrl+Shift+Delete` 清除浏览器缓存
4. **使用测试数据**: 使用 `scripts/create_test_jwt.py` 生成测试 token

### 5.2 高效调试技巧

**技巧 1: 使用 `debugger` 语句**
```javascript
// 在代码中插入断点
async function fetchData() {
  debugger  // ← 执行到此处会自动暂停
  const res = await api.getData()
  return res
}
```

**技巧 2: 使用 `$0` 引用选中元素**
```javascript
// 在 Elements 面板选中元素后
$0  // 当前选中的 DOM 元素
$0.__vueParentComponent  // 元素对应的 Vue 组件
```

**技巧 3: 使用 `copy()` 复制数据**
```javascript
const data = { name: 'Alice', age: 25 }
copy(data)  // 复制到剪贴板
```

**技巧 4: 使用 `monitor()` 监听函数调用**
```javascript
monitor(console.log)  // 监听 console.log 调用
// 每次调用时会输出: function console.log called with arguments: ...
```

### 5.3 性能优化检查清单

- [ ] 首屏加载时间 < 3 秒
- [ ] 路由切换时间 < 500ms
- [ ] API 响应时间 < 1 秒
- [ ] 未使用代码 < 30%
- [ ] 图片使用 WebP 格式
- [ ] 启用 Gzip/Brotli 压缩
- [ ] 使用 CDN 加载第三方库
- [ ] 懒加载非首屏组件

---

## 6. 故障排查

### 6.1 常见问题

**问题 1: 页面白屏**

**症状**: 访问 `http://localhost:3101` 显示空白页面

**排查步骤**:
1. 打开 Console 查看错误信息
2. 检查 Network 面板是否有 404 错误
3. 检查 `web/index.html` 是否正确加载
4. 检查 Vite 服务器是否正常运行

**解决方案**:
```bash
# 清除缓存并重启
cd web
rm -rf node_modules/.vite
pnpm dev
```

**问题 2: API 请求 CORS 错误**

**症状**: Console 显示 `Access-Control-Allow-Origin` 错误

**排查步骤**:
1. 检查 `web/vite.config.js` 的 proxy 配置
2. 检查后端 CORS 中间件配置
3. 确认请求 URL 是否正确（应为 `/api/v1/*` 而非 `http://localhost:9999/api/v1/*`）

**解决方案**:
```javascript
// web/vite.config.js
export default defineConfig({
  server: {
    proxy: {
      '/api/v1': {
        target: 'http://localhost:9999',
        changeOrigin: true
      }
    }
  }
})
```

**问题 3: Vue DevTools 无法检测到 Vue**

**症状**: Vue DevTools 显示 "Vue.js not detected"

**排查步骤**:
1. 确认 Vue DevTools 扩展已安装并启用
2. 检查页面是否使用生产环境构建（生产环境需要特殊配置）
3. 刷新页面并重新打开 DevTools

**解决方案**:
```javascript
// web/src/main.js
const app = createApp(App)
app.config.devtools = true  // ✅ 启用 DevTools
```

### 6.2 紧急调试命令

```bash
# 1. 快速重启前端（清除缓存）
cd web && rm -rf node_modules/.vite && pnpm dev

# 2. 快速重启后端（清除 Python 缓存）
Get-ChildItem -Path . -Include __pycache__ -Recurse -Force | Remove-Item -Force -Recurse
python run.py

# 3. 生成测试 JWT token
python scripts/create_test_jwt.py

# 4. 测试后端 API
python scripts/test_phase2_api.py

# 5. 检查端口占用
netstat -ano | Select-String ":3101 "
netstat -ano | Select-String ":9999 "
```

---

## 附录: 项目特定配置

### A.1 前端代理配置

```javascript
// web/vite.config.js
export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 3101,
    strictPort: true,
    proxy: {
      '/api/v1': {
        target: 'http://localhost:9999',
        changeOrigin: true,
        rewrite: path => path
      }
    }
  }
})
```

### A.2 后端 CORS 配置

```python
# app/core/application.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3101"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### A.3 JWT 认证流程

```mermaid
sequenceDiagram
    participant F as Frontend
    participant B as Backend
    participant DB as Database
    
    F->>B: POST /api/v1/base/access_token
    B->>DB: 验证用户名密码
    DB-->>B: 用户信息
    B-->>F: JWT token
    F->>F: 存储 token 到 localStorage
    F->>B: GET /api/v1/stats/dashboard (Header: Authorization)
    B->>B: 验证 JWT token
    B-->>F: 统计数据
```

---

## 📚 参考资源

- [Chrome DevTools 官方文档](https://developer.chrome.com/docs/devtools/)
- [Vue.js DevTools 使用指南](https://devtools.vuejs.org/)
- [Vite 调试指南](https://vitejs.dev/guide/troubleshooting.html)
- [Naive UI 组件库文档](https://www.naiveui.com/)
- [项目架构文档](./PROJECT_OVERVIEW.md)
- [JWT 硬化指南](./JWT_HARDENING_GUIDE.md)

---

## 附录 B: 自动化调试脚本

### B.1 前端诊断脚本

项目提供了 `scripts/debug_frontend.py` 脚本用于自动化调试任务。

**使用方法**:

```bash
# 1. 完整诊断（推荐）
python scripts/debug_frontend.py

# 2. 仅检查服务状态
python scripts/debug_frontend.py check

# 3. 测试 API 端点（需要 token）
python scripts/debug_frontend.py test <token>

# 4. 检查网络性能
python scripts/debug_frontend.py perf

# 5. 生成测试 token
python scripts/debug_frontend.py token
```

**输出示例**:

```
============================================================
前端调试诊断报告
时间: 2025-10-12 09:01:31
============================================================

检查服务状态
============================================================
✅ 前端服务: http://localhost:3101 - 200
✅ 后端服务: http://localhost:9999 - 200
✅ 后端健康检查: {'status': 'ok', 'service': 'GymBro API'}

检查网络性能
============================================================
✅ http://localhost:3101/
   状态码: 200
   响应时间: 3.82ms
   内容大小: 1420 bytes

测试 API 端点
============================================================
✅ GET /api/v1/healthz - 200 (1.67ms)
✅ GET /api/v1/stats/dashboard - 200 (5.37ms)
✅ GET /api/v1/stats/daily-active-users - 200 (2.51ms)

诊断总结
============================================================
前端服务: ✅ 正常
后端服务: ✅ 正常
健康检查: ✅ 正常
API 测试: 3/4 通过
平均响应时间: 2.59ms

📄 完整报告已保存到: debug_report_20251012_090135.json
```

**报告文件格式**:

```json
{
  "timestamp": "2025-10-12T09:01:35.123456",
  "service_status": {
    "frontend": { "url": "http://localhost:3101", "status": "running", "status_code": 200 },
    "backend": { "url": "http://localhost:9999", "status": "running", "status_code": 200 },
    "backend_health": { "status": "healthy", "data": { "status": "ok", "service": "GymBro API" } }
  },
  "network_performance": {
    "tests": [
      { "url": "http://localhost:3101/", "status_code": 200, "response_time_ms": 3.82, "content_length": 1420 }
    ]
  },
  "api_tests": [
    { "method": "GET", "path": "/api/v1/healthz", "status_code": 200, "status": "success", "response_time_ms": 1.67 }
  ],
  "summary": {
    "frontend_ok": true,
    "backend_ok": true,
    "health_ok": true,
    "api_success_rate": "3/4",
    "avg_response_time_ms": 2.59
  }
}
```

### B.2 其他调试脚本

| 脚本 | 用途 | 命令 |
|------|------|------|
| `create_test_jwt.py` | 生成测试 JWT token | `python scripts/create_test_jwt.py` |
| `test_phase2_api.py` | 测试 Dashboard API | `python scripts/test_phase2_api.py` |
| `check_routes.py` | 检查路由注册 | `python scripts/check_routes.py` |
| `verify_supabase_config.py` | 验证 Supabase 配置 | `python scripts/verify_supabase_config.py` |

---

**最后更新**: 2025-10-12
**维护者**: GymBro 开发团队

