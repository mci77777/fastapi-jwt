# 环境配置指南（Env Configuration）

本页作为 **环境变量与配置文件** 的索引与最小约定（SSOT：以代码读取路径为准）。

## 1) 后端（FastAPI）

- 本地开发：根目录 `.env`（模板：`.env.example`）
- 代码读取入口：`app/settings/config.py`
- 常见关注项：
  - JWT：`JWT_*`
  - 策略门/限流：`POLICY_GATE_ENABLED` / `RATE_LIMIT_ENABLED`
  - SSE：`SSE_*`（心跳/并发等）
  - AI：`AI_*`（仅服务端持有 key；客户端只用 `/api/v1/llm/models` 返回的映射名）

## 2) 前端（Vue）

- 开发/生产环境文件：`web/.env.development`、`web/.env.production`
- 变量前缀：`VITE_*`（Vite 约定）

## 3) Docker / 部署

- 推荐用 `.env` 注入容器环境（避免把密钥写进镜像/仓库）
- 变更后确认：
  - `GET /api/v1/healthz` 返回 200
  - `GET /api/v1/metrics` 可访问（如启用监控）

## 4) 安全与排障

- **不要提交密钥**：`.env` 已在 gitignore；文档/日志示例必须脱敏。
- 出现配置不生效：优先核对服务启动方式是否加载了对应 env（本地/容器/系统服务）。

