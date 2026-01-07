"""Entitlement resolution + gating (SSOT: Supabase user_entitlements)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from app.repositories.user_repo import UserRepository


@dataclass(frozen=True)
class ResolvedEntitlement:
    tier: str
    expires_at_ms: Optional[int]
    flags: dict[str, Any]
    resolved_at_ms: int

    @property
    def is_pro(self) -> bool:
        if self.tier != "pro":
            return False
        if self.expires_at_ms is None:
            return True
        return self.expires_at_ms > self.resolved_at_ms


class EntitlementService:
    def __init__(self, user_repository: UserRepository, *, ttl_seconds: int = 60) -> None:
        self._repo = user_repository
        self._ttl_seconds = max(int(ttl_seconds), 1)
        self._cache: dict[str, tuple[float, ResolvedEntitlement]] = {}

    async def resolve(self, user_id: str) -> ResolvedEntitlement:
        now = time.monotonic()
        cached = self._cache.get(user_id)
        if cached is not None:
            expires_at, value = cached
            if now < expires_at:
                return value

        resolved_at_ms = int(time.time() * 1000)
        row = None
        try:
            row = await self._repo.get_entitlements(user_id)
        except Exception:
            row = None

        tier = "free"
        expires_at_ms: Optional[int] = None
        flags: dict[str, Any] = {}

        if isinstance(row, dict):
            raw_tier = row.get("tier")
            if isinstance(raw_tier, str) and raw_tier.strip():
                tier = raw_tier.strip().lower()
            raw_expires = row.get("expires_at")
            if isinstance(raw_expires, int):
                expires_at_ms = raw_expires
            raw_flags = row.get("flags")
            if isinstance(raw_flags, dict):
                flags = dict(raw_flags)

        entitlement = ResolvedEntitlement(
            tier=tier,
            expires_at_ms=expires_at_ms,
            flags=flags,
            resolved_at_ms=resolved_at_ms,
        )
        self._cache[user_id] = (now + float(self._ttl_seconds), entitlement)
        return entitlement

