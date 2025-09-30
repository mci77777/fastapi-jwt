任务标题：E2E-ANON-JWT→AI→APP（SSE）闭环与策略校验

目标：在 staging 环境完成以下闭环并生成报告与证据包：

通过 Supabase Anonymous 获取真实 JWT（access_token）。

使用该 JWT 以 SSE 方式调用后端 AI 消息接口（/api/v1/messages 或等价端点），拿到流式响应并被 App 成功消费。

数据库侧验证新建/更新记录符合表结构与外键要求，匿名轨迹落表正确。

验证策略门（匿名访问受限端点 403）、限流（429）与统一错误体契约。

一、准备（环境/依赖/变量）

新建目录 e2e/anon_jwt_sse/，内含：

scripts/anon_signin.js（或 py）：使用 Supabase SDK 执行 signInAnonymously()，打印 access_token 与 claims。

scripts/sse_client.js：发起 SSE 请求，打印事件帧、最终汇总，回写 artifacts/sse.log。

postman/collection.json + postman/env.json：供 Newman 批量回归。

sql/assertions.sql：断言/查询脚本。

配置 .env.local（勿入库）：

SUPABASE_URL, SUPABASE_ANON_KEY

API_BASE（后端域名，如 https://staging.api.example.com）

DB_CONN（只读账号；或走 DWH 视图）

生成 README.md：给出一键脚本：pnpm i && pnpm run e2e:anon。

参考：匿名 Bearer 头与统一错误体（status/code/message/trace_id/hint），策略门样例端点（分享、admin、批量消息）。

二、步骤 A：真实获取 JWT（匿名会话）

在 Supabase 控制台开启 Anonymous Sign-ins（若有 Turnstile/CAPTCHA，也需开启），脚本中调用 supabase.auth.signInAnonymously()。

输出并缓存：

access_token（发给后续 SSE 调用）

claims：校验含 is_anonymous=true、sub/iss/exp/iat。

落盘 artifacts/token.json。

记录一次最小闭环调用：POST /api/v1/messages with Authorization: Bearer <token>，消息体 "hello"，期望 202/200 + SSE 正常返回（与 J1 验收一致），并在后端日志中可看到 user_type=anonymous 标记。

三、步骤 B：SSE 流式调用与 App 消费

客户端（脚本或 App 调试入口）以 SSE 发起对话：

Header：Authorization: Bearer <access_token>、Accept: text/event-stream、X-Trace-Id: <uuid4>。

Body：{ "messages": [{"role":"user","content":"hello"}] }（按现网契约）。

将每条事件帧（含 delta/final）写入 artifacts/sse.log；首/末帧各截一份 artifacts/sse_first.json / sse_final.json。

App 侧（如已有 Debug 开关）演示接收并渲染“最终输出”；若走内部 UI 管线（ThinkingBox/Hybrid 渲染），输出 UI 日志片段到 artifacts/app_ui.log（可留空占位，本次以网络层为主）。

说明：Anonymous Bearer 的请求形态见契约“认证与上下文”；若触发策略门/限流，则返回码与错误体按 K1 统一格式。

四、步骤 C：数据库断言（只读）

编写 sql/assertions.sql 并在 scripts/db_assert.py 执行以下校验，输出 artifacts/db_assert_report.md：

用户侧

users 表：新/旧匿名用户的 isanonymous=1（或相应字段为 true）；lastloginat 刷新。

会话与消息侧

chat_sessions：存在关联 user_id 的会话，message_count ≥ 1，db_updated_at 更新。

chat_raw：新增一条 role='user' 与对应 model/assistant 的事件，final_markdown 非空（如果你们落最终文），外键 session_id 正确。

messages / conversations：conversations.user_type='anonymous'（若你们已启用该列），时间戳字段合理增长。

向量/记忆（若启用）

memory_records / message_embedding：仅在相应 pipeline 打开时断言 embedding_status 状态与外键。

