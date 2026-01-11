from __future__ import annotations

import json
from datetime import datetime
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
