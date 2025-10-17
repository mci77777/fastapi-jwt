# 根路径跳转问题修复文档

> **版本**: v1.0  
> **日期**: 2025-10-14  
> **状态**: ✅ 已修复（待测试）

---

## 📋 问题描述

### 现象
- 访问 `http://localhost:3101/` 时无法自动跳转到登录页 `/login`
- 可能停留在空白页、404 页面或其他错误状态

### 上下文
- 刚刚修复了登录后跳转到 Dashboard 的问题（修改了 `app/api/v1/base.py` 中的菜单配置）
- 近期改动可能影响了路由系统的完整性

---

## 🔍 问题诊断

### 根本原因 1：路由守卫路径格式错误 ⭐⭐⭐

**文件**：`web/src/router/guard/auth-guard.js`  
**位置**：第 13 行

**问题代码**（修复前）：
```javascript
if (isNullOrWhitespace(token)) {
  if (WHITE_LIST.includes(to.path)) return true
  return { path: 'login', query: { ...to.query, redirect: to.path } }
  //             ^^^^^^^ ❌ 错误：相对路径
}
```

**问题分析**：
- 返回的路径是 `'login'`（相对路径），应该是 `'/login'`（绝对路径）
- Vue Router 将相对路径解析为相对于当前路径的路径
- 访问 `/` 时，`'login'` 会被解析为 `/login`（碰巧正确）
- 但访问其他路径时（如 `/dashboard`），`'login'` 会被解析为 `/dashboard/login`（错误）

**影响范围**：
- 所有未登录用户访问受保护路径时的重定向
- 可能导致路由匹配失败或跳转到错误的路径

---

### 根本原因 2：根路径重定向配置不合理 ⭐⭐

**文件**：`web/src/router/routes/index.js`  
**位置**：第 8-11 行

**问题代码**（修复前）：
```javascript
{
  path: '/',
  redirect: '/login', // 未登录默认跳转登录页
  meta: { order: 0 },
}
```

**问题分析**：
- 基础路由配置：`/` → `/login`（静态重定向）
- 路由守卫：`/` → `/login`（动态重定向，根据 Token 状态）
- 两者逻辑**重复**，且静态重定向无法根据 Token 状态动态调整

**执行流程**（修复前）：
```
未登录用户访问 /
  ↓
基础路由: / → /login（静态重定向）
  ↓
路由守卫: /login → 允许访问（在白名单中）
  ↓
显示登录页 ✅（结果正确，但逻辑不清晰）

已登录用户访问 /
  ↓
基础路由: / → /login（静态重定向）
  ↓
路由守卫: /login → /dashboard（动态重定向）
  ↓
显示 Dashboard ✅（结果正确，但多了一次重定向）
```

**问题**：
- 已登录用户访问 `/` 时，会先重定向到 `/login`，再重定向到 `/dashboard`
- 多了一次不必要的重定向，影响性能和用户体验

---

## ✅ 解决方案

### 修复 1：修正路由守卫中的路径格式 ⭐⭐⭐

**文件**：`web/src/router/guard/auth-guard.js`

**修复内容**：
```javascript
/** 没有token的情况 */
if (isNullOrWhitespace(token)) {
  if (WHITE_LIST.includes(to.path)) return true
  // 修复：使用绝对路径 '/login' 而不是相对路径 'login'
  // 如果访问根路径 '/'，不保存 redirect 参数（避免循环重定向）
  if (to.path === '/') {
    return { path: '/login' }
  }
  return { path: '/login', query: { ...to.query, redirect: to.path } }
}
```

**修复说明**：
1. **使用绝对路径**：`'/login'` 而不是 `'login'`
2. **特殊处理根路径**：访问 `/` 时不保存 `redirect` 参数，避免循环重定向
3. **保持其他路径逻辑**：访问其他受保护路径时，保存 `redirect` 参数以便登录后跳转回原路径

---

### 修复 2：优化基础路由配置 ⭐⭐

**文件**：`web/src/router/routes/index.js`

**修复内容**：
```javascript
{
  path: '/',
  name: 'Root',
  redirect: '/dashboard', // 默认跳转到 Dashboard，路由守卫会根据 Token 状态处理
  meta: { order: 0 },
}
```

**修复说明**：
1. **改为重定向到 `/dashboard`**：让路由守卫统一处理跳转逻辑
2. **添加 name 属性**：便于调试和路由管理
3. **简化配置**：移除不必要的注释

