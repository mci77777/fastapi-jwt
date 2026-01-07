# 匿名用户（Anonymous）支持 · 分阶段计划（J1~J4）
**版本**: v1.0  
**更新时间**: 2025-09-28 23:43 PDT

> 交付方式：每个阶段产出文档 + 可复用脚本；无须服务不可控大范围改动。

## J1 · 平台开关与最小闭环（配置 + App 接入）
- 在 Supabase 控制台开启 **Anonymous Sign-ins**；若有 Turnstile/CAPTCHA，开启人机校验。
- App 集成 `supabase.auth.signInAnonymously()`，成功后携带 Bearer 调用后端 `/api/v1/messages` “hello” 闭环。
- 后端读取 JWT claim `is_anonymous`，在日志中打点 `user_type=anonymous`。

### 验收
- Postman/Newman：匿名用户“hello”→ 202，SSE 正常返回，审计日志含 `user_type=anonymous`。

## J2 · 数据与策略（RLS + 审计）
- 为 conversations/messages 表追加可选审计字段 `user_type`（或由日志侧承载）。
- 新增 RLS：禁止匿名用户访问他人数据、禁止匿名写公开资源。
- 服务端在 **敏感端点** 前加策略门（Policy Gate）。

### 验收
- 通过 SQL/策略回归：匿名不可越权；永久用户不受影响。

## J3 · 限流与观测（匿名降配）
- 限流阈值分级：匿名 < 永久；新增 401 连续失败冷静期；SSE 并发缩减。
- 观测：仪表盘增加 `user_type` 维度；新增匿名流量/命中率面板与告警。

### 验收
- 压测命中 429；Grafana 展示匿名相关曲线；告警规则验证通过。

## J4 · 升级与回滚（Link Identity + Toggle）
- App 内提供“升级账号”入口（email/phone/OAuth）；升级后保持原 user_id。
- 配置化开关：`ANON_ENABLED=true|false`；回滚只需关闭开关。

### 验收
- 升级后继续访问历史会话；关闭匿名后旧匿名会话拒绝创建新内容。

## 📂 合并文档速览

匿名用户子任务的详细设计与测试要点已合并为速览。

- **ANON-prompt**（原 `ANON-prompt.md`）：🧩 任务分派（最少编译、强依赖收口）
- **匿名用户（Anonymous）支持 · API 契约增补**（原 `ANON_API_CONTRACTS.md`）：**版本**: v1.0
- **匿名用户（Anonymous）支持 · 端到端测试套件**（原 `ANON_E2E_TESTS.md`）：**版本**: v1.0
- **匿名用户（Anonymous）支持 · 限流与并发配置**（原 `ANON_RATE_LIMITING.md`）：**版本**: v1.0
- **匿名用户（Anonymous）支持 · 顶层架构设计**（原 `ANON_SUPPORT_TOPLEVEL_DESIGN.md`）：**版本**: v1.0
