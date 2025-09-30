# GymBro 管理后台项目概览

## 📋 项目简介

GymBro是一个基于FastAPI + Vue 3的现代化管理后台系统，提供完整的RBAC（基于角色的访问控制）功能，支持移动App的JWT认证对接。

## 🏗️ 系统架构

### 技术栈

**后端**：
- **框架**：FastAPI 0.x（异步Web框架）
- **Python版本**：3.12
- **数据库**：Supabase PostgreSQL
- **ORM**：SQLAlchemy（异步）
- **迁移工具**：Alembic
- **认证**：Supabase JWT（HS256签名）
- **缓存**：Redis（计划中）
- **监控**：Prometheus + Grafana

**前端**：
- **框架**：Vue 3（Composition API）
- **构建工具**：Vite 5
- **UI库**：Naive UI 2.x
- **状态管理**：Pinia
- **路由**：Vue Router 4
- **HTTP客户端**：Axios
- **图表库**：ECharts（计划中）

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         前端层 (Vue 3)                        │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ 用户管理 │  │ 角色管理 │  │ 菜单管理 │  │ 系统监控 │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│         │              │              │              │        │
│         └──────────────┴──────────────┴──────────────┘        │
│                          │                                     │
│                    ┌─────▼─────┐                              │
│                    │  Pinia    │                              │
│                    │  Store    │                              │
│                    └─────┬─────┘                              │
│                          │                                     │
│                    ┌─────▼─────┐                              │
│                    │  Axios    │                              │
│                    │  HTTP     │                              │
│                    └─────┬─────┘                              │
└──────────────────────────┼─────────────────────────────────────┘
                           │ JWT Token (Header: token)
                           │
