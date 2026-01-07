from __future__ import annotations

from unittest.mock import Mock, patch

from app.auth.jwt_verifier import AuthenticatedUser


def _auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(uid="test-user-123", claims={"user_metadata": {"username": "admin", "is_admin": True}})


@patch("app.auth.dependencies.get_jwt_verifier")
def test_llm_models_check_all_returns_202_and_triggers_probe(mock_get_verifier, client) -> None:
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = _auth_user()
    mock_get_verifier.return_value = mock_verifier

    headers = {"Authorization": "Bearer mock-jwt-token"}

    with patch("app.services.monitor_service.EndpointMonitor.trigger_probe") as mock_trigger:
        resp = client.post("/api/v1/llm/models/check-all", headers=headers)

    assert resp.status_code == 202
    body = resp.json()
    assert body["code"] == 202
    assert body["msg"]
    mock_trigger.assert_called_once()


@patch("app.auth.dependencies.get_jwt_verifier")
def test_llm_models_check_all_get_returns_202_and_triggers_probe(mock_get_verifier, client) -> None:
    mock_verifier = Mock()
    mock_verifier.verify_token.return_value = _auth_user()
    mock_get_verifier.return_value = mock_verifier

    headers = {"Authorization": "Bearer mock-jwt-token"}

    with patch("app.services.monitor_service.EndpointMonitor.trigger_probe") as mock_trigger:
        resp = client.get("/api/v1/llm/models/check-all", headers=headers)

    assert resp.status_code == 202
    body = resp.json()
    assert body["code"] == 202
    assert body["msg"]
    mock_trigger.assert_called_once()
