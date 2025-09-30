"""应用配置与环境变量加载逻辑。"""
from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """集中式配置定义，便于后续依赖注入与测试覆盖。"""

    app_name: str = Field("GymBro API", env="APP_NAME")
    app_description: str = Field(
        "GymBro 对话与认证服务", env="APP_DESCRIPTION"
    )
    app_version: str = Field("0.1.0", env="APP_VERSION")
    debug: bool = Field(False, env="DEBUG")

    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"], env="CORS_ALLOW_ORIGINS")
    cors_allow_methods: List[str] = Field(default_factory=lambda: ["*"], env="CORS_ALLOW_METHODS")
    cors_allow_headers: List[str] = Field(default_factory=lambda: ["*"], env="CORS_ALLOW_HEADERS")
    cors_allow_credentials: bool = Field(True, env="CORS_ALLOW_CREDENTIALS")
    allowed_hosts: List[str] = Field(default_factory=lambda: ["*"], env="ALLOWED_HOSTS")
    force_https: bool = Field(False, env="FORCE_HTTPS")

    supabase_project_id: Optional[str] = Field(None, env="SUPABASE_PROJECT_ID")
    supabase_jwks_url: Optional[AnyHttpUrl] = Field(None, env="SUPABASE_JWKS_URL")
    supabase_jwk: Optional[str] = Field(None, env="SUPABASE_JWK")
    supabase_issuer: Optional[AnyHttpUrl] = Field(None, env="SUPABASE_ISSUER")
    supabase_audience: Optional[str] = Field(None, env="SUPABASE_AUDIENCE")
    supabase_service_role_key: Optional[str] = Field(None, env="SUPABASE_SERVICE_ROLE_KEY")
    supabase_jwt_secret: Optional[str] = Field(None, env="SUPABASE_JWT_SECRET")
    supabase_chat_table: str = Field("chat_messages", env="SUPABASE_CHAT_TABLE")

    jwks_cache_ttl_seconds: int = Field(900, env="JWKS_CACHE_TTL_SECONDS")
    allowed_issuers: List[AnyHttpUrl] = Field(default_factory=list, env="JWT_ALLOWED_ISSUERS")
    required_audience: Optional[str] = Field(None, env="JWT_AUDIENCE")
    token_leeway_seconds: int = Field(30, env="JWT_LEEWAY_SECONDS")

    # JWT 验证硬化配置
    jwt_clock_skew_seconds: int = Field(120, env="JWT_CLOCK_SKEW_SECONDS")
    jwt_max_future_iat_seconds: int = Field(120, env="JWT_MAX_FUTURE_IAT_SECONDS")
    jwt_require_nbf: bool = Field(False, env="JWT_REQUIRE_NBF")
    jwt_allowed_algorithms: List[str] = Field(["ES256", "RS256", "HS256"], env="JWT_ALLOWED_ALGORITHMS")

    http_timeout_seconds: float = Field(10.0, env="HTTP_TIMEOUT_SECONDS")
    event_stream_heartbeat_seconds: float = Field(15.0, env="SSE_HEARTBEAT_SECONDS")
    trace_header_name: str = Field("x-trace-id", env="TRACE_HEADER_NAME")
    ai_provider: Optional[str] = Field(None, env="AI_PROVIDER")
    ai_model: Optional[str] = Field(None, env="AI_MODEL")
    ai_api_base_url: Optional[AnyHttpUrl] = Field(None, env="AI_API_BASE_URL")
    ai_api_key: Optional[str] = Field(None, env="AI_API_KEY")

    # 匿名用户支持配置
    anon_enabled: bool = Field(True, env="ANON_ENABLED")

    # 限流配置
    rate_limit_per_user_qps: int = Field(10, env="RATE_LIMIT_PER_USER_QPS")
    rate_limit_per_user_daily: int = Field(1000, env="RATE_LIMIT_PER_USER_DAILY")
    rate_limit_per_ip_qps: int = Field(20, env="RATE_LIMIT_PER_IP_QPS")
    rate_limit_per_ip_daily: int = Field(2000, env="RATE_LIMIT_PER_IP_DAILY")
    rate_limit_anonymous_qps: int = Field(5, env="RATE_LIMIT_ANONYMOUS_QPS")
    rate_limit_anonymous_daily: int = Field(1000, env="RATE_LIMIT_ANONYMOUS_DAILY")
    rate_limit_cooldown_seconds: int = Field(300, env="RATE_LIMIT_COOLDOWN_SECONDS")
    rate_limit_failure_threshold: int = Field(10, env="RATE_LIMIT_FAILURE_THRESHOLD")

    # SSE 并发控制
    sse_max_concurrent_per_user: int = Field(2, env="SSE_MAX_CONCURRENT_PER_USER")
    sse_max_concurrent_per_conversation: int = Field(1, env="SSE_MAX_CONCURRENT_PER_CONVERSATION")
    sse_max_concurrent_per_anonymous_user: int = Field(2, env="SSE_MAX_CONCURRENT_PER_ANONYMOUS_USER")

    # 回滚预案配置
    auth_fallback_enabled: bool = Field(False, env="AUTH_FALLBACK_ENABLED")
    rate_limit_enabled: bool = Field(True, env="RATE_LIMIT_ENABLED")
    policy_gate_enabled: bool = Field(True, env="POLICY_GATE_ENABLED")

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> List[str]:
        """支持逗号分隔的字符串或直接传入列表。"""
        if value is None:
            return ["*"]
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",") if item.strip()]
            return items or ["*"]
        return list(value)

    @field_validator("allowed_issuers", mode="before")
    @classmethod
    def _split_issuers(cls, value: object) -> List[AnyHttpUrl]:
        if value in (None, "", []):
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return list(value)

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _split_hosts(cls, value: object) -> List[str]:
        if value in (None, "", []):
            return ["*"]
        if isinstance(value, str):
            hosts = [item.strip() for item in value.split(",") if item.strip()]
            return hosts or ["*"]
        return list(value)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """使用 LRU 缓存避免 BaseSettings 反复解析。"""

    return Settings()
