from __future__ import annotations

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
        },
    )


@patch("app.auth.dependencies.get_jwt_verifier")
def test_llm_models_default_view_is_mapped_and_endpoints_view_still_works(mock_get_verifier, client) -> None:
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = _auth_user()
    mock_get_verifier.return_value = mock_verifier

    headers = {
        "Authorization": "Bearer mock-jwt-token",
        "X-LLM-Admin-Key": "test-llm-admin",
    }

    mapping_id = "tenant:test-mapped"

    upsert = client.post(
        "/api/v1/llm/model-groups",
        headers=headers,
        json={
            "scope_type": "tenant",
            "scope_key": "test-mapped",
            "name": "test-mapped",
            "default_model": "gpt-4o-mini",
            "candidates": ["gpt-4o-mini"],
            "is_active": True,
            "metadata": {},
        },
    )
    assert upsert.status_code == 200

    # 默认 view=mapped：仅返回映射后的标准模型（不暴露 endpoint/base_url/model_list 等供应商字段）
    mapped = client.get("/api/v1/llm/models", headers={"Authorization": "Bearer mock-jwt-token"})
    assert mapped.status_code == 200
    mapped_items = mapped.json().get("data") or []
    assert any(item.get("name") == mapping_id for item in mapped_items)

    picked = next(item for item in mapped_items if item.get("name") == mapping_id)
    assert "base_url" not in picked
    assert "model_list" not in picked
    assert picked.get("scope_type") == "tenant"
    assert picked.get("scope_key") == "test-mapped"
    assert int(picked.get("candidates_count") or 0) >= 1

    # view=endpoints：管理后台仍可拉取供应商 endpoint 列表
    endpoints = client.get("/api/v1/llm/models?view=endpoints", headers={"Authorization": "Bearer mock-jwt-token"})
    assert endpoints.status_code == 200
    endpoint_items = endpoints.json().get("data") or []
    assert endpoint_items, "expected at least one endpoint (seeded from env or created by tests)"
    assert "id" in endpoint_items[0]

    client.delete(f"/api/v1/llm/model-groups/{mapping_id}", headers=headers)
