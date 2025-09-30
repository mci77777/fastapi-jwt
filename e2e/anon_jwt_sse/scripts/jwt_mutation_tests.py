"""
JWT 变体/攻击面快速校验
- 过期 token
- 错误 aud
- alg=none
运行：python e2e/anon_jwt_sse/scripts/jwt_mutation_tests.py
输出：状态码与响应体（应为 401/403 + 统一错误体）
"""
import json, base64, time, httpx, os

API = os.environ.get("API_BASE", "http://localhost:9999")
token_path = os.path.join(os.path.dirname(__file__), "..", "artifacts", "token.json")
TOK = json.load(open(token_path))["access_token"]

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
