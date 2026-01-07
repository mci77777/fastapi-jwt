# GymBro 重构：User SSOT + Supabase 同步 + FastAPI 门控（Overall）

## 你问的关键点结论

### 1) 云端 user 没做、同步全部走 Supabase —— 需要建表吗？
需要。因为 App 侧已经在做 Supabase PostgREST 的 upsert（例如 user_settings 的 upsert + onConflict），没有对应表会直接失败/走降级分支。
因此必须在 Supabase Postgres 建立 **user_profiles / user_settings / user_entitlements**（或你命名的等价表），并配置唯一约束与 RLS 策略。

### 2) FastAPI 后端需要做什么调整？
FastAPI 不需要“存储”用户数据（因为 SSOT 在 Supabase），但需要做两件事：
1. **聚合与门控**：提供 **GET /v1/me**，把 Supabase 的 profile/settings/entitlements 聚合成 app 友好的快照（并做订阅等级/功能门控）。
2. **AI 端点鉴权与限流**：在 AI 端点上挂 entitlement gate（例如 pro 才能用 memory/更大模型），并保留现有 JWT(JWKS) 验证、TraceID、RateLimit 中间件链。

---

## 目标架构（SSOT + KISS）

### App（Android, MVI）
- 本地 SSOT：`core-user-data-center` 的 `UnifiedUserData`
- 云端 SSOT：Supabase（profile/settings/entitlements 三表）
- 同步策略：**best-effort push + 登录后 pull（hydrate） + 手动触发 forceSync**
- DataStore：只保留 **设备级** 设置（避免用户级数据重复存储）

### Backend（FastAPI）
- 不再做 user 的主存储
- 只做：认证（Supabase JWT）+ /v1/me 聚合 + entitlement gate + AI 编排

---

## 目标 TREE

### App 目标树（关键目录）
```text
X:/GymBro
├── core-user-data-center
│   └── src/main/kotlin/com/example/gymbro/core/userdata
│       ├── api
│       │   ├── model
│       │   │   ├── UnifiedUserData.kt
│       │   │   ├── UserEntitlement.kt
│       │   │   ├── UserDataState.kt
│       │   │   └── SyncStatus.kt
│       │   ├── prompt
│       │   │   └── UserProfilePromptContextProvider.kt
│       │   └── UserDataCenterApi.kt
│       └── internal
│           ├── api
│           │   └── UserDataCenterApiImpl.kt
│           ├── di
│           │   └── UserDataCenterModule.kt
│           ├── mapper
│           │   ├── UserDataMapper.kt
│           │   └── EntitlementResolver.kt
│           ├── repository
│           │   └── UserDataRepositoryImpl.kt
│           └── synchronizer
│               └── UserDataSynchronizer.kt
├── data
│   └── src/main/kotlin/com/example/gymbro/data
│       ├── local/datastore
│       │   └── UserPreferencesRepositoryImpl.kt
│       ├── repository/subscription
│       │   └── SubscriptionRepositoryImpl.kt
│       └── auth/provider/supabase
│           ├── SupabaseAuthServiceProvider.kt
│           └── SupabaseRealtimeServiceProvider.kt
└── features
    ├── profile
    │   └── ... (DataManagementScreen / Profile 入口/设置)
    └── coach
        └── ... (Debug: /v1/me 测试卡片)

```

### FastAPI 目标树（关键目录）
```text
D:\GymBro\vue-fastapi-admin
├── run.py
├── app
│   ├── core
│   │   ├── application.py
│   │   ├── exceptions.py
│   │   └── middleware
│   │       ├── trace_id.py
│   │       ├── policy_gate.py
│   │       └── rate_limit.py
│   ├── auth
│   │   └── dependencies.py
│   ├── repositories
│   │   └── user_repo.py                 # NEW
│   ├── services
│   │   ├── supabase_admin.py            # NEW
│   │   └── entitlement_service.py       # NEW
│   └── api
│       └── v1
│           ├── me.py                    # NEW  (GET /v1/me)
│           └── ai.py                    # existing (AI endpoints)
├── tests
│   ├── test_me_endpoint.py              # NEW
│   └── test_entitlement_gate.py         # NEW
└── docs
    └── archive/dashboard-refactor
        └── ARCHITECTURE_OVERVIEW.md     # update mobile API section

```

---

## 改动影响目录（按模块聚合）

