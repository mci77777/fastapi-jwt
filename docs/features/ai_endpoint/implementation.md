# GymBro AI Endpoint 实现说明（2025-10 更新）

## 功能概览
- **双层存储**：在 `db.sqlite3` 中维护 `ai_endpoints`、`ai_prompts`、`ai_prompt_tests` 三张表，支持离线编辑、状态检测；借助 Supabase REST API 做远端备份与协同。
- **Supabase 同步**：后端提供单个/批量推送（push）、拉取（pull）、双向（both）同步 API，并暴露 `/llm/status/supabase` 供前端实时展示连接状态及最近同步时间。
- **状态监控**：调用 `/v1/models` 自动探测端点可用性、响应时间与模型列表，结果持久化在本地 SQLite，并可通过后端观测任务实现 10~600 秒的周期巡检。
- **Prompt 管理**：本地 CRUD + 激活控制 + 历史测试记录，Prompt 测试通过 `/llm/prompts/test` 直接触发选定端点的 Chat Completions 请求。
- **前端 UI**：`/system/ai` 页面可统一管理端点状态、同步策略、自动推断标准路径；`/system/ai/prompt` 支持 Prompt 选择、测试、同步与历史回溯。

## 关键组件
- `app/db/sqlite_manager.py`：负责 SQLite 初始化、列变更探测以及线程安全 CRUD。
- `app/services/monitor_service.py`：封装背景巡检任务，管理启动、停止与状态快照。
- `app/services/ai_config_service.py`：封装端点/Prompt 的本地读写、状态检测、Supabase 同步与 Prompt 测试逻辑。
- `app/api/v1/llm.py`：统一对外提供 RESTful 接口（端点 CRUD、检测、同步、Prompt CRUD、测试、历史记录、Supabase 状态、观测任务控制等），返回结构遵循现有 `create_response` 格式。
- `web/src/views/system/ai/index.vue` & `web/src/views/system/ai/prompt/index.vue`：对应的管理界面与用户交互层。

## API 速查
| 路径 | 方法 | 说明 |
| --- | --- | --- |
| `/api/v1/llm/models` | GET/POST/PUT/DELETE | 端点列表、创建、更新、删除 |
| `/api/v1/llm/models/{endpoint_id}/check` | POST | 触发单个端点状态检测 |
| `/api/v1/llm/models/check-all` | POST | 批量检测所有端点 |
| `/api/v1/llm/models/{endpoint_id}/sync` | POST | 针对单个端点的 push/pull/both 同步 |
| `/api/v1/llm/models/sync` | POST | 批量同步所有端点 |
| `/api/v1/llm/status/supabase` | GET | 返回 Supabase 在线状态、延迟与最近同步时间 |
| `/api/v1/llm/monitor/status` | GET | 查询观测任务状态（是否运行、当前间隔、最近一次检测、最后错误） |
| `/api/v1/llm/monitor/start` | POST | 启动观测任务，Body: `{ "interval_seconds": 10-600 }` |
| `/api/v1/llm/monitor/stop` | POST | 停止观测任务并清理后台定时器 |
| `/api/v1/llm/prompts` | GET/POST/PUT/DELETE | Prompt CRUD |
| `/api/v1/llm/prompts/{prompt_id}/activate` | POST | 激活单个 Prompt |
| `/api/v1/llm/prompts/sync` | POST | Prompt 批量同步 |
| `/api/v1/llm/prompts/{prompt_id}/tests` | GET | 获取 Prompt 最近测试历史 |
| `/api/v1/llm/prompts/test` | POST | 触发 Prompt 测试并记录历史 |

## 本地测试流程
1. **准备虚拟环境**  
   ```powershell
   uv venv
   uv pip install -r requirements.txt
   ```
2. **拉起本地 API 并执行测试**  
   ```powershell
   uv run python -c "import threading,time,uvicorn,pytest,sys;
   config=uvicorn.Config('app:app',host='127.0.0.1',port=9999,log_level='warning');
   server=uvicorn.Server(config); server.install_signal_handlers=lambda: None;
   thread=threading.Thread(target=server.run,daemon=True); thread.start(); time.sleep(3);
   result=pytest.main(); server.should_exit=True; thread.join(); sys.exit(result)"
   ```
   > 说明：项目现有集成测试依赖真实 HTTP 端口。若开启速率限制，可通过测试夹具或环境变量放宽限流阈值后重试。
3. **前端检查**  
   ```powershell
   cd web
   pnpm install
   pnpm lint
   pnpm build
   ```

## 注意事项
- RateLimitMiddleware 默认启用，测试环境可通过临时调整 `RATE_LIMIT_*` 环境变量放宽阈值，避免 429 干扰契约断言。
- Supabase 同步需要正确配置 `SUPABASE_PROJECT_ID`、`SUPABASE_SERVICE_ROLE_KEY`、`SUPABASE_JWT_SECRET` 等环境变量；缺失时接口将返回 `supabase_not_configured`。
- Prompt 测试会真发起 Chat Completions 调用，请确保目标端点的 API Key 有限流策略，必要时在非生产模型上进行验证。
