# SSE / 对话链路（SSOT）

## 最新
- `2026-01-07/`：Cloud SSE 统一事件 + 4 dialect payload 模式 + E2E 验收

## 对接必读
- `../api-contracts/README.md`
- `../ai预期响应结构.md`

## SSE 必须真流式（端到端 SSOT）

服务端代码层面已使用 `StreamingResponse`，但**只要网关/代理开启缓冲或压缩**，客户端仍可能出现“首段很小 + 长时间空白 + 末尾一次性到达”的假流式。

### 1) 探针端点（推荐先测这个）

- `GET /api/v1/base/sse_probe`
  - 认证：需要 JWT（与 App 一致）
  - 行为：每秒发送 1 条 `event: probe`（共 8 条）+ 末尾 `event: completed`
  - 判定：若客户端收到的 probe 不是“每秒到达”，而是合并到一起，说明存在缓冲/压缩

### 2) 网关/代理必要配置（必须）

对 `/api/v1/messages`（包含 SSE `/events`）必须：
- `proxy_buffering off;`
- `proxy_cache off;`
- `gzip off;`
- `proxy_http_version 1.1;`

参考：`deploy/web.conf` 与 `docs/deployment/CLOUD_DEPLOYMENT_GUIDE.md`。
