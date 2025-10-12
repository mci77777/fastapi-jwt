# GymBro FastAPI + Vue3 Admin - Copilot 指令

> 现代化全栈 RBAC 管理平台：FastAPI + Vue3 + JWT 认证 + 限流 + 策略访问控制
# 调试文档
```
D:\GymBro\vue-fastapi-admin\docs\dashboard-refactor\ARCHITECTURE_OVERVIEW.md
D:\GymBro\vue-fastapi-admin\docs\dashboard-refactor\CODE_REVIEW_AND_GAP_ANALYSIS.md
D:\GymBro\vue-fastapi-admin\docs\dashboard-refactor\IMPLEMENTATION_PLAN.md
D:\GymBro\vue-fastapi-admin\docs\dashboard-refactor\IMPLEMENTATION_SPEC.md
```

## 🏗️ 架构总览

### 后端 (FastAPI 0.111.0, Python 3.11+)
- **入口**: `run.py` → 启动 `app:app`，端口 9999，热重载
- **应用工厂**: `app/core/application.py::create_app()` → 组装中间件栈，注册路由
- **中间件链**（外→内）: CORS → **TraceID** → **PolicyGate** → **RateLimiter** → 路由处理器
  - `TraceIDMiddleware`: 每个请求生成或透传 Trace ID（用于追踪）
  - `PolicyGateMiddleware`: 限制匿名用户访问管理端点（`/api/v1/admin/*`, `/api/v1/user/*` 等）
  - `RateLimitMiddleware`: 令牌桶 + 滑动窗口算法，永久用户限额高于匿名用户
- **JWT 认证**: `app/auth/dependencies.py::get_current_user()`
  - 支持 `Authorization: Bearer <token>` header（Supabase JWT）
  - 区分匿名用户 vs 永久用户（`user.user_type`）
  - JWKS 动态验证，时钟偏移容忍 ±120s，兼容无 `nbf` 的 Supabase token
- **数据库**: SQLite（`app/db/sqlite_manager.py`）存储 AI 配置、模型映射、JWT 测试数据
- **服务层**: 单例模式通过 `app.state` 注入（`application.py` 生命周期钩子）
  - `AIConfigService`, `ModelMappingService`, `JWTTestService` 管理运行时状态
  - `EndpointMonitor` 收集 Prometheus 指标

### 前端 (Vue 3.3, Vite 4, Naive UI 2.x)
- **入口**: `web/src/main.js` → `pnpm dev` 启动 Vite 开发服务器
- **路由**: `web/src/router/index.js::addDynamicRoutes()` 验证 token 后从后端获取 RBAC 路由
- **状态**: Pinia stores (`web/src/store/modules/`) - user, permission, tags
- **HTTP 客户端**: `web/src/utils/http/index.js` 封装 axios（拦截器自动注入 token，处理 401）
- **API 调用**: `web/src/api/*.js` 导出函数如 `fetchModels()` → 调用 `/api/v1/llm/models`

## ⚡ 关键开发工作流

### 本地开发
```bash
# 后端（终端 1）
python run.py  # 或 make start
# → http://localhost:9999/docs 访问 Swagger UI

# 前端（终端 2）
cd web && pnpm dev
# → http://localhost:5173（代理 /api 到后端）
```

### 测试
```bash
# 后端测试（pytest）
make test  # 导出 .env，运行 pytest -vv

# 核心测试文件：
# - tests/test_jwt_auth.py: JWT 验证边界用例
# - tests/test_jwt_hardening.py: 时钟偏移、nbf 可选、算法限制
# - tests/test_api_contracts.py: API schema 验证
```

### 代码质量
```bash
# Python（行宽 120，black + isort + ruff）
make check        # 格式化和 lint 空跑（dry-run）
make format       # 应用 black + isort
make lint         # ruff check ./app

# Vue（2 空格缩进，ESLint + Prettier）
cd web && pnpm lint:fix
cd web && pnpm prettier
```

### 数据库迁移
```bash
# Aerich（Tortoise ORM 迁移工具）
make clean-db     # ⚠️ 删除 migrations/ 和 db.sqlite3
make migrate      # aerich migrate（生成迁移文件）
make upgrade      # aerich upgrade（应用迁移）
```

### 运维脚本
使用 `scripts/` 目录中的工具（详见 `docs/SCRIPTS_INDEX.md`，24 个脚本分类）：
- **JWT 验证**: `python scripts/verify_jwks_cache.py`（验证 JWKS + token 链）
- **Supabase 健康**: `python scripts/verify_supabase_config.py`（检查 API/表）
- **冒烟测试**: `python scripts/smoke_test.py`（注册→JWT→SSE→持久化）
- **K5 CI 管线**: `python scripts/k5_build_and_test.py`（构建 + Newman 测试）

## 📐 项目特定约定

### 后端模式
1. **依赖注入**: 使用 FastAPI `Depends()` 进行认证，不要手动解析 header
   ```python
   from app.auth import get_current_user
   
   @router.get("/protected")
   async def endpoint(user: AuthenticatedUser = Depends(get_current_user)):
       # user.user_type 是 "anonymous" 或 "permanent"
   ```

2. **错误响应**: 使用 `app/core/exceptions.py::create_error_response()` 确保格式一致
   ```python
   # 返回: {"status": 401, "code": "token_expired", "message": "...", "trace_id": "...", "hint": "..."}
   ```

