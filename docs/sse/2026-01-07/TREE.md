# SSE 相关代码/文档索引（TREE）· 2026-01-07

用于快速定位「消息创建 + SSE 拉流」链路的关键文件（含 E2E baseline 与契约 SSOT）。

---

## 1) 本次输出目录

```
docs/sse/2026-01-07/
  REPORT.md
  API.md
  TREE.md
  MINDMAP.md
```

---

## 2) 后端（FastAPI）关键路径

```
app/
  core/
    application.py          # create_app(): middleware 链 + /api 路由挂载 + mobile router
    middleware.py           # RequestIDMiddleware（SSOT: X-Request-Id）
    policy_gate.py          # 匿名白名单：允许 /api/v1/messages + /events
    rate_limiter.py         # SSE /events 豁免限流计数；429 由 sse_guard 控制
    sse_guard.py            # SSE 并发控制（user/conversation 维度）
  api/
    __init__.py             # api_router: /api/v1 聚合
    mobile.py               # mobile_router: /v1/*（无 /api 前缀）
    v1/
      __init__.py           # v1_router 汇总（messages / llm / base 等）
      messages.py           # POST /messages + GET /messages/{id}/events（SSE）
      llm_tests.py          # JWT 测试用户/匿名 token（Web 测试页使用）
  services/
    ai_service.py           # MessageEventBroker + AIService.run_conversation（发布 SSE 事件）
  settings/
    config.py               # SSE_HEARTBEAT_SECONDS / SSE_MAX_CONCURRENT_* 等
```

---

## 3) 前端（Vue3）关键路径

```
web/src/
  views/
    ai/model-suite/jwt/RealUserSseSsot.vue   # 发送消息 + SSE 拉流 + 解析（fetch reader）
  api/
    aiModelSuite.js                          # createMessage(): 对齐后端 schema 构建请求体
  utils/http/
    requestLogHooks.js                       # fetch/EventSource 打点（EventSource 默认只监听 message）
    requestLog.js                            # 日志状态落地（Dashboard Raw Logs tab）
```

---

## 4) Nginx/网关（301/缓冲相关）

```
deploy/web.conf                # 关键：/api/v1/messages location 覆盖，避免 301 破坏 POST/SSE
```

---

## 5) 测试 / E2E baseline

```
tests/
  test_request_id_ssot_e2e.py     # SSE 解析器参考实现 + request_id 对账
  test_real_user_sse_e2e.py       # 运行 scripts/monitoring/real_user_sse_e2e.py（默认 skip）

scripts/monitoring/
  real_user_sse_e2e.py            # 真实用户：Supabase 登录 → /messages → SSE

e2e/
  anon_jwt_sse/README.md          # 匿名 JWT → SSE → policy gate / rate limit 校验套件
  real_user_sse/README.md         # 真用户 SSE E2E 入口与产物说明
```

---

## 6) 契约（SSOT 文档）

```
docs/api-contracts/
  api_gymbro_cloud_app_min_contract.md
  api_gymbro_cloud_conversation_min_contract.md
```

