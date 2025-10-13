# FRP 一键启动配置

> **已废弃**：请使用新的自动化脚本 `scripts/start-frp-client.ps1`

## 服务器信息

- **服务器 IP**: 74.113.96.240
- **认证 Token**: c86dbea00a800f87935646a238a43e09
- **服务端口**: 7000

## 快速启动

```powershell
# 一键启动 FRP 客户端
.\scripts\start-frp-client.ps1
```

## 详细文档

请参阅：[FRP 客户端使用指南](./FRP_CLIENT_GUIDE.md)

## 手动配置（不推荐）

如需手动配置，请参考配置模板：`frpc.toml.template`

### 手动启动步骤

1. 下载 FRP 客户端：https://github.com/fatedier/frp/releases
2. 解压到 `frp/` 目录
3. 复制配置模板：`cp frpc.toml.template frp/frpc.toml`
4. 编辑配置文件，填入服务器信息
5. 启动客户端：`cd frp && .\frpc.exe -c frpc.toml`

## 远程访问地址

| 服务 | 本地地址 | 远程地址（IP） | 远程地址（域名） |
|------|---------|---------------|-----------------|
| 前端 | http://localhost:3101 | http://74.113.96.240:3101 | http://web.gymbro.cloud |
| 后端 | http://localhost:9999 | http://74.113.96.240:9999 | http://api.gymbro.cloud |

## 注意事项

1. **本地服务必须先启动**：运行 `.\start-dev.ps1` 启动前端和后端
2. **Token 保密**：不要将 Token 提交到公开仓库
3. **域名访问**：需要远程服务器 Nginx 配置域名反向代理
4. **防火墙**：确保本地防火墙允许 FRP 客户端访问网络

## 故障排查

如遇问题，请查看：[FRP 客户端使用指南 - 故障排查](./FRP_CLIENT_GUIDE.md#故障排查)