"""LLM Prompts：System/Tools Prompt 可分别激活（双激活）。"""

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
def test_system_and_tools_prompts_can_be_active_together(mock_get_verifier, client, mock_auth_user, auth_headers):
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = mock_auth_user
    mock_get_verifier.return_value = mock_verifier

    created_ids: list[int] = []

    # 1) 创建 system prompt（无 tools_json）
    resp_system = client.post(
        "/api/v1/llm/prompts",
        headers=auth_headers,
        json={"name": "sys", "content": "system", "is_active": False},
    )
    assert resp_system.status_code == 200
    sys_id = int(resp_system.json()["data"]["id"])
    created_ids.append(sys_id)

    # 2) 创建 tools prompt（带 tools_json）
    tools = [{"type": "function", "function": {"name": "ping", "description": "ping", "parameters": {}}}]
    resp_tools = client.post(
        "/api/v1/llm/prompts",
        headers=auth_headers,
        json={"name": "tools", "content": "tools", "tools_json": tools, "is_active": False},
    )
    assert resp_tools.status_code == 200
    tools_id = int(resp_tools.json()["data"]["id"])
    created_ids.append(tools_id)

    # 3) 分别激活两条
    assert client.post(f"/api/v1/llm/prompts/{sys_id}/activate", headers=auth_headers).status_code == 200
    assert client.post(f"/api/v1/llm/prompts/{tools_id}/activate", headers=auth_headers).status_code == 200

    # 4) 验证同时处于 active（各自类型内唯一 active）
    resp_active = client.get("/api/v1/llm/prompts", headers=auth_headers, params={"only_active": True, "page_size": 50})
    assert resp_active.status_code == 200
    items = resp_active.json()["data"] or []

    active_system = [p for p in items if p.get("prompt_type") == "system" and p.get("is_active")]
    active_tools = [p for p in items if p.get("prompt_type") == "tools" and p.get("is_active")]
    assert len(active_system) == 1
    assert len(active_tools) == 1
    assert active_system[0]["id"] == sys_id
    assert active_tools[0]["id"] == tools_id

    # 清理
    for pid in created_ids:
        client.delete(f"/api/v1/llm/prompts/{pid}", headers=auth_headers)

