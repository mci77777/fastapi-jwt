"""JWT 校验与 JWKS 缓存逻辑。"""
import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional

import httpx
import jwt
from fastapi import HTTPException, status

from app.settings.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class AuthenticatedUser:
    """统一的用户身份信息。"""

    uid: str
    claims: Dict[str, Any]


class JWKSCache:
    """简单的 JWKS 缓存，支持 15 分钟 TTL。"""

    def __init__(
        self,
        jwks_url: Optional[str],
        static_jwk: Optional[str],
        ttl_seconds: int,
        timeout_seconds: float,
    ) -> None:
        self._jwks_url = jwks_url
        self._static_jwk = static_jwk
        self._ttl_seconds = max(ttl_seconds, 60)
        self._timeout_seconds = timeout_seconds
        self._keys: List[Dict[str, Any]] = []
        self._expires_at: float = 0.0
        self._init_static()

    def _init_static(self) -> None:
        if not self._static_jwk:
            return
        try:
            data = json.loads(self._static_jwk)
        except json.JSONDecodeError as exc:  # pragma: no cover - 配置错误
            raise RuntimeError("Invalid SUPABASE_JWK value") from exc

        if isinstance(data, dict) and "keys" in data:
            self._keys = list(data.get("keys") or [])
        elif isinstance(data, dict):
            self._keys = [data]
        elif isinstance(data, list):
            self._keys = list(data)
        else:
            raise RuntimeError("Unsupported SUPABASE_JWK format")

        self._expires_at = float("inf")

    def get_keys(self) -> List[Dict[str, Any]]:
        if self._keys and self._expires_at == float("inf"):
            return self._keys

        if not self._jwks_url:
            raise RuntimeError("JWKS source not configured")

        now = time.monotonic()
        if self._keys and now < self._expires_at:
            return self._keys

        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.get(self._jwks_url)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Failed to fetch JWKS: {exc}") from exc

        keys = payload.get("keys") if isinstance(payload, dict) else None
        if not keys:
            raise RuntimeError("JWKS response missing keys")

        self._keys = list(keys)
        self._expires_at = now + self._ttl_seconds
        return self._keys

    def get_key(self, kid: Optional[str]) -> Dict[str, Any]:
        keys = self.get_keys()
        if kid:
            for key in keys:
                if key.get("kid") == kid:
                    return key
        if len(keys) == 1:
            return keys[0]
        raise RuntimeError("Signing key not found for given kid")


class JWTVerifier:
    """封装 JWT 校验逻辑，负责调用 JWKS 与声明验证。"""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._cache = JWKSCache(
            jwks_url=str(self._settings.supabase_jwks_url)
            if self._settings.supabase_jwks_url
            else None,
            static_jwk=self._settings.supabase_jwk,
            ttl_seconds=self._settings.jwks_cache_ttl_seconds,
            timeout_seconds=self._settings.http_timeout_seconds,
        )

    def verify_token(self, token: str) -> AuthenticatedUser:
        if not token:
            raise self._unauthorized("token_missing", "Authorization token is required")

        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            logger.warning("无法解析 JWT 头部: %s", exc)
            raise self._unauthorized("invalid_token_header", "Invalid JWT header") from exc

        kid = header.get("kid")
        algorithm = header.get("alg")
        if not algorithm:
            raise self._unauthorized("algorithm_missing", "JWT header missing alg field")

        try:
            key_dict = self._cache.get_key(kid)
        except Exception as exc:  # pragma: no cover - 依赖外部配置
            logger.error("获取 JWKS 失败: kid=%s error=%s", kid, exc)
            raise self._unauthorized("jwks_key_not_found", "Signing key not found") from exc

        try:
            algorithm_cls = jwt.algorithms.get_default_algorithms()[algorithm]
        except KeyError as exc:
            raise self._unauthorized("unsupported_alg", f"Unsupported alg: {algorithm}") from exc

        public_key = algorithm_cls.from_jwk(json.dumps(key_dict))

        audience = (
            self._settings.required_audience
            or self._settings.supabase_audience
            or self._settings.supabase_project_id
        )

        issuers = self._expected_issuers()
        required_claims = ["iss", "sub", "exp", "iat", "nbf"]
        if audience:
            required_claims.append("aud")
        options = {
            "require": required_claims,
            "verify_aud": bool(audience),
        }

        try:
            payload = jwt.decode(
                token,
                key=public_key,
                algorithms=[algorithm],
                audience=audience,
                issuer=issuers[0] if len(issuers) == 1 else None,
                leeway=self._settings.token_leeway_seconds,
                options=options,
            )
        except jwt.ExpiredSignatureError as exc:
            raise self._unauthorized("token_expired", "Token has expired") from exc
        except jwt.ImmatureSignatureError as exc:
            raise self._unauthorized("token_not_yet_valid", "Token not active yet") from exc
        except jwt.InvalidAudienceError as exc:
            raise self._unauthorized("invalid_audience", "Audience validation failed") from exc
        except jwt.InvalidIssuerError as exc:
            raise self._unauthorized("invalid_issuer", "Issuer validation failed") from exc
        except jwt.InvalidTokenError as exc:
            raise self._unauthorized("invalid_token", "JWT validation failed") from exc

        issuer = payload.get("iss")
        if issuers and issuer not in issuers:
            raise self._unauthorized("issuer_not_allowed", "Issuer is not in allow list")

        subject = payload.get("sub")
        if not subject:
            raise self._unauthorized("subject_missing", "Token missing subject claim")

        logger.debug("JWT 验证成功 uid=%s", subject)
        return AuthenticatedUser(uid=subject, claims=payload)

    def _expected_issuers(self) -> List[str]:
        values: List[str] = []
        if self._settings.supabase_issuer:
            values.append(str(self._settings.supabase_issuer))
        values.extend(str(item) for item in self._settings.allowed_issuers)
        return values

    @staticmethod
    def _unauthorized(code: str, message: str) -> HTTPException:
        logger.warning("JWT 验证失败 code=%s message=%s", code, message)
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": code, "message": message},
        )


@lru_cache(maxsize=1)
def get_jwt_verifier() -> JWTVerifier:
    """提供带缓存的校验器实例。"""

    return JWTVerifier()
