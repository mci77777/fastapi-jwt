"""Exercise Library admin patch contracts."""

from __future__ import annotations

from app.api.v1.base import create_test_jwt_token


def _patch_url() -> str:
    return "/api/v1/admin/exercise/library/patch"


class TestExerciseLibraryAdminPatch:
    def test_patch_requires_token(self, client):
        meta = client.get("/api/v1/exercise/library/meta").json()
        resp = client.post(_patch_url(), json={"baseVersion": int(meta["version"]), "updated": []})
        assert resp.status_code == 401

    def test_patch_requires_admin(self, client):
        token = create_test_jwt_token("alice")
        meta = client.get("/api/v1/exercise/library/meta").json()
        resp = client.post(
            _patch_url(),
            headers={"token": token},
            json={"baseVersion": int(meta["version"]), "updated": [{"id": "off_not_exists", "description": "x"}]},
        )
        assert resp.status_code == 403

    def test_patch_version_conflict(self, client):
        token = create_test_jwt_token("admin")
        meta = client.get("/api/v1/exercise/library/meta").json()
        current_version = int(meta["version"])
        resp = client.post(
            _patch_url(),
            headers={"token": token},
            json={"baseVersion": max(1, current_version - 1), "updated": [{"id": "off_not_exists", "description": "x"}]},
        )
        assert resp.status_code == 409

    def test_patch_update_field_level(self, client):
        token = create_test_jwt_token("admin")

        meta = client.get("/api/v1/exercise/library/meta").json()
        base_version = int(meta["version"])

        full = client.get("/api/v1/exercise/library/full").json()
        assert isinstance(full, list) and full
        target = full[0]
        target_id = target["id"]
        new_desc = f"{target.get('description') or ''} patched".strip()

        resp = client.post(
            _patch_url(),
            headers={"token": token},
            json={
                "baseVersion": base_version,
                "updated": [{"id": target_id, "description": new_desc}],
            },
        )
        assert resp.status_code == 200
        meta2 = resp.json()
        assert int(meta2["version"]) == base_version + 1

        full2 = client.get("/api/v1/exercise/library/full").json()
        matched = [item for item in full2 if item.get("id") == target_id]
        assert matched and matched[0].get("description") == new_desc

    def test_patch_add_and_delete(self, client):
        token = create_test_jwt_token("admin")
        meta = client.get("/api/v1/exercise/library/meta").json()
        base_version = int(meta["version"])

        new_item = {
            "id": "off_deadbeef",
            "name": "测试动作（Patch Add）",
            "description": "patch add test",
            "muscleGroup": "CORE",
            "category": "CORE",
            "equipment": ["NONE"],
            "difficulty": "BEGINNER",
            "source": "OFFICIAL",
            "isCustom": False,
            "isOfficial": True,
            "createdAt": 1767398400000,
            "updatedAt": 1767398400000,
        }

        resp = client.post(
            _patch_url(),
            headers={"token": token},
            json={"baseVersion": base_version, "added": [new_item]},
        )
        assert resp.status_code == 200
        meta2 = resp.json()
        assert int(meta2["version"]) == base_version + 1

        full = client.get("/api/v1/exercise/library/full").json()
        assert any(item.get("id") == new_item["id"] for item in full)

        resp2 = client.post(
            _patch_url(),
            headers={"token": token},
            json={"baseVersion": int(meta2["version"]), "deleted": [new_item["id"]]},
        )
        assert resp2.status_code == 200

        full2 = client.get("/api/v1/exercise/library/full").json()
        assert not any(item.get("id") == new_item["id"] for item in full2)

