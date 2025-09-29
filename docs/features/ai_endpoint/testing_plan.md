# AI Endpoint 测试计划（Phase 3 初稿）

## 目标
- 验证 `/api/v1/llm/chat` 在正常、异常场景下的行为符合预期。
- 覆盖 PromptBuilder/LLMClient 核心逻辑，确保上下文组装与上游请求参数正确。
- 保障权限与审计日志安全性，不泄露敏感配置。

## 测试分层
1. **单元测试**
   - `PromptBuilder`
     - [x] `prompt_id` 指定与默认激活 Prompt 选择。
     - [x] `tools_json` 字符串解析成功/失败分支。
     - [x] `user_info`/`extra_context` 拼接到系统 Prompt。
   - `LLMClient`
     - [x] 模型解析顺序：override -> request -> 数据库 -> settings。
     - [ ] `verify_ssl`/`timeout` 覆盖逻辑。
     - [ ] httpx 超时、HTTPError、4xx/5xx 响应转换为 HTTPException。

2. **接口测试（pytest + respx）**
   - [x] 成功路径：200 返回、提取 `reply`、`latency_ms`。
   - [ ] 权限验证：普通用户缺少 `/api/v1/llm/chat` 权限时返回 403。
   - [x] JSON 校验：非法 `toolsJson`、空 `messages` 返回 4xx。
   - [ ] 上游异常：模拟 500、超时，接口返回 502/504。
   - [ ] 日志安全：`overrideConfig.apiKey` 在 `request.state.request_args` 中被脱敏。

3. **集成/回归**
   - 同步执行 `/api/v1/api/refresh` 后，通过超级管理员角色验证菜单/API 权限映射。
   - 管理后台手动操作 Prompt 激活 + Chat 接口调通，观察审计日志记录模型、耗时。

## 测试实现建议
- 新增 `tests/api/test_llm_chat.py`：
  - 使用 `pytest.mark.asyncio` 与 `respx.mock` 拦截外部 HTTP。
  - 构造轻量 `AIPrompt`、`AIModel` fixture，使用 sqlite 内存库。
  - 提供 `superuser_token` / `normal_token` fixture 复用已有登录生成逻辑。
- `PromptBuilder`/`LLMClient` 单测位于 `tests/services/` 目录，覆盖边界条件。
- 配置 `pytest.ini` 增加 `asyncio_mode=auto`，简化协程测试。

## 覆盖状态追踪
- [x] 单元测试：PromptBuilder、LLMClient（基础路径）
- [x] 接口测试：chat 正常&异常（权限、上游异常待补）
- [ ] 权限/日志手动验证脚本

> 提示：完成每组测试后在 `progress.md` 中补充记录，并同步回归结果。
