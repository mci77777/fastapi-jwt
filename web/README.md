## 快速开始

进入前端目录

```sh
cd web
```

安装依赖(建议使用 pnpm: https://pnpm.io/zh/installation)

```sh
npm i -g pnpm # 已安装可忽略
pnpm i # 或者 npm i
```

启动

```sh
pnpm dev
```

## 本地配置（复用 E2E 的 Supabase SSOT）

如果你已在 `e2e/anon_jwt_sse/.env.local` 配置了 `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `API_BASE`，
建议用脚本同步到 Web 的 Vite env：

```sh
python3 scripts/dev/sync_e2e_env_to_web.py
```

会生成 `web/.env.development.local`（已被 gitignore 忽略），Web 侧会读取：
`VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY`（以及可选的 `VITE_PROXY_TARGET`）。

示例模板见：`web/.env.local.example`
