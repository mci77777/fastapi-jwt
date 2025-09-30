以下是整理好的 Markdown 格式归纳，涵盖了匿名 token 相关需求、Edge Function 代码、环境变量说明、数据库表及 RLS 策略、匿名用户迁移示例 SQL，以及部署使用简要说明。

***

# 匿名 Token 功能需求摘要

- 匿名 token 有效期：60 分钟（可配置）
- 限制：每日每个来源 IP 最多 10 次请求生成匿名 JWT
- 不使用 recaptcha 或设备指纹，仅通过 IP 限流
- 匿名用户以真实用户记录形式存在，标记 `user_metadata` 为匿名
- 维护 `user_anon` 表追踪匿名用户，允许后续迁移到正式用户
- 使用 Supabase Admin API，基于服务角色密钥创建匿名用户，返回 access_token
- token TTL 通过记录和管理实现，不直接由 Supabase JWT 生成接口控制

***

# Edge Function 代码（TypeScript / Deno）

```ts
// 文件名: get-anon-token/index.ts
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const TOKEN_TTL_MIN = Number(Deno.env.get("ANON_TOKEN_TTL_MIN") ?? "60");
const DAILY_LIMIT_PER_IP = Number(Deno.env.get("DAILY_LIMIT_PER_IP") ?? "10");

function getClientIp(req: Request): string {
  const forwarded = req.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0].trim();
  const real = req.headers.get("x-real-ip");
  if (real) return real;
  return "unknown";
}

async function checkAndIncrementIpLimit(ip: string) {
  const today = new Date().toISOString().slice(0, 10);
  const url = `${SUPABASE_URL}/rest/v1/anon_rate_limits`;
  const payload = { ip, day: today, count: 1 };
  const res = await fetch(url, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
      Prefer: "resolution=merge-duplicates,return=representation",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Rate limit table upsert failed: ${res.status} ${text}`);
  }
  const rows = await res.json();
  const row = Array.isArray(rows) ? rows[0] : rows;
  const cnt = Number(row.count ?? 0);
  if (cnt > DAILY_LIMIT_PER_IP) return { allowed: false, count: cnt };
  return { allowed: true, count: cnt };
}

