from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import status

from app.auth import AuthenticatedUser


@pytest.mark.asyncio
async def test_llm_models_get_allowed_without_admin_key(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
        mock_get_verifier.return_value = mock_verifier

        resp = await async_client.get(
            "/api/v1/llm/models",
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
        )
        assert resp.status_code == status.HTTP_200_OK


@pytest.mark.asyncio
async def test_llm_models_post_requires_admin(async_client, mock_jwt_token: str):
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.side_effect = [
            AuthenticatedUser(uid="test-user-123", claims={}),
            AuthenticatedUser(uid="test-user-123", claims={"user_metadata": {"username": "admin", "is_admin": True}}),
        ]
        mock_get_verifier.return_value = mock_verifier

        payload = {"name": "endpoint-guard", "base_url": "https://api.openai.com"}

        denied = await async_client.post(
            "/api/v1/llm/models",
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
            json=payload,
        )
        assert denied.status_code == status.HTTP_403_FORBIDDEN

        allowed = await async_client.post(
            "/api/v1/llm/models",
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
            json=payload,
        )
        assert allowed.status_code == status.HTTP_200_OK
