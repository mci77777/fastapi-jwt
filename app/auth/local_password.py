"""本地账号密码哈希工具（Dashboard 本地账号 SSOT）。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64d(text: str) -> bytes:
    pad = "=" * ((4 - (len(text) % 4)) % 4)
    return base64.urlsafe_b64decode((text + pad).encode("ascii"))


def hash_password(password: str) -> str:
    # KISS：使用 stdlib scrypt（无需额外依赖），仅用于本地 Dashboard 账号存储。
    salt = secrets.token_bytes(16)
    n, r, p = 2**14, 8, 1
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_b64, key_b64 = stored.split("$", 5)
        if algo != "scrypt":
            return False
        salt = _b64d(salt_b64)
        expected = _b64d(key_b64)
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(derived, expected)
    except Exception:
        return False

