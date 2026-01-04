from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.auth import AuthenticatedUser
from app.auth.provider import get_auth_provider
from app.core.application import create_app
from app.settings.config import get_settings


def _auth_user() -> AuthenticatedUser:
    return AuthenticatedUser(uid="test-user-123", claims={"sub": "test-user-123"})


def test_persistence_and_delete_do_not_rebounce_after_restart(tmp_path: Path) -> None:
    """微E2E：配置可持久化；删除后重启不回弹；禁用 auto-seed 时不会复活 global:global。"""

    keys = [
        "SQLITE_DB_PATH",
        "AI_RUNTIME_STORAGE_DIR",
        "ALLOW_TEST_AI_ENDPOINTS",
        "ENDPOINT_MONITOR_PROBE_ENABLED",
        "SUPABASE_PROVIDER_ENABLED",
        "SUPABASE_KEEPALIVE_ENABLED",
        "RATE_LIMIT_ENABLED",
        "LLM_ADMIN_API_KEY",
        "DEBUG",
        "CORS_ALLOW_ORIGINS",
    ]
    original_env = {key: os.environ.get(key) for key in keys}
    original_cwd = Path.cwd()

    workdir = tmp_path / "workdir"
    workdir.mkdir(parents=True, exist_ok=True)

    db_path = workdir / "data" / "db.sqlite3"
    runtime_dir = workdir / "data" / "ai_runtime"
    legacy_runtime_dir = workdir / "storage" / "ai_runtime"
    legacy_runtime_dir.mkdir(parents=True, exist_ok=True)

    # 准备 legacy 文件（模拟从 storage/ai_runtime 迁移到 data/ai_runtime）
    (legacy_runtime_dir / "model_mappings.json").write_text(
        json.dumps(
            {
                "tenant": {
                    "xai": {
                        "name": "xai",
                        "mapping": {
                            "candidates": ["grok-4"],
                            "default_model": "grok-4",
                            "is_active": True,
                            "updated_at": "2026-01-01T00:00:00+00:00",
                            "metadata": {"source": "legacy_seed"},
                        },
                    }
                }
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    try:
        os.chdir(workdir)

        os.environ["SQLITE_DB_PATH"] = str(db_path)
        os.environ["AI_RUNTIME_STORAGE_DIR"] = str(runtime_dir)
        os.environ["ALLOW_TEST_AI_ENDPOINTS"] = "false"
        os.environ["ENDPOINT_MONITOR_PROBE_ENABLED"] = "false"
        os.environ["SUPABASE_PROVIDER_ENABLED"] = "false"
        os.environ["SUPABASE_KEEPALIVE_ENABLED"] = "false"
        os.environ["RATE_LIMIT_ENABLED"] = "false"
        os.environ["LLM_ADMIN_API_KEY"] = "test-llm-admin"
        os.environ["DEBUG"] = "false"
        os.environ["CORS_ALLOW_ORIGINS"] = "*"

        get_settings.cache_clear()
        get_auth_provider.cache_clear()

        admin_headers = {"Authorization": "Bearer mock", "X-LLM-Admin-Key": "test-llm-admin"}
        user_headers = {"Authorization": "Bearer mock"}

        created_endpoint_id: int | None = None

        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = Mock()
            mock_verifier.verify_token.return_value = _auth_user()
            mock_get_verifier.return_value = mock_verifier

            # 1) 第一次启动：触发 legacy→data 迁移，并创建一个 endpoint
            app1 = create_app()
            with TestClient(app1) as client:
                assert (runtime_dir / ".legacy_import_done").exists()
                assert (runtime_dir / "model_mappings.json").exists()

                mappings = client.get("/api/v1/llm/model-groups", headers=user_headers)
                assert mappings.status_code == 200
                mapping_items = mappings.json().get("data") or []
                assert any(item.get("id") == "tenant:xai" for item in mapping_items)

                created = client.post(
                    "/api/v1/llm/models",
                    headers=admin_headers,
                    json={
                        "name": "persist-endpoint",
                        "base_url": "https://api.openai.com",
                        "api_key": "sk-test",
                        "model": "gpt-4o-mini",
                        "model_list": ["gpt-4o-mini"],
                        "is_active": True,
                        "is_default": True,
                    },
                )
                assert created.status_code == 200
                created_endpoint_id = int((created.json().get("data") or {}).get("id"))

            # 2) 第二次启动：验证持久化（endpoint + mapping 仍存在），随后删除并移除 runtime 文件
            app2 = create_app()
            with TestClient(app2) as client:
                endpoints = client.get("/api/v1/llm/models?view=endpoints", headers=admin_headers)
                assert endpoints.status_code == 200
                endpoint_items = endpoints.json().get("data") or []
                assert any(int(item.get("id")) == created_endpoint_id for item in endpoint_items)

                mappings = client.get("/api/v1/llm/model-groups", headers=user_headers)
                assert mappings.status_code == 200
                mapping_items = mappings.json().get("data") or []
                assert any(item.get("id") == "tenant:xai" for item in mapping_items)

                deleted_mapping = client.delete("/api/v1/llm/model-groups/tenant:xai", headers=admin_headers)
                assert deleted_mapping.status_code == 200
                assert (deleted_mapping.json().get("data") or {}).get("deleted") is True

                deleted_endpoint = client.delete(f"/api/v1/llm/models/{created_endpoint_id}", headers=admin_headers)
                assert deleted_endpoint.status_code == 200

                # 模拟“用户清理运行态目录文件”后重启：不应从 legacy 回弹
                try:
                    (runtime_dir / "model_mappings.json").unlink()
                except FileNotFoundError:
                    pass

            # 3) 第三次启动：验证删除不回弹；并且 global:global 不会因为 auto-seed 而复活
            app3 = create_app()
            with TestClient(app3) as client:
                endpoints = client.get("/api/v1/llm/models?view=endpoints", headers=admin_headers)
                assert endpoints.status_code == 200
                assert (endpoints.json().get("data") or []) == []

                mappings = client.get("/api/v1/llm/model-groups", headers=user_headers)
                assert mappings.status_code == 200
                assert (mappings.json().get("data") or []) == []

                mapped = client.get("/api/v1/llm/models", headers=user_headers)
                assert mapped.status_code == 200
                assert (mapped.json().get("data") or []) == []

                rejected = client.post(
                    "/api/v1/messages",
                    headers=user_headers,
                    json={"text": "hi", "model": "global:global"},
                )
                assert rejected.status_code == 422
    finally:
        os.chdir(original_cwd)
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()
        get_auth_provider.cache_clear()
