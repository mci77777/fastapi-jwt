from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app import app as fastapi_app
from app.auth import AuthenticatedUser, ProviderError
from app.db.sqlite_manager import get_sqlite_manager


@pytest.mark.asyncio
async def test_dashboard_stats_includes_mapped_models(async_client) -> None:
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = mock_get_verifier.return_value
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={}, user_type="permanent")

        resp = await async_client.get("/api/v1/stats/dashboard", headers={"Authorization": "Bearer mock.supabase.jwt"})
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("code") == 200
        data = body.get("data") or {}
        assert isinstance(data.get("mapped_models"), dict)
        assert isinstance(data.get("e2e_mapped_models"), dict)


@pytest.mark.asyncio
async def test_mapped_models_stats_returns_availability_and_usage(async_client, monkeypatch) -> None:
    today = datetime.now().date().isoformat()
    db = get_sqlite_manager(fastapi_app)

    await db.execute(
        """
        INSERT INTO llm_model_mappings
        (id, scope_type, scope_key, name, default_model, candidates_json, is_active, updated_at, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
          scope_type = excluded.scope_type,
          scope_key = excluded.scope_key,
          name = excluded.name,
          default_model = excluded.default_model,
          candidates_json = excluded.candidates_json,
          is_active = excluded.is_active,
          updated_at = excluded.updated_at,
          metadata_json = excluded.metadata_json
        """,
        (
            "mapping:broken",
            "mapping",
            "broken",
            "broken",
            "does-not-matter",
            json.dumps(["does-not-matter"], ensure_ascii=False),
            today + "T00:00:00Z",
            json.dumps({}, ensure_ascii=False),
        ),
    )

    await db.execute(
        """
        INSERT INTO ai_request_stats
        (user_id, endpoint_id, model, request_date, count, total_latency_ms, success_count, error_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, endpoint_id, model, request_date)
        DO UPDATE SET
          count = excluded.count,
          total_latency_ms = excluded.total_latency_ms,
          success_count = excluded.success_count,
          error_count = excluded.error_count,
          updated_at = CURRENT_TIMESTAMP
        """,
        ("u1", 1, "broken", today, 3, 300.0, 2, 1),
    )
    await db.execute(
        """
        INSERT INTO ai_request_stats
        (user_id, endpoint_id, model, request_date, count, total_latency_ms, success_count, error_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, endpoint_id, model, request_date)
        DO UPDATE SET
          count = excluded.count,
          total_latency_ms = excluded.total_latency_ms,
          success_count = excluded.success_count,
          error_count = excluded.error_count,
          updated_at = CURRENT_TIMESTAMP
        """,
        ("u2", 1, "broken", today, 1, 120.0, 1, 0),
    )

    registry = fastapi_app.state.llm_model_registry
    original_resolve = registry.resolve_model_key

    async def _fake_resolve(model_key: str, **kwargs):
        if model_key == "broken":
            raise ProviderError("no_active_ai_endpoint")
        return await original_resolve(model_key, **kwargs)

    monkeypatch.setattr(registry, "resolve_model_key", _fake_resolve)

    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = mock_get_verifier.return_value
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={}, user_type="permanent")

        resp = await async_client.get(
            "/api/v1/stats/mapped-models",
            params={"time_window": "24h"},
            headers={"Authorization": "Bearer mock.supabase.jwt"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("time_window") == "24h"
        assert isinstance(body.get("rows"), list)

        broken = next((row for row in body["rows"] if row.get("model_key") == "broken"), None)
        assert broken is not None
        assert broken["availability"] is False
        assert broken["availability_reason"] == "no_active_ai_endpoint"
        assert broken["calls_total"] == 4
        assert broken["unique_users"] == 2
        assert broken["success_rate"] == 75.0
        assert broken["avg_latency_ms"] == 105.0


@pytest.mark.asyncio
async def test_mapped_models_stats_rejects_1h_time_window(async_client) -> None:
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = mock_get_verifier.return_value
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={}, user_type="permanent")

        resp = await async_client.get(
            "/api/v1/stats/mapped-models",
            params={"time_window": "1h"},
            headers={"Authorization": "Bearer mock.supabase.jwt"},
        )

        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_e2e_mapped_models_stats_returns_latest(async_client) -> None:
    db = get_sqlite_manager(fastapi_app)
    now = datetime.now().replace(microsecond=0).isoformat()
    results_json = json.dumps(
        [
            {"model_key": "xai", "success": True, "latency_ms": 120.0, "request_id": "r1"},
            {"model_key": "deepseek", "success": False, "latency_ms": 80.0, "request_id": "r2", "error": "failed"},
        ],
        ensure_ascii=False,
    )

    await db.execute(
        """
        INSERT INTO e2e_mapped_model_runs
        (run_id, user_type, auth_mode, prompt_text, prompt_mode, result_mode,
         models_total, models_success, models_failed, started_at, finished_at,
         duration_ms, status, error_summary, results_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "run-anon-1",
            "anonymous",
            "edge",
            "hello",
            "server",
            "xml_plaintext",
            2,
            1,
            1,
            now,
            now,
            200.0,
            "failed",
            "partial_fail",
            results_json,
        ),
    )

    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = mock_get_verifier.return_value
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={}, user_type="permanent")

        resp = await async_client.get(
            "/api/v1/stats/e2e-mapped-models",
            headers={"Authorization": "Bearer mock.supabase.jwt"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("code") == 200
        data = body.get("data") or {}
        latest = data.get("latest") or {}
        anon = latest.get("anonymous") or {}
        assert anon.get("models_total") == 2
        assert anon.get("models_success") == 1
        assert anon.get("models_failed") == 1
        items = anon.get("results") or []
        assert isinstance(items, list)
        assert items[0].get("model_key") == "xai"


@pytest.mark.asyncio
async def test_e2e_mapped_model_runs_returns_paginated(async_client) -> None:
    db = get_sqlite_manager(fastapi_app)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    within_30d = now - timedelta(days=2)
    too_old = now - timedelta(days=31)

    results_json = json.dumps(
        [
            {"model_key": "xai", "success": True, "latency_ms": 120.0, "request_id": "r1", "thinkingml_ok": True},
            {"model_key": "deepseek", "success": False, "latency_ms": 80.0, "request_id": "r2", "error": "failed"},
        ],
        ensure_ascii=False,
    )

    await db.execute(
        """
        INSERT INTO e2e_mapped_model_runs
        (run_id, user_type, auth_mode, prompt_text, prompt_mode, result_mode,
         models_total, models_success, models_failed, started_at, finished_at,
         duration_ms, status, error_summary, results_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "run-recent-1",
            "permanent",
            "password",
            "hello",
            "server",
            "xml_plaintext",
            2,
            1,
            1,
            within_30d.isoformat(),
            within_30d.isoformat(),
            200.0,
            "failed",
            "partial_fail",
            results_json,
            within_30d.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )

    await db.execute(
        """
        INSERT INTO e2e_mapped_model_runs
        (run_id, user_type, auth_mode, prompt_text, prompt_mode, result_mode,
         models_total, models_success, models_failed, started_at, finished_at,
         duration_ms, status, error_summary, results_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "run-too-old",
            "permanent",
            "password",
            "hello",
            "server",
            "xml_plaintext",
            2,
            2,
            0,
            too_old.isoformat(),
            too_old.isoformat(),
            100.0,
            "success",
            "",
            results_json,
            too_old.strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )

    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = mock_get_verifier.return_value
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={}, user_type="permanent")

        resp = await async_client.get(
            "/api/v1/stats/e2e-mapped-model-runs",
            params={"user_type": "permanent", "time_window": "30d", "limit": 10, "offset": 0},
            headers={"Authorization": "Bearer mock.supabase.jwt"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("code") == 200
        data = body.get("data") or {}
        assert data.get("user_type") == "permanent"
        assert data.get("time_window") == "30d"
        assert data.get("total") == 1

        runs = data.get("runs") or []
        assert isinstance(runs, list)
        assert len(runs) == 1
        assert runs[0].get("run_id") == "run-recent-1"
        items = runs[0].get("results") or []
        assert isinstance(items, list)
        assert items[0].get("model_key") == "xai"


@pytest.mark.asyncio
async def test_dashboard_config_includes_e2e_interval_hours(async_client) -> None:
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = mock_get_verifier.return_value
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={}, user_type="permanent")

        resp = await async_client.get("/api/v1/stats/config", headers={"Authorization": "Bearer mock.supabase.jwt"})
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("code") == 200
        config = (body.get("data") or {}).get("config") or {}
        assert int(config.get("e2e_interval_hours") or 0) == 24


@pytest.mark.asyncio
async def test_dashboard_config_can_update_e2e_interval_hours(async_client) -> None:
    with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
        mock_verifier = mock_get_verifier.return_value
        mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={}, user_type="permanent")

        updated = await async_client.put(
            "/api/v1/stats/config",
            headers={"Authorization": "Bearer mock.supabase.jwt"},
            json={
                "websocket_push_interval": 10,
                "http_poll_interval": 30,
                "log_retention_size": 100,
                "e2e_interval_hours": 6,
                "e2e_daily_time": "05:00",
                "e2e_prompt_text": "hello",
            },
        )
        assert updated.status_code == 200
        body = updated.json()
        assert body.get("code") == 200
        config = (body.get("data") or {}).get("config") or {}
        assert int(config.get("e2e_interval_hours") or 0) == 6
