"""API契约验证测试。"""
import json
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app import app
from app.auth.jwt_verifier import AuthenticatedUser


class TestAPIContracts:
    """API契约验证测试。"""

    @pytest.fixture
    def client(self):
        """测试客户端。"""
        return TestClient(app)

    @pytest.fixture
    def mock_auth_user(self):
        """模拟认证用户。"""
        return AuthenticatedUser(
            uid="test-user-123",
            claims={
                "sub": "test-user-123",
                "email": "test@example.com",
                "iss": "https://test.supabase.co",
                "aud": "test-audience"
            }
        )

    @pytest.fixture
    def auth_headers(self):
        """认证头。"""
        return {"Authorization": "Bearer mock-jwt-token"}

    def test_messages_post_contract(self, client):
        """测试POST /api/v1/messages契约。"""
        # 测试未授权访问
        response = client.post("/api/v1/messages", json={"text": "Hello"})
        assert response.status_code == 401
        
        data = response.json()
        required_fields = ["code", "message", "trace_id"]
        for field in required_fields:
            assert field in data, f"Response missing required field: {field}"

    @patch('app.auth.dependencies.get_jwt_verifier')
    def test_messages_post_success_contract(self, mock_get_verifier, client, mock_auth_user, auth_headers):
        """测试POST /api/v1/messages成功响应契约。"""
        # Mock JWT 验证
        mock_verifier = Mock()
        mock_verifier.verify_token.return_value = mock_auth_user
        mock_get_verifier.return_value = mock_verifier
        
        # 测试成功创建消息
        response = client.post(
            "/api/v1/messages",
            json={"text": "Hello AI", "conversation_id": "conv-123"},
            headers=auth_headers
        )
        
        assert response.status_code == 202
        data = response.json()
        
        # 验证响应结构
        assert "message_id" in data
        assert isinstance(data["message_id"], str)
        assert len(data["message_id"]) > 0

    @patch('app.auth.dependencies.get_jwt_verifier')
    def test_messages_post_validation_contract(self, mock_get_verifier, client, mock_auth_user, auth_headers):
        """测试POST /api/v1/messages输入验证契约。"""
        # Mock JWT 验证
        mock_verifier = Mock()
        mock_verifier.verify_token.return_value = mock_auth_user
        mock_get_verifier.return_value = mock_verifier
        
        # 测试缺少必需字段
        response = client.post("/api/v1/messages", json={}, headers=auth_headers)
        assert response.status_code == 422
        
        # 测试空文本
        response = client.post("/api/v1/messages", json={"text": ""}, headers=auth_headers)
        assert response.status_code == 422
        
        # 测试额外字段被拒绝
        response = client.post(
            "/api/v1/messages",
            json={"text": "Hello", "extra_field": "should_be_rejected"},
            headers=auth_headers
        )
        assert response.status_code == 422

    @patch('app.auth.dependencies.get_jwt_verifier')
    def test_messages_events_get_contract(self, mock_get_verifier, client, mock_auth_user, auth_headers):
        """测试GET /api/v1/messages/{message_id}/events契约。"""
        # Mock JWT 验证
        mock_verifier = Mock()
        mock_verifier.verify_token.return_value = mock_auth_user
        mock_get_verifier.return_value = mock_verifier
        
        # 测试不存在的消息ID
        response = client.get("/api/v1/messages/nonexistent/events", headers=auth_headers)
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data

    def test_error_response_contract(self, client):
        """测试错误响应契约。"""
        # 测试401错误
        response = client.post("/api/v1/messages", json={"text": "Hello"})
        assert response.status_code == 401
        
        data = response.json()
        required_fields = ["code", "message", "trace_id"]
        for field in required_fields:
            assert field in data
        
        assert isinstance(data["code"], str)
        assert isinstance(data["message"], str)
        assert isinstance(data["trace_id"], str)

    def test_trace_id_contract(self, client):
        """测试Trace ID契约。"""
        custom_trace_id = "test-trace-12345"
        headers = {"x-trace-id": custom_trace_id}
        
        response = client.post("/api/v1/messages", json={"text": "Hello"}, headers=headers)
        
        # 验证响应头包含Trace ID
        assert response.headers.get("x-trace-id") == custom_trace_id
        
        # 验证响应体包含Trace ID
        data = response.json()
        assert data.get("trace_id") == custom_trace_id

    def test_content_type_contract(self, client):
        """测试Content-Type契约。"""
        # 测试JSON响应
        response = client.post("/api/v1/messages", json={"text": "Hello"})
        assert "application/json" in response.headers.get("content-type", "")

    @patch('app.auth.dependencies.get_jwt_verifier')
    def test_sse_content_type_contract(self, mock_get_verifier, client, mock_auth_user, auth_headers):
        """测试SSE Content-Type契约。"""
        # Mock JWT 验证
        mock_verifier = Mock()
        mock_verifier.verify_token.return_value = mock_auth_user
        mock_get_verifier.return_value = mock_verifier
        
        # 先创建一个消息
        response = client.post(
            "/api/v1/messages",
            json={"text": "Hello"},
            headers=auth_headers
        )
        assert response.status_code == 202
        message_id = response.json()["message_id"]
        
        # 测试SSE端点的Content-Type
        response = client.get(f"/api/v1/messages/{message_id}/events", headers=auth_headers)
        # 可能返回404（消息已处理完成）或200（SSE流）
        if response.status_code == 200:
            assert "text/event-stream" in response.headers.get("content-type", "")

    def test_cors_contract(self, client):
        """测试CORS契约。"""
        # 发送OPTIONS预检请求
        response = client.options(
            "/api/v1/messages",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Authorization,Content-Type"
            }
        )
        
        # 验证CORS头存在
        cors_headers = [
            "access-control-allow-origin",
            "access-control-allow-methods",
            "access-control-allow-headers"
        ]
        
        for header in cors_headers:
            assert header in response.headers, f"Missing CORS header: {header}"

    def test_http_methods_contract(self, client):
        """测试HTTP方法契约。"""
        # POST /api/v1/messages 应该支持
        response = client.post("/api/v1/messages", json={"text": "Hello"})
        assert response.status_code != 405  # Method Not Allowed
        
        # GET /api/v1/messages 应该不支持
        response = client.get("/api/v1/messages")
        assert response.status_code == 405
        
        # PUT /api/v1/messages 应该不支持
        response = client.put("/api/v1/messages", json={"text": "Hello"})
        assert response.status_code == 405


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
