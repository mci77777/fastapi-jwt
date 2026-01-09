# Docs 写入时间索引（mtime）

生成时间：2026-01-09

## 规则
- “写入时间”以工作区文件的 **mtime**（最后修改时间）为准。
- **活动区**：`docs/`（不含 `docs/archive/`）。
- **归档区**：`docs/archive/`。
- **归档阈值**：超过 30 天未更新（以 2026-01-09 回推）。

## 最近 7 天（活动区，按时间倒序）
```
2026-01-09 18:16 docs/supabase/migrations/002_user_rls.sql
2026-01-09 18:16 docs/SUMMARY.md
2026-01-09 18:16 docs/runbooks/README.md
2026-01-09 18:16 docs/runbooks/gw-auth/GW_AUTH_INSTALLATION.md
2026-01-09 18:16 docs/runbooks/gw-auth/GW_AUTH_DELIVERY_REPORT.md
2026-01-09 18:16 docs/GW_AUTH_README.md
2026-01-09 18:16 docs/README.md
2026-01-09 18:16 docs/incidents/2024-10-repo-restoration-report.md
2026-01-09 18:16 docs/incidents/2024-10-repo-migration.md
2026-01-09 18:16 docs/incidents/2024-10-key-leak.md
2026-01-09 18:16 docs/auth/migrations/README.md
2026-01-09 17:53 docs/sse/app_ai_sse_raw_结构体与样本.md
2026-01-09 17:42 docs/schemas/SUPABASE_SCHEMA_OWNERSHIP_AND_NAMING.md
2026-01-09 17:42 docs/schemas/supabase_ownership_map.json
2026-01-09 16:21 docs/SCRIPTS_INDEX.md
2026-01-09 11:32 docs/api-contracts/api_gymbro_cloud_app_min_contract.md
2026-01-09 11:31 docs/api-contracts/README.md
2026-01-09 09:29 docs/e2e-ai-conversation/QUICK_START.md
2026-01-09 09:28 docs/ai预期响应结构.md
2026-01-08 19:41 docs/reports/2026-01-08_real-user-jwt-thinkingml-e2e.md
2026-01-08 17:47 docs/reports/2026-01-08_xai-deepseek_real_e2e.md
2026-01-08 11:15 docs/guides/dev/START_DEV_OPTIMIZATION.md
2026-01-08 11:01 docs/mail-api.md
2026-01-07 21:03 docs/PROJECT_OVERVIEW.md
2026-01-07 20:59 docs/ENV_CONFIGURATION_GUIDE.md
```

## 归档结果（本次整理）
- 活动区 `>30 天未更新` 的文档：**0**（已全部归档/或不存在）。
- 认证迁移历史材料统一集中到：`docs/archive/auth/migration-history/`。

## 自助生成命令
```bash
# 活动区：按 mtime 倒序
find docs -type f ! -path 'docs/archive/*' -printf '%TY-%Tm-%Td %TH:%TM %p\n' | sort -r

# 归档区：按 mtime 倒序
find docs/archive -type f -printf '%TY-%Tm-%Td %TH:%TM %p\n' | sort -r

# 查找活动区中过期（>30 天）文档
find docs -type f -mtime +30 ! -path 'docs/archive/*' -printf '%TY-%Tm-%Td %p\n' | sort -r
```
