"""JWT验证器硬化功能的回归测试。"""
import json
import time
from unittest.mock import Mock, patch
from typing import Dict, Any

import jwt
import pytest
from fastapi import HTTPException

from app.auth.jwt_verifier import JWTVerifier, JWTError


class TestJWTHardening:
    """JWT验证器硬化功能测试。"""

    @pytest.fixture
    def mock_settings(self):
        """模拟配置。"""
        return Mock(
            supabase_jwks_url=None,
            supabase_jwk='{"kty":"RSA","kid":"test-kid","use":"sig","alg":"ES256","n":"test","e":"AQAB"}',
            jwks_cache_ttl_seconds=900,
            http_timeout_seconds=10.0,
            required_audience="test-audience",
            supabase_audience=None,
            supabase_project_id=None,
            supabase_issuer="https://test.supabase.co",
            allowed_issuers=[],
            token_leeway_seconds=30,
            # 新的硬化配置
            jwt_clock_skew_seconds=120,
            jwt_max_future_iat_seconds=120,
            jwt_require_nbf=False,
            jwt_allowed_algorithms=["ES256", "RS256", "HS256"]
        )

    @pytest.fixture
    def base_payload(self):
        """基础JWT payload。"""
        now = int(time.time())
        return {
            "iss": "https://test.supabase.co",
            "sub": "test-user-123",
            "aud": "test-audience",
            "exp": now + 3600,
            "iat": now,
        }

    def test_supabase_jwt_without_nbf_success(self, mock_settings, base_payload):
        """测试Supabase JWT无nbf声明的兼容性。"""
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            with patch('jwt.decode', return_value=base_payload):
                verifier = JWTVerifier()
                result = verifier.verify_token("mock.jwt.token")
                
                assert result.uid == "test-user-123"
                assert result.claims == base_payload

    def test_jwt_with_nbf_success(self, mock_settings, base_payload):
        """测试包含nbf声明的JWT正常验证。"""
        payload_with_nbf = base_payload.copy()
        payload_with_nbf["nbf"] = int(time.time()) - 10  # 10秒前生效
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            with patch('jwt.decode', return_value=payload_with_nbf):
                verifier = JWTVerifier()
                result = verifier.verify_token("mock.jwt.token")
                
                assert result.uid == "test-user-123"

    def test_iat_too_future_rejection(self, mock_settings, base_payload):
        """测试iat过于未来的JWT被拒绝。"""
        future_payload = base_payload.copy()
        future_payload["iat"] = int(time.time()) + 200  # 200秒后签发
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            with patch('jwt.decode', return_value=future_payload):
                verifier = JWTVerifier()
                
                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")
                
                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "iat_too_future"
                assert "status" in exc_info.value.detail
                assert "trace_id" in exc_info.value.detail

    def test_nbf_future_rejection(self, mock_settings, base_payload):
        """测试nbf未来时间的JWT被拒绝。"""
        future_nbf_payload = base_payload.copy()
        future_nbf_payload["nbf"] = int(time.time()) + 200  # 200秒后生效
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            with patch('jwt.decode', return_value=future_nbf_payload):
                verifier = JWTVerifier()
                
                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")
                
                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "token_not_yet_valid"

    def test_clock_skew_tolerance(self, mock_settings, base_payload):
        """测试时钟偏移容忍度。"""
        # 测试在允许范围内的时钟偏移
        skewed_payload = base_payload.copy()
        skewed_payload["iat"] = int(time.time()) + 100  # 100秒未来，在120秒容忍范围内
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            with patch('jwt.decode', return_value=skewed_payload):
                verifier = JWTVerifier()
                result = verifier.verify_token("mock.jwt.token")
                
                assert result.uid == "test-user-123"

    def test_unsupported_algorithm_rejection(self, mock_settings, base_payload):
        """测试不支持的算法被拒绝。"""
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            with patch('jwt.get_unverified_header', return_value={"alg": "HS512", "kid": "test-kid"}):
                verifier = JWTVerifier()
                
                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")
                
                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "unsupported_alg"

    def test_missing_algorithm_rejection(self, mock_settings):
        """测试缺失算法的JWT被拒绝。"""
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            with patch('jwt.get_unverified_header', return_value={"kid": "test-kid"}):
                verifier = JWTVerifier()
                
                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")
                
                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "algorithm_missing"

    def test_invalid_issuer_rejection(self, mock_settings, base_payload):
        """测试无效签发者被拒绝。"""
        invalid_issuer_payload = base_payload.copy()
        invalid_issuer_payload["iss"] = "https://malicious.com"
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            with patch('jwt.decode', return_value=invalid_issuer_payload):
                verifier = JWTVerifier()
                
                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")
                
                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "issuer_not_allowed"

    def test_missing_subject_rejection(self, mock_settings, base_payload):
        """测试缺失subject的JWT被拒绝。"""
        no_sub_payload = base_payload.copy()
        del no_sub_payload["sub"]
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            with patch('jwt.decode', return_value=no_sub_payload):
                verifier = JWTVerifier()
                
                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")
                
                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "subject_missing"

    def test_jwks_key_not_found_rejection(self, mock_settings):
        """测试JWKS密钥未找到的情况。"""
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            with patch('jwt.get_unverified_header', return_value={"alg": "ES256", "kid": "unknown-kid"}):
                verifier = JWTVerifier()
                # Mock cache.get_key to raise exception
                verifier._cache.get_key = Mock(side_effect=RuntimeError("Key not found"))
                
                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")
                
                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "jwks_key_not_found"

    def test_error_response_format(self, mock_settings):
        """测试错误响应格式的统一性。"""
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            verifier = JWTVerifier()
            
            with pytest.raises(HTTPException) as exc_info:
                verifier.verify_token("")
            
            detail = exc_info.value.detail
            assert "status" in detail
            assert "code" in detail
            assert "message" in detail
            assert "trace_id" in detail
            assert detail["status"] == 401
            assert detail["code"] == "token_missing"

    @patch('app.auth.jwt_verifier.logger')
    def test_success_logging(self, mock_logger, mock_settings, base_payload):
        """测试成功验证的日志记录。"""
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            with patch('jwt.decode', return_value=base_payload):
                verifier = JWTVerifier()
                verifier.verify_token("mock.jwt.token")
                
                # 验证成功日志被调用
                mock_logger.info.assert_called_once()
                call_args = mock_logger.info.call_args
                assert "JWT verification successful" in call_args[0]
                assert "extra" in call_args[1]
                extra = call_args[1]["extra"]
                assert extra["subject"] == "test-user-123"
                assert extra["event"] == "jwt_verification_success"

    @patch('app.auth.jwt_verifier.logger')
    def test_failure_logging(self, mock_logger, mock_settings):
        """测试失败验证的日志记录。"""
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_settings):
            verifier = JWTVerifier()
            
            try:
                verifier.verify_token("")
            except HTTPException:
                pass
            
            # 验证失败日志被调用
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "JWT verification failed" in call_args[0]
            assert "extra" in call_args[1]
            extra = call_args[1]["extra"]
            assert extra["code"] == "token_missing"
            assert extra["event"] == "jwt_verification_failure"


class TestJWTErrorClass:
    """JWT错误类测试。"""

    def test_jwt_error_to_dict(self):
        """测试JWT错误转换为字典。"""
        error = JWTError(
            status=401,
            code="test_error",
            message="Test message",
            trace_id="trace-123",
            hint="Test hint"
        )
        
        result = error.to_dict()
        expected = {
            "status": 401,
            "code": "test_error",
            "message": "Test message",
            "trace_id": "trace-123",
            "hint": "Test hint"
        }
        
        assert result == expected

    def test_jwt_error_to_dict_minimal(self):
        """测试JWT错误最小字段转换。"""
        error = JWTError(
            status=401,
            code="test_error",
            message="Test message"
        )
        
        result = error.to_dict()
        expected = {
            "status": 401,
            "code": "test_error",
            "message": "Test message"
        }
        
        assert result == expected


if __name__ == "__main__":
    pytest.main([__file__])
