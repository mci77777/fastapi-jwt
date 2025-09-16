# API 接口规范

<cite>
**本文档引用的文件**
- [users.py](file://app/api/v1/users/users.py)
- [roles.py](file://app/api/v1/roles/roles.py)
- [menus.py](file://app/api/v1/menus/menus.py)
- [apis.py](file://app/api/v1/apis/apis.py)
- [auditlog.py](file://app/api/v1/auditlog/auditlog.py)
- [users.py](file://app/schemas/users.py)
- [roles.py](file://app/schemas/roles.py)
- [menus.py](file://app/schemas/menus.py)
- [apis.py](file://app/schemas/apis.py)
- [dependency.py](file://app/core/dependency.py)
</cite>

## 目录
1. [简介](#简介)
2. [用户管理接口](#用户管理接口)
3. [角色管理接口](#角色管理接口)
4. [菜单管理接口](#菜单管理接口)
5. [API 权限接口](#api-权限接口)
6. [审计日志接口](#审计日志接口)
7. [认证与权限机制](#认证与权限机制)

## 简介
本文档系统化描述 `vue-fastapi-admin` 项目中 v1 版本的 RESTful API 接口。涵盖用户、角色、菜单、API 权限和审计日志五大功能模块，详细说明各接口的 URL 路径、HTTP 方法、请求参数、请求/响应体结构以及认证权限要求。通过分析 `users.py` 和 `roles.py` 中的路由实现，展示 FastAPI 的路由装饰器与依赖注入机制的实际应用。

## 用户管理接口

提供对系统用户的增删改查操作，支持分页查询、状态管理与密码重置。

| 端点 | 方法 | 描述 | 认证要求 | 权限要求 |
|------|------|------|----------|----------|
| `/api/v1/users` | GET | 分页查询用户列表 | 是 | `user:read` |
| `/api/v1/users/{user_id}` | GET | 获取指定用户详情 | 是 | `user:read` |
| `/api/v1/users` | POST | 创建新用户 | 是 | `user:create` |
| `/api/v1/users/{user_id}` | PUT | 更新用户信息 | 是 | `user:update` |
| `/api/v1/users/{user_id}` | DELETE | 删除用户 | 是 | `user:delete` |
| `/api/v1/users/{user_id}/reset-password` | PUT | 重置用户密码 | 是 | `user:update` |

**请求参数说明**
- 路径参数：`user_id` (str) - 用户唯一标识
- 查询参数（GET 列表）：
  - `page` (int, 默认 1)
  - `page_size` (int, 默认 10)
  - `username` (str, 可选)
  - `status` (int, 可选)

**请求体 Schema**
- 创建/更新用户使用 `UserCreate` 和 `UserUpdate` 模型，定义于 `app/schemas/users.py`，包含用户名、邮箱、昵称、状态、角色关联等字段。

**响应体 Schema**
- 单个用户返回 `UserOut` 模型，包含用户基本信息及关联角色。
- 列表返回 `StandardResp[List[UserOut]]`，封装分页信息与数据。

**示例：FastAPI 路由定义**
```python
@router.get("/{user_id}", response_model=StandardResp[UserOut])
async def get_user(
    user_id: str,
    current_user: CurrentUserDep,
    _: None = Depends(RBAC("user:read"))
):
    ...
```

**中文说明**
该接口使用 FastAPI 的 `response_model` 指定返回结构，通过 `CurrentUserDep` 依赖注入获取当前登录用户，并使用 `RBAC("user:read")` 验证权限。

**本节来源**
- [users.py](file://app/api/v1/users/users.py#L1-L200)
- [users.py](file://app/schemas/users.py#L1-L50)

## 角色管理接口

管理角色的创建、分配与权限配置，支持角色与用户的绑定关系操作。

| 端点 | 方法 | 描述 | 认证要求 | 权限要求 |
|------|------|------|----------|----------|
| `/api/v1/roles` | GET | 分页查询角色列表 | 是 | `role:read` |
| `/api/v1/roles/{role_id}` | GET | 获取角色详情 | 是 | `role:read` |
| `/api/v1/roles` | POST | 创建角色 | 是 | `role:create` |
| `/api/v1/roles/{role_id}` | PUT | 更新角色信息 | 是 | `role:update` |
| `/api/v1/roles/{role_id}` | DELETE | 删除角色 | 是 | `role:delete` |
| `/api/v1/roles/{role_id}/users` | GET | 获取角色下所有用户 | 是 | `role:read` |
| `/api/v1/roles/{role_id}/bind-users` | PUT | 绑定用户到角色 | 是 | `role:update` |

**请求参数说明**
- 路径参数：`role_id` (str)
- 查询参数（GET 列表）：
  - `page`, `page_size`
  - `name` (str, 可选)

**请求体 Schema**
- 创建/更新使用 `RoleCreate` 和 `RoleUpdate` 模型，包含角色名称、编码、描述、状态及关联的菜单和 API 权限。

**响应体 Schema**
- 返回 `RoleOut` 模型，包含角色信息及关联的菜单 ID 列表和 API 权限列表。
- 列表返回 `StandardResp[List[RoleOut]]`。

**示例：依赖注入使用**
```python
@router.post("", response_model=StandardResp)
async def create_role(
    role_in: RoleCreate,
    current_user: CurrentUserDep,
    _: None = Depends(RBAC("role:create"))
):
    ...
```

**中文说明**
`role_in: RoleCreate` 实现了请求体自动解析与验证，`Depends(RBAC(...))` 实现声明式权限控制。

**本节来源**
- [roles.py](file://app/api/v1/roles/roles.py#L1-L180)
- [roles.py](file://app/schemas/roles.py#L1-L40)

## 菜单管理接口

提供对系统菜单树的管理功能，支持层级结构的增删改查。

| 端点 | 方法 | 描述 | 认证要求 | 权限要求 |
|------|------|------|----------|----------|
| `/api/v1/menus` | GET | 获取菜单树（支持扁平化） | 是 | `menu:read` |
| `/api/v1/menus/{menu_id}` | GET | 获取菜单详情 | 是 | `menu:read` |
| `/api/v1/menus` | POST | 创建菜单 | 是 | `menu:create` |
| `/api/v1/menus/{menu_id}` | PUT | 更新菜单 | 是 | `menu:update` |
| `/api/v1/menus/{menu_id}` | DELETE | 删除菜单 | 是 | `menu:delete` |

**请求参数说明**
- 路径参数：`menu_id` (str)
- 查询参数：
  - `flat` (bool, 默认 False) - 是否返回扁平列表

**请求体 Schema**
- 使用 `MenuCreate` 和 `MenuUpdate` 模型，包含菜单名称、图标、路径、组件、排序、父级 ID、状态等字段。

**响应体 Schema**
- 返回 `MenuOut` 模型，支持树形结构嵌套。
- 列表返回 `StandardResp[List[MenuOut]]` 或树形结构。

**本节来源**
- [menus.py](file://app/api/v1/menus/menus.py#L1-L150)
- [menus.py](file://app/schemas/menus.py#L1-L35)

## API 权限接口

管理系统的 API 端点权限，用于角色授权。

| 端点 | 方法 | 描述 | 认证要求 | 权限要求 |
|------|------|------|----------|----------|
| `/api/v1/apis` | GET | 分页查询 API 权限列表 | 是 | `api:read` |
| `/api/v1/apis/{api_id}` | GET | 获取 API 详情 | 是 | `api:read` |
| `/api/v1/apis` | POST | 创建 API 权限 | 是 | `api:create` |
| `/api/v1/apis/{api_id}` | PUT | 更新 API 权限 | 是 | `api:update` |
| `/api/v1/apis/{api_id}` | DELETE | 删除 API 权限 | 是 | `api:delete` |

**请求参数说明**
- 路径参数：`api_id` (str)
- 查询参数：`page`, `page_size`, `method`, `path`

**请求体 Schema**
- 使用 `ApiCreate` 和 `ApiUpdate` 模型，包含 API 名称、路径、方法、描述、模块等。

**响应体 Schema**
- 返回 `ApiOut` 模型。
- 列表返回 `StandardResp[List[ApiOut]]`。

**本节来源**
- [apis.py](file://app/api/v1/apis/apis.py#L1-L130)
- [apis.py](file://app/schemas/apis.py#L1-L30)

## 审计日志接口

提供系统操作日志的查询功能，用于安全审计。

| 端点 | 方法 | 描述 | 认证要求 | 权限要求 |
|------|------|------|----------|----------|
| `/api/v1/auditlog` | GET | 分页查询审计日志 | 是 | `auditlog:read` |
| `/api/v1/auditlog/{log_id}` | GET | 获取日志详情 | 是 | `auditlog:read` |

**请求参数说明**
- 路径参数：`log_id` (str)
- 查询参数：`page`, `page_size`, `user_id`, `action`, `start_time`, `end_time`

**响应体 Schema**
- 返回 `AuditLogOut` 模型，包含操作用户、时间、IP、操作类型、目标对象、请求参数等。
- 列表返回 `StandardResp[List[AuditLogOut]]`。

**本节来源**
- [auditlog.py](file://app/api/v1/auditlog/auditlog.py#L1-L80)

## 认证与权限机制

系统采用 JWT 进行认证，通过依赖注入实现细粒度权限控制。

### 认证流程
1. 用户登录获取 JWT Token
2. 后续请求在 `Authorization` 头部携带 `Bearer <token>`
3. `CurrentUserDep` 依赖解析 Token 并验证用户状态

### 权限控制
使用 `RBAC(permission_code)` 依赖实现基于角色的访问控制（RBAC）：

```python
_: None = Depends(RBAC("user:read"))
```

该依赖会检查当前用户是否拥有指定权限码，若无权限则抛出 403 异常。

**核心组件**
- `app/core/dependency.py`：定义 `CurrentUserDep` 和 `RBAC` 依赖
- `app/utils/jwt_utils.py`：JWT 编码解码逻辑
- `app/schemas/base.py`：定义通用响应结构 `StandardResp`

**本节来源**
- [dependency.py](file://app/core/dependency.py#L1-L100)
- [jwt_utils.py](file://app/utils/jwt_utils.py#L1-L80)
- [base.py](file://app/schemas/base.py#L1-L20)