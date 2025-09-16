# API 请求封装

<cite>
**本文档引用文件**  
- [index.js](file://web/src/utils/http/index.js)
- [interceptors.js](file://web/src/utils/http/interceptors.js)
- [helpers.js](file://web/src/utils/http/helpers.js)
- [api/index.js](file://web/src/api/index.js)
- [token.js](file://web/src/utils/auth/token.js)
</cite>

## 目录
1. [简介](#简介)
2. [请求层设计与实现](#请求层设计与实现)
3. [拦截器逻辑详解](#拦截器逻辑详解)
4. [辅助函数说明](#辅助函数说明)
5. [API 接口组织方式](#api-接口组织方式)
6. [认证信息注入机制](#认证信息注入机制)
7. [实际调用示例](#实际调用示例)

## 简介
本项目前端通过 Axios 封装了一套统一的 HTTP 请求机制，旨在简化网络请求流程、统一错误处理、自动管理认证状态。该封装体系由多个模块组成：`http/index.js` 创建请求实例，`interceptors.js` 处理请求与响应拦截，`helpers.js` 提供通用工具，`api/index.js` 按功能模块组织接口调用，`token.js` 管理 JWT 令牌的存储与读取。

## 请求层设计与实现

`utils/http/index.js` 文件中定义了 `createAxios` 工厂函数，用于创建自定义的 Axios 实例。该实例默认设置了 12 秒的超时时间，并允许传入额外配置（如 `baseURL`）进行扩展。通过 `import.meta.env.VITE_BASE_API` 动态注入基础 API 地址，确保开发与生产环境的正确路由指向。

请求实例创建后，自动注册了请求和响应拦截器，分别处理认证令牌附加和异常响应解析。最终导出的 `request` 实例即为整个应用中所有 API 调用的基础。

**Section sources**
- [index.js](file://web/src/utils/http/index.js#L1-L19)

## 拦截器逻辑详解

拦截器位于 `interceptors.js` 文件中，分为请求拦截（`reqResolve` / `reqReject`）和响应拦截（`resResolve` / `resReject`）两部分。

在请求阶段，`reqResolve` 函数会检查请求配置中的 `noNeedToken` 标志。若为 `true`（如登录接口），则跳过令牌附加；否则从本地存储中读取 JWT 令牌并注入到请求头的 `token` 字段中。

在响应阶段，`resResolve` 对成功响应进行统一判断：若后端返回的 `code !== 200`，则使用 `resolveResError` 解析错误信息并弹出提示。`resReject` 处理网络异常或 HTTP 错误状态码，特别地，当收到 `401` 状态码时，自动触发用户登出流程，清除用户状态并跳转至登录页。

**Section sources**
- [interceptors.js](file://web/src/utils/http/interceptors.js#L1-L59)

## 辅助函数说明

`helpers.js` 提供了两个关键辅助函数：

- `addBaseParams(params)`：用于在请求参数中自动补充当前用户的 `userId`，便于后端审计或个性化数据查询。
- `resolveResError(code, message)`：根据 HTTP 状态码或业务错误码映射为用户友好的提示信息，例如 `401` 显示“登录已过期”，`403` 显示“没有权限”等。

这些函数增强了请求的智能化和用户体验的一致性。

**Section sources**
- [helpers.js](file://web/src/utils/http/helpers.js#L1-L31)

## API 接口组织方式

`api/index.js` 文件集中定义了所有后端接口的调用方法，按模块划分，包括用户管理、角色管理、菜单管理、部门管理、API 管理和审计日志等。

每个接口均以函数形式暴露，使用 `request` 实例发起请求，并支持参数传递。例如：
- `getUserList(params)` 发起 GET 请求获取用户列表
- `createUser(data)` 发起 POST 请求创建用户
- `deleteUser(params)` 发起 DELETE 请求删除用户

该设计使得接口调用简洁明了，且易于维护和类型推导（配合 TypeScript 可实现完整类型提示）。

**Section sources**
- [index.js](file://web/src/api/index.js#L1-L42)

## 认证信息注入机制

认证流程依赖于 `token.js` 中的 `getToken()` 函数，该函数从本地存储（`lStorage`）中读取名为 `access_token` 的 JWT 令牌。

此函数被 `interceptors.js` 中的请求拦截器调用，实现认证信息的无缝注入。只要用户已登录且令牌有效，所有后续请求将自动携带 `token` 头部，无需在每次调用时手动传参。

此外，`setToken()` 和 `removeToken()` 分别用于登录成功后保存令牌和登出时清除令牌，形成完整的令牌生命周期管理。

**Section sources**
- [token.js](file://web/src/utils/auth/token.js#L1-L31)

## 实际调用示例

从前端组件发起请求的完整链路如下：

1. 用户在登录页提交账号密码，调用 `api.login(data)`。
2. 该请求带有 `{ noNeedToken: true }` 配置，跳过令牌检查。
3. 登录成功后，后端返回 JWT 令牌，前端调用 `setToken(token)` 存储。
4. 进入系统后，调用 `api.getUserInfo()` 获取用户信息。
5. 请求拦截器自动读取 `token` 并附加至请求头。
6. 后端验证通过，返回用户数据。
7. 若用户长时间未操作导致令牌过期，后端返回 `401`，响应拦截器捕获该错误，自动执行 `userStore.logout()` 清除状态并跳转登录页。

这一流程实现了无感认证与异常自动处理，极大提升了系统的健壮性和用户体验。

**Section sources**
- [index.js](file://web/src/utils/http/index.js#L1-L19)
- [interceptors.js](file://web/src/utils/http/interceptors.js#L1-L59)
- [api/index.js](file://web/src/api/index.js#L1-L42)
- [token.js](file://web/src/utils/auth/token.js#L1-L31)