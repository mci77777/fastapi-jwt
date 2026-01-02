"""LLM Prompts API 契约与兼容性测试。"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app.auth.jwt_verifier import AuthenticatedUser


@pytest.fixture
def mock_auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        uid="test-user-123",
        claims={
            "sub": "test-user-123",
            "email": "test@example.com",
            "iss": "https://test.supabase.co",
            "aud": "test-audience",
        },
    )


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer mock-jwt-token"}


@patch("app.auth.dependencies.get_jwt_verifier")
def test_create_prompt_accepts_system_prompt_alias(mock_get_verifier, client, mock_auth_user, auth_headers):
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = mock_auth_user
    mock_get_verifier.return_value = mock_verifier

    response = client.post(
        "/api/v1/llm/prompts",
        headers=auth_headers,
        json={"name": "compat-system-prompt", "system_prompt": "你是一个测试助手", "is_active": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200

    prompt = body["data"]
    assert prompt["content"] == "你是一个测试助手"
    assert prompt["system_prompt"] == "你是一个测试助手"

    # 清理
    prompt_id = prompt.get("id")
    if prompt_id:
        client.delete(f"/api/v1/llm/prompts/{prompt_id}", headers=auth_headers)


@patch("app.auth.dependencies.get_jwt_verifier")
def test_create_prompt_rejects_conflicting_content_and_system_prompt(mock_get_verifier, client, mock_auth_user, auth_headers):
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = mock_auth_user
    mock_get_verifier.return_value = mock_verifier

    response = client.post(
        "/api/v1/llm/prompts",
        headers=auth_headers,
        json={"name": "conflict", "content": "a", "system_prompt": "b"},
    )
    assert response.status_code == 422


@patch("app.auth.dependencies.get_jwt_verifier")
def test_create_prompt_accepts_tools_alias(mock_get_verifier, client, mock_auth_user, auth_headers):
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = mock_auth_user
    mock_get_verifier.return_value = mock_verifier

    tools = [{"type": "function", "function": {"name": "ping", "description": "ping", "parameters": {}}}]
    response = client.post(
        "/api/v1/llm/prompts",
        headers=auth_headers,
        json={"name": "compat-tools", "content": "hello", "tools": tools},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200

    prompt = body["data"]
    assert prompt["tools_json"] == tools
    assert prompt["tools"] == tools

    prompt_id = prompt.get("id")
    if prompt_id:
        client.delete(f"/api/v1/llm/prompts/{prompt_id}", headers=auth_headers)

