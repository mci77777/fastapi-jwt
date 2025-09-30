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

from app.core.middleware import get_current_trace_id
from app.settings.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class AuthenticatedUser:
    """统一的用户身份信息。"""

    uid: str
    claims: Dict[str, Any]
    user_type: str = "permanent"  # "anonymous" or "permanent"

    @property
    def is_anonymous(self) -> bool:
        """检查用户是否为匿名用户。"""
        return self.user_type == "anonymous"


@dataclass
class JWTError:
    """统一的JWT错误响应结构。"""

    status: int
    code: str
    message: str
    trace_id: Optional[str] = None
    hint: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式。"""
        result = {
            "status": self.status,
            "code": self.code,
            "message": self.message,
        }
        if self.trace_id:
            result["trace_id"] = self.trace_id
        if self.hint:
            result["hint"] = self.hint
        return result


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
        trace_id = get_current_trace_id()

        if not token:
            self._log_verification_failure("token_missing", "Token missing", trace_id=trace_id)
            raise self._create_unauthorized_error("token_missing", "Authorization token is required")

        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            self._log_verification_failure("invalid_token_header", f"Invalid JWT header: {exc}", trace_id=trace_id)
            raise self._create_unauthorized_error("invalid_token_header", "Invalid JWT header") from exc

        kid = header.get("kid")
        algorithm = header.get("alg")

        # 验证算法是否在允许列表中
        if not algorithm:
            self._log_verification_failure("algorithm_missing", "JWT header missing alg field",
                                         trace_id=trace_id, kid=kid)
            raise self._create_unauthorized_error("algorithm_missing", "JWT header missing alg field")

        if algorithm not in self._settings.jwt_allowed_algorithms:
            self._log_verification_failure("unsupported_algorithm", f"Algorithm {algorithm} not allowed",
                                         trace_id=trace_id, kid=kid, algorithm=algorithm)
            raise self._create_unauthorized_error("unsupported_alg", f"Unsupported algorithm: {algorithm}")

        try:
            key_dict = self._cache.get_key(kid)
        except Exception as exc:  # pragma: no cover - 依赖外部配置
            self._log_verification_failure("jwks_key_not_found", f"JWKS key retrieval failed: {exc}",
                                         trace_id=trace_id, kid=kid, algorithm=algorithm)
            raise self._create_unauthorized_error("jwks_key_not_found", "Signing key not found") from exc

        try:
            algorithm_cls = jwt.algorithms.get_default_algorithms()[algorithm]
        except KeyError as exc:
            self._log_verification_failure("unsupported_alg", f"Unsupported algorithm: {algorithm}",
                                         trace_id=trace_id, kid=kid, algorithm=algorithm)
            raise self._create_unauthorized_error("unsupported_alg", f"Unsupported algorithm: {algorithm}") from exc

        public_key = algorithm_cls.from_jwk(json.dumps(key_dict))

        audience = (
            self._settings.required_audience
            or self._settings.supabase_audience
            or self._settings.supabase_project_id
        )

        issuers = self._expected_issuers()

        # 构建必需声明列表 - nbf 现在是可选的
        required_claims = ["iss", "sub", "exp", "iat"]
        if audience:
            required_claims.append("aud")
        if self._settings.jwt_require_nbf:
            required_claims.append("nbf")

        options = {
            "require": required_claims,
            "verify_aud": bool(audience),
            "verify_nbf": self._settings.jwt_require_nbf,  # 控制 nbf 验证
        }

        try:
            payload = jwt.decode(
                token,
                key=public_key,
                algorithms=[algorithm],
                audience=audience,
                issuer=issuers[0] if len(issuers) == 1 else None,
                leeway=self._settings.jwt_clock_skew_seconds,  # 使用新的 clock skew 配置
                options=options,
            )
        except jwt.ExpiredSignatureError as exc:
            self._log_verification_failure("token_expired", "Token has expired",
                                         trace_id=trace_id, kid=kid, algorithm=algorithm,
                                         audience=audience, issuer=issuers[0] if len(issuers) == 1 else None)
            raise self._create_unauthorized_error("token_expired", "Token has expired") from exc
        except jwt.ImmatureSignatureError as exc:
            self._log_verification_failure("token_not_yet_valid", "Token not active yet",
                                         trace_id=trace_id, kid=kid, algorithm=algorithm,
                                         audience=audience, issuer=issuers[0] if len(issuers) == 1 else None)
            raise self._create_unauthorized_error("token_not_yet_valid", "Token not active yet") from exc
        except jwt.InvalidAudienceError as exc:
            self._log_verification_failure("invalid_audience", "Audience validation failed",
                                         trace_id=trace_id, kid=kid, algorithm=algorithm,
                                         audience=audience, issuer=issuers[0] if len(issuers) == 1 else None)
            raise self._create_unauthorized_error("invalid_audience", "Audience validation failed") from exc
        except jwt.InvalidIssuerError as exc:
            self._log_verification_failure("invalid_issuer", "Issuer validation failed",
                                         trace_id=trace_id, kid=kid, algorithm=algorithm,
                                         audience=audience, issuer=issuers[0] if len(issuers) == 1 else None)
            raise self._create_unauthorized_error("invalid_issuer", "Issuer validation failed") from exc
        except jwt.InvalidTokenError as exc:
            self._log_verification_failure("invalid_token", f"JWT validation failed: {exc}",
                                         trace_id=trace_id, kid=kid, algorithm=algorithm,
                                         audience=audience, issuer=issuers[0] if len(issuers) == 1 else None)
            raise self._create_unauthorized_error("invalid_token", "JWT validation failed") from exc

        # 执行额外的时间验证
        self._validate_time_claims(payload, trace_id, kid, algorithm, audience, issuers[0] if len(issuers) == 1 else None)

        issuer = payload.get("iss")
        if issuers and issuer not in issuers:
            self._log_verification_failure("issuer_not_allowed", f"Issuer {issuer} not in allow list",
                                         trace_id=trace_id, kid=kid, algorithm=algorithm,
                                         audience=audience, issuer=issuer, subject=payload.get("sub"))
            raise self._create_unauthorized_error("issuer_not_allowed", "Issuer is not in allow list")

        subject = payload.get("sub")
        if not subject:
            self._log_verification_failure("subject_missing", "Token missing subject claim",
                                         trace_id=trace_id, kid=kid, algorithm=algorithm,
                                         audience=audience, issuer=issuer)
            raise self._create_unauthorized_error("subject_missing", "Token missing subject claim")

        # 提取用户类型（匿名或永久）
        is_anonymous = payload.get("is_anonymous", False)
        user_type = "anonymous" if is_anonymous else "permanent"

        # 记录成功验证，包含用户类型信息
        self._log_verification_success(trace_id, subject, audience, issuer, kid, algorithm, user_type)
        return AuthenticatedUser(uid=subject, claims=payload, user_type=user_type)

    def _validate_time_claims(self, payload: Dict[str, Any], trace_id: Optional[str],
                             kid: Optional[str], algorithm: str, audience: Optional[str],
                             issuer: Optional[str]) -> None:
        """验证时间相关声明，包括自定义的 iat 未来时间检查。"""
        now = time.time()
        iat = payload.get("iat")

        if iat is not None:
            # 检查 iat 是否过于未来（超过允许的时钟偏移）
            if iat > now + self._settings.jwt_max_future_iat_seconds:
                self._log_verification_failure("iat_too_future",
                                             f"Token issued too far in future: iat={iat}, now={now}, max_future={self._settings.jwt_max_future_iat_seconds}",
                                             trace_id=trace_id, kid=kid, algorithm=algorithm,
                                             audience=audience, issuer=issuer, subject=payload.get("sub"))
                raise self._create_unauthorized_error("iat_too_future", "Token issued too far in the future")

        # 如果存在 nbf 声明，验证它（即使不是必需的）
        nbf = payload.get("nbf")
        if nbf is not None:
            if nbf > now + self._settings.jwt_clock_skew_seconds:
                self._log_verification_failure("token_not_yet_valid",
                                             f"Token not yet valid: nbf={nbf}, now={now}, skew={self._settings.jwt_clock_skew_seconds}",
                                             trace_id=trace_id, kid=kid, algorithm=algorithm,
                                             audience=audience, issuer=issuer, subject=payload.get("sub"))
                raise self._create_unauthorized_error("token_not_yet_valid", "Token not yet valid")

    def _expected_issuers(self) -> List[str]:
        values: List[str] = []
        if self._settings.supabase_issuer:
            values.append(str(self._settings.supabase_issuer))
        values.extend(str(item) for item in self._settings.allowed_issuers)
        return values

    def _create_unauthorized_error(self, code: str, message: str, hint: Optional[str] = None) -> HTTPException:
        """创建统一格式的401错误响应。"""
        trace_id = get_current_trace_id()
        error = JWTError(
            status=401,
            code=code,
            message=message,
            trace_id=trace_id,
            hint=hint
        )
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error.to_dict(),
        )

    def _log_verification_success(self, trace_id: Optional[str], subject: str,
                                audience: Optional[str], issuer: Optional[str],
                                kid: Optional[str], algorithm: str, user_type: str = "permanent") -> None:
        """记录JWT验证成功的结构化日志。"""
        logger.info(
            "JWT verification successful",
            extra={
                "trace_id": trace_id,
                "subject": subject,
                "audience": audience,
                "issuer": issuer,
                "kid": kid,
                "algorithm": algorithm,
                "user_type": user_type,
                "event": "jwt_verification_success"
            }
        )

    def _log_verification_failure(self, code: str, reason: str, trace_id: Optional[str] = None,
                                subject: Optional[str] = None, audience: Optional[str] = None,
                                issuer: Optional[str] = None, kid: Optional[str] = None,
                                algorithm: Optional[str] = None) -> None:
        """记录JWT验证失败的结构化日志。"""
        logger.warning(
            "JWT verification failed",
            extra={
                "trace_id": trace_id,
                "code": code,
                "reason": reason,
                "subject": subject,
                "audience": audience,
                "issuer": issuer,
                "kid": kid,
                "algorithm": algorithm,
                "event": "jwt_verification_failure"
            }
        )


@lru_cache(maxsize=1)
def get_jwt_verifier() -> JWTVerifier:
    """提供带缓存的校验器实例。"""

    return JWTVerifier()
