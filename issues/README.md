# Issue CSV 工作流规范

> 使用 CSV 文件跟踪开发任务，确保端到端可追溯

## 目录结构

```
issues/
├── README.md                                    # 本文档
├── YYYY-MM-DD_HH-MM-SS-<描述>.csv              # Issue 文件
└── ...
```

## 命名规范

**格式**: `YYYY-MM-DD_HH-MM-SS-<描述>.csv`

**示例**:
- `2026-01-16_16-31-05-e2e-run-records-page.csv`
- `2026-01-15_17-58-07-dashboard-admin-accounts-rbac.csv`

## CSV 列定义

| 列名 | 必填 | 说明 | 示例 |
|------|------|------|------|
| `ID` | ✅ | 唯一标识，格式 `<前缀>-<序号>` | `RUN-001`, `DASH-002` |
| `Title` | ✅ | 简短标题（≤50 字符） | `添加运行记录列表页` |
| `Description` | ✅ | 详细描述，包含背景和目标 | `实现 /api/v1/runs 的分页列表...` |
| `Acceptance` | ✅ | 验收标准（可测试的条件） | `GET /runs 返回 200 + 分页数据` |
| `Test_Method` | ✅ | 测试方法 | `pytest tests/test_runs.py` |
| `Tools` | ⬚ | 使用的 MCP 工具 | `codebase-retrieval, supabase` |
| `Dev_Status` | ✅ | 开发状态 | `TODO` / `DOING` / `DONE` |
| `Review1_Status` | ✅ | 代码审查状态 | `TODO` / `DOING` / `DONE` |
| `Regression_Status` | ✅ | 回归测试状态 | `TODO` / `DOING` / `DONE` |
| `Files` | ⬚ | 涉及的文件列表 | `app/api/runs.py, tests/test_runs.py` |
| `Dependencies` | ⬚ | 依赖的其他 Issue ID | `RUN-001` |
| `Notes` | ⬚ | 备注（风险、决策、回滚方案） | `需要先完成数据库迁移` |

## 状态值

| 状态 | 含义 | 颜色建议 |
|------|------|----------|
| `TODO` | 待处理 | 🔴 红色 |
| `DOING` | 进行中 | 🟡 黄色 |
| `DONE` | 已完成 | 🟢 绿色 |

## 工作流程

### 1. 创建 Issue CSV

```bash
# 使用 plan skill 生成
/plan <任务描述>

# 或手动创建
touch issues/$(date +%Y-%m-%d_%H-%M-%S)-<描述>.csv
```

### 2. 填写 Issue

```csv
ID,Title,Description,Acceptance,Test_Method,Tools,Dev_Status,Review1_Status,Regression_Status,Files,Dependencies,Notes
RUN-001,创建运行记录表,设计 runs 表结构并迁移,迁移成功且表存在,make test,supabase,TODO,TODO,TODO,app/models/run.py,,"需要 RLS 策略"
RUN-002,实现运行记录 API,GET/POST /api/v1/runs,API 返回正确数据,pytest tests/test_runs.py,codebase-retrieval,TODO,TODO,TODO,app/api/runs.py,RUN-001,
```

### 3. 执行 E2E Loop

```
plan → issues → implement → test → review → commit → regression
  ↓       ↓         ↓         ↓       ↓        ↓          ↓
创建    填写      编码      验证    审查     提交      回归
CSV     详情      实现      测试    代码     变更      测试
```

### 4. 更新状态

逐条处理 Issue，完成后立即更新状态：

```csv
# 开始开发
Dev_Status: TODO → DOING

# 开发完成
Dev_Status: DOING → DONE

# 审查完成
Review1_Status: TODO → DONE

# 回归测试通过
Regression_Status: TODO → DONE
```

## MCP 工具选择

根据 `docs/mcp-tools.md` 的优先级选择工具：

| 任务类型 | 推荐工具 |
|----------|----------|
| 代码定位/搜索 | `feedback:codebase-retrieval` 🥇 |
| 数据库结构查询 | `supabase-mcp-server:list_tables` 🥈 |
| 执行 SQL | `supabase-mcp-server:execute_sql` 🥈 |
| 第三方库用法 | `context7:query-docs` 🥉 |
| 网页搜索 | `exa:web_search_exa` |

## 示例 Issue CSV

```csv
ID,Title,Description,Acceptance,Test_Method,Tools,Dev_Status,Review1_Status,Regression_Status,Files,Dependencies,Notes
AUTH-001,JWT 时钟偏移修复,修复 Supabase JWT 的时钟偏移问题,测试通过且生产环境无 401,pytest tests/test_jwt_*.py,codebase-retrieval,DONE,DONE,DONE,app/auth/jwt.py,,已部署生产
AUTH-002,添加 nbf 可选支持,Supabase token 缺少 nbf 声明,JWT_REQUIRE_NBF=false 时不校验 nbf,pytest tests/test_jwt_hardening.py,codebase-retrieval,DONE,DONE,DONE,app/auth/jwt.py,AUTH-001,
DASH-001,仪表盘数据管道,实现仪表盘 API 数据获取,/api/v1/dashboard 返回正确数据,make test,codebase-retrieval supabase,DOING,TODO,TODO,app/api/dashboard.py,,需要缓存优化
```

## 最佳实践

1. **单一职责**: 每个 Issue 只解决一个问题
2. **可测试验收**: Acceptance 必须是可验证的条件
3. **依赖明确**: 有依赖时必须填写 Dependencies
4. **风险记录**: 在 Notes 中记录风险和回滚方案
5. **及时更新**: 完成后立即更新状态，不要批量更新
6. **工具记录**: 在 Tools 列记录实际使用的 MCP 工具

## 与 AGENTS.md 的关系

本规范是 `AGENTS.md` 中 E2E Loop 和 Issue CSV Guidelines 的详细实现。

参考文档：
- `AGENTS.md` - Agent 行为规范
- `CLAUDE.md` - 项目技术文档
- `docs/mcp-tools.md` - MCP 工具目录
