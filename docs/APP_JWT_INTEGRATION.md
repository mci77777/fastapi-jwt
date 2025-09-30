# App JWT 对接指南

## 📋 概述

本文档提供移动App（Android/iOS）与GymBro后端API的JWT认证对接指南。

## 🔐 认证流程

### 1. 登录获取Token

```
用户输入用户名密码
    ↓
POST /api/v1/base/access_token
    ↓
返回JWT token
    ↓
App保存token到本地存储
    ↓
后续请求携带token
```

### 2. Token刷新流程

```
API请求返回401
    ↓
检测到token过期
    ↓
POST /api/v1/base/refresh_token
    ↓
返回新token
    ↓
重试原始请求
```

## 🎫 Token格式

### JWT Claims

```json
{
  "iss": "https://rykglivrwzcykhhnxwoz.supabase.co/auth/v1",
  "sub": "test-user-admin",
  "aud": "authenticated",
  "exp": 1735550400,
  "iat": 1735546800,
  "email": "admin@test.local",
  "role": "authenticated",
  "is_anonymous": false,
  "user_metadata": {
    "username": "admin",
    "is_admin": true
  },
  "app_metadata": {
    "provider": "test",
    "providers": ["test"]
  }
}
```

### Claims说明

| 字段 | 类型 | 说明 |
|------|------|------|
| iss | string | 发行者（Supabase URL） |
| sub | string | 用户唯一标识 |
| aud | string | 受众（固定为"authenticated"） |
| exp | number | 过期时间（Unix时间戳） |
| iat | number | 签发时间（Unix时间戳） |
| email | string | 用户邮箱 |
| role | string | 用户角色 |
| is_anonymous | boolean | 是否匿名用户 |
| user_metadata | object | 用户元数据 |
| app_metadata | object | 应用元数据 |

## 🔌 API端点

### 基础URL

```
开发环境: http://localhost:9999
生产环境: https://api.gymbro.com
```

### 1. 登录

**端点**: `POST /api/v1/base/access_token`

**请求头**:
```
Content-Type: application/json
```

**请求体**:
```json
{
  "username": "admin",
  "password": "123456"
}
```

**成功响应** (200):
```json
{
  "code": 200,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  },
  "msg": "success"
}
```

**失败响应** (401):
```json
{
  "code": 401,
  "data": null,
  "msg": "用户名或密码错误"
}
```

### 2. 刷新Token

**端点**: `POST /api/v1/base/refresh_token`

**请求头**:
```
token: <your_current_token>
```

**成功响应** (200):
```json
{
  "code": 200,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  },
  "msg": "success"
}
```

**失败响应** (401):
```json
{
  "code": 401,
  "data": null,
  "msg": "Token过期时间超过7天，请重新登录"
}
```

### 3. 获取用户信息

**端点**: `GET /api/v1/base/userinfo`

**请求头**:
```
token: <your_token>
```

**成功响应** (200):
```json
{
  "code": 200,
  "data": {
    "id": "test-user-admin",
    "username": "admin",
    "email": "admin@test.local",
    "avatar": null,
    "roles": ["admin"],
    "is_superuser": true,
    "is_active": true
  },
  "msg": "success"
}
```

### 4. 获取用户菜单

**端点**: `GET /api/v1/base/usermenu`

**请求头**:
```
token: <your_token>
```

**成功响应** (200):
```json
{
  "code": 200,
  "data": [],
  "msg": "success"
}
```

## 📱 客户端实现示例

### Android (Kotlin)

```kotlin
// 1. 定义数据模型
data class LoginRequest(
    val username: String,
    val password: String
)

data class LoginResponse(
    val code: Int,
    val data: TokenData?,
    val msg: String
)

data class TokenData(
    val access_token: String,
    val token_type: String
)

// 2. 创建API接口
interface GymBroApi {
    @POST("/api/v1/base/access_token")
    suspend fun login(@Body request: LoginRequest): LoginResponse
    
    @POST("/api/v1/base/refresh_token")
    suspend fun refreshToken(@Header("token") token: String): LoginResponse
    
    @GET("/api/v1/base/userinfo")
    suspend fun getUserInfo(@Header("token") token: String): UserInfoResponse
}

// 3. 实现Token拦截器
class TokenInterceptor(private val tokenManager: TokenManager) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val originalRequest = chain.request()
        
        // 添加token到请求头
        val token = tokenManager.getToken()
        val newRequest = if (token != null) {
            originalRequest.newBuilder()
                .header("token", token)
                .build()
        } else {
            originalRequest
        }
        
        val response = chain.proceed(newRequest)
        
        // 检测401错误并刷新token
        if (response.code == 401 && !originalRequest.url.encodedPath.contains("access_token")) {
            synchronized(this) {
                val currentToken = tokenManager.getToken()
                if (currentToken != null) {
                    val refreshResponse = runBlocking {
                        api.refreshToken(currentToken)
                    }
                    
                    if (refreshResponse.code == 200 && refreshResponse.data != null) {
                        tokenManager.saveToken(refreshResponse.data.access_token)
                        
                        // 重试原始请求
                        val retryRequest = originalRequest.newBuilder()
                            .header("token", refreshResponse.data.access_token)
                            .build()
                        return chain.proceed(retryRequest)
                    } else {
                        // 刷新失败，跳转登录
                        tokenManager.clearToken()
                    }
                }
            }
        }
        
        return response
    }
}

// 4. 使用示例
class AuthRepository(private val api: GymBroApi, private val tokenManager: TokenManager) {
    suspend fun login(username: String, password: String): Result<TokenData> {
        return try {
            val response = api.login(LoginRequest(username, password))
            if (response.code == 200 && response.data != null) {
                tokenManager.saveToken(response.data.access_token)
                Result.success(response.data)
            } else {
                Result.failure(Exception(response.msg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }
}
```

