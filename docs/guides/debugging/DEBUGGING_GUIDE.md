# GymBro 前端调试完整指南

> 基于 Chrome DevTools 的实战调试手册  
> 技术栈: Vue 3.3 + Vite 4 + Naive UI 2.x + Pinia + Vue Router

**文档来源**：合并自以下文档
- `CHROME_DEVTOOLS_DEBUG_GUIDE.md` - Chrome DevTools 使用手册（431 行）
- `DEBUG_QUICK_REFERENCE.md` - 快速参考卡片（263 行）
- `DEBUG_TOOLS_SUMMARY.md` - 工具总结（334 行）

---

## 📋 目录

1. [快速开始](#1-快速开始)
2. [Chrome DevTools 工具速查](#2-chrome-devtools-工具速查)
3. [常用调试命令](#3-常用调试命令)
4. [实战调试场景](#4-实战调试场景)
5. [自动化调试工具](#5-自动化调试工具)
6. [故障排查](#6-故障排查)
7. [最佳实践](#7-最佳实践)

---

## 1. 快速开始

### 1.1 启动开发环境

```powershell
# 一键启动前后端（推荐）
.\start-dev.ps1

# 手动启动
python run.py              # 后端 (终端 1) - 端口 9999
cd web && pnpm dev         # 前端 (终端 2) - 端口 3101
```

**访问地址**:
- 前端: http://localhost:3101
- 后端: http://localhost:9999
- API 文档: http://localhost:9999/docs

### 1.2 前提条件

✅ 开发环境已启动（前端 3101 + 后端 9999）  
✅ 用户已登录（admin 账户）  
✅ Chrome DevTools 已打开（`F12`）

### 1.3 快捷键速查

| 功能 | Windows/Linux | macOS |
|------|---------------|-------|
| 打开 DevTools | `F12` 或 `Ctrl+Shift+I` | `Cmd+Option+I` |
| 元素检查器 | `Ctrl+Shift+C` | `Cmd+Shift+C` |
| 控制台 | `Ctrl+Shift+J` | `Cmd+Option+J` |
| 命令面板 | `Ctrl+Shift+P` | `Cmd+Shift+P` |
| 清除控制台 | `Ctrl+L` | `Cmd+K` |
| 刷新页面 | `Ctrl+R` | `Cmd+R` |
| 硬刷新（清缓存） | `Ctrl+Shift+R` | `Cmd+Shift+R` |

---

## 2. Chrome DevTools 工具速查

### 2.1 核心面板

| 面板 | 用途 | 快捷键 |
|------|------|--------|
| **Elements** | 检查 DOM 结构和 CSS 样式 | `Ctrl+Shift+C` |
| **Console** | 执行 JavaScript、查看日志 | `Ctrl+Shift+J` |
| **Sources** | 调试 JavaScript 代码、设置断点 | `Ctrl+Shift+O` |
| **Network** | 监控网络请求、查看 API 响应 | `Ctrl+Shift+E` |
| **Application** | 查看 localStorage、sessionStorage、Cookies | - |
| **Performance** | 性能分析、录制页面加载 | - |

### 2.2 MCP 工具列表

| 工具 | 用途 | 示例 |
|------|------|------|
| `list_pages_chrome-devtools` | 列出所有打开的页面 | 查看当前有哪些标签页 |
| `navigate_page_chrome-devtools` | 导航到指定 URL | 打开前端页面 |
| `take_snapshot_chrome-devtools` | 获取页面 DOM 结构 | 查看页面元素树 |
| `take_screenshot_chrome-devtools` | 截取页面截图 | 保存当前页面视觉状态 |
| `execute_script_chrome-devtools` | 执行 JavaScript 代码 | 查询 Pinia store、修改状态 |
| `get_console_logs_chrome-devtools` | 获取控制台日志 | 查看错误和警告 |
| `get_network_logs_chrome-devtools` | 获取网络请求日志 | 分析 API 调用 |

---

## 3. 常用调试命令

### 3.1 Console 面板命令

```javascript
// 1. 查看 Pinia store
window.__PINIA__.state.value.user          // 用户状态
window.__PINIA__.state.value.permission    // 权限状态
window.__PINIA__.state.value.tags          // 标签状态

// 2. 查看 Vue Router
window.$router.currentRoute.value          // 当前路由
window.$router.getRoutes()                 // 所有路由

// 3. 查看 localStorage
localStorage.getItem('ACCESS_TOKEN')       // JWT token
localStorage.getItem('USER_INFO')          // 用户信息
localStorage.clear()                       // 清除所有数据

// 4. 查看 sessionStorage
sessionStorage.getItem('TABS_ROUTES')      // 标签页路由

// 5. 网络请求调试
fetch('/api/v1/stats/dashboard?time_window=24h', {
  headers: {
    'Authorization': 'Bearer ' + JSON.parse(localStorage.getItem('ACCESS_TOKEN')).value
  }
}).then(r => r.json()).then(console.log)

// 6. 性能监控
performance.getEntriesByType('navigation')  // 页面加载性能
performance.getEntriesByType('resource')    // 资源加载性能
```

### 3.2 Sources 面板调试

```javascript
// 1. 设置断点
// 在 Sources 面板中点击行号设置断点

// 2. 条件断点
// 右键行号 → Add conditional breakpoint
// 示例: userInfo.role === 'admin'

// 3. 监视表达式
// Watch 面板中添加表达式
// 示例: userStore.userInfo.username

// 4. 调用栈
// Call Stack 面板查看函数调用链

// 5. 作用域变量
// Scope 面板查看当前作用域的所有变量
```

### 3.3 Network 面板分析

```javascript
// 1. 过滤请求
// Filter: /api/v1/stats/dashboard
// Filter: status-code:401

// 2. 查看请求详情
// Headers: 请求头和响应头
// Preview: 格式化的响应数据
// Response: 原始响应数据
// Timing: 请求时间分析

// 3. 复制请求
// 右键请求 → Copy → Copy as fetch
// 在 Console 中粘贴并修改参数重新发送
```

---

## 4. 实战调试场景

### 场景 1: Dashboard 数据为 0

**问题**: Dashboard 显示所有数据为 0

**调试步骤**:

1. **检查 API 请求**（Network 面板）
   ```javascript
   // 查找 /api/v1/stats/dashboard 请求
   // 检查响应状态码和数据
   ```

2. **检查 token**（Console 面板）
   ```javascript
   JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value
   // 如果为空或过期，重新登录
   ```

3. **检查后端数据**（后端终端）
   ```bash
   sqlite3 db.sqlite3 "SELECT COUNT(*) FROM user_activity_stats;"
   ```

4. **手动测试 API**（Console 面板）
   ```javascript
   fetch('/api/v1/stats/dashboard?time_window=24h', {
     headers: {
       'Authorization': 'Bearer ' + JSON.parse(localStorage.getItem('ACCESS_TOKEN')).value
     }
   }).then(r => r.json()).then(console.log)
   ```

### 场景 2: 登录后跳转到 404

**问题**: 登录成功后跳转到 404 页面

**调试步骤**:

1. **检查路由配置**（Console 面板）
   ```javascript
   window.$router.getRoutes()
   // 查看是否有 /dashboard 路由
   ```

2. **检查权限路由**（Console 面板）
   ```javascript
   window.__PINIA__.state.value.permission.routes
   // 查看动态路由是否加载
   ```

3. **检查登录跳转逻辑**（Sources 面板）
   ```javascript
   // 在 web/src/views/login/index.vue 中设置断点
   // 查看 handleLogin() 函数的跳转逻辑
   ```

### 场景 3: API 请求返回 401

**问题**: API 请求返回 401 Unauthorized

**调试步骤**:

1. **检查 token**（Console 面板）
   ```javascript
   const token = JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value
   console.log('Token:', token)
   
   // 解码 JWT token
   const payload = JSON.parse(atob(token.split('.')[1]))
   console.log('Payload:', payload)
   console.log('Expired:', payload.exp < Date.now() / 1000)
   ```

2. **检查请求头**（Network 面板）
   ```javascript
   // 查看 Authorization header 是否正确
   // 应该是: Bearer <token>
   ```

3. **重新登录**（Console 面板）
   ```javascript
   localStorage.clear()
   location.reload()
   ```

### 场景 4: WebSocket 连接失败

**问题**: WebSocket 连接失败或频繁断开

**调试步骤**:

1. **检查 WebSocket 连接**（Network 面板 → WS 标签）
   ```javascript
   // 查看 WebSocket 连接状态
   // 查看发送和接收的消息
   ```

2. **检查 token**（Console 面板）
   ```javascript
   const token = JSON.parse(localStorage.getItem('ACCESS_TOKEN')||'{}').value
   console.log('Token for WebSocket:', token)
   ```

3. **手动测试 WebSocket**（Console 面板）
   ```javascript
   const ws = new WebSocket('ws://localhost:9999/api/v1/ws/dashboard')
   ws.onopen = () => console.log('WebSocket connected')
   ws.onmessage = (e) => console.log('Message:', e.data)
   ws.onerror = (e) => console.error('Error:', e)
   ws.onclose = (e) => console.log('Closed:', e.code, e.reason)
   ```

---

## 5. 自动化调试工具

### 5.1 前端诊断脚本

**命令**:
```bash
python scripts/debug_frontend.py
```

**功能**:
- ✅ 检查前后端服务状态
- ✅ 测试 API 端点连通性
- ✅ 分析性能指标
- ✅ 生成 JSON 诊断报告

**输出示例**:
```
============================================================
前端调试诊断报告
时间: 2025-10-12 09:01:31
============================================================

检查服务状态
============================================================
✅ 前端服务 (http://localhost:3101): 正常
✅ 后端服务 (http://localhost:9999): 正常

测试 API 端点
============================================================
✅ GET /api/v1/healthz: 200 OK
✅ GET /api/v1/stats/dashboard: 200 OK
✅ GET /api/v1/llm/models: 200 OK

性能分析
============================================================
📊 API 响应时间:
  - /api/v1/healthz: 15ms
  - /api/v1/stats/dashboard: 234ms
  - /api/v1/llm/models: 89ms
```

### 5.2 JWT 生成器

**命令**:
```bash
python scripts/create_test_jwt.py
```

**功能**:
- 生成测试 JWT token
- 用于 API 测试和调试

### 5.3 API 测试脚本

**命令**:
```bash
python scripts/test_monitoring_pipeline.py
```

**功能**:
- 测试所有 Dashboard API 端点
- 验证数据完整性
- 生成测试报告

---

## 6. 故障排查

### 6.1 常见问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| Dashboard 数据为 0 | 数据库无数据 | 运行 `python scripts/test_monitoring_pipeline.py` 生成测试数据 |
| 登录后跳转 404 | 动态路由未加载 | 检查 `/api/v1/base/getRouterList` 响应 |
| API 返回 401 | Token 过期或无效 | 重新登录或检查 JWT 配置 |
| WebSocket 断开 | Token 过期 | 刷新页面重新连接 |
| 页面白屏 | JavaScript 错误 | 查看 Console 面板错误信息 |
| 样式错乱 | CSS 缓存问题 | 硬刷新 `Ctrl+Shift+R` |

### 6.2 紧急修复

```bash
# 1. 清除所有缓存
localStorage.clear()
sessionStorage.clear()
location.reload()

# 2. 重启开发服务器
# 关闭所有终端，重新运行
.\start-dev.ps1

# 3. 清除浏览器缓存
# Chrome: Ctrl+Shift+Delete → 清除缓存和 Cookie

# 4. 检查端口占用
netstat -ano | findstr "3101"
netstat -ano | findstr "9999"
```

---

## 7. 最佳实践

### 7.1 调试原则

1. **先看 Console**：90% 的问题都会在 Console 中显示错误信息
2. **再看 Network**：检查 API 请求和响应
3. **最后看 Sources**：设置断点深入调试

### 7.2 性能优化

1. **使用 Performance 面板**：录制页面加载，分析性能瓶颈
2. **使用 Lighthouse**：生成性能报告和优化建议
3. **使用 Coverage**：查看未使用的 CSS 和 JavaScript

### 7.3 调试技巧

1. **使用 `debugger` 语句**：在代码中插入断点
2. **使用 `console.table()`**：格式化输出数组和对象
3. **使用 `console.time()` 和 `console.timeEnd()`**：测量代码执行时间
4. **使用 `$0` 引用**：在 Console 中引用当前选中的 DOM 元素

---

## 📚 相关文档

- **项目概览**: [docs/PROJECT_OVERVIEW.md](../../PROJECT_OVERVIEW.md)
- **API 文档**: http://localhost:9999/docs
- **脚本索引**: [docs/SCRIPTS_INDEX.md](../../SCRIPTS_INDEX.md)

---

**最后更新**: 2025-10-17  
**维护者**: GymBro Team

