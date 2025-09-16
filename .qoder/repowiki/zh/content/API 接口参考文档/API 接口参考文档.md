# API 接口参考文档

<cite>
**本文档中引用的文件**  
- [users.py](file://app/api/v1/users/users.py)
- [roles.py](file://app/api/v1/roles/roles.py)
- [menus.py](file://app/api/v1/menus/menus.py)
- [apis.py](file://app/api/v1/apis/apis.py)
- [auditlog.py](file://app/api/v1/auditlog/auditlog.py)
- [base.py](file://app/api/v1/base/base.py)
- [dependency.py](file://app/core/dependency.py)
- [schemas/users.py](file://app/schemas/users.py)
- [schemas/roles.py](file://app/schemas/roles.py)
- [schemas/menus.py](file://app/schemas/menus.py)
- [schemas/apis.py](file://app/schemas/apis.py)
- [schemas/base.py](file://app/schemas/base.py)
</cite>

## 目录
1. [简介](#简介)
2. [认证机制](#认证机制)
3. [用户管理接口](#用户管理接口)
4. [角色管理接口](#角色管理接口)
5. [菜单管理接口](#菜单管理接口)
6. [API管理接口](#api管理接口)
7. [操作日志接口](#操作日志接口)
8. [基础功能接口](#基础功能接口)
9. [Swagger UI 交互式文档](#swagger-ui-交互式文档)

## 简介
本API接口参考文档详细描述了 `app/api/v1/` 目录下所有模块的RESTful端点，包括用户、角色、菜单、API、操作日志和基础功能。每个接口均包含HTTP方法、完整路径、功能描述、请求头、请求体（如适用）、响应状态码及结构，并提供curl调用示例。

**Section sources**  
- [users.py](file://app/api/v1/users/users.py#L1-L82)
- [roles.py](file://app/api/v1/roles/roles.py#L1-L74)
- [menus.py](file://app/api/v1/menus/menus.py#L1-L64)
- [apis.py](file://app/api/v1/apis/apis.py#L1-L68)
- [auditlog.py](file://app/api/v1/auditlog/auditlog.py#L1-L49)
- [base.py](file://app/api/v1/base/base.py#L1-L104)

## 认证机制
所有需要权限的接口均通过 `Authorization: Bearer <token>` 进行身份验证。系统使用JWT（JSON Web Token）实现认证，由 `DependAuth` 和 `DependPermission` 两个依赖项控制。

- `DependAuth`：验证Token有效性，提取用户信息。
- `DependPermission`：检查当前用户是否具有访问该接口的权限。

未携带Token或Token无效将返回401状态码；无权限访问则返回403。

```mermaid
sequenceDiagram
participant Client as "客户端"
participant Auth as "AuthControl.is_authed"
participant Perm as "PermissionControl.has_permission"
participant API as "API端点"
Client->>Auth : 发送请求带Bearer Token
Auth->>Auth : 验证Token签名与过期时间
Auth-->>API : 返回用户对象或401错误
API->>Perm : 请求权限检查
Perm->>Perm : 查询用户角色及API权限
Perm-->>API : 通过或返回403错误
API-->>Client : 返回业务数据或错误信息
```

**Diagram sources**  
- [dependency.py](file://app/core/dependency.py#L1-L53)

**Section sources**  
- [dependency.py](file://app/core/dependency.py#L1-L53)

## 用户管理接口

### 获取用户列表
- **HTTP方法**: GET
- **路径**: `/api/v1/user/list`
- **功能描述**: 分页查询用户列表，支持按用户名、邮箱、部门ID搜索。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**:
  - `page`: 页码，默认1
  - `page_size`: 每页数量，默认10
  - `username`: 用户名模糊搜索
  - `email`: 邮箱模糊搜索
  - `dept_id`: 所属部门ID
- **响应状态码**:
  - 200: 成功，返回 `SuccessExtra` 结构，`data` 为用户列表（不含密码），包含部门信息
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/user/list?page=1&page_size=10" \
-H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 获取单个用户
- **HTTP方法**: GET
- **路径**: `/api/v1/user/get`
- **功能描述**: 根据用户ID获取用户详情。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**:
  - `user_id`: 用户ID
- **响应状态码**:
  - 200: 成功，返回 `Success` 结构，`data` 为用户信息（不含密码）
  - 401: 未认证
  - 403: 无权限
  - 404: 用户不存在
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/user/get?user_id=1" \
-H "Authorization: Bearer ..."
```

### 创建用户
- **HTTP方法**: POST
- **路径**: `/api/v1/user/create`
- **功能描述**: 创建新用户并分配角色。
- **请求头**: `Authorization: Bearer <token>`
- **请求体**: `UserCreate` 模型（定义于 `schemas/users.py`）
- **响应状态码**:
  - 200: 创建成功
  - 400: 邮箱已存在
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/user/create" \
-H "Authorization: Bearer ..." \
-H "Content-Type: application/json" \
-d '{"username":"testuser","email":"test@example.com","password":"123456","role_ids":[1]}'
```

### 更新用户
- **HTTP方法**: POST
- **路径**: `/api/v1/user/update`
- **功能描述**: 更新用户信息及角色分配。
- **请求头**: `Authorization: Bearer <token>`
- **请求体**: `UserUpdate` 模型（含ID和角色ID列表）
- **响应状态码**:
  - 200: 更新成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/user/update" \
-H "Authorization: Bearer ..." \
-H "Content-Type: application/json" \
-d '{"id":1,"username":"updated","email":"new@example.com","role_ids":[2]}'
```

### 删除用户
- **HTTP方法**: DELETE
- **路径**: `/api/v1/user/delete`
- **功能描述**: 根据用户ID删除用户。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**:
  - `user_id`: 用户ID
- **响应状态码**:
  - 200: 删除成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X DELETE "http://localhost:9999/api/v1/user/delete?user_id=1" \
-H "Authorization: Bearer ..."
```

### 重置密码
- **HTTP方法**: POST
- **路径**: `/api/v1/user/reset_password`
- **功能描述**: 将指定用户密码重置为默认值（123456）。
- **请求头**: `Authorization: Bearer <token>`
- **请求体**: `{"user_id": 1}`
- **响应状态码**:
  - 200: 重置成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/user/reset_password" \
-H "Authorization: Bearer ..." \
-H "Content-Type: application/json" \
-d '{"user_id":1}'
```

**Section sources**  
- [users.py](file://app/api/v1/users/users.py#L1-L82)
- [schemas/users.py](file://app/schemas/users.py)

## 角色管理接口

### 获取角色列表
- **HTTP方法**: GET
- **路径**: `/api/v1/role/list`
- **功能描述**: 分页查询角色列表，支持按角色名称搜索。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**:
  - `page`, `page_size`, `role_name`
- **响应状态码**:
  - 200: 成功，返回 `SuccessExtra`，`data` 为角色列表
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/role/list?role_name=admin" \
-H "Authorization: Bearer ..."
```

### 获取单个角色
- **HTTP方法**: GET
- **路径**: `/api/v1/role/get`
- **功能描述**: 根据角色ID获取角色详情。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: `role_id`
- **响应状态码**:
  - 200: 成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/role/get?role_id=1" \
-H "Authorization: Bearer ..."
```

### 创建角色
- **HTTP方法**: POST
- **路径**: `/api/v1/role/create`
- **功能描述**: 创建新角色。
- **请求头**: `Authorization: Bearer <token>`
- **请求体**: `RoleCreate` 模型
- **响应状态码**:
  - 200: 创建成功
  - 400: 角色名已存在
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/role/create" \
-H "Authorization: Bearer ..." \
-H "Content-Type: application/json" \
-d '{"name":"new_role","description":"a new role"}'
```

### 更新角色
- **HTTP方法**: POST
- **路径**: `/api/v1/role/update`
- **功能描述**: 更新角色信息。
- **请求头**: `Authorization: Bearer <token>`
- **请求体**: `RoleUpdate` 模型
- **响应状态码**:
  - 200: 更新成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/role/update" \
-H "Authorization: Bearer ..." \
-H "Content-Type: application/json" \
-d '{"id":1,"name":"updated_role"}'
```

### 删除角色
- **HTTP方法**: DELETE
- **路径**: `/api/v1/role/delete`
- **功能描述**: 删除指定角色。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: `role_id`
- **响应状态码**:
  - 200: 删除成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X DELETE "http://localhost:9999/api/v1/role/delete?role_id=1" \
-H "Authorization: Bearer ..."
```

### 获取角色权限
- **HTTP方法**: GET
- **路径**: `/api/v1/role/authorized`
- **功能描述**: 获取角色的菜单和API权限。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: `id` (角色ID)
- **响应状态码**:
  - 200: 成功，返回角色及其关联的菜单和API
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/role/authorized?id=1" \
-H "Authorization: Bearer ..."
```

### 更新角色权限
- **HTTP方法**: POST
- **路径**: `/api/v1/role/authorized`
- **功能描述**: 更新角色的菜单和API权限。
- **请求头**: `Authorization: Bearer <token>`
- **请求体**: `RoleUpdateMenusApis` 模型
- **响应状态码**:
  - 200: 更新成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/role/authorized" \
-H "Authorization: Bearer ..." \
-H "Content-Type: application/json" \
-d '{"id":1,"menu_ids":[1,2],"api_infos":[{"method":"GET","path":"/api/v1/user/list"}]}'
```

**Section sources**  
- [roles.py](file://app/api/v1/roles/roles.py#L1-L74)
- [schemas/roles.py](file://app/schemas/roles.py)

## 菜单管理接口

### 获取菜单列表
- **HTTP方法**: GET
- **路径**: `/api/v1/menu/list`
- **功能描述**: 获取完整的菜单树结构（含子菜单）。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: `page`, `page_size`
- **响应状态码**:
  - 200: 成功，返回树形结构菜单列表
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/menu/list" \
-H "Authorization: Bearer ..."
```

### 获取单个菜单
- **HTTP方法**: GET
- **路径**: `/api/v1/menu/get`
- **功能描述**: 根据菜单ID获取菜单详情。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: `menu_id`
- **响应状态码**:
  - 200: 成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/menu/get?menu_id=1" \
-H "Authorization: Bearer ..."
```

### 创建菜单
- **HTTP方法**: POST
- **路径**: `/api/v1/menu/create`
- **功能描述**: 创建新菜单项。
- **请求头**: `Authorization: Bearer <token>`
- **请求体**: `MenuCreate` 模型
- **响应状态码**:
  - 200: 创建成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/menu/create" \
-H "Authorization: Bearer ..." \
-H "Content-Type: application/json" \
-d '{"name":"New Menu","path":"/new","order":1}'
```

### 更新菜单
- **HTTP方法**: POST
- **路径**: `/api/v1/menu/update`
- **功能描述**: 更新菜单信息。
- **请求头**: `Authorization: Bearer <token>`
- **请求体**: `MenuUpdate` 模型
- **响应状态码**:
  - 200: 更新成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/menu/update" \
-H "Authorization: Bearer ..." \
-H "Content-Type: application/json" \
-d '{"id":1,"name":"Updated Menu"}'
```

### 删除菜单
- **HTTP方法**: DELETE
- **路径**: `/api/v1/menu/delete`
- **功能描述**: 删除菜单，若存在子菜单则禁止删除。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: `id`
- **响应状态码**:
  - 200: 删除成功
  - 400: 存在子菜单，无法删除
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X DELETE "http://localhost:9999/api/v1/menu/delete?id=1" \
-H "Authorization: Bearer ..."
```

**Section sources**  
- [menus.py](file://app/api/v1/menus/menus.py#L1-L64)
- [schemas/menus.py](file://app/schemas/menus.py)

## API管理接口

### 获取API列表
- **HTTP方法**: GET
- **路径**: `/api/v1/api/list`
- **功能描述**: 分页查询系统中所有API接口，支持按路径、简介、模块过滤。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: `page`, `page_size`, `path`, `summary`, `tags`
- **响应状态码**:
  - 200: 成功，返回API列表
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/api/list?tags=user" \
-H "Authorization: Bearer ..."
```

### 获取单个API
- **HTTP方法**: GET
- **路径**: `/api/v1/api/get`
- **功能描述**: 根据ID获取API详情。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: `id`
- **响应状态码**:
  - 200: 成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/api/get?id=1" \
-H "Authorization: Bearer ..."
```

### 创建API
- **HTTP方法**: POST
- **路径**: `/api/v1/api/create`
- **功能描述**: 手动创建API记录。
- **请求头**: `Authorization: Bearer <token>`
- **请求体**: `ApiCreate` 模型
- **响应状态码**:
  - 200: 创建成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/api/create" \
-H "Authorization: Bearer ..." \
-H "Content-Type: application/json" \
-d '{"path":"/api/v1/test","method":"GET","summary":"test api","tags":"test"}'
```

### 更新API
- **HTTP方法**: POST
- **路径**: `/api/v1/api/update`
- **功能描述**: 更新API信息。
- **请求头**: `Authorization: Bearer <token>`
- **请求体**: `ApiUpdate` 模型
- **响应状态码**:
  - 200: 更新成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/api/update" \
-H "Authorization: Bearer ..." \
-H "Content-Type: application/json" \
-d '{"id":1,"summary":"updated summary"}'
```

### 删除API
- **HTTP方法**: DELETE
- **路径**: `/api/v1/api/delete`
- **功能描述**: 删除API记录。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: `api_id`
- **响应状态码**:
  - 200: 删除成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X DELETE "http://localhost:9999/api/v1/api/delete?api_id=1" \
-H "Authorization: Bearer ..."
```

### 刷新API列表
- **HTTP方法**: POST
- **路径**: `/api/v1/api/refresh`
- **功能描述**: 扫描代码中的路由，自动刷新API列表。
- **请求头**: `Authorization: Bearer <token>`
- **请求体**: 无
- **响应状态码**:
  - 200: 刷新成功
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/api/refresh" \
-H "Authorization: Bearer ..."
```

**Section sources**  
- [apis.py](file://app/api/v1/apis/apis.py#L1-L68)
- [schemas/apis.py](file://app/schemas/apis.py)

## 操作日志接口

### 获取操作日志列表
- **HTTP方法**: GET
- **路径**: `/api/v1/auditlog/list`
- **功能描述**: 分页查询操作日志，支持多条件过滤（操作人、模块、方法、路径、状态码、时间范围等）。
- **请求头**: `Authorization: Bearer <token>`
- **请求参数**: `page`, `page_size`, `username`, `module`, `method`, `summary`, `path`, `status`, `start_time`, `end_time`
- **响应状态码**:
  - 200: 成功，返回日志列表
  - 401: 未认证
  - 403: 无权限
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/auditlog/list?username=admin&status=200" \
-H "Authorization: Bearer ..."
```

**Section sources**  
- [auditlog.py](file://app/api/v1/auditlog/auditlog.py#L1-L49)

## 基础功能接口

### 获取访问令牌
- **HTTP方法**: POST
- **路径**: `/api/v1/base/access_token`
- **功能描述**: 使用用户名密码获取JWT访问令牌。
- **请求头**: 无
- **请求体**: `CredentialsSchema` 模型（`username`, `password`）
- **响应状态码**:
  - 200: 登录成功，返回 `JWTOut` 结构
  - 400: 凭证错误
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/base/access_token" \
-H "Content-Type: application/json" \
-d '{"username":"admin","password":"admin"}'
```

### 获取用户信息
- **HTTP方法**: GET
- **路径**: `/api/v1/base/userinfo`
- **功能描述**: 获取当前登录用户的基本信息。
- **请求头**: `Authorization: Bearer <token>`
- **响应状态码**:
  - 200: 成功，返回用户信息（含头像）
  - 401: 未认证
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/base/userinfo" \
-H "Authorization: Bearer ..."
```

### 获取用户菜单
- **HTTP方法**: GET
- **路径**: `/api/v1/base/usermenu`
- **功能描述**: 获取当前用户有权访问的菜单树。
- **请求头**: `Authorization: Bearer <token>`
- **响应状态码**:
  - 200: 成功，返回菜单树结构
  - 401: 未认证
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/base/usermenu" \
-H "Authorization: Bearer ..."
```

### 获取用户API权限
- **HTTP方法**: GET
- **路径**: `/api/v1/base/userapi`
- **功能描述**: 获取当前用户有权访问的API列表（格式：`method+path`）。
- **请求头**: `Authorization: Bearer <token>`
- **响应状态码**:
  - 200: 成功，返回API权限列表
  - 401: 未认证
- **示例**:
```bash
curl -X GET "http://localhost:9999/api/v1/base/userapi" \
-H "Authorization: Bearer ..."
```

### 修改密码
- **HTTP方法**: POST
- **路径**: `/api/v1/base/update_password`
- **功能描述**: 用户修改自己的密码。
- **请求头**: `Authorization: Bearer <token>`
- **请求体**: `UpdatePassword` 模型（`old_password`, `new_password`）
- **响应状态码**:
  - 200: 修改成功
  - 400: 旧密码错误
  - 401: 未认证
- **示例**:
```bash
curl -X POST "http://localhost:9999/api/v1/base/update_password" \
-H "Authorization: Bearer ..." \
-H "Content-Type: application/json" \
-d '{"old_password":"old123","new_password":"new456"}'
```

**Section sources**  
- [base.py](file://app/api/v1/base/base.py#L1-L104)
- [schemas/login.py](file://app/schemas/login.py)
- [schemas/users.py](file://app/schemas/users.py)

## Swagger UI 交互式文档
系统提供自动生成的交互式API文档，可通过访问 `http://localhost:9999/docs` 查看。

### 优势
- **实时更新**：基于FastAPI自动生成，与代码同步。
- **交互测试**：可直接在浏览器中发送请求，无需外部工具。
- **参数验证**：自动验证输入参数格式。
- **认证支持**：提供 `Authorize` 按钮，方便携带Bearer Token。
- **响应预览**：清晰展示成功/失败响应示例。
- **模型定义**：展示所有Pydantic模型结构。

### 使用方法
1. 访问 `http://localhost:9999/docs`
2. 点击右上角 `Authorize` 按钮，输入 `Bearer <token>`
3. 展开任意API分组，点击 `Try it out`
4. 填写参数，点击 `Execute` 发送请求
5. 查看响应结果

此文档极大提升了API的可发现性和易用性，推荐开发者和测试人员优先使用。

[无来源，此部分为通用说明]