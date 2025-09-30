# 匿名用户（Anonymous）支持 · 端到端测试套件
**版本**: v1.0  
**更新时间**: 2025-09-28 23:43 PDT

## 场景 A：匿名用户发送 “hello”
1) App：调用 `supabase.auth.signInAnonymously()` 获取 access_token  
2) API：`POST /api/v1/messages` 带 Bearer  
3) SSE：`GET /api/v1/messages/{message_id}/events`  
**预期**：202 + 流式事件完整，日志含 `user_type=anonymous`、限流未触发

## 场景 B：匿名越权读取被拒
1) 使用 A 的匿名用户，尝试读取他人 conversation/message  
**预期**：403（RLS/策略生效），日志记录 `authorization_denied`

## 场景 C：匿名配额/并发命中
1) 以同一匿名用户发起 8 个 SSE 连接或高频请求  
**预期**：部分 429/`SSE_CONCURRENCY_LIMIT`，返回 `Retry-After` 或错误体

## 场景 D：匿名升级为永久用户
1) App：触发“升级账号”（link email/phone/OAuth）  
2) 再次访问历史对话  
**预期**：同一 user_id，权限按永久用户策略；E2E 正常

## Newman 样例变量
- `ANON_ACCESS_TOKEN`：运行前由脚本获取并注入
- `BASE_URL`：后端地址
