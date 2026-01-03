"""Exercise Library admin publish contracts."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from app.api.v1.base import create_test_jwt_token


def _load_seed_envelope() -> dict:
    raw = json.loads(Path("assets/exercise/exercise_official_seed.json").read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError("seed envelope must be an object")
    return raw


def _mutate_envelope(envelope: dict, *, marker: str, entity_version: int) -> dict:
    mutated = copy.deepcopy(envelope)
    payload = mutated.get("payload")
    if not isinstance(payload, list) or not payload:
        raise RuntimeError("seed payload missing")
    payload[0]["description"] = f'{payload[0].get("description") or ""} {marker}'.strip()
    payload[0]["updatedAt"] = int(payload[0]["updatedAt"]) + 1
    mutated["entityVersion"] = int(entity_version)
    mutated["totalCount"] = len(payload)
    if mutated.get("generatedAt") is not None:
        mutated["generatedAt"] = int(mutated["generatedAt"]) + 1
    return mutated


class TestExerciseLibraryAdminPublish:
    def test_publish_requires_token(self, client):
        payload = _mutate_envelope(_load_seed_envelope(), marker="no-token", entity_version=1)
        resp = client.post("/api/v1/admin/exercise/library/publish", json=payload)
        assert resp.status_code == 401

    def test_publish_requires_admin(self, client):
        token = create_test_jwt_token("alice")
        payload = _mutate_envelope(_load_seed_envelope(), marker="non-admin", entity_version=1)
        resp = client.post("/api/v1/admin/exercise/library/publish", headers={"token": token}, json=payload)
        assert resp.status_code == 403

    def test_publish_increments_version(self, client):
        # 基线：先确保已有一个可比对的当前版本（必要时会从内置 seed 发布 v1）
        initial_meta = client.get("/api/v1/exercise/library/meta").json()
        initial_version = int(initial_meta["version"])

        token = create_test_jwt_token("admin")
        payload_v_next = _mutate_envelope(
            _load_seed_envelope(),
            marker="v-next-1",
            entity_version=initial_version + 1,
        )

        resp = client.post("/api/v1/admin/exercise/library/publish", headers={"token": token}, json=payload_v_next)
        assert resp.status_code == 200
        meta = resp.json()
        assert int(meta["version"]) == initial_version + 1
        assert "lastUpdated" in meta
        assert "totalCount" in meta
        assert "checksum" in meta

        resp2 = client.post(
            "/api/v1/admin/exercise/library/publish",
            headers={"token": token},
            json=_mutate_envelope(payload_v_next, marker="v-next-2", entity_version=initial_version + 2),
        )
        assert resp2.status_code == 200
        meta2 = resp2.json()
        assert int(meta2["version"]) == initial_version + 2

        latest_meta = client.get("/api/v1/exercise/library/meta").json()
        assert int(latest_meta["version"]) == initial_version + 2
