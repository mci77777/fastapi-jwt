from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

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
def test_llm_prompts_test_accepts_skip_prompt_and_resolves_mapping_key(mock_get_verifier, client):
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = _auth_user()
    mock_get_verifier.return_value = mock_verifier

    headers = {
        "Authorization": "Bearer mock-jwt-token",
        "X-LLM-Admin-Key": "test-llm-admin",
    }

    prompt_resp = client.post(
        "/api/v1/llm/prompts",
        headers=headers,
        json={
            "name": "prompt-test-endpoint",
            "content": "You are a test assistant.",
            "prompt_type": "system",
            "is_active": False,
        },
    )
    assert prompt_resp.status_code == 200
    prompt_id = int(prompt_resp.json()["data"]["id"])

    models_resp = client.get("/api/v1/llm/models", headers=headers)
    assert models_resp.status_code == 200
    endpoints = models_resp.json().get("data") or []
    assert endpoints, "expected at least one endpoint (seeded from env or created by tests)"
    endpoint_id = int(endpoints[0]["id"])

    with (
        patch("app.services.model_mapping_service.ModelMappingService.resolve_model_key", new=AsyncMock(return_value={"hit": True, "resolved_model": "gpt-4o-mini"})),
        patch("app.services.ai_config_service.AIConfigService.test_prompt", new=AsyncMock(return_value={"response": "ok"})) as mock_test_prompt,
    ):
        resp = client.post(
            "/api/v1/llm/prompts/test",
            headers=headers,
            json={
                "prompt_id": prompt_id,
                "endpoint_id": endpoint_id,
                "message": "hi",
                "model": "global:global",
                "skip_prompt": True,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 200
        assert body["data"]["response"] == "ok"

        _, kwargs = mock_test_prompt.await_args
        assert kwargs["model"] == "gpt-4o-mini"
        assert kwargs["skip_prompt"] is True

    client.delete(f"/api/v1/llm/prompts/{prompt_id}", headers=headers)

