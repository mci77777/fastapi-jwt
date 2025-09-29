"""JWT 认证系统测试用例。"""
import json
import time
from unittest.mock import Mock, patch

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import app
from app.auth.jwt_verifier import AuthenticatedUser, JWTVerifier
from app.auth.provider import InMemoryProvider, UserDetails


class TestJWTVerifier:
    """JWT 验证器测试。"""

    def test_verify_token_missing(self):
        """测试缺失 token 的情况。"""
        verifier = JWTVerifier()
        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_token("")
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "token_missing"

    def test_verify_token_invalid_header(self):
        """测试无效 JWT 头部。"""
        verifier = JWTVerifier()
        with pytest.raises(HTTPException) as exc_info:
            verifier.verify_token("invalid.token")
        
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail["code"] == "invalid_token_header"

    @patch('app.auth.jwt_verifier.get_settings')
    def test_verify_token_success(self, mock_settings):
        """测试成功验证 JWT。"""
        # 模拟配置
        mock_settings.return_value = Mock(
            supabase_jwks_url=None,
            supabase_jwk='{"kty":"RSA","kid":"test","use":"sig","alg":"RS256","n":"test","e":"AQAB"}',
            jwks_cache_ttl_seconds=900,
            http_timeout_seconds=10.0,
            required_audience="test-audience",
            supabase_audience=None,
            supabase_project_id=None,
            supabase_issuer="https://test.supabase.co",
            allowed_issuers=[],
            token_leeway_seconds=30
        )
        
        # 创建测试 JWT
        payload = {
            "iss": "https://test.supabase.co",
            "sub": "test-user-123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "nbf": int(time.time())
        }
        
        # 这里需要用实际的私钥签名，但为了测试简化，我们mock掉验证过程
        with patch('jwt.decode') as mock_decode:
            mock_decode.return_value = payload
            
            verifier = JWTVerifier()
            result = verifier.verify_token("mock.jwt.token")
            
            assert isinstance(result, AuthenticatedUser)
            assert result.uid == "test-user-123"
            assert result.claims == payload


class TestInMemoryProvider:
    """内存 Provider 测试。"""

    def test_get_user_details(self):
        """测试获取用户详情。"""
        provider = InMemoryProvider()
        user_details = provider.get_user_details("test-uid")
        
        assert isinstance(user_details, UserDetails)
        assert user_details.uid == "test-uid"

    def test_sync_chat_record(self):
        """测试同步聊天记录。"""
        provider = InMemoryProvider()
        record = {
            "message_id": "msg-123",
            "user_id": "user-123",
            "user_message": "Hello",
            "ai_reply": "Hi there!"
        }
        
        provider.sync_chat_record(record)
        assert len(provider.records) == 1
        assert provider.records[0] == record


class TestAPIEndpoints:
    """API 端点测试。"""

    @pytest.fixture
    def client(self):
        """测试客户端。"""
        return TestClient(app)

    @pytest.fixture
    def mock_auth_user(self):
        """模拟认证用户。"""
        return AuthenticatedUser(
            uid="test-user-123",
            claims={"sub": "test-user-123", "email": "test@example.com"}
        )

    def test_create_message_unauthorized(self, client):
        """测试未授权访问消息创建端点。"""
        response = client.post("/api/v1/messages", json={"text": "Hello"})
        assert response.status_code == 401

    @patch('app.auth.dependencies.get_jwt_verifier')
    def test_create_message_success(self, mock_get_verifier, client, mock_auth_user):
        """测试成功创建消息。"""
        # Mock JWT 验证
        mock_verifier = Mock()
        mock_verifier.verify_token.return_value = mock_auth_user
        mock_get_verifier.return_value = mock_verifier
        
        headers = {"Authorization": "Bearer mock-jwt-token"}
        response = client.post(
            "/api/v1/messages",
            json={"text": "Hello AI", "conversation_id": "conv-123"},
            headers=headers
        )
        
        assert response.status_code == 202
        data = response.json()
        assert "message_id" in data
        assert len(data["message_id"]) > 0

    @patch('app.auth.dependencies.get_jwt_verifier')
    def test_stream_message_events_not_found(self, mock_get_verifier, client, mock_auth_user):
        """测试访问不存在的消息事件流。"""
        # Mock JWT 验证
        mock_verifier = Mock()
        mock_verifier.verify_token.return_value = mock_auth_user
        mock_get_verifier.return_value = mock_verifier
        
        headers = {"Authorization": "Bearer mock-jwt-token"}
        response = client.get("/api/v1/messages/nonexistent/events", headers=headers)
        
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__])
