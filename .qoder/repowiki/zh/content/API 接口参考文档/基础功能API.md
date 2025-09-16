# 基础功能API

<cite>
**本文档引用的文件**  
- [base.py](file://app/api/v1/base/base.py)
- [login.py](file://app/schemas/login.py)
- [users.py](file://app/schemas/users.py)
- [jwt_utils.py](file://app/utils/jwt_utils.py)
- [dependency.py](file://app/core/dependency.py)
</cite>

## 目录
1. [简介](#简介)
2. [核心端点说明](#核心端点说明)
3. [JWT认证机制](#jwt认证机制)
4. [使用示例](#使用示例)
5. [依赖关系与流程图](#依赖关系与流程图)

## 简介
本API文档详细描述系统的基础认证功能，涵盖用户登录（`POST /api/v1/base/login`）和获取当前用户信息（`GET /api/v1/base/profile`）两个核心端点。登录成功后返回JWT令牌，该令牌是访问系统其他受保护API的必要凭证。所有后续请求均需在请求头中携带此令牌进行身份验证。

**Section sources**  
- [base.py](file://app/api/v1/base/base.py#L1-L103)

## 核心端点说明

### 登录端点：`POST /api/v1/base/access_token`
该端点用于用户身份验证并获取访问令牌。

#### 请求体参数
- `username`（字符串，必填）：用户登录名  
- `password`（字符串，必填）：用户密码  

请求体结构引用自 `schemas.CredentialsSchema`。

#### 成功响应
```json
{
  "code": 200,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "username": "admin"
  },
  "msg": "Success"
}
```

响应字段说明：
- `access_token`: JWT格式的访问令牌
- `username`: 当前登录用户名

#### 错误响应
- `401 Unauthorized`: 用户名或密码错误
- `422 Unprocessable Entity`: 请求参数格式错误

**Section sources**  
- [base.py](file://app/api/v1/base/base.py#L10-L25)
- [login.py](file://app/schemas/login.py#L5-L15)

### 获取用户信息端点：`GET /api/v1/base/userinfo`
该端点返回当前认证用户的所有信息。

#### 请求头要求
- `Authorization`: Bearer {access_token}

#### 成功响应
响应数据结构基于 `schemas.BaseUser`，并排除 `password` 字段，同时添加 `avatar` 头像字段。

```json
{
  "code": 200,
  "data": {
    "id": 1,
    "email": "admin@qq.com",
    "username": "admin",
    "is_active": true,
    "is_superuser": true,
    "created_at": "2023-01-01T00:00:00",
    "updated_at": "2023-01-01T00:00:00",
    "last_login": "2023-10-01T10:00:00",
    "roles": [],
    "avatar": "https://avatars.githubusercontent.com/u/54677442?v=4"
  },
  "msg": "Success"
}
```

**Section sources**  
- [base.py](file://app/api/v1/base/base.py#L27-L35)
- [users.py](file://app/schemas/users.py#L5-L15)

## JWT认证机制

### 令牌生成
使用 `create_access_token` 函数生成JWT令牌，载荷（payload）包含以下信息：
- `user_id`: 用户ID
- `username`: 用户名
- `is_superuser`: 是否为超级用户
- `exp`: 过期时间戳

令牌有效期由配置文件中的 `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` 决定，默认为60分钟。

```mermaid
flowchart TD
Start([开始]) --> ValidateInput["验证用户名密码"]
ValidateInput --> Authenticated{"认证成功?"}
Authenticated --> |否| Return401["返回401错误"]
Authenticated --> |是| GeneratePayload["生成JWT载荷"]
GeneratePayload --> EncodeJWT["使用SECRET_KEY签名"]
EncodeJWT --> ReturnToken["返回access_token"]
Return401 --> End([结束])
ReturnToken --> End
```

**Diagram sources**  
- [base.py](file://app/api/v1/base/base.py#L10-L25)
- [jwt_utils.py](file://app/utils/jwt_utils.py#L5-L10)

### 令牌验证
通过 `DependAuth` 依赖注入实现全局认证。验证流程如下：
1. 从请求头提取 `Authorization` 字段
2. 使用 `SECRET_KEY` 解码JWT
3. 验证签名有效性及是否过期
4. 查询数据库获取用户对象
5. 将用户ID存入上下文（CTX_USER_ID）

支持开发模式免密登录（token="dev"）。

**Section sources**  
- [dependency.py](file://app/core/dependency.py#L5-L53)
- [base.py](file://app/api/v1/base/base.py#L1)

## 使用示例

### 步骤1：登录获取Token
```bash
curl -X POST "http://localhost:8000/api/v1/base/access_token" \
     -H "Content-Type: application/json" \
     -d '{
           "username": "admin",
           "password": "123456"
         }'
```

输出：
```json
{
  "code": 200,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "username": "admin"
  },
  "msg": "Success"
}
```

### 步骤2：使用Token获取用户信息
```bash
curl -X GET "http://localhost:8000/api/v1/base/userinfo" \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

输出：
```json
{
  "code": 200,
  "data": {
    "id": 1,
    "email": "admin@qq.com",
    "username": "admin",
    "is_active": true,
    "is_superuser": true,
    "created_at": "2023-01-01T00:00:00",
    "last_login": "2023-10-01T10:00:00",
    "roles": [],
    "avatar": "https://avatars.githubusercontent.com/u/54677442?v=4"
  },
  "msg": "Success"
}
```

**Section sources**  
- [base.py](file://app/api/v1/base/base.py#L10-L35)

## 依赖关系与流程图

```mermaid
sequenceDiagram
participant Client as 客户端
participant BaseAPI as BaseAPI
participant UserController as UserController
participant JWTUtil as JWT工具
participant DB as 数据库
Client->>BaseAPI : POST /api/v1/base/access_token
BaseAPI->>UserController : authenticate(credentials)
UserController->>DB : 查询用户
DB-->>UserController : 返回用户对象
UserController-->>BaseAPI : 认证结果
BaseAPI->>JWTUtil : create_access_token(payload)
JWTUtil-->>BaseAPI : 返回JWT令牌
BaseAPI->>Client : 返回access_token
Client->>BaseAPI : GET /api/v1/base/userinfo
BaseAPI->>BaseAPI : DependAuth验证Token
BaseAPI->>UserController : get(user_id)
UserController->>DB : 查询用户信息
DB-->>UserController : 用户数据
UserController-->>BaseAPI : 用户对象
BaseAPI-->>Client : 返回用户信息不含密码
```

**Diagram sources**  
- [base.py](file://app/api/v1/base/base.py#L10-L35)
- [dependency.py](file://app/core/dependency.py#L5-L53)
- [jwt_utils.py](file://app/utils/jwt_utils.py#L5-L10)