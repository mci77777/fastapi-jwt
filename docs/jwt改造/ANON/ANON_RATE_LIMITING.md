# 匿名用户（Anonymous）支持 · 限流与并发配置
**版本**: v1.0  
**更新时间**: 2025-09-28 23:43 PDT

## 建议默认值（按环境）
- dev：QPS=10，日配额=5000，SSE并发=5
- staging：QPS=7，日配额=2000，SSE并发=3
- prod：QPS=5，日配额=1000，SSE并发=2

## 环境变量（示例）
```
ANON_ENABLED=true
ANON_RATE_LIMIT_PER_USER_QPS=5
ANON_RATE_LIMIT_PER_USER_DAILY=1000
ANON_SSE_MAX_CONCURRENT_PER_USER=2
ANON_SSE_MAX_CONCURRENT_PER_CONVERSATION=1
ANON_COOLDOWN_SECONDS=600
```
> 其余限流项复用 K3 既有变量（per-IP、全局阈值等）。

## 指标与告警
- 新增或细化：`rate_limit_hit{user_type="anonymous"}`、`sse_reject_total{user_type="anonymous"}`、401→刷新成功率（匿名维度）。
- 观测面板添加维度：`user_type`，并给出分组曲线与阈值建议。
