# 前端调试快速参考卡片

> 一页纸速查手册 - 最常用的调试命令和技巧

---

## 🚀 快速启动

```powershell
# 一键启动前后端
.\start-dev.ps1

# 手动启动
python run.py              # 后端 (终端 1)
cd web && pnpm dev         # 前端 (终端 2)
```

**访问地址**:
- 前端: http://localhost:3101
- 后端: http://localhost:9999
- API 文档: http://localhost:9999/docs

---

## 🔍 Chrome DevTools 快捷键

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

## 🛠️ 常用调试命令

### Console 面板

```javascript
// 1. 查看 Pinia store
window.__PINIA__.state.value.user

// 2. 查看 Vue Router
window.$router.currentRoute.value

// 3. 查看 localStorage
localStorage.getItem('token')

// 4. 手动调用 API
const res = await fetch('/api/v1/healthz')
console.log(await res.json())

// 5. 复制数据到剪贴板
copy({ name: 'test', age: 25 })

// 6. 查看当前选中元素的 Vue 组件
$0.__vueParentComponent

// 7. 性能计时
console.time('API Call')
await fetch('/api/v1/data')
console.timeEnd('API Call')
```

### Network 面板

```javascript
// 过滤器语法
method:POST              // 只显示 POST 请求
status-code:401          // 只显示 401 错误
larger-than:1M           // 大于 1MB 的资源
domain:localhost         // 只显示本地请求
-domain:cdn.example.com  // 排除 CDN 请求
```

---

## 🐛 常见问题速查

### 问题 1: 页面白屏

```bash
# 1. 检查控制台错误
F12 → Console → 查看红色错误

# 2. 检查网络请求
F12 → Network → 查看是否有 404/500

# 3. 清除缓存重启
cd web && rm -rf node_modules/.vite && pnpm dev
```

### 问题 2: API 调用 401

```javascript
// 1. 检查 token
localStorage.getItem('token')

// 2. 检查请求 header
// Network → 点击请求 → Headers → Request Headers → Authorization

// 3. 重新登录
const userStore = useUserStore()
userStore.logout()
// 然后重新登录
```

### 问题 3: 组件状态未更新

```javascript
// 1. 检查响应式
import { toRaw } from 'vue'
console.log(toRaw(yourReactiveObject))

// 2. 检查 Pinia store
// Vue DevTools → Pinia → 查看状态

// 3. 添加 watch 监听
watch(() => data.value, (newVal) => {
  console.log('Data changed:', newVal)
}, { deep: true })
```

### 问题 4: 路由跳转失败

```javascript
// 1. 检查路由配置
console.log(window.$router.getRoutes())

// 2. 检查权限
const userStore = useUserStore()
console.log(userStore.permissions)

// 3. 手动跳转测试
window.$router.push('/dashboard')
```

---

## 📊 性能优化检查

```javascript
// 1. 查看未使用代码
// DevTools → Coverage → Record → 刷新页面

// 2. 分析包大小
// 构建后查看 dist/stats.html
pnpm build

// 3. 检查内存泄漏
// DevTools → Memory → Take heap snapshot

// 4. 分析渲染性能
// DevTools → Performance → Record → 刷新页面
```

---

## 🔧 自动化调试脚本

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

---

## 📝 断点调试技巧

```javascript
// 1. 代码中插入断点
debugger

// 2. 条件断点
// Sources → 右键行号 → Add conditional breakpoint
// 条件: user.id === 123

// 3. XHR 断点
// Sources → XHR Breakpoints → Add breakpoint
// URL: /api/v1/login

// 4. 事件监听器断点
// Sources → Event Listener Breakpoints → Mouse → click
```

---

## 🎯 Vue DevTools 技巧

```javascript
// 1. 查看组件树
// Vue DevTools → Components

// 2. 查看 Pinia 状态
// Vue DevTools → Pinia

// 3. 查看路由
// Vue DevTools → Routes

// 4. 时间旅行调试
// Vue DevTools → Timeline → 选择时间点

// 5. 编辑组件数据
// Vue DevTools → Components → 选择组件 → 点击 data 旁的编辑图标
```

---

## 🚨 紧急修复命令

```powershell
# 1. 杀死所有 Node 进程
taskkill /F /IM node.exe

# 2. 杀死所有 Python 进程
taskkill /F /IM python.exe

# 3. 清除前端缓存
cd web
rm -rf node_modules/.vite
rm -rf dist
pnpm install

# 4. 清除后端缓存
Get-ChildItem -Path . -Include __pycache__ -Recurse -Force | Remove-Item -Force -Recurse

# 5. 重置数据库
python scripts/reset_database.py

# 6. 检查端口占用
netstat -ano | Select-String ":3101 "
netstat -ano | Select-String ":9999 "
```

---

## 📚 更多资源

- 完整调试指南: [CHROME_DEVTOOLS_DEBUG_GUIDE.md](./CHROME_DEVTOOLS_DEBUG_GUIDE.md)
- 项目架构: [PROJECT_OVERVIEW.md](./PROJECT_OVERVIEW.md)
- JWT 认证: [JWT_HARDENING_GUIDE.md](./JWT_HARDENING_GUIDE.md)
- 脚本索引: [SCRIPTS_INDEX.md](./SCRIPTS_INDEX.md)

---

**提示**: 将此文档打印或保存为 PDF，放在手边随时查阅！

**最后更新**: 2025-10-12

