# Mail API（真实邮箱流测试）

用于“真实邮箱流”联调与 E2E：生成临时邮箱、拉取邮件内容（验证码/确认链接等）。

## 安全提醒

- 不要把真实 API Key 写进仓库文件；请使用环境变量或本地 `.env` 保存。
- 示例中的域名仅用于演示；以 `GET /api/config` 返回的可用域名为准。

## 环境变量（后端 SSOT）

- `MAIL_API_KEY`：Mail API Key（必需）
- `MAIL_API_BASE_URL`：默认 `https://taxbattle.xyz`（可选）
- `MAIL_DOMAIN`：优先使用的邮箱域名（可选；未设置时会从 `/api/config` 取第一个）
- `MAIL_EXPIRY_MS`：邮箱有效期（毫秒，默认 `3600000`）

## API 示例（curl）

### 1) 获取系统配置（查询可用域名等）

```bash
curl "https://taxbattle.xyz/api/config" \
  -H "X-API-Key: YOUR_API_KEY"
```

### 2) 生成临时邮箱

```bash
curl -X POST "https://taxbattle.xyz/api/emails/generate" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test",
    "expiryTime": 3600000,
    "domain": "moemail.app"
  }'
```

### 3) 获取邮箱列表（分页）

```bash
curl "https://taxbattle.xyz/api/emails?cursor=CURSOR" \
  -H "X-API-Key: YOUR_API_KEY"
```

### 4) 获取邮件列表（分页）

```bash
curl "https://taxbattle.xyz/api/emails/{emailId}?cursor=CURSOR" \
  -H "X-API-Key: YOUR_API_KEY"
```

### 5) 获取单封邮件

```bash
curl "https://taxbattle.xyz/api/emails/{emailId}/{messageId}" \
  -H "X-API-Key: YOUR_API_KEY"
```

## 与本仓库联动

- E2E（匿名 JWT SSE）：`e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py`（`--email-mode auto|mailapi|local`）
- 后端调试接口：`POST /api/v1/llm/tests/create-mail-user`（需要配置 `MAIL_API_KEY`）

