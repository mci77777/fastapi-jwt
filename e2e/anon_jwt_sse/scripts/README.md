# 匿名 JWT SSE E2E 脚本说明

本目录集中维护匿名用户端到端相关脚本，推荐执行顺序如下：

1. `verify_setup.py`：检查依赖、环境变量、网络连通性以及必需文件。
2. `generate_test_token.py`：生成匿名访问用的测试 Token，默认写入 `../artifacts/token.json`（支持 `--method {auto|edge|native}` 与 `--verify`）。
3. `run_e2e_enhanced.py`：单脚本串联注册 → 登录 → 消息发送 → SSE 拉流，并把完整链路写入 JSON。

若需进一步调试，可根据场景选用下列脚本：

- `anon_signin_enhanced.py`：逐步观察匿名登录与 SSE 行为。
- `sse_client.py` / `sse_chaos.py`：调试或施压 SSE 通道。
- `validate_anon_integration.py`：快速校验匿名 JWT API。
- `jwt_mutation_tests.py`：执行 Token 变体与安全测试。
- `patch_postman_env.mjs`：同步 Postman 环境变量。

## 快速运行

```bash
# 环境体检
python e2e/anon_jwt_sse/scripts/verify_setup.py

# 生成 Token 并执行端到端脚本
python e2e/anon_jwt_sse/scripts/generate_test_token.py
python e2e/anon_jwt_sse/scripts/run_e2e_enhanced.py
```

## 维护准则

- 新增脚本时请同步更新本 README 以及 `docs/SCRIPTS_INDEX.md` 的说明。
- 不再保留旧版脚本（例如 `run_simple_e2e.py`）；如需增强功能，请直接扩展现有脚本或通过参数切换。
- 运行高压或长时间测试（如 `sse_chaos.py`）前，请提前向后端与基础设施值班同步。