async function createAnonUserAndGetToken() {
  const uidPart = crypto.randomUUID();
  const anonEmail = `anon+${uidPart}@example.com`;
  const pwArray = new Uint8Array(24);
  crypto.getRandomValues(pwArray);
  const password = Array.from(pwArray).map(b => b.toString(16).padStart(2, "0")).join("");

  const createUrl = `${SUPABASE_URL}/auth/v1/admin/users`;
  const createBody = {
    email: anonEmail,
    password,
    email_confirm: true,
    user_metadata: { anon: true, created_by: "edge-get-anon" },
  };

  let r = await fetch(createUrl, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(createBody),
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`Create user failed: ${r.status} ${t}`);
  }
  const user = await r.json();

  const tokenUrl = `${SUPABASE_URL}/auth/v1/token?grant_type=password`;
  const form = new URLSearchParams();
  form.set("email", anonEmail);
  form.set("password", password);

  r = await fetch(tokenUrl, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: form.toString(),
  });

  if (!r.ok) {
    const t = await r.text();
    try {
      await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${user.id}`, {
        method: "DELETE",
        headers: {
          apikey: SERVICE_KEY,
          Authorization: `Bearer ${SERVICE_KEY}`,
        },
      });
    } catch (_) {}
    throw new Error(`Token exchange failed: ${r.status} ${t}`);
  }
  const tokenResp = await r.json();
  return { user, tokenResp };
}

async function insertUserAnonRecord(userId: string, ip: string, expiresAtIso: string) {
  const url = `${SUPABASE_URL}/rest/v1/user_anon`;
  const payload = {
    user_id: userId,
    created_at: new Date().toISOString(),
    ip,
    expires_at: expiresAtIso,
  };
  const res = await fetch(url, {
    method: "POST",
    headers: {
      apikey: SERVICE_KEY,
      Authorization: `Bearer ${SERVICE_KEY}`,
      "Content-Type": "application/json",
      Prefer: "return=minimal",
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const text = await res.text();
    console.error("Insert user_anon failed:", res.status, text);
  }
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== "POST") {
      return new Response(JSON.stringify({ error: "Method not allowed" }), { status: 405, headers: { "Content-Type": "application/json" } });
    }
    const ip = getClientIp(req);
    const rl = await checkAndIncrementIpLimit(ip);
    if (!rl.allowed) {
      return new Response(JSON.stringify({ error: "Rate limit exceeded" }), { status: 429, headers: { "Content-Type": "application/json" } });
    }
    const { user, tokenResp } = await createAnonUserAndGetToken();
    const expiresAt = new Date(Date.now() + TOKEN_TTL_MIN * 60_000).toISOString();

    try {
      await insertUserAnonRecord(user.id, ip, expiresAt);
    } catch (e) {
      console.error("Failed to record user_anon", e);
    }

    const out = {
      access_token: tokenResp.access_token,
      expires_at: expiresAt,
      token_type: tokenResp.token_type,
      user: { id: user.id, email: user.email, user_metadata: user.user_metadata },
    };
    return new Response(JSON.stringify(out), { status: 200, headers: { "Content-Type": "application/json" } });
  } catch (err) {
    console.error("Error creating anon token", err);
    return new Response(JSON.stringify({ error: String(err) }), { status: 500, headers: { "Content-Type": "application/json" } });
  }
});
```

***

# 环境变量说明（Supabase Edge Function）

| 环境变量                 | 说明                                     | 默认值       |
| ------------------------ | ---------------------------------------- | ------------ |
| SUPABASE_URL             | Supabase 项目 URL                        | 必填          |
| SUPABASE_SERVICE_ROLE_KEY| Supabase 服务角色密钥，允许管理员操作    | 必填          |
| ANON_TOKEN_TTL_MIN       | 匿名 token 有效期（分钟）                 | 60           |
| DAILY_LIMIT_PER_IP       | 每个 IP 每天请求匿名 token 最大次数       | 10           |

请确保将 `SUPABASE_SERVICE_ROLE_KEY` 以 Secret 方式配置。

***

# 数据库表与 RLS 策略示例 SQL

```sql
-- 记录匿名用户信息（用于迁移）
CREATE TABLE IF NOT EXISTS public.user_anon (
  user_id uuid PRIMARY KEY,
  created_at timestamptz NOT NULL DEFAULT now(),
  ip text,
  expires_at timestamptz
);

-- IP 限流表，按日期统计请求次数
CREATE TABLE IF NOT EXISTS public.anon_rate_limits (
  ip text NOT NULL,
  day date NOT NULL,
  count int NOT NULL DEFAULT 0,
  PRIMARY KEY (ip, day)
);
```

### RLS 策略示例

```sql
-- 在需要公开访问的表上启用 RLS，例如 public_content
ALTER TABLE public.public_content ENABLE ROW LEVEL SECURITY;

-- 登录用户查看自己的数据
CREATE POLICY "user_owner_select" ON public.public_content
  FOR SELECT TO authenticated
  USING ((auth.uid()) = owner_id);

-- 匿名用户只能查看公共数据，且 token 标记 anon = true
CREATE POLICY "anon_select_public" ON public.public_content
  FOR SELECT TO public
  USING (
    (auth.jwt() ->> 'anon') = 'true' AND is_public = true
  );

-- 使用 user_anon 表验证匿名用户和数据权限，避免依赖 JWT 内容
CREATE POLICY "anon_select_active" ON public.public_content
  FOR SELECT TO public
  USING (
    EXISTS (
      SELECT 1 FROM public.user_anon ua
      WHERE ua.user_id = (SELECT auth.uid())
        AND ua.expires_at > now()
    ) AND is_public = true
  );
```

***

# 匿名用户迁移到正式用户示例 SQL

```sql
BEGIN;

-- 将匿名用户的数据转移到新用户
UPDATE public.notes
SET owner_id = '<NEW_USER_UUID>'
WHERE owner_id = '<ANON_USER_UUID>';

-- 删除匿名用户记录
DELETE FROM public.user_anon WHERE user_id = '<ANON_USER_UUID>';

COMMIT;
```

迁移完成后，建议调用 Supabase Admin API 删除匿名用户的认证记录，避免残留。

***

# Token TTL 与撤销说明

- Supabase token 的过期时间由项目全局设置决定
- 若需严格 60 分钟过期，可通过：
  - 设置 Supabase 项目全局 token TTL 为 60 分钟（影响所有 token）
  - 存储 expires_at 在 user_anon 表，并结合 RLS 策略拒绝过期用户访问
- 主动撤销策略：删除用户或者调用 Admin API 撤销会话

***

# 简洁部署与使用说明

1. 在 Supabase SQL 编辑器运行上面创建表与 RLS 策略的 SQL。
2. 创建 Edge Function，上传 `get-anon-token/index.ts` 代码文件。
3. 配置环境变量 `SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`、`ANON_TOKEN_TTL_MIN=60`、`DAILY_LIMIT_PER_IP=10`。
4. 部署 Edge Function。
5. 客户端发送 POST 请求到 Edge Function 端点，获取带有限期的匿名 access_token。
6. 使用该 token 调用受保护接口，根据 RLS 策略可访问允许匿名的内容。
7. 每日每个 IP 请求限制为 10 次，第 11 次起返回 429。

***

如需生成并部署 Edge Function 代码文件，请回复“部署”；若先需手动创建数据库表，请回复“先不部署，我要先创建 DB 表”。
