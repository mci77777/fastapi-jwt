"""Seed manifest + file download contracts."""

from __future__ import annotations


class TestSeedManifestContracts:
    def test_seed_manifest_contract(self, client):
        resp = client.get("/api/v1/seed/manifest")
        assert resp.status_code == 200
        data = resp.json()
        assert data["channel"] == "stable"
        assert isinstance(data["updated_at"], int)
        assert isinstance(data.get("resources"), list)
        assert data["resources"]

        resource = data["resources"][0]
        assert resource["name"] == "exercise_library"
        assert isinstance(resource["version"], int)
        assert isinstance(resource["checksum"], str)
        assert isinstance(resource["etag"], str)
        assert isinstance(resource["download_url"], str)
        assert isinstance(resource["update_strategy"], dict)

    def test_seed_manifest_etag_not_modified(self, client):
        first = client.get("/api/v1/seed/manifest")
        assert first.status_code == 200
        etag = first.headers.get("ETag")
        assert etag

        second = client.get("/api/v1/seed/manifest", headers={"If-None-Match": etag})
        assert second.status_code == 304

    def test_seed_file_download_etag_not_modified(self, client):
        meta = client.get("/api/v1/exercise/library/meta").json()
        version = meta["version"]

        first = client.get(f"/api/v1/seed/files/exercise_library?version={version}")
        assert first.status_code == 200
        etag = first.headers.get("ETag")
        assert etag

        second = client.get(
            f"/api/v1/seed/files/exercise_library?version={version}",
            headers={"If-None-Match": etag},
        )
        assert second.status_code == 304

