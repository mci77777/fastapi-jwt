"""Exercise Library seed sync contracts."""

from __future__ import annotations


class TestExerciseLibraryContracts:
    def test_meta_contract(self, client):
        resp = client.get("/api/v1/exercise/library/meta")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) <= {"version", "totalCount", "lastUpdated", "checksum", "downloadUrl"}
        assert isinstance(data["version"], int)
        assert data["version"] >= 1
        assert isinstance(data["totalCount"], int)
        assert isinstance(data["lastUpdated"], int)
        assert isinstance(data["checksum"], str)

    def test_meta_etag_not_modified(self, client):
        first = client.get("/api/v1/exercise/library/meta")
        assert first.status_code == 200
        etag = first.headers.get("ETag")
        assert etag
        second = client.get("/api/v1/exercise/library/meta", headers={"If-None-Match": etag})
        assert second.status_code == 304

    def test_full_contract(self, client):
        resp = client.get("/api/v1/exercise/library/full")
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        assert len(items) > 0
        sample = items[0]
        for key in (
            "id",
            "name",
            "description",
            "muscleGroup",
            "category",
            "equipment",
            "difficulty",
            "source",
            "isCustom",
            "isOfficial",
            "createdAt",
            "updatedAt",
        ):
            assert key in sample

        assert isinstance(sample["id"], str)
        assert isinstance(sample["equipment"], list)
        assert isinstance(sample["isCustom"], bool)

    def test_full_supports_version_query_and_etag(self, client):
        meta = client.get("/api/v1/exercise/library/meta").json()
        version = meta["version"]

        first = client.get(f"/api/v1/exercise/library/full?version={version}")
        assert first.status_code == 200
        etag = first.headers.get("ETag")
        assert etag

        second = client.get(f"/api/v1/exercise/library/full?version={version}", headers={"If-None-Match": etag})
        assert second.status_code == 304

    def test_updates_contract_from_zero(self, client):
        meta = client.get("/api/v1/exercise/library/meta").json()
        version = meta["version"]

        resp = client.get(f"/api/v1/exercise/library/updates?from=0&to={version}")
        assert resp.status_code == 200
        data = resp.json()
        assert set(data.keys()) == {"fromVersion", "toVersion", "added", "updated", "deleted", "timestamp"}
        assert int(data["fromVersion"]) == 0
        assert int(data["toVersion"]) == int(version)
        assert isinstance(data["timestamp"], int)
        assert isinstance(data["added"], list)
        assert isinstance(data["updated"], list)
        assert isinstance(data["deleted"], list)
        assert all(isinstance(item, str) for item in data["deleted"])

        added_ids = {item["id"] for item in data["added"]}
        updated_ids = {item["id"] for item in data["updated"]}
        deleted_ids = set(data["deleted"])
        assert added_ids.isdisjoint(updated_ids)
        assert added_ids.isdisjoint(deleted_ids)
        assert updated_ids.isdisjoint(deleted_ids)

    def test_updates_invalid_range(self, client):
        resp = client.get("/api/v1/exercise/library/updates?from=2&to=1")
        assert resp.status_code == 400
