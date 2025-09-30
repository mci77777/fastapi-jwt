// Edge Function: get-anon-token
// Creates a temporary anonymous Supabase user and returns access token
// Environment variables required:
// SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, ANON_TOKEN_TTL_MIN (default 60), DAILY_LIMIT_PER_IP (default 10)

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!;
const SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const TOKEN_TTL_MIN = Number(Deno.env.get('ANON_TOKEN_TTL_MIN') ?? '60');
const DAILY_LIMIT_PER_IP = Number(Deno.env.get('DAILY_LIMIT_PER_IP') ?? '10');

function getClientIp(req: Request): string {
  const forwarded = req.headers.get('x-forwarded-for');
  if (forwarded) return forwarded.split(',')[0].trim();
  const real = req.headers.get('x-real-ip');
  if (real) return real;
  return 'unknown';
}

async function checkAndIncrementIpLimit(ip: string) {
  const today = new Date().toISOString().slice(0, 10);
  const url = `${SUPABASE_URL}/rest/v1/anon_rate_limits`;
  const payload = { ip, day: today, count: 1 };
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'apikey': SERVICE_KEY,
      'Authorization': `Bearer ${SERVICE_KEY}`,
      'Content-Type': 'application/json',
      'Prefer': 'resolution=merge-duplicates,return=representation'
    },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const t = await res.text();
    throw new Error(`Rate limit upsert failed: ${res.status} ${t}`);
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
  const password = Array.from(pwArray).map(b => b.toString(16).padStart(2, '0')).join('');

  const createUrl = `${SUPABASE_URL}/auth/v1/admin/users`;
  const createBody = { email: anonEmail, password, email_confirm: true, user_metadata: { anon: true, created_by: 'edge-get-anon' } };
  let r = await fetch(createUrl, { method: 'POST', headers: { 'apikey': SERVICE_KEY, 'Authorization': `Bearer ${SERVICE_KEY}`, 'Content-Type': 'application/json' }, body: JSON.stringify(createBody) });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(`Create user failed: ${r.status} ${t}`);
  }
  const user = await r.json();

  const tokenUrl = `${SUPABASE_URL}/auth/v1/token?grant_type=password`;
  const form = new URLSearchParams();
  form.set('email', anonEmail);
  form.set('password', password);
  r = await fetch(tokenUrl, { method: 'POST', headers: { 'apikey': SERVICE_KEY, 'Authorization': `Bearer ${SERVICE_KEY}`, 'Content-Type': 'application/x-www-form-urlencoded' }, body: form.toString() });
  if (!r.ok) {
    const t = await r.text();
    try { await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${user.id}`, { method: 'DELETE', headers: { 'apikey': SERVICE_KEY, 'Authorization': `Bearer ${SERVICE_KEY}` } }); } catch (_) { }
    throw new Error(`Token exchange failed: ${r.status} ${t}`);
  }
  const tokenResp = await r.json();
  return { user, tokenResp };
}

async function insertUserAnonRecord(userId: string, ip: string, expiresAtIso: string) {
  const url = `${SUPABASE_URL}/rest/v1/user_anon`;
  const payload = { user_id: userId, created_at: new Date().toISOString(), ip, expires_at: expiresAtIso };
  const res = await fetch(url, { method: 'POST', headers: { 'apikey': SERVICE_KEY, 'Authorization': `Bearer ${SERVICE_KEY}`, 'Content-Type': 'application/json', 'Prefer': 'return=minimal' }, body: JSON.stringify(payload) });
  if (!res.ok) {
    const text = await res.text();
    console.error('Insert user_anon failed:', res.status, text);
  }
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== 'POST') return new Response(JSON.stringify({ error: 'Method not allowed' }), { status: 405, headers: { 'Content-Type': 'application/json' } });
    const ip = getClientIp(req);
    const rl = await checkAndIncrementIpLimit(ip);
    if (!rl.allowed) return new Response(JSON.stringify({ error: 'Rate limit exceeded' }), { status: 429, headers: { 'Content-Type': 'application/json' } });
    const { user, tokenResp } = await createAnonUserAndGetToken();
    const expiresAt = new Date(Date.now() + TOKEN_TTL_MIN * 60_000).toISOString();
    try { await insertUserAnonRecord(user.id, ip, expiresAt); } catch (e) { console.error('Failed to record user_anon', e); }
    const out = { access_token: tokenResp.access_token, expires_at: expiresAt, token_type: tokenResp.token_type, user: { id: user.id, email: user.email, user_metadata: user.user_metadata } };
    return new Response(JSON.stringify(out), { status: 200, headers: { 'Content-Type': 'application/json' } });
  } catch (err) {
    console.error('Error creating anon token', err);
    return new Response(JSON.stringify({ error: String(err) }), { status: 500, headers: { 'Content-Type': 'application/json' } });
  }
});
