
Auth 服务 JWT 改造顶层设计与任务计划
背景
现有后端采用 vue-fastapi-admin 项目作为服务端框架【532044736930836†L152-L159】。前端 App 经过多轮迭代已经实现了供应商认证 SDK 抽象（支持 Firebase、Supabase）、Token 刷新、SSE 会话等。当前需要对后端进行改造，以满足以下主要业务需求：
统一认证：App 使用 Supabase/Firebase 等 Provider 认证后获取的 JWT（ID Token）作为用户访问后端的唯一凭证。后端需要验证该 JWT 并识别用户身份。
AI 服务对话：App 用户发送对话消息至 FastAPI 后端，后端调用 AI 服务生成回复并推送给用户，同时需要同步对话内容到 Supabase 以便持久化。
轻耦合架构：App 不应包含过多后端逻辑，后端也不应耦合具体 Provider SDK，需要通过抽象层解耦。
本文档提供一个顶层架构设计和详细任务拆解，供开发团队或自动化编程助手分步执行。最终目标是在后端中完成 JWT 验证、AI 对话处理、聊天记录同步等功能，并为系统引入端到端测试。
顶层架构设计
              ┌─────────────┐
              │   Supabase  │
              │ Auth & DB   │
              └───────┬─────┘
                      │JWT/DB
                      ▼
       ┌─────────────────────────┐
       │  FastAPI 服务 (本仓库) │
       │ ┌─────────────────────┐ │
       │ │  Auth 验证层        │ │←—— 验证 JWT：解析并校验 iss/aud/sub/exp 等声明
       │ │  Provider 抽象层    │ │
       │ └─────────┬───────────┘ │
       │           │用户信息     │
       │           ▼             │
       │ ┌─────────────────────┐ │
       │ │  AI 服务调用层      │ │←—— 接入 OpenAI 或内部模型，处理对话
       │ └─────────┬───────────┘ │
       │           │回复消息     │
       │           ▼             │
       │ ┌─────────────────────┐ │
       │ │  数据同步层         │ │←—— 将对话数据写入 Supabase 数据库
       │ └─────────────────────┘ │
       └─────────────────────────┘
                      ▲
                      │HTTP(S) 请求
                      ▼
             ┌─────────────────┐
             │      App        │
             │ Supabase login  │
             └─────────────────┘
该架构主要包含以下模块：
1.Auth 验证层：负责从请求头中解析 Authorization: Bearer <token>，通过指定的 JWK/JWKS 验证 JWT 的签名与声明，拒绝非法或过期 token。
2.Provider 抽象层：封装不同供应商（Supabase/Firebase）提供的用户信息获取与自定义逻辑，避免业务逻辑直接依赖具体 SDK。验证通过后，该层将返回统一的用户对象（如 uid、email 等）。
3.AI 服务调用层：封装对 AI 服务的调用，例如 OpenAI ChatGPT API 或内部模型，负责请求响应、错误处理、超时控制等。
4.数据同步层：将用户对话数据及 AI 回复同步保存至 Supabase 数据库。需要安全地调用 Supabase REST 或 RPC 接口，可使用 Supabase API Key 或服务角色 Token，但这些操作在后端完成，前端不暴露。
5.接口定义：通过 FastAPI 定义清晰的 REST 或 WebSocket 接口，例如：POST /api/v1/messages 用于提交对话并返回 message_id、GET /api/v1/messages/{message_id}/events 用于 SSE 或 WebSocket 推送对话进度等。
任务拆解
Task 1：后端项目初始化与依赖清理
确认仓库 vue-fastapi-admin 已在 allforwodwsasda 内；使用 GitHub 连接器检查 app 目录结构。建议删除不必要的多余模块，确保环境干净。
安装必要依赖：fastapi, uvicorn[standard], pyjwt, httpx, pydantic, supabase-py 等。
在 app 目录中创建新子模块 auth，用于放置 JWT 校验与 Provider 抽象。
Task 2：实现 JWT 验证中间件
创建 auth/jwt_verifier.py：
使用 pyjwt 或 jwcrypto 实现签名验证。通过配置读取 Supabase 提供的 JWKS URL 或直接提供静态 JWK。
验证 iss（issuer）、aud（audience）与 sub（subject）字段是否匹配 Supabase 项目，检查 exp、nbf、iat。
缓存 JWKS，设置合理的缓存 TTL（如 15 分钟）。
将验证失败时返回 401（含错误详情代码），同时写入日志。
创建 FastAPI dependency get_current_user()：
从 header 中获取 Bearer token，调用 jwt_verifier.verify_token() 返回用户信息（uid、claims）。
将用户对象注入请求上下文，供后续路由使用。
Task 3：定义 Provider 抽象与实现
在 auth/provider.py 中定义一个抽象基类 AuthProvider，包含方法：get_user_details(uid: str) -> UserDetails，sync_chat_record(record: dict) -> None。
创建 supabase_provider.py 实现上述接口：
利用 supabase-py 调用 Supabase REST/RPC 获取用户详细信息、保存聊天记录。
配置中提供 Supabase 服务角色密钥，避免前端参与。
若需兼容 Firebase，可创建 firebase_provider.py。但推荐仅保留 Supabase，以减少客户端对 Firebase 文件的依赖。
Task 4：实现 AI 对话接口与调用层
在 api/routes.py（或 views）中定义对话相关端点：
POST /api/v1/messages：接收用户消息内容（text, conversation_id 等），调用 AI 服务生成回复。返回 message_id 并开始后台任务推送 events（可通过 FastAPI BackgroundTasks 或 Celery）。
GET /api/v1/messages/{message_id}/events：采用 Server-Sent Events（SSE）或 WebSocket 推送对话进度。需加入鉴权依赖、心跳、重连逻辑。
创建 services/ai_service.py：封装对 AI 模型的调用逻辑，支持使用环境变量配置模型 provider、API Key 及可选的流式输出。
在 AI 回复生成后，调用 Provider 实现的 sync_chat_record() 将用户问题和 AI 回复写入 Supabase 数据库。
Task 5：前后端对接与网关统一
根据制定的 API 契约（见 API_CONTRACTS.md），确保前端调用使用 POST /api/v1/messages 与 GET /api/v1/messages/{id}/events。
配置 CORS、HTTPS 以及全局异常处理。
引入 X-Trace-Id 机制：FastAPI 层生成或透传前端传入的 Trace Id，写入日志并返回响应头。
Task 6：端到端测试设计
编写 pytest 测试用例，使用 httpx 的 AsyncClient：
模拟登录，获取 JWT，从而测试 /api/v1/messages 端点返回 401/200。
测试 JWKS 缓存失效刷新；模拟错误签名 token，确保返回 401。
使用 SSE 客户端订阅 /api/v1/messages/{message_id}/events，验证事件顺序、心跳重连及 401 刷新逻辑。
使用数据库或 Supabase mock（或 test project）检查聊天记录同步。
在 CI 中运行端到端测试，确保后端与前端契约匹配。
执行计划与提示语 (Prompt) 模板
下述 Prompt 模板为与 AI 编程助手交互时使用，帮助自动完成任务。开发者可根据需要调整参数。
Prompt for Task 2: 实现 JWT 验证中间件
【Prompt 名称】：实现 JWT 验证中间件
【目标】：在 FastAPI 后端添加一个 JWT 验证中间件和依赖，以支持 Supabase 提供的 ID Token 签名校验。
【输入】：
  - 项目目录结构；
  - Supabase 项目的 JWKS URL、项目 ID（作为 issuer 和 audience）；
