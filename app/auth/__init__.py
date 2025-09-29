"""认证模块公共导出。"""
from .dependencies import get_current_user
from .jwt_verifier import AuthenticatedUser, JWTVerifier, get_jwt_verifier
from .provider import AuthProvider, ProviderError, UserDetails
from .supabase_provider import SupabaseProvider, get_supabase_provider

__all__ = [
    "AuthenticatedUser",
    "AuthProvider",
    "JWTVerifier",
    "ProviderError",
    "SupabaseProvider",
    "UserDetails",
    "get_jwt_verifier",
    "get_supabase_provider",
    "get_current_user",
]
