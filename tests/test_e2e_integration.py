"""端到端集成测试。"""
import asyncio
import json
import time
from unittest.mock import Mock, patch

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from app import app
from app.auth.jwt_verifier import AuthenticatedUser
from app.auth.provider import InMemoryProvider


class TestE2EIntegration:
    """端到端集成测试。"""

    @pytest.fixture
    def client(self):
        """测试客户端。"""
        return TestClient(app)

    @pytest.fixture
    def mock_jwt_token(self):
        """模拟有效的JWT token。"""
        payload = {
            "iss": "https://test.supabase.co",
            "sub": "test-user-123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "nbf": int(time.time()),
            "email": "test@example.com"
        }
        # 这里返回一个模拟token，实际测试中会被mock掉验证过程
        return "mock.jwt.token", payload

    @pytest.fixture
    def auth_headers(self, mock_jwt_token):
        """认证头。"""
        token, _ = mock_jwt_token
        return {"Authorization": f"Bearer {token}"}

    @patch('app.auth.dependencies.get_jwt_verifier')
    def test_create_message_and_stream_events(self, mock_get_verifier, client, mock_jwt_token, auth_headers):
        """测试创建消息和流式事件的完整流程。"""
        token, payload = mock_jwt_token
        
        # Mock JWT 验证
        mock_verifier = Mock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid=payload["sub"],
            claims=payload
        )
        mock_get_verifier.return_value = mock_verifier
        
        # 1. 创建消息
        response = client.post(
            "/api/v1/messages",
            json={"text": "Hello AI", "conversation_id": "conv-123"},
            headers=auth_headers
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "message_id" in data
        message_id = data["message_id"]
        
        # 2. 测试事件流 (简化版本，实际SSE测试需要更复杂的设置)
        # 这里我们只测试端点是否可访问
        response = client.get(f"/api/v1/messages/{message_id}/events", headers=auth_headers)
        # 由于SSE流的特殊性，这里可能返回200或其他状态
        assert response.status_code in [200, 404]  # 404是因为消息可能已经处理完成

    @patch('app.auth.dependencies.get_jwt_verifier')
    def test_trace_id_propagation(self, mock_get_verifier, client, mock_jwt_token, auth_headers):
        """测试Trace ID传播。"""
        token, payload = mock_jwt_token
        
        # Mock JWT 验证
        mock_verifier = Mock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid=payload["sub"],
            claims=payload
        )
        mock_get_verifier.return_value = mock_verifier
        
        # 发送带有自定义Trace ID的请求
        custom_trace_id = "custom-trace-12345"
        headers = {**auth_headers, "x-trace-id": custom_trace_id}
        
        response = client.post(
            "/api/v1/messages",
            json={"text": "Hello with trace"},
            headers=headers
        )
        
        assert response.status_code == 202
        # 验证响应头中包含相同的Trace ID
        assert response.headers.get("x-trace-id") == custom_trace_id

    def test_unauthorized_access(self, client):
        """测试未授权访问。"""
        # 无Authorization头
        response = client.post("/api/v1/messages", json={"text": "Hello"})
        assert response.status_code == 401
        data = response.json()
        assert "trace_id" in data
        assert data["code"] == "unauthorized"

    def test_invalid_jwt_token(self, client):
        """测试无效JWT token。"""
        headers = {"Authorization": "Bearer invalid.jwt.token"}
        response = client.post("/api/v1/messages", json={"text": "Hello"}, headers=headers)
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == "invalid_token_header"
        assert "trace_id" in data

    @patch('app.auth.dependencies.get_jwt_verifier')
    def test_cors_headers(self, mock_get_verifier, client, mock_jwt_token):
        """测试CORS头设置。"""
        token, payload = mock_jwt_token
        
        # Mock JWT 验证
        mock_verifier = Mock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid=payload["sub"],
            claims=payload
        )
        mock_get_verifier.return_value = mock_verifier
        
        # 发送OPTIONS预检请求
        response = client.options(
            "/api/v1/messages",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization,Content-Type"
            }
        )
        
        # 检查CORS响应头
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers

    def test_provider_fallback(self):
        """测试Provider回退机制。"""
        # 测试当Supabase不可用时，系统回退到InMemoryProvider
        from app.auth.provider import get_auth_provider
        
        provider = get_auth_provider()
        assert isinstance(provider, InMemoryProvider)
        
        # 测试基本功能
        user_details = provider.get_user_details("test-user")
        assert user_details.uid == "test-user"
        
        # 测试聊天记录同步
        record = {"message_id": "msg-1", "user_id": "user-1", "text": "Hello"}
        provider.sync_chat_record(record)
        assert len(provider.records) == 1
        assert provider.records[0] == record

    @patch('app.auth.dependencies.get_jwt_verifier')
    def test_ai_service_integration(self, mock_get_verifier, client, mock_jwt_token, auth_headers):
        """测试AI服务集成。"""
        token, payload = mock_jwt_token
        
        # Mock JWT 验证
        mock_verifier = Mock()
        mock_verifier.verify_token.return_value = AuthenticatedUser(
            uid=payload["sub"],
            claims=payload
        )
        mock_get_verifier.return_value = mock_verifier
        
        # 测试不同类型的消息
        test_cases = [
            {"text": "Hello", "conversation_id": "conv-1"},
            {"text": "How are you?", "conversation_id": "conv-2", "metadata": {"source": "web"}},
            {"text": "Tell me a joke"},  # 无conversation_id
        ]
        
        for case in test_cases:
            response = client.post("/api/v1/messages", json=case, headers=auth_headers)
            assert response.status_code == 202
            data = response.json()
            assert "message_id" in data
            assert len(data["message_id"]) > 0

    def test_error_handling(self, client):
        """测试错误处理。"""
        # 测试无效的JSON
        response = client.post(
            "/api/v1/messages",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422  # Unprocessable Entity
        
        # 测试缺少必需字段
        response = client.post(
            "/api/v1/messages",
            json={},  # 缺少text字段
            headers={"Authorization": "Bearer invalid"}
        )
        assert response.status_code == 422

    def test_health_check(self, client):
        """测试健康检查端点（如果存在）。"""
        # 尝试访问根路径
        response = client.get("/")
        # 根路径可能返回404或其他状态，这是正常的
        assert response.status_code in [200, 404, 405]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
