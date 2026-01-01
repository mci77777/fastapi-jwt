function getSupabaseConfig() {
  const supabaseUrl = String(import.meta.env.VITE_SUPABASE_URL || '').trim()
  const supabaseAnonKey = String(import.meta.env.VITE_SUPABASE_ANON_KEY || '').trim()

  if (!supabaseUrl || !/^https?:\/\//.test(supabaseUrl)) {
    throw new Error('缺少或无效的 VITE_SUPABASE_URL（示例：https://<project>.supabase.co）')
  }
  if (!supabaseAnonKey) {
    throw new Error('缺少 VITE_SUPABASE_ANON_KEY（请在 .env.*.local 中配置）')
  }

  return { supabaseUrl: supabaseUrl.replace(/\/+$/, ''), supabaseAnonKey }
}

function buildSupabaseAuthHeaders(anonKey) {
  return {
    apikey: anonKey,
    Authorization: `Bearer ${anonKey}`,
    'Content-Type': 'application/json',
  }
}

async function parseSupabaseError(res) {
  const text = await res.text().catch(() => '')
  try {
    const json = JSON.parse(text)
    const msg =
      json?.msg ||
      json?.message ||
      json?.error_description ||
      json?.error ||
      json?.code ||
      text ||
      `HTTP ${res.status}`
    return String(msg)
  } catch {
    return text || `HTTP ${res.status}`
  }
}

/**
 * Supabase Auth - Password 登录（真实用户）
 * Docs: POST /auth/v1/token?grant_type=password
 */
export async function supabaseSignInWithPassword({ email, password } = {}) {
  const resolvedEmail = String(email || '').trim()
  const resolvedPassword = String(password || '')
  if (!resolvedEmail || !resolvedPassword) {
    throw new Error('email/password 不能为空')
  }

  const { supabaseUrl, supabaseAnonKey } = getSupabaseConfig()
  const url = `${supabaseUrl}/auth/v1/token?grant_type=password`

  const res = await fetch(url, {
    method: 'POST',
    headers: buildSupabaseAuthHeaders(supabaseAnonKey),
    body: JSON.stringify({ email: resolvedEmail, password: resolvedPassword }),
  })

  if (!res.ok) {
    throw new Error(`Supabase 登录失败：${await parseSupabaseError(res)}`)
  }

  const data = await res.json()
  const accessToken = data?.access_token
  const refreshToken = data?.refresh_token

  if (!accessToken) {
    throw new Error('Supabase 登录响应缺少 access_token')
  }

  return {
    access_token: accessToken,
    refresh_token: refreshToken || null,
    expires_in: data?.expires_in ?? null,
    token_type: data?.token_type ?? null,
    user: data?.user ?? null,
  }
}

/**
 * Supabase Auth - Refresh Token
 * Docs: POST /auth/v1/token?grant_type=refresh_token
 */
export async function supabaseRefreshSession(refreshToken) {
  const resolvedRefreshToken = String(refreshToken || '').trim()
  if (!resolvedRefreshToken) {
    throw new Error('refresh_token 不能为空')
  }

  const { supabaseUrl, supabaseAnonKey } = getSupabaseConfig()
  const url = `${supabaseUrl}/auth/v1/token?grant_type=refresh_token`

  const res = await fetch(url, {
    method: 'POST',
    headers: buildSupabaseAuthHeaders(supabaseAnonKey),
    body: JSON.stringify({ refresh_token: resolvedRefreshToken }),
  })

  if (!res.ok) {
    throw new Error(`Supabase refresh 失败：${await parseSupabaseError(res)}`)
  }

  const data = await res.json()
  const accessToken = data?.access_token
  if (!accessToken) {
    throw new Error('Supabase refresh 响应缺少 access_token')
  }

  return {
    access_token: accessToken,
    refresh_token: data?.refresh_token || null,
    expires_in: data?.expires_in ?? null,
    token_type: data?.token_type ?? null,
    user: data?.user ?? null,
  }
}

