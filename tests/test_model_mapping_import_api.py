from __future__ import annotations

import json
from unittest.mock import Mock, patch

from app.auth.jwt_verifier import AuthenticatedUser


def _admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="test-admin",
        claims={
            "sub": "test-admin",
            "user_metadata": {"username": "admin", "is_admin": True},
        },
    )


@patch("app.auth.dependencies.get_jwt_verifier")
def test_import_local_mappings_success(mock_get_verifier, client):
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = _admin_user()
    mock_get_verifier.return_value = mock_verifier

    payload = {
        "exported_at": "2026-01-19T00:00:00+00:00",
        "mappings": [
            {
                "scope_type": "module",
                "scope_key": "chat",
                "name": "Chat Module",
                "default_model": "gpt-4o-mini",
                "candidates": ["gpt-4o-mini"],
                "is_active": True,
                "metadata": {"env": "test"},
            }
        ],
    }
    files = {
        "file": ("model-mappings.json", json.dumps(payload), "application/json"),
    }
    headers = {"Authorization": "Bearer mock-admin"}

    resp = client.post("/api/v1/llm/model-groups/import-local-json", headers=headers, files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 200
    assert body["data"]["imported_count"] == 1

    list_resp = client.get("/api/v1/llm/model-groups", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json().get("data") or []
    assert any(item.get("id") == "module:chat" for item in items)


@patch("app.auth.dependencies.get_jwt_verifier")
def test_import_local_mappings_invalid_json(mock_get_verifier, client):
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = _admin_user()
    mock_get_verifier.return_value = mock_verifier

    files = {
        "file": ("model-mappings.json", "{not-json}", "application/json"),
    }
    headers = {"Authorization": "Bearer mock-admin"}

    resp = client.post("/api/v1/llm/model-groups/import-local-json", headers=headers, files=files)
    assert resp.status_code == 422
    body = resp.json()
    assert body.get("code") == 422


@patch("app.auth.dependencies.get_jwt_verifier")
def test_import_local_mappings_partial_invalid(mock_get_verifier, client):
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = _admin_user()
    mock_get_verifier.return_value = mock_verifier

    payload = {
        "mappings": [
            {
                "scope_type": "module",
                "scope_key": "routing",
                "default_model": "gpt-4o-mini",
                "candidates": ["gpt-4o-mini"],
            },
            {"scope_type": "", "scope_key": ""},
        ]
    }
    files = {
        "file": ("model-mappings.json", json.dumps(payload), "application/json"),
    }
    headers = {"Authorization": "Bearer mock-admin"}

    resp = client.post("/api/v1/llm/model-groups/import-local-json", headers=headers, files=files)
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["imported_count"] == 1
    assert body["data"]["skipped_count"] == 1
    assert body["data"]["errors"], "expected errors for invalid entries"
