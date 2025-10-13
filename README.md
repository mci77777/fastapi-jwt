<p align="center">
  <a href="https://github.com/mizhexiaoxiao/vue-fastapi-admin">
    <img alt="Vue FastAPI Admin Logo" width="200" src="https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/logo.svg">
  </a>
</p>

<h1 align="center">vue-fastapi-admin</h1>

[English](./README-en.md) | 简体中文

基于 FastAPI + Vue3 + Naive UI 的现代化前后端分离开发平台，融合了 RBAC 权限管理、动态路由和 JWT 鉴权，助力中小型应用快速搭建，也可用于学习参考。

### 特性
- **最流行技术栈**：基于 Python 3.11 和 FastAPI 高性能异步框架，结合 Vue3 和 Vite 等前沿技术进行开发，同时使用高效的 npm 包管理器 pnpm。
- **代码规范**：项目内置丰富的规范插件，确保代码质量和一致性，有效提高团队协作效率。
- **动态路由**：后端动态路由，结合 RBAC（Role-Based Access Control）权限模型，提供精细的菜单路由控制。
- **JWT鉴权**：使用 JSON Web Token（JWT）进行身份验证和授权，增强应用的安全性。
- **细粒度权限控制**：实现按钮和接口级别的权限控制，确保不同用户或角色在界面操作和接口访问时具有不同的权限限制。

本机直接 python run.py（后端）+ cd web && pnpm dev（前端）进行实时开发，调试链路最短且符合仓库 README。

### 快速开始

#### 方法一：一键启动开发环境（推荐）

使用 PowerShell 脚本自动启动前后端服务：

```powershell
.\start-dev.ps1
```

**自动完成**：
- 检查并清理端口 3101（前端）和 9999（后端）
- 清除 Python 缓存
- 启动后端服务（新窗口）
- 启动前端服务（新窗口）

**访问地址**：
- 前端：http://localhost:3101
- 后端 API 文档：http://localhost:9999/docs

**默认账号**：
- 用户名：`admin`
- 密码：`123456`

#### 方法二：Docker 部署（生产环境）

##### dockerhub拉取镜像

```sh
docker pull mizhexiaoxiao/vue-fastapi-admin:latest
docker run -d --restart=always --name=vue-fastapi-admin -p 80:80 mizhexiaoxiao/vue-fastapi-admin
```

##### dockerfile构建镜像

```sh
git clone https://github.com/mizhexiaoxiao/vue-fastapi-admin.git
cd vue-fastapi-admin
docker build --no-cache . -t vue-fastapi-admin
docker run -d --restart=always --name=vue-fastapi-admin -p 80:80 vue-fastapi-admin
```

**访问地址**：http://localhost

**默认账号**：
- 用户名：`admin`
- 密码：`123456`

### 手动启动（开发调试）

#### 环境要求
- **后端**：Python 3.11+
- **前端**：Node.js v18.8.0+, pnpm

#### 后端启动

**方法一（推荐）：使用 uv 安装依赖**
```sh
# 1. 安装 uv
pip install uv

# 2. 创建并激活虚拟环境
uv venv
.\.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 3. 安装依赖
uv add pyproject.toml

# 4. 启动服务
python run.py
```

**方法二：使用 Pip 安装依赖**
```sh
# 1. 创建虚拟环境
python3 -m venv venv

# 2. 激活虚拟环境
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 启动服务
python run.py
```

**访问后端**：
- API 文档：http://localhost:9999/docs
- 健康检查：http://localhost:9999/api/v1/healthz

#### 前端启动

```sh
# 1. 进入前端目录
cd web

# 2. 安装 pnpm（如未安装）
npm i -g pnpm

# 3. 安装依赖
pnpm i

# 4. 启动开发服务器
pnpm dev
```

**访问前端**：http://localhost:3101

**代理配置**：前端开发服务器会自动将 `/api/v1` 请求代理到 `http://127.0.0.1:9999`

### FRP 远程访问（可选）⚠️

**当前状态：FRP 客户端已降级到 v0.52.3，但存在服务器连接问题。**

如需将本地开发环境通过 FRP 隧道映射到远程服务器（如 api.gymbro.cloud），可使用以下脚本：

```powershell
# 启动 FRP 客户端 (v0.52.3)
.\scripts\start-frp-ini.ps1

# 诊断连接问题
.\scripts\diagnose-frp.ps1

# 验证连接
.\scripts\verify-frp-connection.ps1
```

**功能说明**：
- ✅ FRP v0.52.3 已安装（避免 v0.61.1 TOML 解析 bug）
- ✅ 从 `.env` 读取服务器配置（`FRP_BASE_IP`、`FRP_TOKEN`）
- ✅ 生成 INI 格式配置文件
- ✅ 支持 TCP 端口映射和 HTTP 域名访问
- ❌ **服务器认证失败（session shutdown）- 需联系服务器管理员**

**已知问题**：
- FRP 客户端无法连接到服务器（错误：session shutdown）
- 可能原因：服务器版本不匹配、Token 错误、IP 白名单限制
- **需要联系服务器管理员确认配置**

**远程访问地址**（待服务器配置修复）：
- 前端：http://74.113.96.240:3101 或 http://web.gymbro.cloud
- 后端：http://74.113.96.240:9999 或 http://api.gymbro.cloud

**详细文档**：
- [FRP 客户端使用指南](./docs/FRP_CLIENT_GUIDE.md)
- [FRP 故障排除](./docs/FRP_TROUBLESHOOTING.md)
- [FRP 降级报告](./docs/FRP_DOWNGRADE_REPORT.md)

### 使用指南

#### 访问地址

