from __future__ import annotations

import asyncio
import json
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app import app as fastapi_app
from app.auth import AuthenticatedUser
from app.db.sqlite_manager import get_sqlite_manager


def _mock_httpx_stream_json(mock_httpx: MagicMock, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> None:
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    if headers:
        response.headers.update(headers)
    response.raise_for_status = MagicMock()
    response.aread = AsyncMock(return_value=json.dumps(payload).encode("utf-8"))

    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=response)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_httpx.return_value.__aenter__.return_value.stream = MagicMock(return_value=stream_ctx)


async def _collect_sse_events(
    client: AsyncClient,
    url: str,
    headers: dict[str, str],
    *,
    max_events: int = 80,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    async with client.stream("GET", url, headers=headers, timeout=5.0) as response:
        assert response.status_code == status.HTTP_200_OK

        current_event = "message"
        data_lines: list[str] = []

        async def flush() -> None:
            nonlocal current_event, data_lines
            if not data_lines:
                current_event = "message"
                return
            raw = "\n".join(data_lines)
            data_lines = []
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw
            events.append({"event": current_event, "data": parsed})
            current_event = "message"

        lines_iter = response.aiter_lines()
        for _ in range(max_events * 6):
            try:
                line = await asyncio.wait_for(lines_iter.__anext__(), timeout=2.0)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                break

            if line is None:
                break
            line = line.rstrip("\r")
            if not line:
                await flush()
                if events and events[-1]["event"] in {"completed", "error"}:
                    break
                continue

            if line.startswith("event:"):
                current_event = line[len("event:") :].strip() or "message"
                continue
            if line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())

        await flush()

    return events


