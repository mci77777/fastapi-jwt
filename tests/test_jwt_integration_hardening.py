"""JWT验证器硬化功能的集成测试。"""
import json
import time
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app import app


class TestJWTHardeningIntegration:
    """JWT验证器硬化功能的端到端集成测试。"""

    @pytest.fixture
    def client(self):
        """测试客户端。"""
        return TestClient(app)

    @pytest.fixture
    def mock_hardened_settings(self):
        """模拟硬化配置。"""
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
            # 硬化配置
            jwt_clock_skew_seconds=120,
            jwt_max_future_iat_seconds=120,
            jwt_require_nbf=False,
            jwt_allowed_algorithms=["ES256", "RS256"]
        )

    def test_api_endpoint_with_supabase_jwt_no_nbf(self, client, mock_hardened_settings):
        """测试API端点接受无nbf的Supabase JWT。"""
        # 模拟无nbf的Supabase JWT payload
        payload = {
            "iss": "https://test.supabase.co",
            "sub": "user-123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "email": "test@example.com",
            "role": "authenticated"
        }
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_hardened_settings):
            with patch('jwt.decode', return_value=payload):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI", "conversation_id": "conv-123"},
                    headers={"Authorization": "Bearer mock.supabase.jwt"}
                )
                
                assert response.status_code == 202
                data = response.json()
                assert "message_id" in data

    def test_api_endpoint_rejects_future_iat(self, client, mock_hardened_settings):
        """测试API端点拒绝iat过于未来的JWT。"""
        payload = {
            "iss": "https://test.supabase.co",
            "sub": "user-123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()) + 200,  # 200秒后签发
            "email": "test@example.com"
        }
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_hardened_settings):
            with patch('jwt.decode', return_value=payload):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI"},
                    headers={"Authorization": "Bearer future.iat.jwt"}
                )
                
                assert response.status_code == 401
                data = response.json()
                assert data["code"] == "iat_too_future"
                assert data["status"] == 401
                assert "trace_id" in data

    def test_api_endpoint_rejects_unsupported_algorithm(self, client, mock_hardened_settings):
        """测试API端点拒绝不支持的算法。"""
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_hardened_settings):
            with patch('jwt.get_unverified_header', return_value={"alg": "HS512", "kid": "test-kid"}):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI"},
                    headers={"Authorization": "Bearer unsupported.alg.jwt"}
                )
                
                assert response.status_code == 401
                data = response.json()
                assert data["code"] == "unsupported_alg"
                assert data["status"] == 401

    def test_api_endpoint_error_format_consistency(self, client, mock_hardened_settings):
        """测试API端点错误格式的一致性。"""
        test_cases = [
            # 缺失token
            {"headers": {}, "expected_code": "token_missing"},
            # 无效token
            {"headers": {"Authorization": "Bearer invalid"}, "expected_code": "invalid_token_header"},
            # 空token
            {"headers": {"Authorization": "Bearer "}, "expected_code": "token_missing"},
        ]
        
        for case in test_cases:
            with patch('app.auth.jwt_verifier.get_settings', return_value=mock_hardened_settings):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI"},
                    headers=case["headers"]
                )
                
                assert response.status_code == 401
                data = response.json()
                
                # 验证统一错误格式
                assert "status" in data
                assert "code" in data
                assert "message" in data
                assert "trace_id" in data
                assert data["status"] == 401
                
                if case["expected_code"]:
                    assert data["code"] == case["expected_code"]

    def test_trace_id_propagation_in_errors(self, client, mock_hardened_settings):
        """测试错误响应中trace_id的传播。"""
        custom_trace_id = "custom-trace-12345"
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_hardened_settings):
            response = client.post(
                "/api/v1/messages",
                json={"text": "Hello AI"},
                headers={
                    "Authorization": "Bearer invalid",
                    "x-trace-id": custom_trace_id
                }
            )
            
            assert response.status_code == 401
            data = response.json()
            assert data["trace_id"] == custom_trace_id

    def test_clock_skew_tolerance_integration(self, client, mock_hardened_settings):
        """测试时钟偏移容忍度的集成测试。"""
        # 测试在容忍范围内的时钟偏移
        payload = {
            "iss": "https://test.supabase.co",
            "sub": "user-123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()) + 100,  # 100秒未来，在120秒容忍范围内
            "email": "test@example.com"
        }
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_hardened_settings):
            with patch('jwt.decode', return_value=payload):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI"},
                    headers={"Authorization": "Bearer skewed.time.jwt"}
                )
                
                assert response.status_code == 202

    def test_nbf_optional_but_validated_when_present(self, client, mock_hardened_settings):
        """测试nbf可选但存在时会被验证。"""
        # 测试nbf存在且有效的情况
        valid_nbf_payload = {
            "iss": "https://test.supabase.co",
            "sub": "user-123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "nbf": int(time.time()) - 10,  # 10秒前生效
            "email": "test@example.com"
        }
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_hardened_settings):
            with patch('jwt.decode', return_value=valid_nbf_payload):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI"},
                    headers={"Authorization": "Bearer valid.nbf.jwt"}
                )
                
                assert response.status_code == 202

        # 测试nbf无效的情况
        invalid_nbf_payload = valid_nbf_payload.copy()
        invalid_nbf_payload["nbf"] = int(time.time()) + 200  # 200秒后生效
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_hardened_settings):
            with patch('jwt.decode', return_value=invalid_nbf_payload):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI"},
                    headers={"Authorization": "Bearer invalid.nbf.jwt"}
                )
                
                assert response.status_code == 401
                data = response.json()
                assert data["code"] == "token_not_yet_valid"

    def test_es256_algorithm_preference(self, client, mock_hardened_settings):
        """测试ES256算法的优先支持。"""
        payload = {
            "iss": "https://test.supabase.co",
            "sub": "user-123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "email": "test@example.com"
        }
        
        with patch('app.auth.jwt_verifier.get_settings', return_value=mock_hardened_settings):
            with patch('jwt.get_unverified_header', return_value={"alg": "ES256", "kid": "test-kid"}):
                with patch('jwt.decode', return_value=payload):
                    response = client.post(
                        "/api/v1/messages",
                        json={"text": "Hello AI"},
                        headers={"Authorization": "Bearer es256.jwt"}
                    )
                    
                    assert response.status_code == 202

    def test_comprehensive_error_scenarios(self, client, mock_hardened_settings):
        """测试各种错误场景的综合测试。"""
        error_scenarios = [
            {
                "name": "missing_issuer",
                "payload": {"sub": "user-123", "aud": "test-audience", "exp": int(time.time()) + 3600, "iat": int(time.time())},
                "expected_code": "issuer_not_allowed"
            },
            {
                "name": "missing_subject", 
                "payload": {"iss": "https://test.supabase.co", "aud": "test-audience", "exp": int(time.time()) + 3600, "iat": int(time.time())},
                "expected_code": "subject_missing"
            },
            {
                "name": "wrong_issuer",
                "payload": {"iss": "https://malicious.com", "sub": "user-123", "aud": "test-audience", "exp": int(time.time()) + 3600, "iat": int(time.time())},
                "expected_code": "issuer_not_allowed"
            }
        ]
        
        for scenario in error_scenarios:
            with patch('app.auth.jwt_verifier.get_settings', return_value=mock_hardened_settings):
                with patch('jwt.decode', return_value=scenario["payload"]):
                    response = client.post(
                        "/api/v1/messages",
                        json={"text": "Hello AI"},
                        headers={"Authorization": f"Bearer {scenario['name']}.jwt"}
                    )
                    
                    assert response.status_code == 401, f"Scenario {scenario['name']} should return 401"
                    data = response.json()
                    assert data["code"] == scenario["expected_code"], f"Scenario {scenario['name']} should have code {scenario['expected_code']}"
                    assert "trace_id" in data
                    assert data["status"] == 401


if __name__ == "__main__":
    pytest.main([__file__])
