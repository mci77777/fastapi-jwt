from __future__ import annotations

from app.services.upstream_auth import is_retryable_auth_error, iter_auth_headers, should_send_x_api_key


def test_should_send_x_api_key_for_private_ip() -> None:
    assert should_send_x_api_key("http://172.19.32.1:8317/v1/models") is True


def test_should_send_x_api_key_for_localhost() -> None:
    assert should_send_x_api_key("http://localhost:8317/v1/models") is True


def test_should_send_x_api_key_for_public_host() -> None:
    assert should_send_x_api_key("https://api.openai.com/v1/models") is False


def test_iter_auth_headers_public_prefers_bearer_only() -> None:
    headers = iter_auth_headers("key123", "https://api.openai.com/v1/models")
    assert headers == [{"Authorization": "Bearer key123"}]


def test_iter_auth_headers_private_includes_x_api_key_and_raw_authorization() -> None:
    headers = iter_auth_headers("key123", "http://172.19.32.1:8317/v1/models")
    assert headers == [
        {"Authorization": "Bearer key123"},
        {"X-API-Key": "key123"},
        {"Authorization": "key123"},
    ]


def test_is_retryable_auth_error_only_when_api_key_hint_present() -> None:
    assert is_retryable_auth_error(401, {"error": "Missing API key"}) is True
    assert is_retryable_auth_error(401, {"message": "Invalid APIKey"}) is True
    assert is_retryable_auth_error(401, {"detail": "Unauthorized"}) is False
    assert is_retryable_auth_error(403, {"error": "Missing API key"}) is False
    assert is_retryable_auth_error(401, "Missing API key") is False