**开发环境**（使用 `start-dev.ps1` 启动）：
- 前端应用：http://localhost:3101
- 后端 API 文档：http://localhost:9999/docs
- 健康检查：http://localhost:9999/api/v1/healthz
- Prometheus 指标：http://localhost:9999/api/v1/metrics

**生产环境**（Docker 部署）：
- 应用入口：http://localhost（Nginx 反向代理）
- API 路径：http://localhost/api/v1/*

#### 核心 API 端点

基于当前代码实际状态，后端提供以下 API 端点：

**基础认证**（`/api/v1/base/*`）：
- `POST /api/v1/base/access_token` - 用户登录，获取 JWT token
- `GET /api/v1/base/userinfo` - 获取当前用户信息
- `GET /api/v1/base/usermenu` - 获取用户菜单权限
- `GET /api/v1/base/userapi` - 获取用户 API 权限

**Dashboard**（`/api/v1/dashboard/*`）：
- `GET /api/v1/dashboard/stats` - 获取统计数据
- `GET /api/v1/dashboard/quick-access` - 获取快捷入口

**健康探针**（`/api/v1/health/*`）：
- `GET /api/v1/healthz` - 总体健康状态
- `GET /api/v1/livez` - 存活探针
- `GET /api/v1/readyz` - 就绪探针

**LLM 模型管理**（`/api/v1/llm/*`）：
- `GET /api/v1/llm/models` - 获取模型列表
- `POST /api/v1/llm/models` - 创建模型配置
- `PUT /api/v1/llm/models/{id}` - 更新模型配置
- `DELETE /api/v1/llm/models/{id}` - 删除模型配置

**消息与 SSE**（`/api/v1/messages/*`）：
- `POST /api/v1/messages` - 创建消息会话
- `GET /api/v1/messages/{id}/events` - SSE 流式消息推送

**监控指标**：
- `GET /api/v1/metrics` - Prometheus 格式指标导出

#### 认证流程

1. **登录**：POST `/api/v1/base/access_token` 携带用户名密码
2. **获取 Token**：后端返回 JWT token
3. **存储 Token**：前端保存到 localStorage
4. **携带 Token**：后续请求在 Header 中添加 `Authorization: Bearer <token>`
5. **Token 验证**：后端中间件自动验证 JWT 并注入用户信息

#### 中间件链路

所有请求按以下顺序经过中间件处理：

1. **CORS** - 跨域资源共享
2. **TraceID** - 请求追踪（Header: `x-trace-id`）
3. **PolicyGate** - 策略网关（限制匿名用户访问管理端点）
4. **RateLimiter** - 限流控制（匿名用户 QPS=5，永久用户 QPS=10）

### 目录说明

```
├── app                   // 应用程序目录
│   ├── api               // API接口目录
│   │   └── v1            // 版本1的API接口
│   │       ├── apis      // API相关接口
│   │       ├── base      // 基础信息接口
│   │       ├── menus     // 菜单相关接口
│   │       ├── roles     // 角色相关接口
│   │       └── users     // 用户相关接口
│   ├── controllers       // 控制器目录
│   ├── core              // 核心功能模块
│   ├── log               // 日志目录
│   ├── models            // 数据模型目录
│   ├── schemas           // 数据模式/结构定义
│   ├── settings          // 配置设置目录
│   └── utils             // 工具类目录
├── deploy                // 部署相关目录
│   └── sample-picture    // 示例图片目录
└── web                   // 前端网页目录
    ├── build             // 构建脚本和配置目录
    │   ├── config        // 构建配置
    │   ├── plugin        // 构建插件
    │   └── script        // 构建脚本
    ├── public            // 公共资源目录
    │   └── resource      // 公共资源文件
    ├── settings          // 前端项目配置
    └── src               // 源代码目录
        ├── api           // API接口定义
        ├── assets        // 静态资源目录
        │   ├── images    // 图片资源
        │   ├── js        // JavaScript文件
        │   └── svg       // SVG矢量图文件
        ├── components    // 组件目录
        │   ├── common    // 通用组件
        │   ├── icon      // 图标组件
        │   ├── page      // 页面组件
        │   ├── query-bar // 查询栏组件
        │   └── table     // 表格组件
        ├── composables   // 可组合式功能块
        ├── directives    // 指令目录
        ├── layout        // 布局目录
        │   └── components // 布局组件
        ├── router        // 路由目录
        │   ├── guard     // 路由守卫
        │   └── routes    // 路由定义
        ├── store         // 状态管理(pinia)
        │   └── modules   // 状态模块
        ├── styles        // 样式文件目录
        ├── utils         // 工具类目录
        │   ├── auth      // 认证相关工具
        │   ├── common    // 通用工具
        │   ├── http      // 封装axios
        │   └── storage   // 封装localStorage和sessionStorage
        └── views         // 视图/页面目录
            ├── error-page // 错误页面
            ├── login      // 登录页面
            ├── profile    // 个人资料页面
            ├── system     // 系统管理页面
            └── workbench  // 工作台页面
```

### 进群交流
进群的条件是给项目一个star，小小的star是作者维护下去的动力。

你可以在群里提出任何疑问，我会尽快回复答疑。

<img width="300" src="https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/group.jpg">

## 打赏
如果项目有帮助到你，可以请作者喝杯咖啡~

<div style="display: flex">
    <img src="https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/1.jpg" width="300">
    <img src="https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/2.jpg" width="300">
</div>

## 定制开发
如果有基于该项目的定制需求或其他合作，请添加下方微信，备注来意

<img width="300" src="https://github.com/mizhexiaoxiao/vue-fastapi-admin/blob/main/deploy/sample-picture/3.jpg">

### Visitors Count

<img align="left" src = "https://profile-counter.glitch.me/vue-fastapi-admin/count.svg" alt="Loading">
