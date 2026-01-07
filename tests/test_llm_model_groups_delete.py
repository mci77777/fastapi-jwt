from __future__ import annotations

import uuid
from unittest.mock import Mock, patch

from app.auth.jwt_verifier import AuthenticatedUser


def _auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="test-user-123",
        claims={
            "sub": "test-user-123",
            "email": "test@example.com",
            "iss": "https://test.supabase.co",
            "aud": "test-audience",
            "user_metadata": {"username": "admin", "is_admin": True},
        },
    )


@patch("app.auth.dependencies.get_jwt_verifier")
def test_delete_model_group_removes_mapping(mock_get_verifier, client):
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = _auth_user()
    mock_get_verifier.return_value = mock_verifier

    headers = {
        "Authorization": "Bearer mock-jwt-token",
    }

    scope_key = f"delete-{uuid.uuid4().hex[:8]}"
    upsert = client.post(
        "/api/v1/llm/model-groups",
        headers=headers,
        json={
            "scope_type": "module",
            "scope_key": scope_key,
            "name": "Delete Test",
            "default_model": "gpt-4o-mini",
            "candidates": ["gpt-4o-mini"],
            "is_active": True,
            "metadata": {},
        },
    )
    assert upsert.status_code == 200
    mapping_id = upsert.json()["data"]["id"]

    deleted = client.delete(f"/api/v1/llm/model-groups/{mapping_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["data"]["deleted"] is True

    listed = client.get("/api/v1/llm/model-groups", headers=headers)
    assert listed.status_code == 200
    ids = [item.get("id") for item in (listed.json().get("data") or [])]
    assert mapping_id not in ids