class TestAgentRunsMicroE2E:
    @pytest.mark.asyncio
    async def test_agent_runs_to_sse_includes_tool_events(self, async_client: AsyncClient, mock_jwt_token: str):
        created_endpoint_id = None
        mapping_id = "mapping:deepseek-agent"

        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-agent-001", claims={})
            mock_get_verifier.return_value = mock_verifier

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_httpx:
                endpoint = await fastapi_app.state.ai_config_service.create_endpoint(
                    {
                        "name": "deepseek-default",
                        "base_url": "https://api.deepseek.com",
                        "api_key": "test-api-key",
                        "is_active": True,
                        "is_default": False,
                        "model_list": ["deepseek-chat"],
                    }
                )
                created_endpoint_id = endpoint.get("id")

                await fastapi_app.state.model_mapping_service.upsert_mapping(
                    {
                        "scope_type": "mapping",
                        "scope_key": "deepseek-agent",
                        "name": "deepseek-agent",
                        "default_model": "deepseek-chat",
                        "candidates": ["deepseek-chat"],
                        "is_active": True,
                        "metadata": {},
                    }
                )

                _mock_httpx_stream_json(
                    mock_httpx,
                    {"choices": [{"message": {"content": "Hello from agent."}}]},
                    headers={"x-request-id": "upstream-rid"},
                )

                try:
                    create = await async_client.post(
                        "/api/v1/agent/runs",
                        headers={
                            "Authorization": f"Bearer {mock_jwt_token}",
                            "X-Request-Id": "rid-agent-create",
                        },
                        json={
                            "model": "deepseek-agent",
                            "text": "hi",
                            "conversation_id": None,
                            "metadata": {"client": "pytest"},
                        },
                    )
                    assert create.status_code == status.HTTP_202_ACCEPTED
                    payload = create.json()
                    run_id = payload["run_id"]
                    conversation_id = payload["conversation_id"]

                    assert re.match(r"^[0-9a-f]{32}$", run_id)

                    events = await _collect_sse_events(
                        async_client,
                        f"/api/v1/agent/runs/{run_id}/events?conversation_id={conversation_id}",
                        headers={
                            "Authorization": f"Bearer {mock_jwt_token}",
                            "Accept": "text/event-stream",
                            "X-Request-Id": "rid-agent-sse",
                        },
                    )

                    event_names = [item["event"] for item in events]
                    assert "tool_start" in event_names
                    assert "tool_result" in event_names
                    assert "content_delta" in event_names
                    assert "completed" in event_names

                    tool_names = [
                        (item.get("data") or {}).get("tool_name")
                        for item in events
                        if item.get("event") in {"tool_start", "tool_result"} and isinstance(item.get("data"), dict)
                    ]
                    assert "gymbro.exercise.search" in tool_names

                    call_args = mock_httpx.return_value.__aenter__.return_value.stream.call_args
                    assert call_args is not None
                    upstream_payload = call_args[1]["json"]
                    assert upstream_payload.get("model") == "deepseek-chat"
                finally:
                    try:
                        await fastapi_app.state.model_mapping_service.delete_mapping(mapping_id)
                    except Exception:
                        pass
                    if created_endpoint_id is not None:
                        try:
                            await fastapi_app.state.ai_config_service.delete_endpoint(int(created_endpoint_id), sync_remote=False)
                        except Exception:
                            pass

    @pytest.mark.asyncio
    async def test_agent_runs_allows_anonymous_web_search_when_enabled(self, async_client: AsyncClient, mock_jwt_token: str):
        created_endpoint_id = None
        mapping_id = "mapping:deepseek-agent-anon"

        db = get_sqlite_manager(fastapi_app)
        await db.execute(
            """
            INSERT INTO llm_app_settings(key, value_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = CURRENT_TIMESTAMP
            """,
            ("web_search_enabled", json.dumps(True)),
        )
        await db.execute(
            """
            INSERT INTO llm_app_settings(key, value_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json, updated_at = CURRENT_TIMESTAMP
            """,
            ("web_search_exa_api_key", json.dumps("exa_test_key_1234567890")),
        )

        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(
                uid="test-user-anon-001",
                claims={"is_anonymous": True},
                user_type="anonymous",
            )
            mock_get_verifier.return_value = mock_verifier

            with patch("app.services.web_search_service.httpx.AsyncClient") as mock_exa_httpx:
                exa_response = MagicMock()
                exa_response.status_code = 200
                exa_response.headers = {"content-type": "application/json"}
                exa_response.json.return_value = {
                    "requestId": "exa-rid-001",
                    "results": [
                        {
                            "title": "Example Result",
                            "url": "https://example.com",
                            "publishedDate": "2026-01-13",
                            "summary": "Snippet",
                            "score": 1.0,
                        }
                    ],
                }

                exa_client = MagicMock()
                exa_client.post = AsyncMock(return_value=exa_response)

                exa_ctx = MagicMock()
                exa_ctx.__aenter__ = AsyncMock(return_value=exa_client)
                exa_ctx.__aexit__ = AsyncMock(return_value=False)
                mock_exa_httpx.return_value = exa_ctx

                try:
                    endpoint = await fastapi_app.state.ai_config_service.create_endpoint(
                        {
                            "name": "deepseek-default",
                            "base_url": "https://api.deepseek.com",
                            "api_key": "test-api-key",
                            "is_active": True,
                            "is_default": False,
                            "model_list": ["deepseek-chat"],
                        }
                    )
                    created_endpoint_id = endpoint.get("id")

                    await fastapi_app.state.model_mapping_service.upsert_mapping(
                        {
                            "scope_type": "mapping",
                            "scope_key": "deepseek-agent-anon",
                            "name": "deepseek-agent-anon",
                            "default_model": "deepseek-chat",
                            "candidates": ["deepseek-chat"],
                            "is_active": True,
                            "metadata": {},
                        }
                    )

                    create = await async_client.post(
                        "/api/v1/agent/runs",
                        headers={
                            "Authorization": f"Bearer {mock_jwt_token}",
                            "X-Request-Id": "rid-agent-anon-create",
                        },
                        json={
                            "model": "deepseek-agent-anon",
                            "text": "search something",
                            "conversation_id": None,
                            "metadata": {"client": "pytest"},
                        },
                    )
                    assert create.status_code == status.HTTP_202_ACCEPTED
                    payload = create.json()
                    run_id = payload["run_id"]
                    conversation_id = payload["conversation_id"]

                    events = await _collect_sse_events(
                        async_client,
                        f"/api/v1/agent/runs/{run_id}/events?conversation_id={conversation_id}",
                        headers={
                            "Authorization": f"Bearer {mock_jwt_token}",
                            "Accept": "text/event-stream",
                        },
                    )

                    tool_events = [item for item in events if item.get("event") in {"tool_start", "tool_result"}]
                    tool_names = [
                        (item.get("data") or {}).get("tool_name")
                        for item in tool_events
                        if isinstance(item.get("data"), dict)
                    ]
                    assert "web_search.exa" in tool_names

                    web_result = next(
                        (
                            item
                            for item in events
                            if item.get("event") == "tool_result"
                            and isinstance(item.get("data"), dict)
                            and (item.get("data") or {}).get("tool_name") == "web_search.exa"
                        ),
                        None,
                    )
                    assert web_result is not None
                    assert (web_result.get("data") or {}).get("ok") is True
                finally:
                    try:
                        await db.execute(
                            "DELETE FROM llm_app_settings WHERE key IN (?, ?)",
                            ("web_search_enabled", "web_search_exa_api_key"),
                        )
                    except Exception:
                        pass
                    try:
                        await fastapi_app.state.model_mapping_service.delete_mapping(mapping_id)
                    except Exception:
                        pass
                    if created_endpoint_id is not None:
                        try:
                            await fastapi_app.state.ai_config_service.delete_endpoint(int(created_endpoint_id), sync_remote=False)
                        except Exception:
                            pass

    @pytest.mark.asyncio
    async def test_agent_runs_uses_agent_prompts_bundle(self, async_client: AsyncClient, mock_jwt_token: str):
        created_endpoint_id = None
        mapping_id = "mapping:deepseek-agent-prompts"
        agent_system_prompt_id = None
        agent_tools_prompt_id = None

        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-agent-002", claims={})
            mock_get_verifier.return_value = mock_verifier

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_httpx:
                endpoint = await fastapi_app.state.ai_config_service.create_endpoint(
                    {
                        "name": "deepseek-default",
                        "base_url": "https://api.deepseek.com",
                        "api_key": "test-api-key",
                        "is_active": True,
                        "is_default": False,
                        "model_list": ["deepseek-chat"],
                    }
                )
                created_endpoint_id = endpoint.get("id")

                await fastapi_app.state.model_mapping_service.upsert_mapping(
                    {
                        "scope_type": "mapping",
                        "scope_key": "deepseek-agent-prompts",
                        "name": "deepseek-agent-prompts",
                        "default_model": "deepseek-chat",
                        "candidates": ["deepseek-chat"],
                        "is_active": True,
                        "metadata": {},
                    }
                )

                agent_system = await fastapi_app.state.ai_config_service.create_prompt(
                    {
                        "name": "pytest-agent-system",
                        "content": "AGENT_SYSTEM_PROMPT_UNIQUE",
                        "prompt_type": "agent_system",
                        "is_active": True,
                    },
                    auto_sync=False,
                )
                agent_system_prompt_id = agent_system.get("id")
                agent_tools = await fastapi_app.state.ai_config_service.create_prompt(
                    {
                        "name": "pytest-agent-tools",
                        "content": "AGENT_TOOLS_PROMPT_UNIQUE",
                        "prompt_type": "agent_tools",
                        "tools_json": [
                            {
                                "type": "function",
                                "function": {
                                    "name": "web_search.exa",
                                    "description": "search",
                                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                                },
                            }
                        ],
                        "is_active": True,
                    },
                    auto_sync=False,
                )
                agent_tools_prompt_id = agent_tools.get("id")

                _mock_httpx_stream_json(
                    mock_httpx,
                    {"choices": [{"message": {"content": "Hello from agent."}}]},
                    headers={"x-request-id": "upstream-rid"},
                )

                try:
                    create = await async_client.post(
                        "/api/v1/agent/runs",
                        headers={
                            "Authorization": f"Bearer {mock_jwt_token}",
                            "X-Request-Id": "rid-agent-prompts-create",
                        },
                        json={
                            "model": "deepseek-agent-prompts",
                            "text": "hello",
                            "conversation_id": None,
                            "metadata": {"client": "pytest"},
                        },
                    )
                    assert create.status_code == status.HTTP_202_ACCEPTED
                    payload = create.json()
                    run_id = payload["run_id"]
                    conversation_id = payload["conversation_id"]

                    await _collect_sse_events(
                        async_client,
                        f"/api/v1/agent/runs/{run_id}/events?conversation_id={conversation_id}",
                        headers={
                            "Authorization": f"Bearer {mock_jwt_token}",
                            "Accept": "text/event-stream",
                        },
                    )

                    call_args = mock_httpx.return_value.__aenter__.return_value.stream.call_args
                    assert call_args is not None
                    upstream_payload = call_args.kwargs.get("json") or {}
                    assert isinstance(upstream_payload, dict)
                    msgs = upstream_payload.get("messages") or []
                    assert isinstance(msgs, list) and msgs
                    system_message = msgs[0].get("content") if isinstance(msgs[0], dict) else ""
                    assert "AGENT_SYSTEM_PROMPT_UNIQUE" in str(system_message)
                    assert "AGENT_TOOLS_PROMPT_UNIQUE" in str(system_message)
                finally:
                    try:
                        if agent_system_prompt_id is not None:
                            await fastapi_app.state.ai_config_service.delete_prompt(int(agent_system_prompt_id), sync_remote=False)
                        if agent_tools_prompt_id is not None:
                            await fastapi_app.state.ai_config_service.delete_prompt(int(agent_tools_prompt_id), sync_remote=False)
                    finally:
                        try:
                            await fastapi_app.state.ai_config_service.ensure_default_prompts_seeded()
                        except Exception:
                            pass
                    try:
                        await fastapi_app.state.model_mapping_service.delete_mapping(mapping_id)
                    except Exception:
                        pass
                    if created_endpoint_id is not None:
                        try:
                            await fastapi_app.state.ai_config_service.delete_endpoint(int(created_endpoint_id), sync_remote=False)
                        except Exception:
                            pass
