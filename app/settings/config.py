"""应用配置与环境变量加载逻辑。"""

import json
from functools import lru_cache
from typing import Iterable, List, Optional

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """集中式配置定义，便于后续依赖注入与测试覆盖。"""

    app_name: str = Field(default="GymBro API", alias="APP_NAME")
    app_description: str = Field(default="GymBro 对话与认证服务", alias="APP_DESCRIPTION")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")

    # SQLite 路径（SSOT：默认写入 data/，配合 docker-compose bind mount 持久化端点/测试用户等运行态数据）
    sqlite_db_path: str = Field(default="data/db.sqlite3", alias="SQLITE_DB_PATH")

    # 日志落盘（用于按 request_id 聚合最小交接数据）
    log_to_file: bool = Field(default=False, alias="LOG_TO_FILE")
    log_file_path: str = Field(default="logs/app.log", alias="LOG_FILE_PATH")

    cors_allow_origins: List[str] = Field(default_factory=lambda: ["*"], alias="CORS_ALLOW_ORIGINS")
    cors_allow_methods: List[str] = Field(default_factory=lambda: ["*"], alias="CORS_ALLOW_METHODS")
    cors_allow_headers: List[str] = Field(default_factory=lambda: ["*"], alias="CORS_ALLOW_HEADERS")
    cors_allow_credentials: bool = Field(default=True, alias="CORS_ALLOW_CREDENTIALS")
    allowed_hosts: List[str] = Field(default_factory=lambda: ["*"], alias="ALLOWED_HOSTS")
    force_https: bool = Field(default=False, alias="FORCE_HTTPS")

    supabase_project_id: Optional[str] = Field(default=None, alias="SUPABASE_PROJECT_ID")
    supabase_url: Optional[AnyHttpUrl] = Field(default=None, alias="SUPABASE_URL")
    supabase_anon_key: Optional[str] = Field(default=None, alias="SUPABASE_ANON_KEY")
    supabase_jwks_url: Optional[AnyHttpUrl] = Field(default=None, alias="SUPABASE_JWKS_URL")
    supabase_jwk: Optional[str] = Field(default=None, alias="SUPABASE_JWK")
    supabase_issuer: Optional[AnyHttpUrl] = Field(default=None, alias="SUPABASE_ISSUER")
    supabase_audience: Optional[str] = Field(default=None, alias="SUPABASE_AUDIENCE")
    supabase_service_role_key: Optional[str] = Field(default=None, alias="SUPABASE_SERVICE_ROLE_KEY")
    supabase_jwt_secret: Optional[str] = Field(default=None, alias="SUPABASE_JWT_SECRET")
    supabase_chat_table: str = Field(default="chat_messages", alias="SUPABASE_CHAT_TABLE")
    supabase_return_representation: bool = Field(default=False, alias="SUPABASE_RETURN_REPRESENTATION")

    # Supabase 保活配置（防止免费层 7 天无活动后暂停）
    supabase_keepalive_enabled: bool = Field(default=True, alias="SUPABASE_KEEPALIVE_ENABLED")
    supabase_keepalive_interval_minutes: int = Field(
        default=10,
        alias="SUPABASE_KEEPALIVE_INTERVAL_MINUTES",
    )

    jwks_cache_ttl_seconds: int = Field(default=900, alias="JWKS_CACHE_TTL_SECONDS")
    # 这里使用 List[str] 以便更宽松地接受占位符/非完整 URL，由 JWT 验证器在使用时再做规范化
    allowed_issuers: List[str] = Field(default_factory=list, alias="JWT_ALLOWED_ISSUERS")
    required_audience: Optional[str] = Field(default=None, alias="JWT_AUDIENCE")
    token_leeway_seconds: int = Field(default=30, alias="JWT_LEEWAY_SECONDS")

    # JWT 验证硬化配置
    jwt_clock_skew_seconds: int = Field(default=120, alias="JWT_CLOCK_SKEW_SECONDS")
    jwt_max_future_iat_seconds: int = Field(default=120, alias="JWT_MAX_FUTURE_IAT_SECONDS")
    jwt_require_nbf: bool = Field(default=False, alias="JWT_REQUIRE_NBF")
    jwt_allowed_algorithms: List[str] = Field(
        default=["ES256", "RS256", "HS256"],
        alias="JWT_ALLOWED_ALGORITHMS",
    )

    http_timeout_seconds: float = Field(default=10.0, alias="HTTP_TIMEOUT_SECONDS")
    event_stream_heartbeat_seconds: float = Field(default=15.0, alias="SSE_HEARTBEAT_SECONDS")
    ai_provider: Optional[str] = Field(default=None, alias="AI_PROVIDER")
    ai_model: Optional[str] = Field(default=None, alias="AI_MODEL")
    ai_api_base_url: Optional[AnyHttpUrl] = Field(default=None, alias="AI_API_BASE_URL")
    ai_api_key: Optional[str] = Field(default=None, alias="AI_API_KEY")
    mail_api_key: Optional[str] = Field(default=None, alias="MAIL_API_KEY")
    mail_api_base_url: Optional[AnyHttpUrl] = Field(default=None, alias="MAIL_API_BASE_URL")
    mail_domain: Optional[str] = Field(default=None, alias="MAIL_DOMAIN")
    mail_expiry_ms: int = Field(default=3600000, alias="MAIL_EXPIRY_MS")

    # 匿名用户支持配置
    anon_enabled: bool = Field(default=True, alias="ANON_ENABLED")

    # 限流配置
    rate_limit_per_user_qps: int = Field(default=10, alias="RATE_LIMIT_PER_USER_QPS")
    rate_limit_per_user_daily: int = Field(default=1000, alias="RATE_LIMIT_PER_USER_DAILY")
    rate_limit_per_ip_qps: int = Field(default=20, alias="RATE_LIMIT_PER_IP_QPS")
    rate_limit_per_ip_daily: int = Field(default=2000, alias="RATE_LIMIT_PER_IP_DAILY")
    rate_limit_anonymous_qps: int = Field(default=5, alias="RATE_LIMIT_ANONYMOUS_QPS")
    rate_limit_anonymous_daily: int = Field(default=1000, alias="RATE_LIMIT_ANONYMOUS_DAILY")
    rate_limit_cooldown_seconds: int = Field(default=300, alias="RATE_LIMIT_COOLDOWN_SECONDS")
    rate_limit_failure_threshold: int = Field(default=10, alias="RATE_LIMIT_FAILURE_THRESHOLD")

    # SSE 并发控制
    sse_max_concurrent_per_user: int = Field(default=2, alias="SSE_MAX_CONCURRENT_PER_USER")
    sse_max_concurrent_per_conversation: int = Field(
        default=1,
        alias="SSE_MAX_CONCURRENT_PER_CONVERSATION",
    )
    sse_max_concurrent_per_anonymous_user: int = Field(
        default=2,
        alias="SSE_MAX_CONCURRENT_PER_ANONYMOUS_USER",
    )

    # 回滚预案配置
    auth_fallback_enabled: bool = Field(default=False, alias="AUTH_FALLBACK_ENABLED")
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    policy_gate_enabled: bool = Field(default=True, alias="POLICY_GATE_ENABLED")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore",
        enable_decoding=False,
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> List[str]:
        """支持逗号分隔的字符串或直接传入列表。"""
        if value is None:
            return ["*"]
        if isinstance(value, str):
            text = value.strip()
            # 兼容 JSON 数组写法：["*"]
            if text.startswith("["):
                try:
                    data = json.loads(text)
                    if isinstance(data, list):
                        items = [str(item).strip() for item in data if str(item).strip()]
                        return items or ["*"]
                except json.JSONDecodeError:
                    pass
            items = [item.strip() for item in text.split(",") if item.strip()]
            return items or ["*"]
        if isinstance(value, Iterable):
            return [str(item).strip() for item in value if str(item).strip()]
        return ["*"]

    @field_validator("cors_allow_methods", "cors_allow_headers", mode="before")
    @classmethod
    def _split_simple_cors_lists(cls, value: object) -> List[str]:
        """解析 CORS methods/headers，支持 JSON 数组或逗号分隔字符串。"""
        if value in (None, "", []):
            return ["*"]
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                try:
                    data = json.loads(text)
                    if isinstance(data, list):
                        items = [str(item).strip() for item in data if str(item).strip()]
                        return items or ["*"]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in text.split(",") if item.strip()]
        if isinstance(value, Iterable):
            return [str(item).strip() for item in value if str(item).strip()]
        return ["*"]

    @field_validator("allowed_issuers", mode="before")
    @classmethod
    def _split_issuers(cls, value: object) -> List[str]:
        """解析 JWT_ALLOWED_ISSUERS，允许占位符字符串并在后续再做 URL 规范化。"""
        if value in (None, "", []):
            return []
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                try:
                    data = json.loads(text)
                    if isinstance(data, list):
                        return [str(item).strip() for item in data if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in text.split(",") if item.strip()]
        if isinstance(value, Iterable):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _split_hosts(cls, value: object) -> List[str]:
        if value in (None, "", []):
            return ["*"]
        if isinstance(value, str):
            text = value.strip()
            # 兼容 JSON 数组写法：["*","example.com"]
            if text.startswith("["):
                try:
                    data = json.loads(text)
                    if isinstance(data, list):
                        hosts = [str(item).strip() for item in data if str(item).strip()]
                        return hosts or ["*"]
                except json.JSONDecodeError:
                    pass
            hosts = [item.strip() for item in text.split(",") if item.strip()]
            return hosts or ["*"]
        if isinstance(value, Iterable):
            return [str(item).strip() for item in value if str(item).strip()]
        return ["*"]

    @field_validator("jwt_allowed_algorithms", mode="before")
    @classmethod
    def _split_algorithms(cls, value: object) -> List[str]:
        """支持逗号分隔或列表形式配置允许的 JWT 算法。"""
        if value in (None, "", []):
            return ["ES256", "RS256", "HS256"]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, Iterable):
            return [str(item).strip() for item in value if str(item).strip()]
        return ["ES256", "RS256", "HS256"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """使用 LRU 缓存避免 BaseSettings 反复解析。"""

    return Settings()
