"""E2E tests for AI conversation API endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app import app as fastapi_app
from app.auth import AuthenticatedUser
from app.services.ai_service import AIMessageInput, AIService, MessageEventBroker


class TestModelSelection:
    """Test model selection from request."""

    @pytest.mark.asyncio
    async def test_model_from_request_overrides_default(self, async_client: AsyncClient, mock_jwt_token: str):
        """请求 model 必须来自白名单（mapping.id）；并能解析为真实 vendor model。"""
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            mappings = [
                {
                    "id": "user:test-user-123",
                    "scope_type": "user",
                    "scope_key": "test-user-123",
                    "name": "User Override",
                    "default_model": "gpt-4o",
                    "candidates": ["gpt-4o"],
                    "is_active": True,
                    "source": "fallback",
                    "metadata": {},
                }
            ]

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_client:
                await fastapi_app.state.ai_config_service.create_endpoint(
                    {
                        "name": "openai-default",
                        "base_url": "https://api.openai.com",
                        "api_key": "test-api-key",
                        "is_active": True,
                        "is_default": True,
                        "model_list": ["gpt-4o-mini", "gpt-4o"],
                    }
                )

                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "Test response from GPT-4"}}],
                }
                mock_response.raise_for_status = MagicMock()
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

                with patch.object(
                    fastapi_app.state.model_mapping_service,
                    "list_mappings",
                    new=AsyncMock(return_value=mappings),
                ):
                    response = await async_client.post(
                        "/api/v1/messages",
                        headers={"Authorization": f"Bearer {mock_jwt_token}"},
                        json={
                            "text": "Hello, AI!",
                            "model": "user:test-user-123",
                        },
                    )

                assert response.status_code == status.HTTP_202_ACCEPTED
                data = response.json()
                assert "message_id" in data

                # Verify OpenAI was called with the resolved vendor model
                call_args = mock_client.return_value.__aenter__.return_value.post.call_args
                assert call_args is not None
                payload = call_args[1]["json"]
                assert payload["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_model_from_mapping_key_resolves_to_vendor_model(self, async_client: AsyncClient, mock_jwt_token: str):
        """当请求 model 为“业务映射 key”（mapping.id）时，应解析为真实 vendor model。"""
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            mappings = [
                {
                    "id": "user:test-user-123",
                    "scope_type": "user",
                    "scope_key": "test-user-123",
                    "name": "Renamable Label",
                    "default_model": "gpt-4o",
                    "candidates": ["gpt-4o"],
                    "is_active": True,
                    "source": "fallback",
                    "metadata": {},
                }
            ]

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_client:
                await fastapi_app.state.ai_config_service.create_endpoint(
                    {
                        "name": "openai-default",
                        "base_url": "https://api.openai.com",
                        "api_key": "test-api-key",
                        "is_active": True,
                        "is_default": True,
                        "model_list": ["gpt-4o-mini", "gpt-4o"],
                    }
                )

                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "Test response"}}],
                }
                mock_response.raise_for_status = MagicMock()
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

                with patch.object(
                    fastapi_app.state.model_mapping_service,
                    "list_mappings",
                    new=AsyncMock(return_value=mappings),
                ):
                    response = await async_client.post(
                        "/api/v1/messages",
                        headers={"Authorization": f"Bearer {mock_jwt_token}"},
                        json={
                            "text": "Hello, AI!",
                            "model": "user:test-user-123",
                        },
                    )

                assert response.status_code == status.HTTP_202_ACCEPTED

                call_args = mock_client.return_value.__aenter__.return_value.post.call_args
                assert call_args is not None
                payload = call_args[1]["json"]
                assert payload["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_model_name_is_not_used_as_mapping_key(self, async_client: AsyncClient, mock_jwt_token: str):
        """映射 name 仅用于展示；请求 key 必须为 mapping.id（否则 422）。"""
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            mappings = [
                {
                    "id": "user:test-user-123",
                    "scope_type": "user",
                    "scope_key": "test-user-123",
                    "name": "Renamable Label",
                    "default_model": "gpt-4o",
                    "candidates": ["gpt-4o"],
                    "is_active": True,
                    "source": "fallback",
                    "metadata": {},
                }
            ]

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_client:
                await fastapi_app.state.ai_config_service.create_endpoint(
                    {
                        "name": "openai-default",
                        "base_url": "https://api.openai.com",
                        "api_key": "test-api-key",
                        "is_active": True,
                        "is_default": True,
                        "model_list": ["gpt-4o-mini", "gpt-4o"],
                    }
                )

                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "Test response"}}],
                }
                mock_response.raise_for_status = MagicMock()
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

                with patch.object(
                    fastapi_app.state.model_mapping_service,
                    "list_mappings",
                    new=AsyncMock(return_value=mappings),
                ):
                    response = await async_client.post(
                        "/api/v1/messages",
                        headers={"Authorization": f"Bearer {mock_jwt_token}"},
                        json={
                            "text": "Hello, AI!",
                            "model": "Renamable Label",
                        },
                    )

                assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
                payload = response.json()
                assert payload.get("code") == "model_not_allowed"
                assert payload.get("request_id")

                call_args = mock_client.return_value.__aenter__.return_value.post.call_args
                assert call_args is None

    @pytest.mark.asyncio
    async def test_model_fallback_to_default(self, async_client: AsyncClient, mock_jwt_token: str):
        """未提供 model（顶层或 metadata.model）应 422。"""
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_client:
                await fastapi_app.state.ai_config_service.create_endpoint(
                    {
                        "name": "openai-default",
                        "base_url": "https://api.openai.com",
                        "api_key": "test-api-key",
                        "is_active": True,
                        "is_default": True,
                        "model_list": ["gpt-4o-mini", "gpt-4o"],
                    }
                )

                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "Test response"}}],
                }
                mock_response.raise_for_status = MagicMock()
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

                response = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}"},
                    json={
                        "text": "Hello, AI!",
                        # No model specified
                    },
                )

                assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
                payload = response.json()
                assert payload.get("code") == "model_required"
                assert payload.get("request_id")
                assert mock_client.return_value.__aenter__.return_value.post.call_args is None

    @pytest.mark.asyncio
    async def test_endpoint_override_from_metadata(self, async_client: AsyncClient, mock_jwt_token: str):
        """metadata.endpoint_id 指定时，优先命中该端点（不会按 model_list 自动切换）。"""
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            mappings = [
                {
                    "id": "user:test-user-123",
                    "scope_type": "user",
                    "scope_key": "test-user-123",
                    "name": "User Override",
                    "default_model": "gpt-4o",
                    "candidates": ["gpt-4o"],
                    "is_active": True,
                    "source": "fallback",
                    "metadata": {},
                }
            ]

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_client:
                endpoint_a = await fastapi_app.state.ai_config_service.create_endpoint(
                    {
                        "name": "openai-default-a",
                        "base_url": "https://api.openai.com",
                        "api_key": "test-api-key-a",
                        "is_active": True,
                        "is_default": True,
                        "model_list": ["gpt-4o-mini", "gpt-4o"],
                    }
                )
                endpoint_b = await fastapi_app.state.ai_config_service.create_endpoint(
                    {
                        "name": "openai-b",
                        "base_url": "https://example.openai-proxy.local",
                        "api_key": "test-api-key-b",
                        "is_active": True,
                        "is_default": False,
                        "model_list": ["gpt-4o-mini", "gpt-4o"],
                    }
                )

                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "Test response"}}],
                }
                mock_response.raise_for_status = MagicMock()
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

                with patch.object(
                    fastapi_app.state.model_mapping_service,
                    "list_mappings",
                    new=AsyncMock(return_value=mappings),
                ):
                    response = await async_client.post(
                        "/api/v1/messages",
                        headers={"Authorization": f"Bearer {mock_jwt_token}"},
                        json={
                            "text": "Hello, AI!",
                            "model": "user:test-user-123",
                            "metadata": {"endpoint_id": endpoint_b["id"]},
                        },
                    )

                assert response.status_code == status.HTTP_202_ACCEPTED

                call_args = mock_client.return_value.__aenter__.return_value.post.call_args
                assert call_args is not None
                called_url = call_args[0][0]
                assert isinstance(called_url, str)
                assert "example.openai-proxy.local" in called_url
                assert endpoint_a["id"] != endpoint_b["id"]


class TestConditionalPersistence:
    """Test conditional Supabase persistence."""

    @pytest.mark.asyncio
    async def test_save_history_enabled(self):
        """Test conversation saved when save_history=True."""
        mock_provider = MagicMock()
        mock_provider.get_user_details.return_value = MagicMock(uid="user-123", email="test@example.com")
        mock_provider.sync_chat_record = MagicMock()

        ai_service = AIService(provider=mock_provider)
        broker = MessageEventBroker()
        message_id = AIService.new_message_id()
        await broker.create_channel(message_id, owner_user_id="user-123", conversation_id="conv-001")

        user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        message = AIMessageInput(
            text="Hello",
            conversation_id="conv-001",
            model="gpt-4o-mini",
            metadata={"save_history": True},
        )

        with patch.object(
            ai_service,
            "_generate_reply",
            return_value=("Hi there!", "gpt-4o-mini", "req", "resp", None, None, "openai"),
        ):
            await ai_service.run_conversation(message_id, user, message, broker)

        # Verify sync_chat_record was called
        assert mock_provider.sync_chat_record.called
        call_args = mock_provider.sync_chat_record.call_args[0][0]
        assert call_args["user_id"] == "user-123"
        assert call_args["user_message"] == "Hello"
        assert call_args["ai_reply"] == "Hi there!"

    @pytest.mark.asyncio
    async def test_save_history_disabled(self):
        """Test conversation NOT saved when save_history=False."""
        mock_provider = MagicMock()
        mock_provider.get_user_details.return_value = MagicMock(uid="user-123", email="test@example.com")
        mock_provider.sync_chat_record = MagicMock()

        ai_service = AIService(provider=mock_provider)
        broker = MessageEventBroker()
        message_id = AIService.new_message_id()
        await broker.create_channel(message_id, owner_user_id="user-123", conversation_id="conv-001")

        user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        message = AIMessageInput(
            text="Hello",
            conversation_id="conv-001",
            model="gpt-4o-mini",
            metadata={"save_history": False},  # Disabled
        )

        with patch.object(
            ai_service,
            "_generate_reply",
            return_value=("Hi there!", "gpt-4o-mini", "req", "resp", None, None, "openai"),
        ):
            await ai_service.run_conversation(message_id, user, message, broker)

        # Verify sync_chat_record was NOT called
        assert not mock_provider.sync_chat_record.called

    @pytest.mark.asyncio
    async def test_save_history_default_true(self):
        """Test conversation saved by default (backward compatibility)."""
        mock_provider = MagicMock()
        mock_provider.get_user_details.return_value = MagicMock(uid="user-123", email="test@example.com")
        mock_provider.sync_chat_record = MagicMock()

        ai_service = AIService(provider=mock_provider)
        broker = MessageEventBroker()
        message_id = AIService.new_message_id()
        await broker.create_channel(message_id, owner_user_id="user-123", conversation_id="conv-001")

        user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        message = AIMessageInput(
            text="Hello",
            conversation_id="conv-001",
            model="gpt-4o-mini",
            metadata={},  # No save_history flag
        )

        with patch.object(
            ai_service,
            "_generate_reply",
            return_value=("Hi there!", "gpt-4o-mini", "req", "resp", None, None, "openai"),
        ):
            await ai_service.run_conversation(message_id, user, message, broker)

        # Verify sync_chat_record was called (default behavior)
        assert mock_provider.sync_chat_record.called


class TestPrometheusMetrics:
    """Test Prometheus metrics collection."""

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_success(self):
        """Test that metrics are recorded on successful conversation."""
        from app.core.metrics import ai_conversation_latency_seconds

        def get_count() -> float:
            wanted = {"model": "gpt-4o-mini", "user_type": "permanent", "status": "success"}
            for metric in ai_conversation_latency_seconds.collect():
                for sample in metric.samples:
                    if sample.name.endswith("_count") and sample.labels == wanted:
                        return float(sample.value)
            return 0.0

        initial_count = get_count()

        mock_provider = MagicMock()
        mock_provider.get_user_details.return_value = MagicMock(uid="user-123", email="test@example.com")
        mock_provider.sync_chat_record = MagicMock()

        ai_service = AIService(provider=mock_provider)
        broker = MessageEventBroker()
        message_id = AIService.new_message_id()
        await broker.create_channel(message_id, owner_user_id="user-123", conversation_id="conv-001")

        user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        message = AIMessageInput(text="Hello", model="gpt-4o-mini")

        with patch.object(
            ai_service,
            "_generate_reply",
            return_value=("Hi there!", "gpt-4o-mini", "req", "resp", None, None, "openai"),
        ):
            await ai_service.run_conversation(message_id, user, message, broker)

        final_count = get_count()

        assert final_count > initial_count

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_error(self):
        """Test that metrics are recorded on error."""
        from app.core.metrics import ai_conversation_latency_seconds

        def get_count() -> float:
            wanted = {"model": "gpt-4o-mini", "user_type": "permanent", "status": "error"}
            for metric in ai_conversation_latency_seconds.collect():
                for sample in metric.samples:
                    if sample.name.endswith("_count") and sample.labels == wanted:
                        return float(sample.value)
            return 0.0

        initial_count = get_count()

        mock_provider = MagicMock()
        mock_provider.get_user_details.return_value = MagicMock(uid="user-123", email="test@example.com")

        ai_service = AIService(provider=mock_provider)
        broker = MessageEventBroker()
        message_id = AIService.new_message_id()
        await broker.create_channel(message_id, owner_user_id="user-123", conversation_id="conv-001")

        user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        message = AIMessageInput(text="Hello", model="gpt-4o-mini")

        # Simulate error
        with patch.object(ai_service, "_generate_reply", side_effect=Exception("AI provider error")):
            await ai_service.run_conversation(message_id, user, message, broker)

        final_count = get_count()

        assert final_count > initial_count


class TestE2EFlow:
    """Test complete E2E conversation flow."""

    @pytest.mark.asyncio
    async def test_complete_conversation_flow(self, async_client: AsyncClient, mock_jwt_token: str):
        """Test complete flow from request to SSE stream."""
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.json.return_value = {
                    "choices": [{"message": {"content": "This is a test response from the AI."}}],
                }
                mock_response.raise_for_status = MagicMock()
                mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

                # Step 1: Create message
                response = await async_client.post(
                    "/api/v1/messages",
                    headers={"Authorization": f"Bearer {mock_jwt_token}"},
                    json={
                        "text": "What is the best workout?",
                        "conversation_id": "conv-test-001",
                        "model": "global:global",
                        "metadata": {"save_history": True},
                    },
                )

                assert response.status_code == status.HTTP_202_ACCEPTED
                data = response.json()
                message_id = data["message_id"]
                assert message_id is not None

                # Step 2: Stream events (simplified - just verify endpoint exists)
                # Note: Full SSE testing requires more complex setup
                # This is covered by integration tests

    @pytest.mark.asyncio
    async def test_authentication_required(self, async_client: AsyncClient):
        """Test that authentication is required."""
        response = await async_client.post(
            "/api/v1/messages",
            json={"text": "Hello"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_empty_text_validation(self, async_client: AsyncClient, mock_jwt_token: str):
        """Test that empty text is rejected."""
        with patch("app.auth.dependencies.get_jwt_verifier") as mock_get_verifier:
            mock_verifier = MagicMock()
            mock_verifier.verify_token.return_value = AuthenticatedUser(uid="test-user-123", claims={})
            mock_get_verifier.return_value = mock_verifier

            response = await async_client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={"text": ""},
            )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