**执行流程**（修复后）：
```
未登录用户访问 /
  ↓
基础路由: / → /dashboard（静态重定向）
  ↓
路由守卫: /dashboard → /login（动态重定向，无 Token）
  ↓
显示登录页 ✅

已登录用户访问 /
  ↓
基础路由: / → /dashboard（静态重定向）
  ↓
路由守卫: /dashboard → 允许访问（有 Token）
  ↓
显示 Dashboard ✅
```

**优点**：
- 逻辑更清晰：根路径默认跳转到 Dashboard，路由守卫根据 Token 状态决定是否允许访问
- 减少重定向次数：已登录用户访问 `/` 时，只需一次重定向（`/` → `/dashboard`）
- 符合用户预期：已登录用户访问根路径应该看到 Dashboard，而不是登录页

---

## 🔄 完整路由流程

### 场景 1：未登录用户访问根路径 `/`

```
1. 用户访问 http://localhost:3101/
   ↓
2. 基础路由匹配: / → /dashboard（静态重定向）
   ↓
3. 路由守卫检查: to.path = '/dashboard', token = null
   ↓
4. 路由守卫判断: 不在白名单，无 Token → 重定向到 /login
   ↓
5. 基础路由匹配: /login（登录页路由）
   ↓
6. 路由守卫检查: to.path = '/login', token = null
   ↓
7. 路由守卫判断: 在白名单中 → 允许访问
   ↓
8. 显示登录页 ✅
```

### 场景 2：已登录用户访问根路径 `/`

```
1. 用户访问 http://localhost:3101/
   ↓
2. 基础路由匹配: / → /dashboard（静态重定向）
   ↓
3. 路由守卫检查: to.path = '/dashboard', token = 'xxx'
   ↓
4. 路由守卫判断: 有 Token，检查动态路由是否已加载
   ↓
5. 如果动态路由未加载:
   - 调用 addDynamicRoutes() 加载动态路由
   - 重新导航到 /dashboard
   ↓
6. 如果动态路由已加载:
   - 允许访问
   ↓
7. 显示 Dashboard 页面 ✅
```

### 场景 3：已登录用户访问登录页 `/login`

```
1. 用户访问 http://localhost:3101/login
   ↓
2. 基础路由匹配: /login（登录页路由）
   ↓
3. 路由守卫检查: to.path = '/login', token = 'xxx'
   ↓
4. 路由守卫判断: 有 Token，访问登录页 → 重定向到 /dashboard
   ↓
5. 基础路由匹配: /dashboard（Dashboard 路由）
   ↓
6. 路由守卫检查: to.path = '/dashboard', token = 'xxx'
   ↓
7. 路由守卫判断: 有 Token，允许访问
   ↓
8. 显示 Dashboard 页面 ✅
```

### 场景 4：未登录用户访问受保护路径（如 `/system/ai`）

```
1. 用户访问 http://localhost:3101/system/ai
   ↓
2. 路由守卫检查: to.path = '/system/ai', token = null
   ↓
3. 路由守卫判断: 不在白名单，无 Token → 重定向到 /login
   - 保存 redirect 参数: /login?redirect=/system/ai
   ↓
4. 基础路由匹配: /login（登录页路由）
   ↓
5. 路由守卫检查: to.path = '/login', token = null
   ↓
6. 路由守卫判断: 在白名单中 → 允许访问
   ↓
7. 显示登录页 ✅
   ↓
8. 用户登录成功后:
   - 检查 query.redirect 参数
   - 跳转到 /system/ai ✅
```

---

## 🧪 测试步骤

### 前提条件
确保前端服务器正在运行：
```bash
# 检查前端是否运行
curl http://localhost:3101

# 如果没有运行，启动前端
cd web && pnpm dev
```

### 测试 1：使用测试工具（推荐）

1. **打开测试工具**：
   ```
   在浏览器中打开：file:///d:/GymBro/vue-fastapi-admin/scripts/test_root_redirect.html
   ```

2. **执行测试场景**：
   - **场景 1**：未登录用户访问根路径
     - 点击"执行测试 1"
     - 验证是否跳转到 `/login`

   - **场景 2**：已登录用户访问根路径
     - 先登录（访问 `/login`，使用 `admin/123456`）
     - 点击"执行测试 2"
     - 验证是否跳转到 `/dashboard`

   - **场景 3**：已登录用户访问登录页
     - 确保已登录
     - 点击"执行测试 3"
     - 验证是否跳转到 `/dashboard`

### 测试 2：手动测试

#### 测试 2.1：未登录用户访问根路径

