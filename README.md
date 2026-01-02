https://web.gymbro.cloud/
https://web.gymbro.cloud/dashboard

https://api.gymbro.cloud/
https://api.gymbro.cloud/docs


### 快速开始

#### 方法一：一键启动开发环境（推荐）

使用 PowerShell 脚本自动启动前后端服务：

```powershell
.\start-dev.ps1
```

**自动完成**：
- 检查并清理端口 3102（前端）和 9999（后端）
- 清除 Python 缓存
- 启动后端服务（新窗口）
- 启动前端服务（新窗口）

**访问地址**：
- 前端：http://localhost:3102
- 后端 API 文档：http://localhost:9999/docs

**默认账号**：
- 用户名：`admin`
- 密码：`123456`（可在「个人中心 → 修改密码」更新，持久化到 SQLite：Docker 本地为 `db/db.sqlite3`，非 Docker 为 `db.sqlite3`）

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
- 密码：`123456`（可在「个人中心 → 修改密码」更新，持久化到 SQLite：Docker 本地为 `db/db.sqlite3`，非 Docker 为 `db.sqlite3`）

#### 方法三：本地 Docker 打包启动（开发自测）

前置：你已经在 `e2e/anon_jwt_sse/.env.local` 配置了 `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `API_BASE`（SSOT）。

```sh
# 生成 .env.docker.local（不会输出密钥，且已被 gitignore）
python3 scripts/dev/generate_docker_local_env.py

# 一键构建并启动（需要本机 Docker Desktop / WSL 集成）
bash scripts/dev/docker_local_up.sh
```

如需“完整重建”（重置为可登录的干净状态，默认会清空 Docker 本地 SQLite）：

```sh
bash scripts/dev/docker_local_reset.sh
```

验证（真实用户 JWT + /messages + SSE，不做 mock；会产出脱敏 trace）：

```sh
bash scripts/dev/run_local_real_user_e2e.sh
```

访问：
- Web：http://localhost:3101
- API：http://localhost:9999/docs

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

**访问前端**：http://localhost:3102

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

### 运维脚本

项目提供了丰富的运维脚本，已按功能重组（2025-11-03）：

```bash
# 快速验证
python scripts/verification/verify_supabase_config.py  # Supabase 配置验证
python scripts/verification/verify_jwks_cache.py       # JWKS 缓存验证

# 端到端测试
python scripts/monitoring/smoke_test.py                # 冒烟测试

# JWT 测试
python scripts/testing/jwt/test_complete.py            # JWT 完整测试

# API 测试
python scripts/testing/api/test_api.py                 # API 测试
```

**详细说明**：参见 [scripts/README.md](./scripts/README.md)

### 使用指南

#### 访问地址

**开发环境**（使用 `start-dev.ps1` 启动）：
- 前端应用：http://localhost:3102
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
2. **RequestID** - 请求追踪（Header: `X-Request-Id`）
3. **PolicyGate** - 策略网关（限制匿名用户访问管理端点）
4. **RateLimiter** - 限流控制（匿名用户 QPS=5，永久用户 QPS=10）

### 目录说明

```
vue-fastapi-admin/
├── app/                      # 后端应用程序目录
│   ├── api/                  # API 接口目录
│   │   └── v1/               # API v1 版本
│   │       ├── ai_conversation.py    # AI 对话接口
│   │       ├── base.py               # 基础认证接口
│   │       ├── dashboard.py          # Dashboard 接口
│   │       ├── llm_models.py         # LLM 模型管理
│   │       └── messages.py           # 消息与 SSE 接口
│   ├── auth/                 # 认证模块
│   │   ├── dependencies.py   # 认证依赖注入
│   │   ├── jwt_verifier.py   # JWT 验证器
│   │   └── provider.py       # 用户提供者
│   ├── core/                 # 核心功能模块
│   │   ├── application.py    # 应用工厂
│   │   ├── exceptions.py     # 异常处理
│   │   ├── metrics.py        # Prometheus 指标
│   │   ├── policy_gate.py    # 策略网关中间件
│   │   ├── rate_limiter.py   # 限流中间件
│   │   └── sse_guard.py      # SSE 连接保护
│   ├── db/                   # 数据库模块
│   │   └── sqlite_manager.py # SQLite 管理器
│   ├── models/               # 数据模型
│   ├── schemas/              # Pydantic 数据模式
│   ├── services/             # 业务服务层
│   │   ├── ai_config.py      # AI 配置服务
│   │   ├── model_mapping.py  # 模型映射服务
│   │   └── supabase_keepalive.py  # Supabase 保活服务
│   ├── settings/             # 配置管理
│   │   └── config.py         # 应用配置
│   └── utils/                # 工具类
│
├── web/                      # 前端应用目录
│   ├── src/
│   │   ├── api/              # API 接口定义
│   │   ├── components/       # Vue 组件
│   │   ├── router/           # Vue Router 路由
│   │   ├── store/            # Pinia 状态管理
│   │   ├── utils/            # 工具函数
│   │   └── views/            # 页面视图
│   │       ├── ai/           # AI 相关页面
│   │       ├── dashboard/    # Dashboard 页面
│   │       └── login/        # 登录页面
│   ├── build/                # 构建配置
│   └── public/               # 静态资源
│
├── scripts/                  # 运维脚本（已重组）
│   ├── testing/              # 测试脚本
│   │   ├── jwt/              # JWT 测试（5 个）
│   │   ├── api/              # API 测试（2 个）
│   │   ├── supabase/         # Supabase 测试（1 个）
│   │   └── frontend/         # 前端测试（5 个）
│   ├── deployment/           # 部署脚本（6 个 + 5 SQL）
│   │   └── sql/              # SQL 脚本
│   ├── verification/         # 验证脚本（8 个）
│   ├── monitoring/           # 监控脚本（2 个）
│   ├── utils/                # 工具脚本（4 个）
│   └── docs/                 # 脚本文档（3 个）
│
├── tests/                    # 后端测试套件
│   ├── test_jwt_auth.py      # JWT 认证测试
│   ├── test_jwt_hardening.py # JWT 安全强化测试
│   └── test_api_contracts.py # API 契约测试
│
├── docs/                     # 项目文档
│   ├── PROJECT_OVERVIEW.md   # 项目概览
│   ├── JWT_HARDENING_GUIDE.md # JWT 安全指南
│   ├── GW_AUTH_README.md     # 网关认证文档
│   └── SCRIPTS_INDEX.md      # 脚本索引
│
├── .vscode/                  # VSCode 配置
│   └── settings.json         # 编辑器设置
├── pyrightconfig.json        # Pyright 类型检查配置
├── pyproject.toml            # Python 项目配置
├── requirements.txt          # Python 依赖
├── run.py                    # 后端启动脚本
├── start-dev.ps1             # 一键启动开发环境
└── README.md                 # 本文件
```

**目录说明**：
- **app/**: 后端核心代码，采用分层架构（API → Service → Model）
- **web/**: 前端 Vue3 应用，使用 Composition API + Pinia
- **scripts/**: 运维脚本，已按功能重组（2025-11-03 重组，减少 35% 冗余）
- **tests/**: 后端测试套件，使用 pytest
- **docs/**: 项目文档，包含架构、安全、运维指南

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
# test
