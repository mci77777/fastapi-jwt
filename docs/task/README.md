# 任务摘要：E2E-ANON-JWT→AI→APP（SSE）

任务目标：构建匿名登录→AI 消息→SSE 回传→App 消费的闭环，并产出完整策略校验与证据包。

## 🎯 验证范围
- Supabase 匿名 JWT 获取与 claims 校验。
- SSE 接口 `/api/v1/messages` 流式响应收集与日志落盘。
- 数据库断言匿名轨迹写入、表结构及外键完整性。
- 策略门、限流（429）与统一错误体契约。

## 🔧 工程交付
- `e2e/anon_jwt_sse/`：脚本、Postman 集合、SQL 断言与 README。
- `.env.local` 未入库的环境变量样例。
- 运行指南：`pnpm i && pnpm run e2e:anon` 完成一键验证。