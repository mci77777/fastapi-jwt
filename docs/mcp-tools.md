# MCP Tools Catalog

> 项目可用的 MCP 工具目录，按优先级排序

## 工具选择原则

1. **🥇 第一优先级：codebase-retrieval** - 无论遇到什么代码相关问题，优先使用语义代码检索
2. **🥈 第二优先级：supabase-mcp-server** - 云端数据库结构查询和操作
3. **🥉 第三优先级：context7** - 第三方依赖文档查询
4. **其他工具** - 按需使用

## 启用的 MCP 服务器

| 服务器 | 用途 |
|--------|------|
| `feedback` | 代码库语义检索、交互反馈 |
| `supabase-mcp-server` | Supabase 云端数据库管理 |
| `context7` | 第三方库文档查询 |
| `exa` | 网页搜索和代码上下文 |
| `memory` | 知识图谱存储 |
| `sequential-thinking` | 复杂问题推理 |

---

## 🥇 第一优先级：代码库检索

**服务器**: `feedback`

| 工具 | 用途 |
|------|------|
| `feedback:codebase-retrieval` | **首选工具**。基于自然语言查询搜索代码库，返回语义相关的代码片段。自动增量索引，结果始终最新。 |
| `feedback:feedback` | 代码审查交互，支持预定义选项和自由输入。 |

**使用场景**：
- 定位函数/类/模块实现
- 查找相似代码模式
- 理解代码结构和依赖关系
- 同义实现扫描（SSOT 检查）

**示例查询**：
```
"JWT 认证中间件实现"
"Supabase 用户表操作"
"SSE 流式响应处理"
```

---

## 🥈 第二优先级：Supabase 云端数据库

**服务器**: `supabase-mcp-server`

### 查询类工具
| 工具 | 用途 |
|------|------|
| `supabase-mcp-server:list_tables` | 列出 schema 中的所有表 |
| `supabase-mcp-server:list_extensions` | 列出数据库扩展 |
| `supabase-mcp-server:list_migrations` | 列出迁移历史 |
| `supabase-mcp-server:execute_sql` | 执行原始 SQL（只读优先） |
| `supabase-mcp-server:get_logs` | 获取服务日志 |
| `supabase-mcp-server:get_advisors` | 获取安全/性能建议 |
| `supabase-mcp-server:search_docs` | 搜索 Supabase 文档 |

### 项目管理工具
| 工具 | 用途 |
|------|------|
| `supabase-mcp-server:list_projects` | 列出所有项目 |
| `supabase-mcp-server:get_project` | 获取项目详情 |
| `supabase-mcp-server:get_project_url` | 获取 API URL |
| `supabase-mcp-server:get_publishable_keys` | 获取可发布密钥 |
| `supabase-mcp-server:generate_typescript_types` | 生成 TS 类型 |

### 变更类工具（谨慎使用）
| 工具 | 用途 |
|------|------|
| `supabase-mcp-server:apply_migration` | 应用 DDL 迁移 |
| `supabase-mcp-server:create_project` | 创建项目 |
| `supabase-mcp-server:pause_project` | 暂停项目 |
| `supabase-mcp-server:deploy_edge_function` | 部署 Edge Function |

### 分支管理工具
| 工具 | 用途 |
|------|------|
| `supabase-mcp-server:create_branch` | 创建开发分支 |
| `supabase-mcp-server:list_branches` | 列出分支 |
| `supabase-mcp-server:merge_branch` | 合并到生产 |
| `supabase-mcp-server:rebase_branch` | Rebase 分支 |

---

## 🥉 第三优先级：依赖文档

**服务器**: `context7`

| 工具 | 用途 |
|------|------|
| `context7:resolve-library-id` | **必须先调用**。将库名解析为 Context7 ID（如 `/fastapi/fastapi`） |
| `context7:query-docs` | 查询库的最新文档和代码示例 |

**使用流程**：
1. 先调用 `resolve-library-id` 获取库 ID
2. 再调用 `query-docs` 查询具体用法

**示例**：
```
resolve-library-id: "FastAPI" → "/tiangolo/fastapi"
query-docs: libraryId="/tiangolo/fastapi", query="依赖注入"
```

---

## 其他工具

### Exa 网页搜索 (`exa`)
| 工具 | 用途 |
|------|------|
| `exa:web_search_exa` | 实时网页搜索（新闻、规则、价格等时鲜信息） |
| `exa:get_code_context_exa` | 获取 API/SDK 的代码上下文 |

### 知识图谱 (`memory`)
| 工具 | 用途 |
|------|------|
| `memory:create_entities` | 创建知识实体 |
| `memory:create_relations` | 创建实体关系 |
| `memory:search_nodes` | 搜索知识节点 |
| `memory:read_graph` | 读取整个图谱 |

### 推理工具 (`sequential-thinking`)
| 工具 | 用途 |
|------|------|
| `sequential-thinking:sequentialthinking` | 复杂问题的分步推理，支持回溯和分支 |

---

## 工具选择决策树

```
遇到问题
    │
    ├─ 代码相关？
    │   └─ YES → feedback:codebase-retrieval（第一优先级）
    │
    ├─ 数据库结构/Supabase？
    │   └─ YES → supabase-mcp-server:*（第二优先级）
    │
    ├─ 第三方库用法？
    │   └─ YES → context7:resolve-library-id → query-docs
    │
    ├─ 时鲜信息/网页内容？
    │   └─ YES → exa:web_search_exa
    │
    └─ 复杂推理？
        └─ YES → sequential-thinking:sequentialthinking
```

---

## 注意事项

1. **codebase-retrieval 是默认首选** - 任何代码问题先用它
2. **Supabase 变更操作需谨慎** - 优先在本地 SQLite 验证
3. **context7 需要两步调用** - 先 resolve 再 query
4. **不要猜测工具结果** - 工具不可用时记录并使用替代方案
