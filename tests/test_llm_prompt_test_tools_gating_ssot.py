from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

from app.auth.jwt_verifier import AuthenticatedUser


def _admin_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="test-admin-123",
        claims={
            "sub": "test-admin-123",
            "email": "admin@example.com",
            "iss": "https://test.supabase.co",
            "aud": "test-audience",
            "user_metadata": {"username": "admin", "is_admin": True},
        },
    )


@patch("app.auth.dependencies.get_jwt_verifier")
def test_prompt_test_endpoint_does_not_send_tools_without_tool_choice(mock_get_verifier, client):
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = _admin_user()
    mock_get_verifier.return_value = mock_verifier

    headers = {"Authorization": "Bearer mock-jwt-token"}

    system = client.post(
        "/api/v1/llm/prompts",
        headers=headers,
        json={"name": "system", "content": "SYSTEM_PROMPT", "prompt_type": "system", "is_active": True},
    )
    assert system.status_code == 200
    tools = client.post(
        "/api/v1/llm/prompts",
        headers=headers,
        json={
            "name": "tools",
            "content": "TOOLS_PROMPT",
            "prompt_type": "tools",
            "tools_json": [{"type": "function", "function": {"name": "ping", "description": "ping", "parameters": {}}}],
            "is_active": True,
        },
    )
    assert tools.status_code == 200

    endpoint = client.post(
        "/api/v1/llm/models",
        headers=headers,
        json={
            "name": "prompt-test-endpoint-ssot-1",
            "base_url": "https://example.invalid",
            "provider_protocol": "openai",
            "model": "gpt-4o-mini",
            "api_key": "test-api-key",
            "timeout": 10,
            "is_active": True,
            "is_default": False,
            "model_list": ["gpt-4o-mini"],
            "auto_sync": False,
        },
    )
    assert endpoint.status_code == 200
    endpoint_id = int(endpoint.json()["data"]["id"])

    captured: dict[str, object] = {}

    async def _post(_url, *, headers=None, json=None):  # noqa: ANN001
        captured["payload"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"choices": [{"message": {"content": "ok"}}]})
        return resp

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=_post)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    try:
        with patch("app.services.ai_config_service.httpx.AsyncClient", MagicMock(return_value=mock_ctx)):
            resp = client.post(
                "/api/v1/llm/prompts/test",
                headers=headers,
                json={
                    "prompt_id": int(system.json()["data"]["id"]),
                    "endpoint_id": endpoint_id,
                    "message": "hi",
                    "skip_prompt": False,
                },
            )
            assert resp.status_code == 200
    finally:
        client.delete(f"/api/v1/llm/models/{endpoint_id}", headers=headers)

    payload = captured.get("payload")
    assert isinstance(payload, dict)
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][0]["content"] == "SYSTEM_PROMPT\n\nTOOLS_PROMPT"
    assert "tools" not in payload


@patch("app.auth.dependencies.get_jwt_verifier")
def test_prompt_test_endpoint_sends_tools_when_tool_choice_explicit(mock_get_verifier, client):
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = _admin_user()
    mock_get_verifier.return_value = mock_verifier

    headers = {"Authorization": "Bearer mock-jwt-token"}

    system = client.post(
        "/api/v1/llm/prompts",
        headers=headers,
        json={"name": "system-2", "content": "SYSTEM_PROMPT", "prompt_type": "system", "is_active": True},
    )
    assert system.status_code == 200
    tools = client.post(
        "/api/v1/llm/prompts",
        headers=headers,
        json={
            "name": "tools-2",
            "content": "TOOLS_PROMPT",
            "prompt_type": "tools",
            "tools_json": [{"type": "function", "function": {"name": "ping", "description": "ping", "parameters": {}}}],
            "is_active": True,
        },
    )
    assert tools.status_code == 200

    endpoint = client.post(
        "/api/v1/llm/models",
        headers=headers,
        json={
            "name": "prompt-test-endpoint-ssot-2",
            "base_url": "https://example.invalid",
            "provider_protocol": "openai",
            "model": "gpt-4o-mini",
            "api_key": "test-api-key",
            "timeout": 10,
            "is_active": True,
            "is_default": False,
            "model_list": ["gpt-4o-mini"],
            "auto_sync": False,
        },
    )
    assert endpoint.status_code == 200
    endpoint_id = int(endpoint.json()["data"]["id"])

    captured: dict[str, object] = {}

    async def _post(_url, *, headers=None, json=None):  # noqa: ANN001
        captured["payload"] = json
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json = MagicMock(return_value={"choices": [{"message": {"content": "ok"}}]})
        return resp

    mock_client = MagicMock()
    mock_client.post = AsyncMock(side_effect=_post)
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_client)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)

    try:
        with patch("app.services.ai_config_service.httpx.AsyncClient", MagicMock(return_value=mock_ctx)):
            resp = client.post(
                "/api/v1/llm/prompts/test",
                headers=headers,
                json={
                    "prompt_id": int(system.json()["data"]["id"]),
                    "endpoint_id": endpoint_id,
                    "message": "hi",
                    "skip_prompt": False,
                    "tool_choice": "none",
                },
            )
            assert resp.status_code == 200
    finally:
        client.delete(f"/api/v1/llm/models/{endpoint_id}", headers=headers)

    payload = captured.get("payload")
    assert isinstance(payload, dict)
    assert payload.get("tool_choice") == "none"
    assert isinstance(payload.get("tools"), list)
