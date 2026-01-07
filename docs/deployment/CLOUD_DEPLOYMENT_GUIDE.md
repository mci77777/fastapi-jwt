# ☁️ GymBro Cloud 部署配置

> **更新时间**: 2025-10-14  
> **部署环境**: 云端生产环境

---

## 🌐 云端地址

### 前端 Web
- **主页**: https://web.gymbro.cloud/
- **控制台**: https://web.gymbro.cloud/dashboard

### 后端 API
- **API 根地址**: https://api.gymbro.cloud/
- **API 文档**: https://api.gymbro.cloud/docs
- **健康检查**: https://api.gymbro.cloud/api/v1/healthz
- **指标监控**: https://api.gymbro.cloud/api/v1/metrics

---

## 📋 环境配置

### 后端配置 (`.env`)

```bash
# ============ 应用配置 ============
APP_NAME=GymBro API
DEBUG=false  # 生产环境禁用

# ============ 云端地址 ============
WEB_URL=https://web.gymbro.cloud
API_URL=https://api.gymbro.cloud

# ============ CORS（生产环境严格限制）============
CORS_ALLOW_ORIGINS=["https://web.gymbro.cloud","https://api.gymbro.cloud"]
CORS_ALLOW_CREDENTIALS=true

# ============ 安全配置 ============
ALLOWED_HOSTS=["web.gymbro.cloud","api.gymbro.cloud"]
FORCE_HTTPS=true  # 强制 HTTPS

# ============ Supabase ============
SUPABASE_URL=https://rykglivrwzcykhhnxwoz.supabase.co
SUPABASE_PROJECT_ID=rykglivrwzcykhhnxwoz
SUPABASE_SERVICE_ROLE_KEY=<从恢复的 .env 获取>

# ============ AI 服务 ============
AI_PROVIDER=https://zzzzapi.com
AI_MODEL=deepseek-r1
AI_API_KEY=<从恢复的 .env 获取>

# ============ JWT 配置 ============
JWT_CLOCK_SKEW_SECONDS=120
JWT_REQUIRE_NBF=false
JWT_ALLOWED_ALGORITHMS=ES256,RS256,HS256

# ============ 限流配置（生产环境）============
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_USER_QPS=10
RATE_LIMIT_PER_USER_DAILY=1000
RATE_LIMIT_ANONYMOUS_QPS=2
RATE_LIMIT_ANONYMOUS_DAILY=500
```

### 前端配置 (`web/.env.production`)

```bash
# ============ 云端地址 ============
VITE_WEB_URL = 'https://web.gymbro.cloud'
VITE_API_URL = 'https://api.gymbro.cloud'

# ============ API 配置 ============
VITE_BASE_API = 'https://api.gymbro.cloud/api/v1'

# ============ 构建优化 ============
VITE_USE_COMPRESS = true
VITE_COMPRESS_TYPE = gzip
```

---

## 🚀 部署流程

### 1. 后端部署

```bash
# 1. 切换到生产分支
git checkout main

# 2. 拉取最新代码
git pull origin main

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填入生产环境配置

# 5. 数据库迁移
aerich upgrade

# 6. 启动服务（使用进程管理器）
# 方式 A: systemd
sudo systemctl restart gymbro-api

# 方式 B: PM2
pm2 restart gymbro-api

# 方式 C: Docker
docker-compose up -d --build
```

### 2. 前端部署

```bash
# 1. 进入前端目录
cd web

# 2. 安装依赖
pnpm install

# 3. 构建生产版本
pnpm build

# 4. 部署到 CDN/服务器
# 方式 A: 复制到 Nginx
cp -r dist/* /var/www/gymbro-web/

# 方式 B: 上传到 OSS
ossutil cp -r dist/ oss://gymbro-web/

# 方式 C: Vercel/Netlify
vercel --prod
```

---

## 🔧 Nginx 配置示例

### 前端配置 (`web.gymbro.cloud`)

```nginx
server {
    listen 443 ssl http2;
    server_name web.gymbro.cloud;

    ssl_certificate /etc/letsencrypt/live/gymbro.cloud/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gymbro.cloud/privkey.pem;

    root /var/www/gymbro-web;
    index index.html;

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    # SPA 路由
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # 安全头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
}

# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name web.gymbro.cloud;
    return 301 https://$server_name$request_uri;
}
```

### 后端配置 (`api.gymbro.cloud`)

