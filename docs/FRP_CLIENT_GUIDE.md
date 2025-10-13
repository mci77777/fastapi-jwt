# FRP 客户端使用指南

> 将本地开发环境（前端 3101、后端 9999）通过 FRP 隧道映射到远程服务器 api.gymbro.cloud

## 📋 目录

- [快速开始](#快速开始)
- [工作原理](#工作原理)
- [配置说明](#配置说明)
- [常见问题](#常见问题)
- [故障排查](#故障排查)
- [高级用法](#高级用法)

---

## 🚀 快速开始

### 前置条件

1. **本地服务已启动**：
   ```powershell
   # 一键启动前端和后端
   .\start-dev.ps1
   ```

2. **环境变量已配置**：
   确保 `.env` 文件包含以下配置：
   ```bash
   FRP_BASE_IP=74.113.96.240
   FRP_TOKEN=c86dbea00a800f87935646a238a43e09
   ```

### 一键启动

#### Windows (PowerShell)

```powershell
# 在项目根目录执行
.\scripts\start-frp-client.ps1
```

#### Linux/WSL (Bash + Docker)

```bash
# 在项目根目录执行
bash scripts/start-frp-docker.sh
```

**脚本会自动完成以下操作**：
1. ✅ 检测并下载 FRP 客户端（首次运行）
2. ✅ 从 `.env` 读取服务器配置
3. ✅ 生成 FRP 配置文件（`frp/frpc.toml`）
4. ✅ 检查本地服务状态（3101、9999 端口）
5. ✅ 启动 FRP 客户端（新窗口）

### 验证连接

启动成功后，可通过以下方式访问：

| 服务 | 本地地址 | 远程地址（IP） | 远程地址（域名） |
|------|---------|---------------|-----------------|
| 前端 | http://localhost:3101 | http://74.113.96.240:3101 | http://web.gymbro.cloud |
| 后端 | http://localhost:9999 | http://74.113.96.240:9999 | http://api.gymbro.cloud |

**测试命令**：
```powershell
# 测试后端 API
curl http://74.113.96.240:9999/api/v1/healthz

# 测试域名访问（需 Nginx 配置）
curl http://api.gymbro.cloud/api/v1/healthz
```

---

## 🔧 工作原理

### 架构图

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│  本地开发环境    │         │  FRP 服务端       │         │  外部用户        │
│                 │         │  (74.113.96.240) │         │                 │
│  Frontend:3101  │◄────────┤  Port 7000       │◄────────┤  Browser        │
│  Backend:9999   │  隧道    │  + Nginx         │  HTTP   │                 │
└─────────────────┘         └──────────────────┘         └─────────────────┘
```

### 隧道映射

1. **TCP 隧道**（端口直连）：
   - `localhost:3101` → `74.113.96.240:3101`
   - `localhost:9999` → `74.113.96.240:9999`

2. **HTTP 隧道**（域名访问，需 Nginx 配置）：
   - `localhost:3101` → `web.gymbro.cloud`
   - `localhost:9999` → `api.gymbro.cloud`

### 认证机制

- **Token 认证**：客户端使用 `.env` 中的 `FRP_TOKEN` 连接服务端
- **安全性**：Token 仅在客户端和服务端之间传输，不暴露给外部用户

---

## ⚙️ 配置说明

### 环境变量（`.env`）

```bash
# FRP 服务端 IP 地址
FRP_BASE_IP=74.113.96.240

# FRP 认证 Token（与服务端配置一致）
FRP_TOKEN=c86dbea00a800f87935646a238a43e09
```

### 配置文件（`frp/frpc.toml`）

脚本会自动生成配置文件，也可手动编辑：

```toml
# 服务器配置
serverAddr = "74.113.96.240"
serverPort = 7000

# 认证配置
auth.method = "token"
auth.token = "c86dbea00a800f87935646a238a43e09"

# 前端服务隧道
[[proxies]]
name = "gymbro-frontend"
type = "tcp"
localIP = "127.0.0.1"
localPort = 3101
remotePort = 3101

# 后端服务隧道
[[proxies]]
name = "gymbro-backend"
type = "tcp"
localIP = "127.0.0.1"
localPort = 9999
remotePort = 9999

# HTTP 代理（域名访问）
[[proxies]]
name = "gymbro-api-http"
type = "http"
localIP = "127.0.0.1"
localPort = 9999
customDomains = ["api.gymbro.cloud"]
```

**配置项说明**：

| 参数 | 说明 | 示例值 |
|------|------|--------|
| `serverAddr` | FRP 服务端 IP 地址 | `74.113.96.240` |
| `serverPort` | FRP 服务端端口 | `7000` |
| `auth.token` | 认证 Token | `c86dbea00a800f87935646a238a43e09` |
| `localPort` | 本地服务端口 | `3101`, `9999` |
| `remotePort` | 远程映射端口 | `3101`, `9999` |
| `customDomains` | 自定义域名（HTTP 代理） | `["api.gymbro.cloud"]` |

---

## ❓ 常见问题

### Q1: 脚本提示"本地服务未运行"怎么办？

**原因**：前端或后端服务未启动

**解决方案**：
```powershell
# 先启动本地服务
.\start-dev.ps1

# 等待服务启动后（约 10 秒），再运行 FRP 脚本
.\scripts\start-frp-client.ps1
```

### Q2: 如何停止 FRP 客户端？

**方法 1**：关闭 FRP 客户端窗口

**方法 2**：使用 PowerShell 命令
```powershell
Stop-Process -Name frpc -Force
```

### Q3: 如何查看 FRP 日志？

**方法 1**：查看 FRP 客户端窗口输出

**方法 2**：启用日志文件（编辑 `frp/frpc.toml`）
```toml
log.to = "./frpc.log"
log.level = "info"
log.maxDays = 3
```

### Q4: 域名访问失败（404 错误）

**原因**：远程服务器 Nginx 未配置域名反向代理

**解决方案**：联系服务器管理员配置 Nginx，示例配置：
```nginx
server {
    listen 80;
    server_name api.gymbro.cloud;
    
    location / {
        proxy_pass http://127.0.0.1:9999;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Q5: 如何修改远程映射端口？

**编辑脚本**：修改 `scripts/start-frp-client.ps1` 中的变量
```powershell
$REMOTE_FRONTEND_PORT = 8080  # 修改为其他端口
$REMOTE_BACKEND_PORT = 8081
```

**或手动编辑配置文件**：`frp/frpc.toml`
```toml
[[proxies]]
name = "gymbro-backend"
type = "tcp"
localIP = "127.0.0.1"
localPort = 9999
remotePort = 8081  # 修改为其他端口
```

---

## 🛠️ 故障排查

### 问题 1: FRP 客户端启动失败

**症状**：脚本提示"FRP 客户端启动失败"

**排查步骤**：

1. **检查端口占用**：
   ```powershell
   netstat -ano | findstr :7000
   ```

2. **检查防火墙**：
   确保 Windows 防火墙允许 FRP 客户端访问网络

3. **检查服务端状态**：
   ```powershell
   # 测试服务端连接
   Test-NetConnection -ComputerName 74.113.96.240 -Port 7000
   ```

4. **查看详细日志**：
   手动启动 FRP 客户端查看错误信息
   ```powershell
   cd frp
   .\frpc.exe -c frpc.toml
   ```

### 问题 2: 连接超时

**症状**：FRP 客户端无法连接到服务端

**可能原因**：
- 服务端未启动
- 网络防火墙阻止连接
- Token 配置错误

**解决方案**：
1. 确认服务端运行状态
2. 检查 `.env` 中的 `FRP_TOKEN` 是否正确
3. 尝试使用其他网络（如手机热点）排除网络问题

### 问题 3: 隧道建立成功但无法访问

**症状**：FRP 客户端显示连接成功，但远程访问失败

**排查步骤**：

1. **确认本地服务运行**：
   ```powershell
   curl http://localhost:9999/api/v1/healthz
   ```

2. **检查远程端口**：
   ```powershell
   curl http://74.113.96.240:9999/api/v1/healthz
   ```

3. **检查服务端防火墙**：
   确保远程服务器防火墙开放了映射端口（3101、9999）

---

## 🚀 高级用法

### 1. 启用加密和压缩

编辑 `frp/frpc.toml`，添加传输配置：

```toml
# 全局启用加密和压缩
transport.useEncryption = true
transport.useCompression = true

# 或针对单个代理启用
[[proxies]]
name = "gymbro-backend"
type = "tcp"
localIP = "127.0.0.1"
localPort = 9999
remotePort = 9999
transport.useEncryption = true
transport.useCompression = true
```

**注意**：加密和压缩会增加 CPU 开销，仅在需要时启用。

### 2. 连接池优化

减少连接建立时间：

```toml
# 客户端配置
transport.poolCount = 5

# 服务端需配置（联系管理员）
# transport.maxPoolCount = 5
```

### 3. 自定义日志级别

```toml
log.level = "debug"  # trace, debug, info, warn, error
log.to = "./frpc.log"
log.maxDays = 7
```

### 4. 多环境配置

创建不同的配置文件：

```powershell
# 开发环境
.\frpc.exe -c frpc.dev.toml

# 生产环境
.\frpc.exe -c frpc.prod.toml
```

### 5. 使用环境变量

在配置文件中引用环境变量：

```toml
serverAddr = "{{ .Envs.FRP_SERVER_ADDR }}"
auth.token = "{{ .Envs.FRP_TOKEN }}"
```

启动时设置环境变量：

```powershell
$env:FRP_SERVER_ADDR = "74.113.96.240"
$env:FRP_TOKEN = "c86dbea00a800f87935646a238a43e09"
.\frpc.exe -c frpc.toml
```

---

## 📚 参考资料

- **FRP 官方文档**：https://github.com/fatedier/frp
- **FRP 配置示例**：https://github.com/fatedier/frp/tree/dev/conf
- **项目启动脚本**：`start-dev.ps1`
- **环境配置文件**：`.env`

---

## 🔄 更新日志

| 日期 | 版本 | 变更内容 |
|------|------|---------|
| 2025-01-13 | v1.0.0 | 初始版本，支持前端和后端隧道映射 |

---

## 📞 技术支持

如遇到问题，请按以下顺序排查：

1. 查看本文档的 [常见问题](#常见问题) 和 [故障排查](#故障排查) 章节
2. 检查 FRP 客户端窗口的日志输出
3. 联系项目维护者或提交 Issue

---

**祝使用愉快！🎉**

