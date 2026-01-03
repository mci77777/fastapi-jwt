from __future__ import annotations

from unittest.mock import Mock, patch

from app.auth.jwt_verifier import AuthenticatedUser


def test_llm_models_disallow_test_endpoint_name(client) -> None:
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})

    payload = {
        "name": "test-openai-default",
        "base_url": "https://api.openai.com",
        "api_key": "sk-test",
        "is_default": False,
    }

    # 通过 admin key 过 require_llm_admin（debug=false 下也允许）
    with patch("app.auth.dependencies.get_jwt_verifier", return_value=mock_verifier):
        resp = client.post(
            "/api/v1/llm/models",
            json=payload,
            headers={
                "Authorization": "Bearer test.jwt",
                "X-LLM-Admin-Key": "test-llm-admin",
            },
        )

    assert resp.status_code == 400
    body = resp.json()
    assert body["msg"] == "test_endpoint_name_not_allowed"

