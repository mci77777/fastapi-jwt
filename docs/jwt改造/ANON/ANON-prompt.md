🧩 任务分派（最少编译、强依赖收口）

下面每个任务都配了可直接复制的 Agent Prompt（按模块拆分）。你可以把 Prompt 交给你的自动化助手执行；输出回到 docs/jwt改造/ 即可。

T1 · 平台开关与配置（Supabase 控制台/平台侧）

目标：开启匿名登录、防滥用与清理策略；不改代码即可形成最小闭环（J1）。

Agent Prompt（Infra）

Task: Enable Anonymous Sign-ins and anti-abuse for Supabase project.
Steps:
1) In Supabase Dashboard → Authentication → Providers, enable "Anonymous Sign-ins".
2) If available, enable CAPTCHA / Turnstile for Anonymous Sign-ins and copy site/secret keys to vault.
3) Set IP-based rate limit for the anonymous sign-in endpoint (start from 30 req/hour).
4) Prepare SQL for periodic cleanup of old anonymous users (30 days):
   delete from auth.users where is_anonymous is true and created_at < now() - interval '30 days';
5) Export a one-page runbook: where to toggle, current thresholds, and rollback steps.
   Deliverables: docs/jwt改造/ANON_PLATFORM_CHECKLIST.md, ANON_CLEANUP.sql, ANON_DASHBOARD_RUNBOOK.md.


（依据官方建议：启用 CAPTCHA、限制匿名注册速率、定期清理匿名用户。）

T2 · 后端策略与开关（FastAPI）

目标：零侵入接入匿名能力；落在配置/策略与网关层（J1/J2/J3）。

Agent Prompt（Backend）

Task: Add anonymous user support to FastAPI gateway via configuration and policy gates.
Constraints: No breaking changes; reuse K1–K5 infrastructure.
Steps:
1) Config: Add ANON_ENABLED=true|false, plus ANON_* thresholds (QPS/daily/SSE).
2) JWT Context: After verification, derive user_type=anonymous|permanent from 'is_anonymous' claim and attach to request context/log.
3) Policy Gate: For anonymous users, deny sensitive endpoints (e.g., admin, public share, bulk export) with unified error body and hint "Upgrade account".
4) Rate Limiting: If user_type=anonymous, apply lower QPS/daily and SSE concurrency via existing K3 middleware; keep Retry-After.
5) Logging & Metrics: Add user_type dimension to structured logs and metrics; ensure SLO queries can group by user_type.
6) Docs: Output a matrix of endpoints that are restricted for anonymous users.
   Deliverables: docs/jwt改造/ANON_BACKEND_POLICY.md, ANON_ENDPOINT_MATRIX.md, config/.env.example diffs.


（限流/并发与指标对齐 K3 与 K4 的实现与面板约定。）

T3 · 数据与 RLS（Supabase SQL）

目标：RLS 基于 auth.jwt()->>'is_anonymous' 严格隔离；可选冗余审计字段 user_type（J2）。

Agent Prompt（DB & RLS）

Task: Apply RLS policies for anonymous users on conversations/messages and related tables.
Steps:
1) Ensure ENABLE RLS on target tables.
2) Owner-only policy: user_id = auth.uid() for ALL.
3) Anonymous restriction: INSERT/UPDATE to public-sharing tables denied when (auth.jwt()->>'is_anonymous')::boolean = true.
4) Optional: add audit column user_type default null; set by server on write; keep supabase as source of truth via jwt claim.
5) Provide rollback SQL.
   Deliverables: docs/jwt改造/ANON_RLS_POLICIES.sql (update), ANON_RLS_ROLLBACK.sql, ANON_RLS_README.md.


（策略样例已提供；与 K2 数据/权限收口一致。

K_PHASE_IMPLEMENTATION_SUMMARY

）

T4 · App 侧匿名登录（Kotlin 客户端）

目标：App 一键匿名登录，携带 Bearer 完成“hello”闭环（J1/J4 升级为永久账号）。

Agent Prompt（Android）

Task: Wire up Supabase Anonymous Sign-ins in Android app.
Steps:
1) Use supabase.auth.signInAnonymously(captchaToken?) to create an anonymous session; persist and auto-refresh.
2) Inject Authorization: Bearer <access_token> into gateway calls; reuse existing interceptors and token sources.
3) Show "Upgrade account" CTA; link email/phone/OAuth keeping the same user_id.
4) Log user_type=anonymous for observability; surface gentle limits (SSE concurrency/QPS) in UI messages.
5) Provide a smoke test: call POST /api/v1/messages "hello" then open SSE stream and assert success.
   Deliverables: docs/jwt改造/ANON_ANDROID_GUIDE.md, screenshots, minimal sample snippet.


（Kotlin API 参考官方 signInAnonymously；建议开启 CAPTCHA。）

T5 · 观测与告警扩展（K4 衔接）

目标：仪表盘与告警加入 user_type 维度；新增匿名相关 SLI 与告警阈值（J3）。

Agent Prompt（Observability）

Task: Extend SLO/SI dashboards and alerts with user_type dimension.
Steps:
1) Update log pipeline or metrics labels to include user_type.
2) Add panels: anonymous request success rate, anonymous P95 latency, anonymous rate-limit hit%, anonymous SSE rejects.
3) Alerts: warning when anonymous 401→refresh <95% for 10m; critical when anonymous success rate <95% for 2m.
4) Runbook: add anonymous-specific triage (CAPTCHA, sign-in rate-limit, RLS mismatch).
   Deliverables: docs/jwt改造/ANON_DASHBOARD_DIFF.md, ANON_ALERTS_RULES.yaml, ANON_RUNBOOK_PATCH.md.


（与既有 SLO/仪表盘/Runbook 结构完全对齐。

K4_OBSERVABILITY_SLO

）

T6 · 端到端与发布（K5 衔接）

目标：扩展 Newman 集合覆盖匿名用例，执行双构建验证与回滚演练（J1/J4）。

Agent Prompt（QA & Release）

Task: Extend E2E and release flow for anonymous users.
Steps:
1) Newman: add test cases — Anonymous hello, SSE stream, RLS deny cross-user, rate-limit/sse-limit hits.
2) CI: add ANON_ENABLED matrix build; dailyDevFast + assemble; attach logs and metrics snapshots.
3) Rollback drill: toggle ANON_ENABLED=false and verify curves drop to zero; record timing and checkpoints.
   Deliverables: docs/jwt改造/ANON_E2E_TESTS.md (filled), K5_DELIVERY_REPORT_APPENDIX_ANON.md.


（复用 K5 的 CI 门禁、构建与回滚演练骨架。

README

）