# FRP 快速参考卡片

> 一页纸速查手册，适合打印或快速查阅

---

## 🚀 快速启动

```powershell
# 1. 启动本地服务
.\start-dev.ps1

# 2. 启动 FRP 客户端
.\scripts\start-frp-client.ps1

# 3. 验证连接
.\scripts\verify-frp-connection.ps1
```

---

## 🌐 访问地址

| 服务 | 本地地址 | 远程地址（IP） | 远程地址（域名） |
|------|---------|---------------|-----------------|
| 前端 | http://localhost:3101 | http://74.113.96.240:3101 | http://web.gymbro.cloud |
| 后端 | http://localhost:9999 | http://74.113.96.240:9999 | http://api.gymbro.cloud |

---

## ⚙️ 配置文件

### .env（必需）
```bash
FRP_BASE_IP=74.113.96.240
FRP_TOKEN=c86dbea00a800f87935646a238a43e09
```

### frp/frpc.toml（自动生成）
```toml
serverAddr = "74.113.96.240"
serverPort = 7000
auth.method = "token"
auth.token = "c86dbea00a800f87935646a238a43e09"

[[proxies]]
name = "gymbro-backend"
type = "tcp"
localIP = "127.0.0.1"
localPort = 9999
remotePort = 9999
```

---

## 🛠️ 常用命令

### 启动/停止

```powershell
# 启动 FRP 客户端
.\scripts\start-frp-client.ps1

# 停止 FRP 客户端
Stop-Process -Name frpc -Force

# 查看 FRP 进程
Get-Process -Name frpc
```

### 测试连接

```powershell
# 测试本地后端
curl http://localhost:9999/api/v1/healthz

# 测试远程后端
curl http://74.113.96.240:9999/api/v1/healthz

# 测试域名访问
curl http://api.gymbro.cloud/api/v1/healthz
```

### 查看日志

```powershell
# 方法 1：查看 FRP 客户端窗口

# 方法 2：手动启动查看详细日志
cd frp
.\frpc.exe -c frpc.toml
```

---

## ❓ 常见问题

### Q: 脚本提示"本地服务未运行"
**A:** 先运行 `.\start-dev.ps1` 启动本地服务

### Q: 域名访问失败（404）
**A:** 需要远程服务器 Nginx 配置域名反向代理

### Q: 连接超时
**A:** 检查以下内容：
1. `.env` 中的 `FRP_TOKEN` 是否正确
2. 远程服务器防火墙是否开放端口 7000
3. 本地防火墙是否允许 FRP 客户端访问网络

### Q: 如何修改远程端口
**A:** 编辑 `scripts/start-frp-client.ps1` 中的变量：
```powershell
$REMOTE_FRONTEND_PORT = 8080  # 修改为其他端口
$REMOTE_BACKEND_PORT = 8081
```

---

## 🔍 故障排查

### 检查清单

- [ ] 本地服务已启动（`.\start-dev.ps1`）
- [ ] FRP 客户端进程运行中（`Get-Process -Name frpc`）
- [ ] `.env` 文件包含 `FRP_BASE_IP` 和 `FRP_TOKEN`
- [ ] 远程服务器防火墙开放端口 3101、9999、7000
- [ ] 本地防火墙允许 FRP 客户端访问网络

### 验证步骤

```powershell
# 1. 运行验证脚本
.\scripts\verify-frp-connection.ps1

# 2. 检查 FRP 进程
Get-Process -Name frpc

# 3. 测试远程端口
Test-NetConnection -ComputerName 74.113.96.240 -Port 7000

# 4. 查看 FRP 日志
# 查看 FRP 客户端窗口输出
```

---

## 📁 文件结构

```
vue-fastapi-admin/
├── scripts/
│   ├── start-frp-client.ps1          # FRP 客户端启动脚本
│   └── verify-frp-connection.ps1     # FRP 连接验证脚本
├── frp/                               # FRP 客户端目录（自动创建）
│   ├── frpc.exe                       # FRP 客户端可执行文件
│   └── frpc.toml                      # FRP 配置文件（自动生成）
├── docs/
│   ├── FRP_CLIENT_GUIDE.md            # 完整使用指南
│   ├── FRP_QUICK_REFERENCE.md         # 本快速参考
│   └── FRP一键启动.md                  # 快速启动文档
├── frpc.toml.template                 # FRP 配置模板
└── .env                               # 环境变量（包含 FRP 配置）
```

---

## 🔗 相关链接

- **完整文档**：[FRP 客户端使用指南](./FRP_CLIENT_GUIDE.md)
- **交付文档**：[FRP 客户端交付文档](./FRP_CLIENT_HANDOVER.md)
- **FRP 官方**：https://github.com/fatedier/frp
- **项目 README**：[../README.md](../README.md)

---

## 📞 技术支持

1. 查看 [FRP 客户端使用指南](./FRP_CLIENT_GUIDE.md)
2. 运行验证脚本：`.\scripts\verify-frp-connection.ps1`
3. 查看 FRP 客户端日志
4. 联系项目维护者

---

**版本**：v1.0.0  
**更新日期**：2025-01-13

