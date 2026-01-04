from __future__ import annotations

from app.api.v1.base import create_test_jwt_token


class TestLLMBlockedModels:
    def test_blocked_models_admin_only_write(self, client):
        user_token = create_test_jwt_token("alice")
        resp = client.put(
            "/api/v1/llm/models/blocked",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"updates": [{"model": "test-blocked-model", "blocked": True}]},
        )
        assert resp.status_code == 403

        admin_token = create_test_jwt_token("admin")
        resp2 = client.put(
            "/api/v1/llm/models/blocked",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"updates": [{"model": "test-blocked-model", "blocked": True}]},
        )
        assert resp2.status_code == 200
        payload = resp2.json()
        assert payload["code"] == 200
        assert "test-blocked-model" in payload["data"]["blocked"]

        # cleanup: unblock
        client.put(
            "/api/v1/llm/models/blocked",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"updates": [{"model": "test-blocked-model", "blocked": False}]},
        )

    def test_app_models_debug_reflects_blocked(self, client):
        admin_token = create_test_jwt_token("admin")
        special = "test-blocked-model-app"
        admin_headers = {
            "Authorization": f"Bearer {admin_token}",
            "X-LLM-Admin-Key": "test-llm-admin",
        }

        # 创建一个支持 special 的默认端点（否则白名单解析会自动回退到可用候选）
        created_endpoint_id = None
        created = client.post(
            "/api/v1/llm/models",
            headers=admin_headers,
            json={
                "name": "blocked-model-endpoint",
                "base_url": "https://api.openai.com",
                "api_key": "sk-test",
                "model": special,
                "model_list": [special, "gpt-4o-mini"],
                "is_active": True,
                "is_default": True,
            },
        )
        assert created.status_code == 200
        created_endpoint_id = (created.json().get("data") or {}).get("id")

        # 设置 global 映射：默认=特殊模型，候选含一个备用模型
        resp = client.post(
            "/api/v1/llm/model-groups",
            headers=admin_headers,
            json={
                "scope_type": "global",
                "scope_key": "global",
                "name": "Default",
                "default_model": special,
                "candidates": [special, "gpt-4o-mini"],
                "is_active": True,
                "metadata": {},
            },
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 200

        # 未屏蔽：resolved_model 应为 default
        before = client.get(
            "/api/v1/llm/app/models?debug=true",
            headers=admin_headers,
        )
        assert before.status_code == 200
        before_payload = before.json()
        assert before_payload["code"] == 200
        global_item = next(item for item in before_payload["data"] if item.get("scope_type") == "global")
        assert global_item.get("resolved_model") == special

        # 屏蔽 default：应回退到候选模型
        block = client.put(
            "/api/v1/llm/models/blocked",
            headers=admin_headers,
            json={"updates": [{"model": special, "blocked": True}]},
        )
        assert block.status_code == 200

        after = client.get(
            "/api/v1/llm/app/models?debug=true",
            headers=admin_headers,
        )
        assert after.status_code == 200
        after_payload = after.json()
        global_item_after = next(item for item in after_payload["data"] if item.get("scope_type") == "global")
        assert global_item_after.get("resolved_model") == "gpt-4o-mini"
        assert special in (global_item_after.get("blocked_candidates") or [])

        # cleanup
        client.put(
            "/api/v1/llm/models/blocked",
            headers=admin_headers,
            json={"updates": [{"model": special, "blocked": False}]},
        )
        client.delete("/api/v1/llm/model-groups/global:global", headers=admin_headers)
        if created_endpoint_id is not None:
            client.delete(f"/api/v1/llm/models/{created_endpoint_id}", headers=admin_headers)
