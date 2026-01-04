from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.auth.jwt_verifier import AuthenticatedUser


def test_llm_app_models_returns_mapping_keys(client) -> None:
    user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")

    class FakeVerifier:
        def verify_token(self, _token: str) -> AuthenticatedUser:
            return user

    mappings = [
        # App 业务 key（当前 SSOT）：tenant/global 的 scope_key（例如 xai / deepseek / gpt-5）
        {
            "id": "tenant:xai",
            "scope_type": "tenant",
            "scope_key": "xai",
            "name": "XAI",
            "default_model": "gpt-4o-mini",
            "candidates": ["gpt-4o-mini"],
            "is_active": True,
            "updated_at": "2026-01-03T00:00:00+00:00",
            "source": "fallback",
            "metadata": {},
        },
        {
            "id": "global:global",
            "scope_type": "global",
            "scope_key": "global",
            "name": "Default",
            "default_model": "gpt-4o-mini",
            "candidates": ["gpt-4o-mini"],
            "is_active": True,
            "updated_at": "2026-01-03T00:00:00+00:00",
            "source": "fallback",
            "metadata": {},
        },
        # 不应返回：非 tenant/global
        {
            "id": "user:user-123",
            "scope_type": "user",
            "scope_key": "user-123",
            "name": "PerUser",
            "default_model": "gpt-4o-mini",
            "candidates": ["gpt-4o-mini"],
            "is_active": True,
            "updated_at": "2026-01-03T00:00:00+00:00",
            "source": "fallback",
            "metadata": {},
        },
    ]

    from app import app as fastapi_app

    with patch("app.auth.dependencies.get_jwt_verifier", return_value=FakeVerifier()):
        with patch.object(fastapi_app.state.model_mapping_service, "list_mappings", new=AsyncMock(return_value=mappings)):
            resp = client.get(
                "/api/v1/llm/app/models",
                headers={"Authorization": "Bearer test.jwt"},
            )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["code"] == 200
    assert payload["recommended_model"] == "xai"
    returned = payload["data"]
    assert [item["model"] for item in returned] == ["xai", "global"]
