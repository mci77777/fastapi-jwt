from __future__ import annotations

from app.services.url_rewrite import rewrite_localhost_for_docker


def test_rewrite_localhost_for_docker_noop_when_not_in_docker(monkeypatch):
    monkeypatch.delenv("FORCE_DOCKER_LOCALHOST_REWRITE", raising=False)
    assert rewrite_localhost_for_docker("http://localhost:8317") == "http://localhost:8317"


def test_rewrite_localhost_for_docker_rewrites_when_forced(monkeypatch):
    monkeypatch.setenv("FORCE_DOCKER_LOCALHOST_REWRITE", "1")
    assert rewrite_localhost_for_docker("http://localhost:8317") == "http://host.docker.internal:8317"


def test_rewrite_localhost_for_docker_keeps_non_localhost(monkeypatch):
    monkeypatch.setenv("FORCE_DOCKER_LOCALHOST_REWRITE", "1")
    assert rewrite_localhost_for_docker("http://example.com:8317") == "http://example.com:8317"