通过条件：所有断言返回行数/计数均满足阈值；外键不报错；匿名会话链路自洽。

五、步骤 D：负例与策略/限流/错误体契约

策略门（Policy Gate）

匿名调用：POST /api/v1/conversations/{id}/share → 403；

匿名访问：GET /api/v1/admin/* → 403；

批量消息：POST /api/v1/messages/batch → 429 或 403（按配额/禁用策略）。
检查响应是否为统一错误体 status/code/message/trace_id/hint，并包含“升级账号以提升配额”的 hint。把三次响应落盘 artifacts/policy_*.json。

限流阈值（匿名降配）

匿名 QPS=5、日配额=1000、SSE并发=2 的约束下，构造并发用例触发 429，验证告警/日志是否有记录。

阶段验收对齐（J2/J3）

若已启用 RLS/审计：验证匿名不得越权、匿名写公开资源被拒；

若已接限流与观测：检查仪表盘是否出现 user_type 维度曲线与告警。

六、报告与产物

生成 artifacts/：

token.json、sse.log、sse_first.json、sse_final.json、policy_*.json、db_assert_report.md、newman-report.html。

REPORT.md：

概览（成功链路/失败链路一览表 + 关键截图）

追踪（每次调用的 X-Trace-Id 对应响应/日志/SQL 结果）

建议（若有 401 误报/限流阈值不合理等）

七、验收标准（Definition of Done）

闭环成功：匿名 JWT → /api/v1/messages → SSE 完整返回，App 或脚本侧能消费最终内容；后端日志打点 user_type=anonymous。

库表一致：users/chat_sessions/chat_raw/... 记录与外键符合新结构，conversations.user_type='anonymous'（如启用）。

策略/限流/错误体：403/429 命中，错误体结构符合 K1 统一格式（含 trace_id/hint）。

八、提交内容

PR：e2e/anon_jwt_sse/** 全部脚本与说明，不包含 .env.local。

附加：REPORT.md + artifacts/（隐去敏感 Token）。

CI（可选）：新增 e2e-anon 任务，Nightly 在 staging 跑通“最小闭环”。




1) 立即可跑的“补充用例”清单（命中真实隐患）

认证/JWT

过期边界：exp 剩余 ≤30s 的 token 调用是否被接受？（时钟偏差 ±60s）

被撤销/登出：同一匿名会话在服务端“软撤销”后是否 401？

JWKS 轮换：kid 变更、缓存未刷新场景是否能自恢复？

Header 攻击面：alg=none、伪造 kid 指向 404 JWKS、错误 aud/iss。

SSE 稳定性

心跳/keep-alive：>60s 无数据时是否仍维持连接？服务端是否按约输出 ping 帧？

断线重连：中途断网 3s 后自动重连并从最近 offset 继续（若协议支持）。

背压：客户端消费速率下降是否导致内存暴涨或队列阻塞？

顺序与完整性：多帧重排/丢帧检测（按 X-Seq 或事件时间戳）。

策略&限流

组合策略：授权正确但配额用尽 → 429 且错误体 hint 建议升级；
授权缺失 → 401；权限不足 → 403。三者响应体需可区分、可观测。

并发冲击：匿名 SSE并发=2 时第 3 条连接必然 429，且释放资源及时。

数据一致性

跨日留存：lastloginat、message_count、db_updated_at 跨日增长合理。

清道夫/归档：长连接/失败对话是否也被记录并可追踪 trace_id？

2) 可直接粘贴的 CI 接入（GitHub Actions）
name: e2e-anon
on:
  workflow_dispatch:
  schedule: [ { cron: "15 3 * * *" } ] # 每日 03:15 UTC 夜跑
concurrency:
  group: e2e-anon-${{ github.ref }}
  cancel-in-progress: false

jobs:
  run:
    runs-on: ubuntu-latest
    env:
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
      API_BASE: ${{ secrets.API_BASE }}
      DB_CONN: ${{ secrets.DB_CONN_READONLY }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: corepack enable && corepack prepare pnpm@9.7.0 --activate
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: |
          pip install -r e2e/anon_jwt_sse/requirements.txt
          pnpm -C e2e/anon_jwt_sse install
      - name: Verify env
        run: python e2e/anon_jwt_sse/scripts/verify_setup.py
      - name: Run E2E (staging)
        run: pnpm -C e2e/anon_jwt_sse run e2e:anon
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: e2e-anon-artifacts
          path: |
            e2e/anon_jwt_sse/artifacts/**
            e2e/anon_jwt_sse/REPORT.md


作用：夜跑&手动触发、串行并发保护、自动收集 artifacts/* 与 REPORT.md，便于回溯。

3) “JWT 变体/攻击面”快速测试脚本片段
# e2e/anon_jwt_sse/scripts/jwt_mutation_tests.py
import json, base64, time, httpx, os

API = os.environ["API_BASE"]
TOK = json.load(open("e2e/anon_jwt_sse/artifacts/token.json"))["access_token"]

def b64url(d): return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=")

def call(token):
    r = httpx.post(f"{API}/api/v1/messages",
                   headers={"Authorization": f"Bearer {token}"},
                   json={"messages":[{"role":"user","content":"ping"}]}, timeout=20)
    return r.status_code, r.text

# 1) 过期 token
h, p, s = TOK.split(".")
payload = json.loads(base64.urlsafe_b64decode(p + "=="))
payload["exp"] = int(time.time()) - 10
expired = ".".join([h, b64url(payload).decode(), s])
print("expired =>", call(expired)[0])

# 2) 错误 aud
payload2 = payload | {"exp": int(time.time()) + 300, "aud": "wrong-aud"}
wrong_aud = ".".join([h, b64url(payload2).decode(), s])
print("wrong_aud =>", call(wrong_aud)[0])

# 3) alg=none（应被拒绝）
hdr = json.loads(base64.urlsafe_b64decode(h + "==")) | {"alg":"none"}
none_alg = ".".join([b64url(hdr).decode(), b64url(payload2).decode(), ""])
print("alg none =>", call(none_alg)[0])


预期：三者分别 401/403（取决于网关策略），并返回统一错误体 + trace_id/hint。

4) SSE“断连/重连/背压”微型压测（可直接跑）
# e2e/anon_jwt_sse/scripts/sse_chaos.py
import asyncio, aiohttp, json, os, uuid, pathlib
API = os.environ["API_BASE"]
TOK = json.load(open("e2e/anon_jwt_sse/artifacts/token.json"))["access_token"]
ART = pathlib.Path("e2e/anon_jwt_sse/artifacts"); ART.mkdir(parents=True, exist_ok=True)

async def one_stream(i, drop_at=2.0):
    trace = str(uuid.uuid4())
    url = f"{API}/api/v1/messages"
    async with aiohttp.ClientSession() as sess:
        async with sess.post(url,
            headers={"Authorization": f"Bearer {TOK}", "Accept":"text/event-stream","X-Trace-Id":trace},
            json={"messages":[{"role":"user","content":f"hello #{i}"}]}) as r:
            assert r.status == 200
            async for raw in r.content:
                line = raw.decode("utf-8", "ignore").strip()
                if line.startswith("data:"):
                    # 模拟慢消费
                    await asyncio.sleep(0.2)
                if r.content.total_bytes and r.content.total_bytes/1024 > 128:
                    break  # 防止内存累积
    return trace

async def main():
    tasks = [one_stream(i) for i in range(3)]  # 第3条应命中并发上限（期望429）
    print(await asyncio.gather(*tasks, return_exceptions=True))

asyncio.run(main())


预期：前两条成功，第三条 429；服务端无悬挂 goroutine/连接泄漏。

5) SQL 断言可扩展点（追加到 sql/assertions.sql）
-- 近24h 匿名会话均带 user_type='anonymous'
select count(*) as bad from conversations
where created_at > now() - interval '24 hours'
  and (user_type is null or user_type <> 'anonymous');

-- SSE 会话必须产生至少一条 assistant 最终消息
select s.id
from chat_sessions s
left join chat_raw r on r.session_id = s.id and r.role='assistant' and r.is_final=true
where s.created_at > now() - interval '24 hours'
group by s.id
having count(r.id) = 0;

-- JWT 近24h 过期错误体一致性（以错误码/trace_id 检查）
select status, code, count(*) from api_errors
where created_at > now() - interval '24 hours'
  and code in ('auth.token_expired','auth.invalid_audience','auth.invalid_issuer')
group by status, code;

6) 可观测性与运行手册（建议本迭代完成）

指标：e2e_anon_success（gauge）、e2e_anon_latency_ms（histogram）、sse_conns_inflight（gauge）、auth_jwks_refresh_err_total（counter）。

日志：强制打点 trace_id user_id user_type route status duration_ms err_code.

告警：

夜跑失败连续 ≥2 次；

sse_conns_inflight 长时间 > 阈值；

auth.token_* 错误同比突增。

Runbook：docs/runbooks/e2e-anon.md（常见故障、抓包命令、回滚/解限步骤）。

7) 升级路径（下一阶段规划预埋）

匿名→注册合并策略：会话和记忆归并规则（基于 device_id/anon_user_id 绑定一次性迁移）。

配额梯度：匿名限流→注册基础版→高级版（速率、上下文窗口、附件大小）。

RLS/隐私：匿名资源严格私有；分享/导出仅对注册开放。
# E2E-ANON 补丁包 v1

> 目的：在已完成的 E2E 基础上，新增 CI 夜跑、JWT 变体安全测试、SSE 稳定性小压测、SQL 断言扩展，以及 Postman 环境自动注入 token 的小工具。

---

## 1) 新增文件：`.github/workflows/e2e-anon.yml`

```yaml
name: e2e-anon
on:
  workflow_dispatch:
  schedule: [ { cron: "15 3 * * *" } ] # 每日 03:15 UTC 夜跑
concurrency:
  group: e2e-anon-${{ github.ref }}
  cancel-in-progress: false
jobs:
  run:
    runs-on: ubuntu-latest
    env:
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
      API_BASE: ${{ secrets.API_BASE }}
      DB_CONN: ${{ secrets.DB_CONN_READONLY }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: corepack enable && corepack prepare pnpm@9.7.0 --activate
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: |
          pip install -r e2e/anon_jwt_sse/requirements.txt
          pnpm -C e2e/anon_jwt_sse install
      - name: Verify env
        run: python e2e/anon_jwt_sse/scripts/verify_setup.py
      - name: Run E2E (staging)
        run: pnpm -C e2e/anon_jwt_sse run e2e:anon
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: e2e-anon-artifacts
          path: |
            e2e/anon_jwt_sse/artifacts/**
            e2e/anon_jwt_sse/REPORT.md
```

---

## 2) 新增文件：`e2e/anon_jwt_sse/scripts/jwt_mutation_tests.py`

```python
"""
JWT 变体/攻击面快速校验
- 过期 token
- 错误 aud
- alg=none
运行：python e2e/anon_jwt_sse/scripts/jwt_mutation_tests.py
输出：状态码与响应体（应为 401/403 + 统一错误体）
"""
import json, base64, time, httpx, os

API = os.environ["API_BASE"]
TOK = json.load(open("e2e/anon_jwt_sse/artifacts/token.json"))["access_token"]

def b64url(d: dict) -> bytes:
    return base64.urlsafe_b64encode(json.dumps(d, separators=(',',':')).encode()).rstrip(b"=")


def call(token: str):
    r = httpx.post(f"{API}/api/v1/messages",
                   headers={"Authorization": f"Bearer {token}"},
                   json={"messages":[{"role":"user","content":"ping"}]}, timeout=20)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:500]}

# 拆原 token
h, p, s = TOK.split(".")
header = json.loads(base64.urlsafe_b64decode(h + "=="))
payload = json.loads(base64.urlsafe_b64decode(p + "=="))

# 1) 过期 token
payload_expired = dict(payload)
payload_expired["exp"] = int(time.time()) - 10
expired = ".".join([h, b64url(payload_expired).decode(), s])
print("expired =>", *call(expired))

# 2) 错误 aud
payload_bad_aud = dict(payload)
payload_bad_aud["aud"] = "wrong-aud"
bad_aud = ".".join([h, b64url(payload_bad_aud).decode(), s])
print("wrong_aud =>", *call(bad_aud))

# 3) alg=none（应被拒绝）
header_none = dict(header)
header_none["alg"] = "none"
none_alg = ".".join([b64url(header_none).decode(), b64url(payload_bad_aud).decode(), ""])
print("alg none =>", *call(none_alg))
```

---

## 3) 新增文件：`e2e/anon_jwt_sse/scripts/sse_chaos.py`

```python
"""
SSE 稳定性微压测：
- 并发 3 条流（期望命中匿名并发上限：2 成功 + 1 429）
- 模拟慢消费，验证背压与资源释放
运行：python e2e/anon_jwt_sse/scripts/sse_chaos.py
"""
import asyncio, aiohttp, json, os, uuid, pathlib

API = os.environ["API_BASE"]
TOK = json.load(open("e2e/anon_jwt_sse/artifacts/token.json"))["access_token"]
ART = pathlib.Path("e2e/anon_jwt_sse/artifacts"); ART.mkdir(parents=True, exist_ok=True)

async def one_stream(i: int):
    trace = str(uuid.uuid4())
    url = f"{API}/api/v1/messages"
    async with aiohttp.ClientSession() as sess:
        async with sess.post(url,
            headers={"Authorization": f"Bearer {TOK}", "Accept":"text/event-stream", "X-Trace-Id":trace},
            json={"messages":[{"role":"user","content":f"hello #{i}"}]}) as r:
            if i < 2:
                assert r.status == 200, f"expect 200, got {r.status}"
                async for raw in r.content:
                    line = raw.decode("utf-8", "ignore").strip()
                    if line.startswith("data:"):
                        await asyncio.sleep(0.15)  # 模拟慢消费
                    if r.content.total_bytes and r.content.total_bytes/1024 > 128:
                        break  # 防止内存累积
            else:
                # 第三条预期 429
                assert r.status in (429, 403), f"expect 429/403, got {r.status}"
    return trace

async def main():
    tasks = [one_stream(i) for i in range(3)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print(results)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4) 追加 SQL 断言：`e2e/anon_jwt_sse/sql/assertions_extra.sql`

```sql
-- 近24h 匿名会话 user_type 必须为 'anonymous'
select count(*) as bad_convo_user_type
from conversations
where created_at > now() - interval '24 hours'
  and (user_type is null or user_type <> 'anonymous');

-- 每个会话至少有一条 assistant 最终消息
select s.id
from chat_sessions s
left join chat_raw r on r.session_id = s.id and r.role='assistant' and r.is_final=true
where s.created_at > now() - interval '24 hours'
group by s.id
having count(r.id) = 0;

-- JWT 相关错误的统一错误体分布（用于告警基线）
select status, code, count(*)
from api_errors
where created_at > now() - interval '24 hours'
  and code in ('auth.token_expired','auth.invalid_audience','auth.invalid_issuer')
group by status, code;
```

---

## 5) Postman 环境自动注入 token：`e2e/anon_jwt_sse/scripts/patch_postman_env.mjs`

```js
// 用 artifacts/token.json 的 access_token 替换 postman/env.json 中的 ACCESS_TOKEN
// 运行：node e2e/anon_jwt_sse/scripts/patch_postman_env.mjs
import fs from 'node:fs';
const tokenPath = 'e2e/anon_jwt_sse/artifacts/token.json';
const envPath = 'e2e/anon_jwt_sse/postman/env.json';
const token = JSON.parse(fs.readFileSync(tokenPath, 'utf8')).access_token;
const env = JSON.parse(fs.readFileSync(envPath, 'utf8'));

function setVar(env, key, val){
  const v = env.values?.find(x => x.key === key);
  if (v) v.value = val; else (env.values ||= []).push({ key, value: val, enabled: true });
}
setVar(env, 'ACCESS_TOKEN', token);
fs.writeFileSync(envPath, JSON.stringify(env, null, 2));
console.log('Postman env updated with ACCESS_TOKEN');
```

---

## 6) Runbook（运维手册骨架）：`docs/runbooks/e2e-anon.md`

```md
# Runbook: E2E-ANON Nightly

## 观测指标
- e2e_anon_success (gauge)
- e2e_anon_latency_ms (histogram)
- sse_conns_inflight (gauge)
- auth_jwks_refresh_err_total (counter)

## 常见告警
- 夜跑失败连续≥2次
- sse_conns_inflight 长时间 > 阈值
- auth.token_* 错误环比突增

## 故障排查流程
1. 打开 Actions 日志，定位 `X-Trace-Id`
2. 按 trace 在 API 网关/应用/DB 中检索
3. 若为 401/403/429，核对策略配置与最近变更
4. 回滚或临时调阈值，复跑工作流确认恢复

## 附录
- 手动执行脚本
- 生成与收集 artifacts 的路径表
```

---

## 7) `package.json` 追加脚本（可合并）

```json
{
  "scripts": {
    "e2e:anon:jwt": "python ./e2e/anon_jwt_sse/scripts/jwt_mutation_tests.py",
    "e2e:anon:chaos": "python ./e2e/anon_jwt_sse/scripts/sse_chaos.py",
    "postman:patch-token": "node ./e2e/anon_jwt_sse/scripts/patch_postman_env.mjs"
  }
}
```

---

## 8) `requirements.txt` 建议（可覆盖现有版本）

```txt
aiohttp==3.9.5
httpx==0.27.2
python-dotenv==1.0.1
psycopg[binary]==3.2.1
```

> 说明：建议统一到 psycopg3，避免 psycopg2-binary 在部分平台的构建问题。

---

## 9) 系统依赖备忘（若使用源码构建）

```bash
# Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y libpq-dev build-essential python3-dev

# macOS
brew install libpq && echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.zshrc

# Windows（可选）
# 安装 Visual C++ Build Tools；优先使用 psycopg[binary] 以避免编译
```
# E2E-ANON 补丁包 v1

> 目的：在已完成的 E2E 基础上，新增 CI 夜跑、JWT 变体安全测试、SSE 稳定性小压测、SQL 断言扩展，以及 Postman 环境自动注入 token 的小工具。

---

## 1) 新增文件：`.github/workflows/e2e-anon.yml`

```yaml
name: e2e-anon
on:
  workflow_dispatch:
  schedule: [ { cron: "15 3 * * *" } ] # 每日 03:15 UTC 夜跑
concurrency:
  group: e2e-anon-${{ github.ref }}
  cancel-in-progress: false
jobs:
  run:
    runs-on: ubuntu-latest
    env:
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_ANON_KEY: ${{ secrets.SUPABASE_ANON_KEY }}
      API_BASE: ${{ secrets.API_BASE }}
      DB_CONN: ${{ secrets.DB_CONN_READONLY }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: corepack enable && corepack prepare pnpm@9.7.0 --activate
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: |
          pip install -r e2e/anon_jwt_sse/requirements.txt
          pnpm -C e2e/anon_jwt_sse install
      - name: Verify env
        run: python e2e/anon_jwt_sse/scripts/verify_setup.py
      - name: Run E2E (staging)
        run: pnpm -C e2e/anon_jwt_sse run e2e:anon
      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: e2e-anon-artifacts
          path: |
            e2e/anon_jwt_sse/artifacts/**
            e2e/anon_jwt_sse/REPORT.md
```

---

## 2) 新增文件：`e2e/anon_jwt_sse/scripts/jwt_mutation_tests.py`

```python
"""
JWT 变体/攻击面快速校验
- 过期 token
- 错误 aud
- alg=none
运行：python e2e/anon_jwt_sse/scripts/jwt_mutation_tests.py
输出：状态码与响应体（应为 401/403 + 统一错误体）
"""
import json, base64, time, httpx, os

API = os.environ["API_BASE"]
TOK = json.load(open("e2e/anon_jwt_sse/artifacts/token.json"))["access_token"]

def b64url(d: dict) -> bytes:
    return base64.urlsafe_b64encode(json.dumps(d, separators=(',',':')).encode()).rstrip(b"=")


def call(token: str):
    r = httpx.post(f"{API}/api/v1/messages",
                   headers={"Authorization": f"Bearer {token}"},
                   json={"messages":[{"role":"user","content":"ping"}]}, timeout=20)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, {"raw": r.text[:500]}

# 拆原 token
h, p, s = TOK.split(".")
header = json.loads(base64.urlsafe_b64decode(h + "=="))
payload = json.loads(base64.urlsafe_b64decode(p + "=="))

# 1) 过期 token
payload_expired = dict(payload)
payload_expired["exp"] = int(time.time()) - 10
expired = ".".join([h, b64url(payload_expired).decode(), s])
print("expired =>", *call(expired))

# 2) 错误 aud
payload_bad_aud = dict(payload)
payload_bad_aud["aud"] = "wrong-aud"
bad_aud = ".".join([h, b64url(payload_bad_aud).decode(), s])
print("wrong_aud =>", *call(bad_aud))

# 3) alg=none（应被拒绝）
header_none = dict(header)
header_none["alg"] = "none"
none_alg = ".".join([b64url(header_none).decode(), b64url(payload_bad_aud).decode(), ""])
print("alg none =>", *call(none_alg))
```

---

## 3) 新增文件：`e2e/anon_jwt_sse/scripts/sse_chaos.py`

```python
"""
SSE 稳定性微压测：
- 并发 3 条流（期望命中匿名并发上限：2 成功 + 1 429）
- 模拟慢消费，验证背压与资源释放
运行：python e2e/anon_jwt_sse/scripts/sse_chaos.py
"""
import asyncio, aiohttp, json, os, uuid, pathlib

API = os.environ["API_BASE"]
TOK = json.load(open("e2e/anon_jwt_sse/artifacts/token.json"))["access_token"]
ART = pathlib.Path("e2e/anon_jwt_sse/artifacts"); ART.mkdir(parents=True, exist_ok=True)

async def one_stream(i: int):
    trace = str(uuid.uuid4())
    url = f"{API}/api/v1/messages"
    async with aiohttp.ClientSession() as sess:
        async with sess.post(url,
            headers={"Authorization": f"Bearer {TOK}", "Accept":"text/event-stream", "X-Trace-Id":trace},
            json={"messages":[{"role":"user","content":f"hello #{i}"}]}) as r:
            if i < 2:
                assert r.status == 200, f"expect 200, got {r.status}"
                async for raw in r.content:
                    line = raw.decode("utf-8", "ignore").strip()
                    if line.startswith("data:"):
                        await asyncio.sleep(0.15)  # 模拟慢消费
                    if r.content.total_bytes and r.content.total_bytes/1024 > 128:
                        break  # 防止内存累积
            else:
                # 第三条预期 429
                assert r.status in (429, 403), f"expect 429/403, got {r.status}"
    return trace

async def main():
    tasks = [one_stream(i) for i in range(3)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print(results)

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4) 追加 SQL 断言：`e2e/anon_jwt_sse/sql/assertions_extra.sql`

```sql
-- 近24h 匿名会话 user_type 必须为 'anonymous'
select count(*) as bad_convo_user_type
from conversations
where created_at > now() - interval '24 hours'
  and (user_type is null or user_type <> 'anonymous');

-- 每个会话至少有一条 assistant 最终消息
select s.id
from chat_sessions s
left join chat_raw r on r.session_id = s.id and r.role='assistant' and r.is_final=true
where s.created_at > now() - interval '24 hours'
group by s.id
having count(r.id) = 0;

-- JWT 相关错误的统一错误体分布（用于告警基线）
select status, code, count(*)
from api_errors
where created_at > now() - interval '24 hours'
  and code in ('auth.token_expired','auth.invalid_audience','auth.invalid_issuer')
group by status, code;
```

---

## 5) Postman 环境自动注入 token：`e2e/anon_jwt_sse/scripts/patch_postman_env.mjs`

```js
// 用 artifacts/token.json 的 access_token 替换 postman/env.json 中的 ACCESS_TOKEN
// 运行：node e2e/anon_jwt_sse/scripts/patch_postman_env.mjs
import fs from 'node:fs';
const tokenPath = 'e2e/anon_jwt_sse/artifacts/token.json';
const envPath = 'e2e/anon_jwt_sse/postman/env.json';
const token = JSON.parse(fs.readFileSync(tokenPath, 'utf8')).access_token;
const env = JSON.parse(fs.readFileSync(envPath, 'utf8'));

function setVar(env, key, val){
  const v = env.values?.find(x => x.key === key);
  if (v) v.value = val; else (env.values ||= []).push({ key, value: val, enabled: true });
}
setVar(env, 'ACCESS_TOKEN', token);
fs.writeFileSync(envPath, JSON.stringify(env, null, 2));
console.log('Postman env updated with ACCESS_TOKEN');
```

---

## 6) Runbook（运维手册骨架）：`docs/runbooks/e2e-anon.md`

```md
# Runbook: E2E-ANON Nightly

## 观测指标
- e2e_anon_success (gauge)
- e2e_anon_latency_ms (histogram)
- sse_conns_inflight (gauge)
- auth_jwks_refresh_err_total (counter)

## 常见告警
- 夜跑失败连续≥2次
- sse_conns_inflight 长时间 > 阈值
- auth.token_* 错误环比突增

## 故障排查流程
1. 打开 Actions 日志，定位 `X-Trace-Id`
2. 按 trace 在 API 网关/应用/DB 中检索
3. 若为 401/403/429，核对策略配置与最近变更
4. 回滚或临时调阈值，复跑工作流确认恢复

## 附录
- 手动执行脚本
- 生成与收集 artifacts 的路径表
```

---

## 7) `package.json` 追加脚本（可合并）

```json
{
  "scripts": {
    "e2e:anon:jwt": "python ./e2e/anon_jwt_sse/scripts/jwt_mutation_tests.py",
    "e2e:anon:chaos": "python ./e2e/anon_jwt_sse/scripts/sse_chaos.py",
    "postman:patch-token": "node ./e2e/anon_jwt_sse/scripts/patch_postman_env.mjs"
  }
}
```

---

## 8) `requirements.txt` 建议（可覆盖现有版本）

```txt
aiohttp==3.9.5
httpx==0.27.2
python-dotenv==1.0.1
psycopg[binary]==3.2.1
```

> 说明：建议统一到 psycopg3，避免 psycopg2-binary 在部分平台的构建问题。

---

## 9) 系统依赖备忘（若使用源码构建）

```bash
# Debian/Ubuntu
sudo apt-get update && sudo apt-get install -y libpq-dev build-essential python3-dev

# macOS
brew install libpq && echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.zshrc

