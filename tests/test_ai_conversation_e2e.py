"""E2E tests for AI conversation API endpoint."""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from httpx import AsyncClient

from app.auth import AuthenticatedUser
from app.services.ai_service import AIMessageInput, AIService, MessageEventBroker


class TestModelSelection:
    """Test model selection from request."""

    @pytest.mark.asyncio
    async def test_model_from_request_overrides_default(self, client: AsyncClient, mock_jwt_token: str):
        """Test that model from request overrides default setting."""
        with patch("app.services.ai_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Test response from GPT-4"}}],
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            response = await client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={
                    "text": "Hello, AI!",
                    "model": "gpt-4o",  # Specific model
                },
            )

            assert response.status_code == status.HTTP_202_ACCEPTED
            data = response.json()
            assert "message_id" in data

            # Verify OpenAI was called with the specified model
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args
            assert call_args is not None
            payload = call_args[1]["json"]
            assert payload["model"] == "gpt-4o"

    @pytest.mark.asyncio
    async def test_model_fallback_to_default(self, client: AsyncClient, mock_jwt_token: str):
        """Test that missing model falls back to default."""
        with patch("app.services.ai_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Test response"}}],
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            response = await client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={
                    "text": "Hello, AI!",
                    # No model specified
                },
            )

            assert response.status_code == status.HTTP_202_ACCEPTED

            # Verify OpenAI was called with default model
            call_args = mock_client.return_value.__aenter__.return_value.post.call_args
            assert call_args is not None
            payload = call_args[1]["json"]
            # Should use AI_MODEL from settings or fallback to gpt-4o-mini
            assert payload["model"] in ["gpt-4o-mini", "gpt-4o"]


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
        await broker.create_channel(message_id)

        user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        message = AIMessageInput(
            text="Hello",
            conversation_id="conv-001",
            model="gpt-4o-mini",
            metadata={"save_history": True},
        )

        with patch.object(ai_service, "_generate_reply", return_value="Hi there!"):
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
        await broker.create_channel(message_id)

        user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        message = AIMessageInput(
            text="Hello",
            conversation_id="conv-001",
            model="gpt-4o-mini",
            metadata={"save_history": False},  # Disabled
        )

        with patch.object(ai_service, "_generate_reply", return_value="Hi there!"):
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
        await broker.create_channel(message_id)

        user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        message = AIMessageInput(
            text="Hello",
            conversation_id="conv-001",
            model="gpt-4o-mini",
            metadata={},  # No save_history flag
        )

        with patch.object(ai_service, "_generate_reply", return_value="Hi there!"):
            await ai_service.run_conversation(message_id, user, message, broker)

        # Verify sync_chat_record was called (default behavior)
        assert mock_provider.sync_chat_record.called


class TestPrometheusMetrics:
    """Test Prometheus metrics collection."""

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_success(self):
        """Test that metrics are recorded on successful conversation."""
        from app.core.metrics import ai_conversation_latency_seconds

        # Get initial count
        initial_count = ai_conversation_latency_seconds.labels(
            model="gpt-4o-mini", user_type="permanent", status="success"
        )._value._count

        mock_provider = MagicMock()
        mock_provider.get_user_details.return_value = MagicMock(uid="user-123", email="test@example.com")
        mock_provider.sync_chat_record = MagicMock()

        ai_service = AIService(provider=mock_provider)
        broker = MessageEventBroker()
        message_id = AIService.new_message_id()
        await broker.create_channel(message_id)

        user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        message = AIMessageInput(text="Hello", model="gpt-4o-mini")

        with patch.object(ai_service, "_generate_reply", return_value="Hi there!"):
            await ai_service.run_conversation(message_id, user, message, broker)

        # Verify metric was incremented
        final_count = ai_conversation_latency_seconds.labels(
            model="gpt-4o-mini", user_type="permanent", status="success"
        )._value._count

        assert final_count > initial_count

    @pytest.mark.asyncio
    async def test_metrics_recorded_on_error(self):
        """Test that metrics are recorded on error."""
        from app.core.metrics import ai_conversation_latency_seconds

        # Get initial count
        initial_count = ai_conversation_latency_seconds.labels(
            model="gpt-4o-mini", user_type="permanent", status="error"
        )._value._count

        mock_provider = MagicMock()
        mock_provider.get_user_details.return_value = MagicMock(uid="user-123", email="test@example.com")

        ai_service = AIService(provider=mock_provider)
        broker = MessageEventBroker()
        message_id = AIService.new_message_id()
        await broker.create_channel(message_id)

        user = AuthenticatedUser(uid="user-123", claims={}, user_type="permanent")
        message = AIMessageInput(text="Hello", model="gpt-4o-mini")

        # Simulate error
        with patch.object(ai_service, "_generate_reply", side_effect=Exception("AI provider error")):
            await ai_service.run_conversation(message_id, user, message, broker)

        # Verify error metric was incremented
        final_count = ai_conversation_latency_seconds.labels(
            model="gpt-4o-mini", user_type="permanent", status="error"
        )._value._count

        assert final_count > initial_count


class TestE2EFlow:
    """Test complete E2E conversation flow."""

    @pytest.mark.asyncio
    async def test_complete_conversation_flow(self, client: AsyncClient, mock_jwt_token: str):
        """Test complete flow from request to SSE stream."""
        with patch("app.services.ai_service.httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "This is a test response from the AI."}}],
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            # Step 1: Create message
            response = await client.post(
                "/api/v1/messages",
                headers={"Authorization": f"Bearer {mock_jwt_token}"},
                json={
                    "text": "What is the best workout?",
                    "conversation_id": "conv-test-001",
                    "model": "gpt-4o-mini",
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
    async def test_authentication_required(self, client: AsyncClient):
        """Test that authentication is required."""
        response = await client.post(
            "/api/v1/messages",
            json={"text": "Hello"},
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.asyncio
    async def test_empty_text_validation(self, client: AsyncClient, mock_jwt_token: str):
        """Test that empty text is rejected."""
        response = await client.post(
            "/api/v1/messages",
            headers={"Authorization": f"Bearer {mock_jwt_token}"},
            json={"text": ""},
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

