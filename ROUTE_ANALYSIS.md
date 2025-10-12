# 🔍 完整路由链路分析

## 1. 后端菜单配置
**文件**: `app/api/v1/base.py` (第189-269行)

```python
menus = [
    {
        "name": "Dashboard",
        "path": "/dashboard",         # ← 路由路径
        "component": "/dashboard",    # ← 前端组件路径（会拼接为/src/views/dashboard/index.vue）
        "order": 0,                   # ← 菜单顺序（0=最顶部）
    },
    {
        "name": "AI模型管理",
        "path": "/ai",
        "component": "/ai",           # ← 父路由占位符
        "order": 5,
        "children": [
            {"name": "模型目录", "path": "catalog", "component": "/ai/model-suite/catalog"},
            {"name": "模型映射", "path": "mapping", "component": "/ai/model-suite/mapping"},
            {"name": "JWT测试", "path": "jwt", "component": "/ai/model-suite/jwt"},
        ]
    },
    {
        "name": "系统管理",
        "path": "/system",
        "component": "/system",
        "order": 100,
        "children": [
            {"name": "AI 配置", "path": "ai", "component": "/system/ai"},
            {"name": "Prompt 管理", "path": "ai/prompt", "component": "/system/ai/prompt"},
        ]
    }
]
```

## 2. 前端接收与转换
**文件**: `web/src/store/modules/permission/index.js` (buildRoutes函数)

### 转换逻辑：
```javascript
// 后端返回的每个菜单项会被转换为：
{
  name: e.name,
  path: e.path,
  component: Layout,  // 所有顶级路由都用Layout包裹
  children: [...]
}

// 子路由转换：
{
  name: e_child.name,
  path: e_child.path,
  component: vueModules[`/src/views${e_child.component}/index.vue`]  // ← 关键拼接
}
```

### Dashboard转换结果：
```javascript
{
  name: "Dashboard",
  path: "/dashboard",
  component: Layout,
  children: [{
    name: "DashboardDefault",
    path: "",  // 空路径，匹配 /dashboard
    component: vueModules["/src/views/dashboard/index.vue"]  // ← 查找这个文件
  }]
}
```

## 3. 前端组件位置
**必需文件**: `web/src/views/dashboard/index.vue`

✅ **已存在** (已从workbench重命名为dashboard)

## 4. Vue模块加载
**文件**: `web/src/router/routes/index.js` (第123行)

```javascript
const vueModules = import.meta.glob('@/views/**/index.vue')
```

会加载所有符合pattern的组件，包括：
- `/src/views/dashboard/index.vue`
- `/src/views/ai/model-suite/catalog/index.vue`
- `/src/views/ai/model-suite/mapping/index.vue`
- 等等...

## 5. 路由注册流程

1. **应用启动**: `main.js` → `setupRouter(app)`
2. **加载动态路由**: `addDynamicRoutes()`
   - 检查token
   - 调用 `permissionStore.generateRoutes()`
   - 调用后端API: `GET /api/v1/base/usermenu`
   - 使用`buildRoutes()`转换后端数据
   - 通过`router.addRoute()`注册路由
3. **显示菜单**: `Layout`组件读取`permissionStore.menus`
4. **渲染组件**: 访问`/dashboard`时加载`views/dashboard/index.vue`

## 6. 问题修复清单

✅ **后端配置**: base.py中菜单结构正确
✅ **前端组件**: dashboard/index.vue存在
✅ **删除冲突**: 删除了无用的静态route.js文件
⏳ **待验证**: 启动服务并测试

## 7. 预期最终效果

### 左侧菜单结构:
```
Dashboard          ← order:0 (最顶部)
├─ (直接显示dashboard/index.vue)

AI模型管理         ← order:5 (可折叠)
├─ 模型目录
├─ 模型映射
└─ JWT测试

系统管理           ← order:100 (可折叠)
├─ AI 配置
└─ Prompt 管理
```

### URL映射:
- `/dashboard` → `views/dashboard/index.vue`
- `/ai/catalog` → `views/ai/model-suite/catalog/index.vue`
- `/ai/mapping` → `views/ai/model-suite/mapping/index.vue`
- `/ai/jwt` → `views/ai/model-suite/jwt/index.vue`
- `/system/ai` → `views/system/ai/index.vue`
- `/system/ai/prompt` → `views/system/ai/prompt/index.vue`

---
**创建时间**: 2025-01-11
**状态**: ✅ 路由配置完成，等待启动测试
