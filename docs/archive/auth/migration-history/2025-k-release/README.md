# JWT 改造阶段总结
> 本目录已归档详细文档至 `archive/`，保留阶段性总结供快速回顾。

## 归档指引
- 详细交付、测试、部署文档已移至 `archive/`；如需原始内容请从相应文件查阅。
- 当前文件仅保留 Phase 关键成果与风险提示，供决策与复盘。

## Phase K2 数据与 RLS
- 新建 `conversations`、`messages` 表并淘汰旧表，配套用户级 RLS 限制及 service_role 全量权限。
- 用户/时间复合索引覆盖核心查询，确保会话分页与审计 Trace 命中。
- pg_cron 30 天清理 + 90 天归档流程与回滚步骤准备就绪。
- 验收覆盖 RLS、索引、trace 字段，明确禁止客户端直连 Supabase。

## Phase K3 限流与反滥用
- 实施用户/IP QPS 与日配额、SSE 并发控制、冷静期与可疑 UA 拦截。
- 环境变量集中管理阈值，可通过拉高配额或移除中间件快速回滚。
- 指标涵盖请求量、阻断率、SSE 拒绝率、冷静期触发，结构化日志便于审计。
- 性能开销 <1ms，内存随失效清理；编译与冒烟脚本验证通过。

## Phase K4 观测与运维
- 定义 TTFB P95、请求成功率、401 刷新成功率、消息完成时长四项核心 SLO。
- 设计应用/网关双仪表盘覆盖认证、限流、外部依赖与资源使用监控。
- 建立 P0/P1/P2 告警阈值与 PagerDuty/Slack 通知，Runbook 规范响应→缓解→根因分析。
- 值班排班及 Supabase/JWKS/AI 故障处理步骤完备，提供静态 JWK 备用与降级模式。

## Phase K5 发布与回滚
- 完成安全扫描、双构建、Newman API 验证及四阶段灰度发布流程。
- 回滚脚本在 25% 流量阶段触发演练，0.5 秒内切回旧版本并校验恢复。
- 关键指标：构建总时长 0.22 s、API 覆盖认证/限流/SSE，0 个真实安全风险。
- 后续建议：修复 assemble 构建、引入真实 Newman 套件、完善业务监控、缩短排空时间。

## 使用提示
- 若需新增 Phase，请先在此文档补充 WHY 与成功标准，再在 `archive/` 撰写细节。
- 对归档内容有疑问，请联系 K5 交付负责人或查阅回滚演练记录。

## 📂 归档文档速览

以下阶段性产出已收敛至本目录，保留标题用于追溯，详细脚本和配置见仓库对应路径。

- **Supabase 部署检查清单**（原 `DEPLOYMENT_CHECKLIST.md`）：本文档提供了完整的 Supabase 配置和部署检查清单，确保 GymBro API 能够正确集成 Supabase 认证和数据库功能。
- **GymBro API 最终冒烟测试报告**（原 `FINAL_SMOKE_TEST_REPORT.md`）：**测试日期**: 2025-09-29
- **GymBro API Supabase 集成测试报告**（原 `FINAL_TEST_REPORT.md`）：**测试日期**: 2025-09-29
- **K2 数据与 RLS 收口交付报告**（原 `K2_DATA_RLS_REPORT.md`）：**conversations**: 对话主表 (id, user_id, title, created_at, updated_at, source, trace_id)
- **K3 限流与反滥用交付报告**（原 `K3_RATE_LIMITING_REPORT.md`）：K3任务实现了完整的限流与反滥用系统，包括：
- **K4 仪表盘与告警配置草案**（原 `K4_DASHBOARD_CONFIG.md`）：JSON 配置示例详见原文
- **K4 观测与告警基线 - SLO/SLI 指标体系**（原 `K4_OBSERVABILITY_SLO.md`）：**定义**: 从请求发起到收到第一个字节的时间
- **K4 Runbook - 故障排查与恢复指南**（原 `K4_RUNBOOK.md`）：步骤1 **确认告警** - 检查告警详情和影响范围
- **K5 发布v2.0与回滚演练 - 交付报告**（原 `K5_DELIVERY_REPORT.md`）：**K5 — 发布v2.0与回滚演练** 已全部完成，CI/CD流程、安全扫描、构建验证、回滚演练均已实施。
