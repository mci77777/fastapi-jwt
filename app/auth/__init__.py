"""认证模块公共导出。"""
from .dependencies import get_current_user, get_authenticated_user_optional
from .jwt_verifier import AuthenticatedUser, JWTVerifier, get_jwt_verifier
from .provider import AuthProvider, InMemoryProvider, ProviderError, UserDetails, get_auth_provider
from .supabase_provider import SupabaseProvider, get_supabase_provider

__all__ = [
    "AuthenticatedUser",
    "AuthProvider",
    "JWTVerifier",
    "ProviderError",
    "SupabaseProvider",
    "InMemoryProvider",
    "UserDetails",
    "get_auth_provider",
    "get_jwt_verifier",
    "get_supabase_provider",
    "get_current_user",
    "get_authenticated_user_optional",
]
