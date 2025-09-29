"""应用配置与环境变量加载逻辑。"""
from functools import lru_cache
from typing import List, Optional

from pydantic import AnyHttpUrl, BaseSettings, Field, validator


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

    supabase_project_id: Optional[str] = Field(None, env="SUPABASE_PROJECT_ID")
    supabase_jwks_url: Optional[AnyHttpUrl] = Field(None, env="SUPABASE_JWKS_URL")
    supabase_jwk: Optional[str] = Field(None, env="SUPABASE_JWK")
    supabase_issuer: Optional[AnyHttpUrl] = Field(None, env="SUPABASE_ISSUER")
    supabase_audience: Optional[str] = Field(None, env="SUPABASE_AUDIENCE")
    supabase_service_role_key: Optional[str] = Field(None, env="SUPABASE_SERVICE_ROLE_KEY")

    jwks_cache_ttl_seconds: int = Field(900, env="JWKS_CACHE_TTL_SECONDS")
    allowed_issuers: List[AnyHttpUrl] = Field(default_factory=list, env="JWT_ALLOWED_ISSUERS")
    required_audience: Optional[str] = Field(None, env="JWT_AUDIENCE")
    token_leeway_seconds: int = Field(30, env="JWT_LEEWAY_SECONDS")

    http_timeout_seconds: float = Field(10.0, env="HTTP_TIMEOUT_SECONDS")
    trace_header_name: str = Field("x-trace-id", env="TRACE_HEADER_NAME")
    ai_provider: Optional[str] = Field(None, env="AI_PROVIDER")
    ai_model: Optional[str] = Field(None, env="AI_MODEL")
    ai_api_base_url: Optional[AnyHttpUrl] = Field(None, env="AI_API_BASE_URL")
    ai_api_key: Optional[str] = Field(None, env="AI_API_KEY")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @validator("cors_allow_origins", pre=True)
    def _split_origins(cls, value: object) -> List[str]:  # noqa: D401
        """支持逗号分隔的字符串或直接传入列表。"""
        if value is None:
            return ["*"]
        if isinstance(value, str):
            items = [item.strip() for item in value.split(",") if item.strip()]
            return items or ["*"]
        return list(value)

    @validator("allowed_issuers", pre=True)
    def _split_issuers(cls, value: object) -> List[AnyHttpUrl]:
        if value in (None, "", []):
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return list(value)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """使用 LRU 缓存避免 BaseSettings 反复解析。"""

    return Settings()
