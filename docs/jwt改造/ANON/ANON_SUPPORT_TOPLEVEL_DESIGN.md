# 匿名用户（Anonymous）支持 · 顶层架构设计
**版本**: v1.0  
**更新时间**: 2025-09-28 23:43 PDT

## 目标
在保持现有 JWT 改造与 K1~K5 体系不变的前提下，引入 Supabase **匿名登录**（Anonymous Sign-ins），实现：
- App 端一键进入“游客模式”并获得 **短会话**（access_token + refresh_token）。
- 后端以 **生产策略** 验证该 JWT，并依据 `is_anonymous` 进行能力降级与限流。
- 数据层（Supabase）依旧使用 `authenticated` 角色，但通过 **RLS** 精确区分匿名 / 永久用户。
- 观测、限流、回滚均有一键开关与按环境差异化配置（dev/staging/prod）。

## 总览
```
App(Android/Kotlin)
  └─ supabase.auth.signInAnonymously() → {access_token, refresh_token, user_id, is_anonymous=true}
       ↓  Authorization: Bearer <access_token>
FastAPI(API Gateway)
  ├─ RealJwtVerifier (ES256/RS256, ±120s skew, nbf 可选)
  ├─ RateLimitMiddleware (per-user/IP/anonymous 降配)
  ├─ SSE Guard (匿名并发更低)
  └─ Policy Gate (匿名禁用写公开资源、限制敏感端点)
       ↓
Supabase(Postgres + RLS)
  ├─ Role: authenticated
  ├─ JWT Claim: is_anonymous=true
  └─ RLS: 严格限定 user_id 与匿名能力
```

## 能力矩阵（摘要）
- 匿名用户：允许创建会话、创建私有对话与消息、拉取本人会话；**禁止** 公开分享、跨用户读取、批量导出、模型切换为高成本档等。
- 永久用户：与现行策略一致。

## 关键决策
1. **不引入 “anon 角色”**：匿名用户仍使用 `authenticated` 角色，仅通过 `is_anonymous` 在 RLS/后端区分。
2. **防滥用优先**：匿名默认 **更低** 的 QPS、SSE 并发与日配额，并启用 CAPTCHA/Turnstile（如启用）。
3. **渐进升级**：匿名用户可在 App 内“升级账号”（link email/phone/OAuth），升级后 **同一 user_id** 继续使用。

## 对现有系统影响
- **K1 JWT 硬化**：保持不变；仅在日志与错误体中增加 `user_type=anonymous|permanent` 维度。
- **K2 数据/RLS**：新增基于 `auth.jwt()->>'is_anonymous'` 的策略、审计字段 `user_type`（可冗余落库）。
- **K3 限流**：按用户类型分配阈值；匿名默认更低（详见 ANON_RATE_LIMITING.md）。
- **K4 观测**：仪表盘与 Runbook 增加 `user_type` 维度与告警推荐值。
- **K5 发布/回滚**：仅配置层变更即可启/停匿名支持；无代码回滚需求。

## 风险与缓解
- **滥用注册**：上线前开启 **IP 级限流** + **CAPTCHA**；后端对匿名用户设置严格配额。
- **数据膨胀**：定期清理 30 天以上匿名用户与其数据（保留期可调）。
- **体验割裂**：提供“一键升级账号”入口，保持会话与内容连续。
