from pathlib import Path

import pytest

from app.services.jwt_test_service import JWTTestService
from app.settings.config import Settings


class FakeAIConfigService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.fail_next = False

    async def test_prompt(self, *, prompt_id: int, endpoint_id: int, message: str, model: str | None = None):
        self.calls.append(
            {
                "prompt_id": prompt_id,
                "endpoint_id": endpoint_id,
                "message": message,
                "model": model,
            }
        )
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("forced_failure")
        return {"latency_ms": 12.3}

    async def list_prompt_tests_by_run(self, run_id: str, limit: int = 1000):
        return [
            {
                "id": 1,
                "prompt_id": 1,
                "endpoint_id": 2,
                "model": "gpt-4o-mini",
                "request_message": f"hello [run_id={run_id} index=0]",
                "response_message": "ok",
                "success": True,
                "latency_ms": 12.3,
                "error": None,
                "created_at": "2025-01-01T00:00:00Z",
            }
        ]


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def settings() -> Settings:
    cfg = Settings()
    cfg.supabase_jwt_secret = "secret"
    cfg.supabase_issuer = "https://example.supabase.co"
    return cfg


@pytest.mark.anyio("asyncio")
async def test_simulate_dialog_success(tmp_path: Path, settings: Settings) -> None:
    ai_service = FakeAIConfigService()
    service = JWTTestService(ai_service, settings, tmp_path)
    response = await service.simulate_dialog(
        {
            "prompt_id": 1,
            "endpoint_id": 2,
            "message": "hello",
            "model": "gpt-4o-mini",
            "username": "tester",
        }
    )
    assert "jwt_token" in response
    assert response["error"] is None
    assert response["result"]["latency_ms"] == 12.3


@pytest.mark.anyio("asyncio")
async def test_run_load_test(tmp_path: Path, settings: Settings) -> None:
    ai_service = FakeAIConfigService()
    service = JWTTestService(ai_service, settings, tmp_path)
    result = await service.run_load_test(
        {
            "prompt_id": 1,
            "endpoint_id": 2,
            "message": "hello",
            "batch_size": 3,
            "concurrency": 2,
            "model": "gpt-4o-mini",
            "stop_on_error": False,
        }
    )
    summary = result["summary"]
    assert summary["success_count"] == 3
    assert summary["failure_count"] == 0
    assert result["tests"]


@pytest.mark.anyio("asyncio")
async def test_run_load_test_stop_on_error(tmp_path: Path, settings: Settings) -> None:
    ai_service = FakeAIConfigService()
    service = JWTTestService(ai_service, settings, tmp_path)
    ai_service.fail_next = True
    result = await service.run_load_test(
        {
            "prompt_id": 1,
            "endpoint_id": 2,
            "message": "hello",
            "batch_size": 3,
            "concurrency": 3,
            "stop_on_error": True,
        }
    )
    summary = result["summary"]
    assert summary["failure_count"] >= 1
    assert summary["status"] in {"partial", "failed"}
    runs_file = tmp_path / "jwt_runs.json"
    assert runs_file.exists()


@pytest.mark.anyio("asyncio")
async def test_get_run_summary(tmp_path: Path, settings: Settings) -> None:
    ai_service = FakeAIConfigService()
    service = JWTTestService(ai_service, settings, tmp_path)
    run = await service.run_load_test(
        {
            "prompt_id": 1,
            "endpoint_id": 2,
            "message": "hello",
            "batch_size": 1,
            "concurrency": 1,
        }
    )
    run_id = run["summary"]["id"]
    stored = await service.get_run(run_id)
    assert stored["summary"]["id"] == run_id
    assert stored["tests"][0]["request_message"].endswith(f"run_id={run_id} index=0]")