```nginx
upstream gymbro_backend {
    server 127.0.0.1:9999;
    keepalive 64;
}

server {
    listen 443 ssl http2;
    server_name api.gymbro.cloud;

    ssl_certificate /etc/letsencrypt/live/gymbro.cloud/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/gymbro.cloud/privkey.pem;

    # 请求大小限制
    client_max_body_size 10M;

    # 代理到 FastAPI
    location / {
        proxy_pass http://gymbro_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # SSE 支持
        proxy_buffering off;
        proxy_cache off;

        # 超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 300s;  # SSE 长连接
    }

    # 健康检查端点不记录日志
    location /api/v1/healthz {
        proxy_pass http://gymbro_backend;
        access_log off;
    }

    # 安全头
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
}

# HTTP 重定向
server {
    listen 80;
    server_name api.gymbro.cloud;
    return 301 https://$server_name$request_uri;
}
```

---

## 🔐 SSL/TLS 证书

### 使用 Let's Encrypt

```bash
# 1. 安装 Certbot
sudo apt-get install certbot python3-certbot-nginx

# 2. 获取证书（Nginx 自动配置）
sudo certbot --nginx -d web.gymbro.cloud -d api.gymbro.cloud

# 3. 自动续期
sudo crontab -e
# 添加: 0 0 * * * certbot renew --quiet
```

---

## 📊 监控与日志

### Prometheus 指标

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'gymbro-api'
    static_configs:
      - targets: ['api.gymbro.cloud:9999']
    metrics_path: '/api/v1/metrics'
    scrape_interval: 15s
```

### 日志配置

```bash
# 后端日志
tail -f /var/log/gymbro/api.log

# Nginx 访问日志
tail -f /var/log/nginx/api.gymbro.cloud.access.log

# Nginx 错误日志
tail -f /var/log/nginx/api.gymbro.cloud.error.log
```

---

## ✅ 部署验证

### 1. 后端健康检查

```bash
# 健康状态
curl https://api.gymbro.cloud/api/v1/healthz

# 预期输出
{
  "status": "healthy",
  "timestamp": "2025-10-14T...",
  "version": "0.1.0"
}

# API 文档
curl https://api.gymbro.cloud/docs
# 应该返回 Swagger UI HTML
```

### 2. 前端访问测试

```bash
# 主页加载
curl -I https://web.gymbro.cloud/
# 应该返回 200 OK

# 控制台
curl -I https://web.gymbro.cloud/dashboard
# 应该返回 200 OK（SPA 路由）
```

### 3. CORS 测试

```bash
# 从前端域名测试 API 访问
curl -H "Origin: https://web.gymbro.cloud" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS https://api.gymbro.cloud/api/v1/messages

# 应该包含 CORS 响应头
Access-Control-Allow-Origin: https://web.gymbro.cloud
Access-Control-Allow-Credentials: true
```

### 4. SSL 证书检查

```bash
# 检查证书有效期
echo | openssl s_client -servername api.gymbro.cloud -connect api.gymbro.cloud:443 2>/dev/null | openssl x509 -noout -dates

# 在线检查
https://www.ssllabs.com/ssltest/analyze.html?d=api.gymbro.cloud
```

---

## 🚨 故障排查

### 问题 1: CORS 错误

**症状**: 前端无法访问 API，浏览器控制台显示 CORS 错误

**解决**:
```bash
# 检查后端 CORS 配置
grep CORS_ALLOW_ORIGINS .env

# 确保包含前端域名
CORS_ALLOW_ORIGINS=["https://web.gymbro.cloud"]

# 重启后端
sudo systemctl restart gymbro-api
```

### 问题 2: 502 Bad Gateway

**症状**: Nginx 返回 502

**解决**:
```bash
# 检查后端服务状态
sudo systemctl status gymbro-api

# 检查端口监听
sudo netstat -tlnp | grep 9999

# 查看后端日志
tail -f /var/log/gymbro/api.log

# 重启服务
sudo systemctl restart gymbro-api
```

### 问题 3: SSL 证书过期

**症状**: 浏览器提示证书无效

**解决**:
```bash
# 手动续期
sudo certbot renew

# 重载 Nginx
sudo nginx -s reload

# 检查自动续期 cron
sudo crontab -l | grep certbot
```

---

## 📚 相关文档

- **本地开发**: [`DEV_START.md`](../../DEV_START.md)
- **环境配置**: [`docs/ENV_CONFIGURATION_GUIDE.md`](../ENV_CONFIGURATION_GUIDE.md)
- **API 文档**: https://api.gymbro.cloud/docs
- **项目架构**: [`docs/PROJECT_OVERVIEW.md`](../PROJECT_OVERVIEW.md)

---

**部署完成后**: 访问 https://web.gymbro.cloud/ 🎉
