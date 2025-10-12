# GymBro 前端调试指南 - 实战手册

> 基于 Chrome DevTools MCP 的实战调试指南
> 技术栈: Vue 3.3 + Vite 4 + Naive UI 2.x + Pinia + Vue Router

---

## 📋 目录

1. [快速开始](#1-快速开始)
2. [Chrome DevTools MCP 工具速查](#2-chrome-devtools-mcp-工具速查)
3. [5 个实战调试场景](#3-5-个实战调试场景)
4. [工具参考](#4-工具参考)
5. [附录](#5-附录)

---

## 1. 快速开始

### 前提条件

✅ 开发环境已启动（前端 3101 + 后端 9999）
✅ 用户已登录（admin 账户）
✅ Chrome DevTools 已打开（`F12`）

**如果环境未就绪**，参见 [附录 A: 环境准备](#附录-a-环境准备)

### 快捷键速查

| 功能 | Windows/Linux | macOS |
|------|---------------|-------|
| 打开 DevTools | `F12` 或 `Ctrl+Shift+I` | `Cmd+Option+I` |
| 元素检查器 | `Ctrl+Shift+C` | `Cmd+Shift+C` |
| 控制台 | `Ctrl+Shift+J` | `Cmd+Option+J` |
| 命令面板 | `Ctrl+Shift+P` | `Cmd+Shift+P` |
| 清除控制台 | `Ctrl+L` | `Cmd+K` |
| 硬刷新（清缓存） | `Ctrl+Shift+R` | `Cmd+Shift+R` |

---

## 2. Chrome DevTools MCP 工具速查

### 2.1 核心工具列表

| 工具 | 用途 | 示例 |
|------|------|------|
| `list_pages_chrome-devtools` | 列出所有打开的页面 | 查看当前有哪些标签页 |
| `navigate_page_chrome-devtools` | 导航到指定 URL | 打开前端页面 |
| `take_snapshot_chrome-devtools` | 获取页面 DOM 结构 | 查看页面元素树 |
| `take_screenshot_chrome-devtools` | 截取页面截图 | 保存当前页面视觉状态 |
| `list_network_requests_chrome-devtools` | 查看网络请求列表 | 分析 API 调用 |
| `get_network_request_chrome-devtools` | 查看单个请求详情 | 查看请求/响应 body |
| `list_console_messages_chrome-devtools` | 查看控制台消息 | 检查错误和警告 |
| `click_chrome-devtools` | 点击页面元素 | 模拟用户交互 |
| `evaluate_script_chrome-devtools` | 执行 JavaScript | 查询页面状态 |

### 2.2 实际使用示例

**示例 1: 查看所有网络请求**
```javascript
// 工具: list_network_requests_chrome-devtools
// 输出: 129 个请求（包括资源、API、图片等）
// 关键发现: 2 个 401 错误（登录前的 userinfo/usermenu）
```

**示例 2: 查看登录 API 详情**
```javascript
// 工具: get_network_request_chrome-devtools
// URL: http://localhost:3101/api/v1/base/access_token
// 请求体: {"username":"admin","password":"123456"}
// 响应: {"code":200,"data":{"access_token":"eyJ...","token_type":"bearer"}}
// Trace ID: 4024287bb4ec4f779cd4b1dac74983b1
```

**示例 3: 执行脚本查询页面状态**
```javascript
// 工具: evaluate_script_chrome-devtools
() => ({
  title: document.title,
  url: window.location.href,
  hasVue: !!window.__VUE__,
  localStorage: {
    token: localStorage.getItem('token') ? 'exists' : 'not found'
  }
})
// 输出: {"title":"Dashboard | Vue FastAPI Admin","hasVue":true,...}
```

---

## 3. 5 个实战调试场景

### 场景 1: 查看 API 请求详情

**问题**: 需要查看某个 API 的完整请求和响应

**步骤**:
1. ✅ 打开 Network 面板（`Ctrl+Shift+I` → Network）
2. ✅ 刷新页面或触发 API 调用
3. ✅ 点击目标请求（如 `/api/v1/base/access_token`）
4. ✅ 查看 Headers、Request、Response 标签页

**MCP 工具方式**:
```javascript
// 1. 列出所有请求
list_network_requests_chrome-devtools()
// 输出: 129 个请求

// 2. 查看特定请求详情
get_network_request_chrome-devtools({
  url: "http://localhost:3101/api/v1/base/access_token"
})
// 输出: 完整的 request/response headers 和 body
```

**实际输出**:
```json
{
  "status": "success - 200",
  "request_body": "{\"username\":\"admin\",\"password\":\"123456\"}",
  "response_body": "{\"code\":200,\"data\":{\"access_token\":\"eyJ...\",\"token_type\":\"bearer\"}}",
  "trace_id": "4024287bb4ec4f779cd4b1dac74983b1"
}
```

**解决方案**: 使用 `trace_id` 在后端日志中追踪完整请求链路

---

### 场景 2: 调试组件状态

**问题**: Vue 组件数据未正确更新

**步骤**:
1. ✅ 打开 Console 面板（`Ctrl+Shift+J`）
2. ✅ 执行脚本查询 Vue 实例
3. ✅ 检查 Pinia store 状态
4. ✅ 验证响应式数据

**MCP 工具方式**:
```javascript
evaluate_script_chrome-devtools({
  function: `() => {
    return {
      hasVue: !!window.__VUE__,
      hasPinia: !!window.__PINIA__,
      currentRoute: window.$router?.currentRoute?.value?.path,
      userStore: window.__PINIA__?.state?.value?.user
    }
  }`
})
```

**实际输出**:
```json
{
  "hasVue": true,
  "hasPinia": false,
  "currentRoute": "/ai/catalog",
  "userStore": "not found"
}
```

**解决方案**:
- 检查 Pinia 的全局变量名（可能不是 `__PINIA__`）
- 使用 Vue DevTools 扩展查看组件树

---

### 场景 3: 分析网络性能

**问题**: 页面加载缓慢，需要找出瓶颈

**步骤**:
1. ✅ 打开 Network 面板
2. ✅ 勾选 "Disable cache"
3. ✅ 刷新页面（`Ctrl+Shift+R`）
4. ✅ 按 Time 列排序，找出慢请求

**MCP 工具方式**:
```javascript
list_network_requests_chrome-devtools()
// 分析输出中的响应时间
```

**实际发现**:
- 总请求数: 129 个
- 慢请求: Supabase 健康检查（854ms）
- 轮询请求: healthz、metrics 每隔几秒请求一次

**解决方案**:
- 优化 Supabase 连接（使用连接池）
- 增加轮询间隔（从 3 秒改为 10 秒）
- 使用 CDN 加载第三方库

---

### 场景 4: 执行自定义脚本

**问题**: 需要批量修改页面数据或测试功能

**步骤**:
1. ✅ 打开 Console 面板
2. ✅ 编写并执行 JavaScript 代码
3. ✅ 查看返回结果

**MCP 工具方式**:
```javascript
evaluate_script_chrome-devtools({
  function: `() => {
    // 查询所有 AI 端点
    const endpoints = document.querySelectorAll('[data-endpoint]')
    return {
      count: endpoints.length,
      names: Array.from(endpoints).map(el => el.textContent)
    }
  }`
})
```

**常用脚本**:
```javascript
// 1. 查看 localStorage
localStorage.getItem('token')

// 2. 查看 sessionStorage
sessionStorage.getItem('userInfo')

// 3. 复制数据到剪贴板
copy({ name: 'test', age: 25 })

// 4. 查看当前选中元素的 Vue 组件
$0.__vueParentComponent

// 5. 性能计时
console.time('API Call')
await fetch('/api/v1/healthz')
console.timeEnd('API Call')
```

---

### 场景 5: 测试元素交互

**问题**: 需要模拟用户点击或输入

**步骤**:
1. ✅ 获取页面快照（查看元素 UID）
2. ✅ 使用 click 工具点击元素
3. ✅ 查看页面变化

**MCP 工具方式**:
```javascript
// 1. 获取页面快照
take_snapshot_chrome-devtools()
// 输出: 119 个元素，每个有唯一 UID

// 2. 点击按钮（UID: 1_82 = "📦 管理端点"）
click_chrome-devtools({ uid: "1_82" })
// 结果: 页面跳转到 /ai/catalog

// 3. 再次获取快照验证
take_snapshot_chrome-devtools()
// 输出: 页面标题变为 "模型目录 | Vue FastAPI Admin"
```

**实际效果**:
- 点击前: Dashboard 页面
- 点击后: 跳转到 AI 模型目录页面
- 按钮状态: 获得焦点（`focusable focused`）

---

## 4. 工具参考

### 4.1 Console 面板常用命令

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

### 4.2 Network 面板过滤器

```javascript
// 过滤器语法
method:POST              // 只显示 POST 请求
status-code:401          // 只显示 401 错误
larger-than:1M           // 大于 1MB 的资源
domain:localhost         // 只显示本地请求
-domain:cdn.example.com  // 排除 CDN 请求
```

### 4.3 性能优化检查清单

- [ ] 首屏加载时间 < 3 秒
- [ ] 路由切换时间 < 500ms
- [ ] API 响应时间 < 1 秒
- [ ] 未使用代码 < 30%
- [ ] 图片使用 WebP 格式
- [ ] 启用 Gzip/Brotli 压缩
- [ ] 使用 CDN 加载第三方库
- [ ] 懒加载非首屏组件

---

## 5. 附录

### 附录 A: 环境准备

**启动开发环境**:
```powershell
# 一键启动（推荐）
.\start-dev.ps1

# 手动启动
python run.py              # 后端 (终端 1)
cd web && pnpm dev         # 前端 (终端 2)
```

**访问地址**:
- 前端: http://localhost:3101
- 后端: http://localhost:9999
- API 文档: http://localhost:9999/docs

**登录账户**:
- 用户名: `admin`
- 密码: `123456`

### 附录 B: 故障排查

**问题 1: 页面白屏**

```bash
# 1. 检查控制台错误
F12 → Console → 查看红色错误

# 2. 检查网络请求
F12 → Network → 查看是否有 404/500

# 3. 清除缓存重启
cd web && rm -rf node_modules/.vite && pnpm dev
```

**问题 2: API 调用 401**

```javascript
// 1. 检查 token
localStorage.getItem('token')

// 2. 检查请求 header
// Network → 点击请求 → Headers → Request Headers → Authorization

// 3. 重新登录
const userStore = useUserStore()
userStore.logout()
```

**问题 3: Chrome DevTools MCP 未连接**

```bash
# 症状: 调用 MCP 工具时返回 "Not connected"
# 解决方案:
# 1. 使用浏览器内置的 Chrome DevTools（推荐）
# 2. 使用自动化调试脚本: python scripts/debug_frontend.py
# 3. 参考文档手册进行手动调试
```

### 附录 C: 自动化调试脚本

```bash
# 完整诊断
python scripts/debug_frontend.py

# 仅检查服务
python scripts/debug_frontend.py check

# 测试 API
python scripts/debug_frontend.py test

# 生成测试 token
python scripts/create_test_jwt.py
```

**输出示例**:
```
前端服务: ✅ 正常 (200)
后端服务: ✅ 正常 (200)
健康检查: ✅ 正常
API 测试: 3/4 通过
平均响应时间: 2.59ms
```

---

## 📚 参考资源

- [Chrome DevTools 官方文档](https://developer.chrome.com/docs/devtools/)
- [Vue.js DevTools 使用指南](https://devtools.vuejs.org/)
- [Vite 调试指南](https://vitejs.dev/guide/troubleshooting.html)
- [项目架构文档](./PROJECT_OVERVIEW.md)
- [快速参考卡片](./DEBUG_QUICK_REFERENCE.md)

---

**最后更新**: 2025-10-12
**维护者**: GymBro 开发团队
**版本**: 2.0.0（简化版）