【步骤】：
 1. 新建 `auth/jwt_verifier.py`，实现 `verify_token(token: str) -> dict` 方法。
 2. 通过 httpx 获取 JWKS 并缓存，解析 JWK，使用 `jwt.PyJWKClient` 校验 token。
 3. 验证 `iss == 'https://[project-id].supabase.co'`，`aud == '[project-id]'`，检查 `exp`、`nbf`、`iat`。
 4. 验证成功返回 payload，失败抛出 HTTPException(status_code=401)。
 5. 在 `dependencies.py` 中实现 `get_current_user` 依赖，解析 Authorization header，返回用户信息。
【输出】：一个包含中间件和依赖的 Python 文件，确保在服务启动时生效。
Prompt for Task 3: 定义 Provider 抽象与 Supabase 实现
【Prompt 名称】：实现 Supabase Provider
【目标】：创建统一的认证/数据提供器抽象以及基于 Supabase 的实现。
【输入】：
  - Supabase 项目 URL 和 Service Key；
【步骤】：
 1. 在 `auth/provider.py` 定义抽象类 `AuthProvider`：方法 `get_user_details(uid)`、`sync_chat_record(record)`。
 2. 在 `auth/supabase_provider.py` 中引入 `supabase-py`，通过 Service Key 实例化 client；实现上述方法：获取用户资料（from auth.users 表或自定义 RPC）并写入 `chat_records` 表。
 3. 在配置文件加载 Supabase 服务密钥，并通过依赖注入提供实例。
【输出】：抽象类和实现文件，测试方法使用模拟数据返回正确结构。
Prompt for Task 4: AI 对话接口与调用层
【Prompt 名称】：实现 AI 对话接口与服务调用
【目标】：在 FastAPI 中实现对话相关端点，调用 AI 服务生成回复并通过 SSE 推送事件。
【输入】：
  - AI 服务的 API Key 和模型名称；
【步骤】：
 1. 在 `services/ai_service.py` 实现 `generate_reply(message: str, conversation_id: str) -> AsyncGenerator[str]`，逐步返回回复内容。
 2. 在 `api/routes.py` 定义 `POST /api/v1/messages` 端点，验证 token，生成 message_id，调用 AI 服务并返回 `{"message_id": id}`；同时启动后台任务向数据同步层写入消息记录。
 3. 在 `GET /api/v1/messages/{message_id}/events` 中使用 FastAPI’s `EventSourceResponse`，将 AI Service 的生成器输出包装为 SSE 事件推送给客户端。
 4. 确保请求带有 `X-Trace-Id`，回写到响应头中。
【输出】：完整的路由实现、AI 调用逻辑以及 SSE 推送逻辑。
Prompt for Task 6: 编写端到端测试
【Prompt 名称】：编写后端端到端测试
【目标】：为改造后的后端编写 pytest 测试用例，覆盖 JWT 验证、对话接口、SSE 流、聊天记录同步。
【输入】：
  - 模拟的 Supabase JWKS、Service Key 以及 AI 服务响应；
【步骤】：
 1. 使用 pytest-asyncio 编写异步测试函数，启动 FastAPI 测试客户端。
 2. 使用有效和无效 JWT 调用 `/api/v1/messages`，断言 200 和 401 返回。
 3. 调用 `/api/v1/messages/{message_id}/events`，消费 SSE 流，验证事件顺序为 queued → working → content_delta … → completed。
 4. Mock Supabase Client，断言 `sync_chat_record` 被调用并收到正确参数。
【输出】：pytest 测试文件，确保所有场景通过。
交付与注意事项
文档与任务计划应随着项目进展更新。提交时请保持 docs/jwt改造/README.md 内容最新。
设计方案要考虑到安全性（如禁用环境变量注入、防止泄露明文 token）和可扩展性（支持不同 Provider）。
请按照各阶段任务拆解顺序执行，确保每一步都有完善的 Prompt 指引和预期结果。
