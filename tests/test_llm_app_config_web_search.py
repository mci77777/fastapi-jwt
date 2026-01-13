from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.auth import AuthenticatedUser


class TestLlmAppConfigWebSearch:
    @pytest.mark.asyncio
    async def test_llm_app_config_web_search_key_is_masked_and_source_db(
        self,
        async_client: AsyncClient,
        mock_jwt_token: str,
        monkeypatch: pytest.MonkeyPatch,
    ):
        monkeypatch.delenv("EXA_API_KEY", raising=False)

        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(
                uid="test-admin-001",
                claims={"user_metadata": {"is_admin": True}},
            )
            mock_get_verifier.return_value = mock_verifier

            initial = await async_client.get(
                "/api/v1/llm/app/config",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
            )
            assert initial.status_code == status.HTTP_200_OK
            initial_data = initial.json().get("data") or {}
            assert initial_data.get("web_search_exa_api_key_masked") in {"", None}
            assert initial_data.get("web_search_exa_api_key_source") in {"none", "env", "db"}

            key = "exa_test_key_1234567890"
            updated = await async_client.post(
                "/api/v1/llm/app/config",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={
                    "web_search_enabled": True,
                    "web_search_provider": "exa",
                    "web_search_exa_api_key": key,
                },
            )
            assert updated.status_code == status.HTTP_200_OK
            data = updated.json().get("data") or {}

            assert data.get("web_search_enabled") is True
            assert data.get("web_search_provider") == "exa"
            assert data.get("web_search_exa_api_key_source") == "db"
            assert data.get("web_search_exa_api_key_masked")
            assert data.get("web_search_exa_api_key_masked") != key
            assert "web_search_exa_api_key" not in data