### Android（主要）
- `core-user-data-center`：同步器补齐（auth listener + pull/hydrate）、门控统一（EntitlementResolver）、prompt 上下文最小化
- `data`：Supabase schema/mapper 对齐；SubscriptionRepositoryImpl 不再返回 null；UserPreferencesRepositoryImpl 清债
- `features/profile`：DataManagement 手动同步入口；订阅/同步状态展示
- `features/coach`：Debug(/v1/me) 测试卡片与实际 /v1/me 合约一致

### FastAPI（主要）
- 新增 Supabase admin client + user repository（服务端读取 Supabase 表）
- 新增 /v1/me
- 新增 entitlement gate（中间件或依赖）
- 补齐 tests 与 docs

---

## 预计改动文件清单（来自两份 CSV 聚合）
> 说明：包含显式路径与通配符（以 MCP codebase 检索为准）

- D:/GymBro/vue-fastapi-admin/app/api/v1/ai/*.py
- D:/GymBro/vue-fastapi-admin/app/api/v1/me.py
- D:/GymBro/vue-fastapi-admin/app/core/application.py
- D:/GymBro/vue-fastapi-admin/app/repositories/user_repo.py
- D:/GymBro/vue-fastapi-admin/app/services/entitlement_service.py
- D:/GymBro/vue-fastapi-admin/app/services/supabase_admin.py
- D:/GymBro/vue-fastapi-admin/docs/archive/dashboard-refactor/ARCHITECTURE_OVERVIEW.md
- D:/GymBro/vue-fastapi-admin/docs/supabase/migrations/001_user_tables.sql
- D:/GymBro/vue-fastapi-admin/docs/supabase/migrations/002_user_rls.sql
- D:/GymBro/vue-fastapi-admin/tests/test_entitlement_gate.py
- D:/GymBro/vue-fastapi-admin/tests/test_me_endpoint.py
- X:/GymBro/** (按 codebase 检索列出实际修改文件)
- X:/GymBro/core-user-data-center/src/main/kotlin/**/EntitlementResolver*.kt
- X:/GymBro/core-user-data-center/src/main/kotlin/**/UserDataCenterApi*.kt
- X:/GymBro/core-user-data-center/src/main/kotlin/**/UserDataRepository*.kt
- X:/GymBro/core-user-data-center/src/main/kotlin/**/UserDataSynchronizer.kt
- X:/GymBro/core-user-data-center/src/main/kotlin/**/api/model/UserEntitlement*.kt
- X:/GymBro/core-user-data-center/src/main/kotlin/**/prompt/**
- X:/GymBro/core-user-data-center/src/main/kotlin/com/example/gymbro/core/userdata/api/prompt/UserProfilePromptContextProvider.kt
- X:/GymBro/core-user-data-center/src/main/kotlin/com/example/gymbro/core/userdata/internal/synchronizer/UserDataSynchronizer.kt
- X:/GymBro/core-user-data-center/src/test/kotlin/**
- X:/GymBro/core-user-data-center/src/test/kotlin/**/EntitlementResolver*Test*.kt
- X:/GymBro/core-user-data-center/src/test/kotlin/**/Mapper*Test*.kt
- X:/GymBro/data/src/main/kotlin/**/CloudGateway*UserService*.kt
- X:/GymBro/data/src/main/kotlin/**/SubscriptionApi*.kt
- X:/GymBro/data/src/main/kotlin/**/Supabase*CloudSync*.kt
- X:/GymBro/data/src/main/kotlin/**/SupabaseUserCloudSyncPort*.kt
- X:/GymBro/data/src/main/kotlin/**/SupabaseUserSchema*.kt
- X:/GymBro/data/src/main/kotlin/**/SupabaseUserWriteMapper*.kt
- X:/GymBro/data/src/main/kotlin/**/UserPreferencesRepositoryImpl.kt
- X:/GymBro/data/src/main/kotlin/**/UserSettings*.kt
- X:/GymBro/data/src/main/kotlin/com/example/gymbro/data/local/datastore/UserPreferencesRepositoryImpl.kt
- X:/GymBro/data/src/main/kotlin/com/example/gymbro/data/repository/subscription/SubscriptionRepositoryImpl.kt
- X:/GymBro/docs/refactor/REFAC_SMOKE_CHECKLIST.md
- X:/GymBro/docs/refactor/USER_DATA_SSOT.md
- X:/GymBro/docs/refactor/USER_TABLES_CONTRACT.md
- X:/GymBro/features/coach/**/Debug*.*
- X:/GymBro/features/profile/src/main/kotlin/**/dataManagement/**

---

## 两份 CSV TODO
- App CSV：`app_refactor_todo.csv`
- Backend CSV：`backend_fastapi_refactor_todo.csv`

（你可以把它们直接丢到 `issues/` 目录作为任务看板来源。）
