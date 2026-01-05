from __future__ import annotations

from app.services.upstream_auth import should_send_x_api_key


def test_should_send_x_api_key_for_private_ip() -> None:
    assert should_send_x_api_key("http://172.19.32.1:8317/v1/models") is True


def test_should_send_x_api_key_for_localhost() -> None:
    assert should_send_x_api_key("http://localhost:8317/v1/models") is True


def test_should_send_x_api_key_for_public_host() -> None:
    assert should_send_x_api_key("https://api.openai.com/v1/models") is False