3. **服务访问**: 从 `request.app.state` 获取，不要全局导入
   ```python
   async def endpoint(request: Request):
       ai_service = request.app.state.ai_config_service
   ```

4. **指标收集**: 使用 `app/core/metrics.py` 的 Prometheus counters/histograms，导出到 `/api/v1/metrics`

### 前端模式
1. **组件结构**: `<script setup>` + `<template>` + `<style scoped>`（**禁止 JSX 混用**）
   ```vue
   <script setup>
   import { ref } from 'vue'
   const count = ref(0)
   </script>
   <template>
     <n-button @click="count++">{{ count }}</n-button>
   </template>
   ```

2. **Store 使用**: 用 `storeToRefs()` 解构以保持响应性
   ```javascript
   import { storeToRefs } from 'pinia'
   const userStore = useUserStore()
   const { userInfo } = storeToRefs(userStore)  // 响应式
   const { logout } = userStore  // actions 不需要 refs
   ```

3. **API 调用**: 始终使用 `web/src/api/*.js` 函数，禁止内联 axios
   ```javascript
   import { fetchModels } from '@/api/aiModelSuite'
   const models = await fetchModels({ page: 1 })
   ```

## 🔗 集成要点

### JWT 认证流程
1. **前端** → POST `/api/v1/base/access_token` 携带凭证
2. **后端** → PolicyGate 放行公开端点 → 返回 JWT
3. **前端** → 存储 token → 后续请求携带 `Authorization: Bearer <token>`
4. **后端** → `get_current_user()` 通过 JWKS 验证 → 设置 `request.state.user`
5. **中间件** → RateLimiter 检查用户类型 → PolicyGate 执行访问策略

### 匿名用户 vs 永久用户
- **匿名**: 受限的速率限制，仅可访问 `/api/v1/messages*` 和 `/api/v1/llm/models`（仅 GET）
- **永久**: 更高限额，完整 RBAC 访问管理端点
- **检测**: JWT claim `user_type` 或邮箱模式（`anon_*` = 匿名）

### SSE (Server-Sent Events)
- **端点**: `/api/v1/messages/{id}/events`（流式 AI 响应）
- **中间件**: `app/core/sse_guard.py` 防止活跃 SSE 连接被限流阻断
- **前端**: POST `/api/v1/messages` 创建会话后 EventSource 连接

## ⚙️ 配置与密钥

### 环境文件
- **后端**: `.env`（根目录）→ 由 `app/settings/config.py::Settings` 加载
- **前端**: `web/.env.development` / `web/.env.production` → Vite 环境变量（`VITE_*`）

### 关键配置项
```bash
# JWT（详见 docs/JWT_HARDENING_GUIDE.md）
JWT_CLOCK_SKEW_SECONDS=120       # Supabase 时钟偏移容忍
JWT_REQUIRE_NBF=false            # Supabase token 缺少 nbf 声明
JWT_ALLOWED_ALGORITHMS=ES256,RS256,HS256

# 限流（app/core/rate_limiter.py）
RATE_LIMIT_ENABLED=true
ANON_ENABLED=true                # 允许匿名用户
POLICY_GATE_ENABLED=true         # 执行访问策略

# 监控（app/core/metrics.py）
TRACE_HEADER_NAME=X-Trace-ID
```

## ⚠️ 常见陷阱

1. **不要绕过中间件**: PolicyGate/RateLimiter 对安全至关重要；使用 `app/core/policy_gate.py` 中的公开端点模式来豁免
2. **永不提交密钥**: `.env` 已加入 gitignore；使用 `.env.example` 作为模板
3. **数据库模式变更**: 模型更新后始终运行 `make migrate`（Aerich 跟踪变更）
4. **前端 token 刷新**: 401 响应触发 `useUserStore().logout()` → 清除状态 → 重定向到登录
5. **Prometheus 指标**: 未经更新 `docs/GW_AUTH_README.md` 监控章节，不要创建新指标类型

## 📚 核心文档

- **架构**: `docs/PROJECT_OVERVIEW.md`（系统图、技术栈、已完成功能）
- **JWT 硬化**: `docs/JWT_HARDENING_GUIDE.md`（时钟偏移、算法限制、Supabase 兼容性）
- **网关认证**: `docs/GW_AUTH_README.md`（健康探针、指标、回滚程序）
- **脚本索引**: `docs/SCRIPTS_INDEX.md`（24 个按用例分类的运维脚本）
- **Vue 标准**: `docs/coding-standards/vue-best-practices.md`（禁止 JSX、Composition API、Naive UI 模式）
- **现有约定**: `AGENTS.md`（项目结构、命令、风格指南）

## 📋 快速参考

| 任务 | 命令 |
|------|---------|
| 启动后端 | `python run.py` 或 `make start` |
| 启动前端 | `cd web && pnpm dev` |
| 运行测试 | `make test` |
| 格式化代码 | `make format`（后端），`cd web && pnpm prettier`（前端）|
| 代码检查 | `make lint`（后端），`cd web && pnpm lint`（前端）|
| 构建 Docker | `docker build -t vue-fastapi-admin .` |
| 健康检查 | `curl http://localhost:9999/api/v1/healthz` |
| 指标查看 | `curl http://localhost:9999/api/v1/metrics` |
| API 文档 | http://localhost:9999/docs（Swagger UI）|