1. **清除 Token**：
   ```javascript
   // 在浏览器控制台执行
   localStorage.clear()
   ```

2. **访问根路径**：
   ```
   http://localhost:3101/
   ```

3. **验证结果**：
   - ✅ 自动跳转到 `/login`
   - ✅ 浏览器地址栏显示：`http://localhost:3101/login`
   - ✅ 显示登录页面

#### 测试 2.2：已登录用户访问根路径

1. **登录系统**：
   - 访问：`http://localhost:3101/login`
   - 用户名：`admin`
   - 密码：`123456`

2. **访问根路径**：
   ```
   http://localhost:3101/
   ```

3. **验证结果**：
   - ✅ 自动跳转到 `/dashboard`
   - ✅ 浏览器地址栏显示：`http://localhost:3101/dashboard`
   - ✅ 显示 Dashboard 页面

#### 测试 2.3：已登录用户访问登录页

1. **确保已登录**（参考测试 2.2）

2. **访问登录页**：
   ```
   http://localhost:3101/login
   ```

3. **验证结果**：
   - ✅ 自动跳转到 `/dashboard`
   - ✅ 浏览器地址栏显示：`http://localhost:3101/dashboard`
   - ✅ 显示 Dashboard 页面

---

## 📊 验收标准

- [x] 路由守卫路径格式修复（绝对路径）✅
- [x] 基础路由配置优化（重定向到 Dashboard）✅
- [x] 代码无语法错误 ✅
- [ ] 未登录时访问 `/` 自动跳转到 `/login` ⏳
- [ ] 已登录时访问 `/` 自动跳转到 `/dashboard` ⏳
- [ ] 已登录时访问 `/login` 自动跳转到 `/dashboard` ⏳
- [ ] 浏览器控制台无错误 ⏳
- [ ] 不存在死循环重定向 ⏳

---

## 📁 修改文件清单

### 前端（2 个文件）

1. **`web/src/router/guard/auth-guard.js`**
   - 修复路由守卫中的路径格式（第 13 行）
   - 使用绝对路径 `'/login'` 而不是相对路径 `'login'`
   - 特殊处理根路径 `/`，不保存 `redirect` 参数

2. **`web/src/router/routes/index.js`**
   - 优化根路径配置（第 8-11 行）
   - 改为重定向到 `/dashboard`
   - 添加 `name` 属性

### 测试工具（1 个文件）

- **`scripts/test_root_redirect.html`** - 根路径跳转测试工具（300 行）

### 文档（1 个文件）

- **`docs/ROOT_REDIRECT_FIX.md`** - 本文档（300 行）

---

## ⚠️ 注意事项

1. **测试前必须启动前端服务器**：
   - 前端：`http://localhost:3101`
   - 使用 `cd web && pnpm dev` 启动

2. **清除浏览器缓存**：
   - 修复后建议清除浏览器缓存和 localStorage
   - 或使用无痕模式测试

3. **路由守卫逻辑**：
   - 始终使用绝对路径（以 `/` 开头）
   - 根路径 `/` 不保存 `redirect` 参数
   - 其他受保护路径保存 `redirect` 参数

4. **基础路由配置**：
   - 根路径默认重定向到 `/dashboard`
   - 路由守卫根据 Token 状态决定是否允许访问

---

## 🔧 故障排查

### 问题 1：访问 `/` 后停留在空白页

**可能原因**：
1. 路由守卫逻辑错误
2. 基础路由配置错误
3. 动态路由加载失败

**解决方案**：
```javascript
// 在浏览器控制台检查
import { router } from '@/router'
console.log(router.getRoutes())  // 查看所有已注册的路由
```

### 问题 2：访问 `/` 后出现死循环重定向

**可能原因**：
1. 路由守卫逻辑错误（重定向到自身）
2. 基础路由配置错误（循环重定向）

**解决方案**：
- 检查浏览器控制台是否有 "Maximum call stack size exceeded" 错误
- 检查路由守卫逻辑，确保不会重定向到自身

### 问题 3：已登录用户访问 `/` 后仍然跳转到 `/login`

**可能原因**：
1. Token 未正确保存
2. Token 已过期
3. 路由守卫逻辑错误

**解决方案**：
```javascript
// 在浏览器控制台检查
localStorage.getItem('ACCESS_TOKEN')  // 检查是否有 Token
```

---

**完成日期**: 2025-10-14  
**验收状态**: ✅ 代码完成（待测试）  
**下一步**: 启动前端服务器并测试根路径跳转功能
