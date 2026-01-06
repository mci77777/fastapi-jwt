"""User data repository backed by Supabase (service role reads)."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional, TypedDict

from app.services.supabase_admin import SupabaseAdminClient


class UserBundle(TypedDict):
    profile: Optional[dict[str, Any]]
    settings: Optional[dict[str, Any]]
    entitlements: Optional[dict[str, Any]]


class UserRepository:
    def __init__(self, supabase: SupabaseAdminClient, *, bundle_ttl_seconds: int = 60) -> None:
        self._supabase = supabase
        self._bundle_ttl_seconds = max(int(bundle_ttl_seconds), 1)
        self._bundle_cache: dict[str, tuple[float, UserBundle]] = {}

    async def get_profile(self, user_id: str) -> Optional[dict[str, Any]]:
        return await self._supabase.fetch_one_by_user_id(table="user_profiles", user_id=user_id)

    async def get_settings(self, user_id: str) -> Optional[dict[str, Any]]:
        return await self._supabase.fetch_one_by_user_id(table="user_settings", user_id=user_id)

    async def get_entitlements(self, user_id: str) -> Optional[dict[str, Any]]:
        return await self._supabase.fetch_one_by_user_id(table="user_entitlements", user_id=user_id)

    async def get_user_bundle(self, user_id: str) -> UserBundle:
        """Return profile/settings/entitlements with TTL cache (SSOT: Supabase)."""
        now = time.monotonic()
        cached = self._bundle_cache.get(user_id)
        if cached is not None:
            expires_at, value = cached
            if now < expires_at:
                return value

        profile, settings, entitlements = await asyncio.gather(
            self.get_profile(user_id),
            self.get_settings(user_id),
            self.get_entitlements(user_id),
        )
        bundle: UserBundle = {"profile": profile, "settings": settings, "entitlements": entitlements}
        self._bundle_cache[user_id] = (now + float(self._bundle_ttl_seconds), bundle)
        return bundle