┌──────────────────────────▼─────────────────────────────────────┐
│                      中间件层 (FastAPI)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ TraceID      │→ │ RateLimiter  │→ │ PolicyGate   │        │
│  │ Middleware   │  │ Middleware   │  │ Middleware   │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└──────────────────────────┬─────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────┐
│                       API层 (FastAPI)                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ /base/*  │  │ /user/*  │  │ /role/*  │  │ /menu/*  │      │
│  │ 登录认证 │  │ 用户管理 │  │ 角色管理 │  │ 菜单管理 │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ /api/*   │  │/auditlog*│  │ /metrics │  │ /healthz │      │
│  │ API权限  │  │ 审计日志 │  │ 监控指标 │  │ 健康探针 │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└──────────────────────────┬─────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────┐
│                     服务层 (Services)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ UserService  │  │ RoleService  │  │ MenuService  │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└──────────────────────────┬─────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────┐
│                    数据层 (SQLAlchemy)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │  User    │  │  Role    │  │  Menu    │  │   Api    │      │
│  │  Model   │  │  Model   │  │  Model   │  │  Model   │      │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘      │
└──────────────────────────┬─────────────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────────────┐
│                  Supabase PostgreSQL                            │
└─────────────────────────────────────────────────────────────────┘
```

## ✅ 已完成功能

### 后端功能

1. **JWT认证系统**：
   - ✅ Supabase JWT验证（支持JWKS动态获取）
   - ✅ 匿名用户和永久用户区分
   - ✅ Token header和Authorization header双重支持
   - ✅ 时钟偏移容忍（±120秒）
   - ⚠️ Token刷新机制（待实现）

2. **中间件系统**：
   - ✅ TraceID中间件（请求追踪）
   - ✅ RateLimiter中间件（限流控制）
   - ✅ PolicyGate中间件（权限控制）
   - ✅ SSEGuard中间件（SSE并发控制）

3. **健康探针**：
   - ✅ `/api/v1/healthz` - 总体健康状态
   - ✅ `/api/v1/livez` - 存活探针
   - ✅ `/api/v1/readyz` - 就绪探针

4. **监控指标**：
   - ✅ `/api/v1/metrics` - Prometheus指标导出
   - ✅ 6个核心指标（认证、JWT验证、缓存、限流等）

5. **基础API**：
   - ✅ `POST /api/v1/base/access_token` - 登录
   - ✅ `GET /api/v1/base/userinfo` - 用户信息
   - ✅ `GET /api/v1/base/usermenu` - 用户菜单
   - ✅ `GET /api/v1/base/userapi` - 用户API权限

6. **消息API**：
   - ✅ `POST /api/v1/messages` - SSE流式消息

### 前端功能

1. **基础框架**：
   - ✅ Vue 3 + Vite项目结构
   - ✅ Naive UI组件库集成
   - ✅ Pinia状态管理
   - ✅ Vue Router动态路由

2. **认证功能**：
   - ✅ 登录页面（admin/123456）
   - ✅ Token存储和管理
   - ✅ HTTP请求拦截器
   - ✅ 响应错误处理

3. **Store模块**：
   - ✅ userStore - 用户状态管理
   - ✅ permissionStore - 权限管理
   - ✅ appStore - 应用配置
   - ✅ tagsStore - 标签页管理

## 🚧 待开发功能

### 阶段0：JWT认证完善（优先级：P0）

- [ ] Token刷新端点（后端）
- [ ] Token自动刷新逻辑（前端）
- [ ] CORS配置验证
- [ ] 匿名用户测试
- [ ] App JWT对接文档

### 阶段1：数据库模型和RBAC基础（优先级：P1）

- [ ] 数据库Schema设计
- [ ] SQLAlchemy模型创建
- [ ] Alembic迁移脚本
- [ ] 基础CRUD服务层
- [ ] 单元测试

### 阶段2：后端管理API（优先级：P1）

- [ ] 用户管理API（/api/v1/user/*）
- [ ] 角色管理API（/api/v1/role/*）
- [ ] 菜单管理API（/api/v1/menu/*）
- [ ] API权限管理API（/api/v1/api/*）
- [ ] 审计日志API（/api/v1/auditlog/*）

### 阶段3：前端管理界面（优先级：P2）

- [ ] 用户管理页面
- [ ] 角色管理页面
- [ ] 菜单管理页面
- [ ] API权限管理页面
- [ ] 系统监控页面
- [ ] 审计日志页面

### 阶段4：系统优化（优先级：P3）

- [ ] Redis缓存
- [ ] 性能优化
- [ ] 安全加固
- [ ] 生产环境配置

## 📊 数据库设计（规划中）

### 核心表结构

1. **users** - 用户表
2. **roles** - 角色表
3. **user_roles** - 用户-角色关联表
4. **menus** - 菜单表
5. **role_menus** - 角色-菜单关联表
6. **apis** - API端点表
7. **role_apis** - 角色-API关联表
8. **audit_logs** - 审计日志表

详细设计见：[DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md)（待创建）

## 🔐 认证流程

### 登录流程

```
1. 用户输入用户名密码
2. 前端调用 POST /api/v1/base/access_token
3. 后端验证用户名密码
4. 后端生成Supabase格式的JWT token
5. 前端保存token到localStorage
6. 前端调用 GET /api/v1/base/userinfo 获取用户信息
7. 前端调用 GET /api/v1/base/usermenu 获取菜单权限
8. 前端生成动态路由并跳转到首页
```

### Token刷新流程（待实现）

```
1. 前端发送API请求
2. 后端返回401（token过期）
3. 前端拦截器自动调用 POST /api/v1/base/refresh_token
4. 后端验证旧token并生成新token
5. 前端保存新token
6. 前端重试原始请求
```

## 📱 App JWT对接准备

### Token格式

```json
{
  "iss": "https://xxx.supabase.co/auth/v1",
  "sub": "user-uuid",
  "aud": "authenticated",
  "exp": 1234567890,
  "iat": 1234567890,
  "email": "user@example.com",
  "role": "authenticated",
  "is_anonymous": false,
  "user_metadata": {...},
  "app_metadata": {...}
}
```

### 限流策略

- **匿名用户**：QPS=5, 并发SSE=2
- **永久用户**：QPS=10, 并发SSE=2

### 公开端点（无需认证）

- `/api/v1/healthz`, `/api/v1/livez`, `/api/v1/readyz`
- `/api/v1/metrics`
- `/api/v1/base/access_token`
- `/docs`, `/redoc`, `/openapi.json`

## 🎯 MVP（最小可行产品）范围

### 必须完成

1. ✅ JWT认证和刷新机制
2. ✅ 用户管理（CRUD）
3. ✅ 角色管理（CRUD + 菜单权限分配）
4. ✅ 菜单管理（CRUD + 树形展示）
5. ✅ 基础权限控制（路由级 + 按钮级）

### 可以延后

1. ❌ 部门管理
2. ❌ 高级筛选和搜索
3. ❌ 数据导入导出
4. ❌ 系统监控页面（可用Grafana替代）
5. ❌ 审计日志详细查询

## 📚 相关文档

- [详细执行计划](./EXECUTION_PLAN.md)
- [App JWT对接指南](./APP_JWT_INTEGRATION.md)（待创建）
- [数据库设计文档](./DATABASE_SCHEMA.md)（待创建）
- [部署文档](./DEPLOYMENT.md)（待创建）
- [运维手册](./OPERATIONS.md)（待创建）

## 🚀 快速开始

### 后端启动

```bash
# 安装依赖
uv add pyproject.toml

# 启动服务
uv run python run.py

# 访问API文档
http://localhost:9999/docs
```

### 前端启动

```bash
cd web

# 安装依赖
pnpm install

# 启动开发服务器
pnpm dev

# 访问前端
http://localhost:3101
```

### 测试账号

- 用户名：`admin`
- 密码：`123456`

## 📞 联系方式

- 项目仓库：[GitHub](https://github.com/your-repo)
- 问题反馈：[Issues](https://github.com/your-repo/issues)

---

**最后更新**：2025-09-30
**版本**：v0.1.0