### iOS (Swift)

```swift
// 1. 定义数据模型
struct LoginRequest: Codable {
    let username: String
    let password: String
}

struct LoginResponse: Codable {
    let code: Int
    let data: TokenData?
    let msg: String
}

struct TokenData: Codable {
    let access_token: String
    let token_type: String
}

// 2. 创建API客户端
class GymBroAPIClient {
    static let shared = GymBroAPIClient()
    private let baseURL = "http://localhost:9999"
    
    func login(username: String, password: String) async throws -> TokenData {
        let url = URL(string: "\(baseURL)/api/v1/base/access_token")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        
        let body = LoginRequest(username: username, password: password)
        request.httpBody = try JSONEncoder().encode(body)
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.invalidResponse
        }
        
        let loginResponse = try JSONDecoder().decode(LoginResponse.self, from: data)
        
        guard loginResponse.code == 200, let tokenData = loginResponse.data else {
            throw APIError.loginFailed(loginResponse.msg)
        }
        
        // 保存token
        TokenManager.shared.saveToken(tokenData.access_token)
        
        return tokenData
    }
    
    func refreshToken() async throws -> TokenData {
        guard let currentToken = TokenManager.shared.getToken() else {
            throw APIError.noToken
        }
        
        let url = URL(string: "\(baseURL)/api/v1/base/refresh_token")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue(currentToken, forHTTPHeaderField: "token")
        
        let (data, response) = try await URLSession.shared.data(for: request)
        
        let refreshResponse = try JSONDecoder().decode(LoginResponse.self, from: data)
        
        guard refreshResponse.code == 200, let tokenData = refreshResponse.data else {
            throw APIError.refreshFailed(refreshResponse.msg)
        }
        
        TokenManager.shared.saveToken(tokenData.access_token)
        
        return tokenData
    }
}
```

## 🚦 限流策略

### 用户类型限制

| 用户类型 | QPS限制 | 并发SSE流 | 每日请求限制 |
|---------|---------|-----------|-------------|
| 匿名用户 | 5 | 2 | 1000 |
| 永久用户 | 10 | 2 | 无限制 |

### 限流响应

当触发限流时，API返回429状态码：

```json
{
  "code": 429,
  "data": null,
  "msg": "请求过于频繁，请稍后再试"
}
```

## ❌ 错误码说明

| 错误码 | 说明 | 处理建议 |
|-------|------|---------|
| 200 | 成功 | - |
| 400 | 请求参数错误 | 检查请求参数格式 |
| 401 | 未授权/Token无效 | 刷新token或重新登录 |
| 403 | 权限不足 | 检查用户权限 |
| 404 | 资源不存在 | 检查API路径 |
| 429 | 请求过于频繁 | 降低请求频率 |
| 500 | 服务器内部错误 | 联系技术支持 |

## 🔍 调试技巧

### 1. 查看Token内容

使用 [jwt.io](https://jwt.io) 解码token查看claims。

### 2. 测试API

```bash
# 登录
curl -X POST http://localhost:9999/api/v1/base/access_token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'

# 获取用户信息
curl -X GET http://localhost:9999/api/v1/base/userinfo \
  -H "token: <your_token>"

# 刷新token
curl -X POST http://localhost:9999/api/v1/base/refresh_token \
  -H "token: <your_token>"
```

## ❓ 常见问题

### Q1: Token多久过期？

A: Token默认1小时后过期，可以通过refresh_token端点刷新。

### Q2: 刷新token失败怎么办？

A: 如果token过期超过7天，需要重新登录。

### Q3: 如何区分匿名用户和永久用户？

A: 检查JWT claims中的`is_anonymous`字段。

### Q4: 如何处理网络错误？

A: 实现重试机制，建议最多重试3次，间隔1秒。

### Q5: 是否支持多设备登录？

A: 支持，每个设备使用独立的token。

---

**文档版本**：v1.0
**最后更新**：2025-09-30
**技术支持**：support@gymbro.com

