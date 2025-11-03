"""JWT 认证系统完整测试套件。

本文件整合了以下测试模块：
- test_jwt_auth.py: JWT 基础验证测试
- test_jwt_hardening.py: JWT 安全强化测试
- test_jwt_integration_hardening.py: JWT 集成测试

测试结构：
1. 基础验证测试 (TestJWTVerifier)
2. 安全强化测试 (TestJWTHardening)
3. 集成测试 (TestJWTHardeningIntegration)
4. Provider 测试 (TestInMemoryProvider)
5. API 端点测试 (TestAPIEndpoints)
6. 错误类测试 (TestJWTErrorClass)
"""

import time
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import app
from app.auth.jwt_verifier import AuthenticatedUser, JWTError, JWTVerifier
from app.auth.provider import InMemoryProvider, UserDetails

# ============================================================================
# 第一部分：基础验证测试
# ============================================================================


class TestJWTVerifier:
    """JWT 验证器基础测试。"""

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

    @patch("app.auth.jwt_verifier.get_settings")
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
            token_leeway_seconds=30,
        )

        # 创建测试 JWT
        payload = {
            "iss": "https://test.supabase.co",
            "sub": "test-user-123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "nbf": int(time.time()),
        }

        # Mock JWT 解码过程
        with patch("jwt.decode") as mock_decode:
            mock_decode.return_value = payload

            verifier = JWTVerifier()
            result = verifier.verify_token("mock.jwt.token")

            assert isinstance(result, AuthenticatedUser)
            assert result.uid == "test-user-123"
            assert result.claims == payload


# ============================================================================
# 第二部分：安全强化测试
# ============================================================================


class TestJWTHardening:
    """JWT 验证器安全强化功能测试。"""

    @pytest.fixture
    def mock_settings(self):
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
            jwt_allowed_algorithms=["ES256", "RS256", "HS256"],
        )

    @pytest.fixture
    def base_payload(self):
        """基础 JWT payload。"""
        now = int(time.time())
        return {
            "iss": "https://test.supabase.co",
            "sub": "test-user-123",
            "aud": "test-audience",
            "exp": now + 3600,
            "iat": now,
        }

    def test_supabase_jwt_without_nbf_success(self, mock_settings, base_payload):
        """测试 Supabase JWT 无 nbf 声明的兼容性。"""
        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
            with patch("jwt.decode", return_value=base_payload):
                verifier = JWTVerifier()
                result = verifier.verify_token("mock.jwt.token")

                assert result.uid == "test-user-123"
                assert result.claims == base_payload

    def test_jwt_with_nbf_success(self, mock_settings, base_payload):
        """测试包含 nbf 声明的 JWT 正常验证。"""
        payload_with_nbf = base_payload.copy()
        payload_with_nbf["nbf"] = int(time.time()) - 10  # 10秒前生效

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
            with patch("jwt.decode", return_value=payload_with_nbf):
                verifier = JWTVerifier()
                result = verifier.verify_token("mock.jwt.token")

                assert result.uid == "test-user-123"

    def test_iat_too_future_rejection(self, mock_settings, base_payload):
        """测试 iat 过于未来的 JWT 被拒绝。"""
        future_payload = base_payload.copy()
        future_payload["iat"] = int(time.time()) + 200  # 200秒后签发

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
            with patch("jwt.decode", return_value=future_payload):
                verifier = JWTVerifier()

                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")

                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "iat_too_future"
                assert "status" in exc_info.value.detail
                assert "trace_id" in exc_info.value.detail

    def test_nbf_future_rejection(self, mock_settings, base_payload):
        """测试 nbf 未来时间的 JWT 被拒绝。"""
        future_nbf_payload = base_payload.copy()
        future_nbf_payload["nbf"] = int(time.time()) + 200  # 200秒后生效

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
            with patch("jwt.decode", return_value=future_nbf_payload):
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

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
            with patch("jwt.decode", return_value=skewed_payload):
                verifier = JWTVerifier()
                result = verifier.verify_token("mock.jwt.token")

                assert result.uid == "test-user-123"

    def test_unsupported_algorithm_rejection(self, mock_settings, base_payload):
        """测试不支持的算法被拒绝。"""
        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
            with patch("jwt.get_unverified_header", return_value={"alg": "HS512", "kid": "test-kid"}):
                verifier = JWTVerifier()

                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")

                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "unsupported_alg"

    def test_missing_algorithm_rejection(self, mock_settings):
        """测试缺失算法的 JWT 被拒绝。"""
        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
            with patch("jwt.get_unverified_header", return_value={"kid": "test-kid"}):
                verifier = JWTVerifier()

                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")

                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "algorithm_missing"

    def test_invalid_issuer_rejection(self, mock_settings, base_payload):
        """测试无效签发者被拒绝。"""
        invalid_issuer_payload = base_payload.copy()
        invalid_issuer_payload["iss"] = "https://malicious.com"

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
            with patch("jwt.decode", return_value=invalid_issuer_payload):
                verifier = JWTVerifier()

                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")

                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "issuer_not_allowed"

    def test_missing_subject_rejection(self, mock_settings, base_payload):
        """测试缺失 subject 的 JWT 被拒绝。"""
        no_sub_payload = base_payload.copy()
        del no_sub_payload["sub"]

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
            with patch("jwt.decode", return_value=no_sub_payload):
                verifier = JWTVerifier()

                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")

                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "subject_missing"

    def test_jwks_key_not_found_rejection(self, mock_settings):
        """测试 JWKS 密钥未找到的情况。"""
        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
            with patch("jwt.get_unverified_header", return_value={"alg": "ES256", "kid": "unknown-kid"}):
                verifier = JWTVerifier()
                # Mock cache.get_key to raise exception
                verifier._cache.get_key = Mock(side_effect=RuntimeError("Key not found"))

                with pytest.raises(HTTPException) as exc_info:
                    verifier.verify_token("mock.jwt.token")

                assert exc_info.value.status_code == 401
                assert exc_info.value.detail["code"] == "jwks_key_not_found"

    def test_error_response_format(self, mock_settings):
        """测试错误响应格式的统一性。"""
        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
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

    @patch("app.auth.jwt_verifier.logger")
    def test_success_logging(self, mock_logger, mock_settings, base_payload):
        """测试成功验证的日志记录。"""
        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
            with patch("jwt.decode", return_value=base_payload):
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

    @patch("app.auth.jwt_verifier.logger")
    def test_failure_logging(self, mock_logger, mock_settings):
        """测试失败验证的日志记录。"""
        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_settings):
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


# ============================================================================
# 第三部分：集成测试
# ============================================================================


class TestJWTHardeningIntegration:
    """JWT 验证器硬化功能的端到端集成测试。"""

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
            jwt_allowed_algorithms=["ES256", "RS256"],
        )

    def test_api_endpoint_with_supabase_jwt_no_nbf(self, client, mock_hardened_settings):
        """测试 API 端点接受无 nbf 的 Supabase JWT。"""
        # 模拟无 nbf 的 Supabase JWT payload
        payload = {
            "iss": "https://test.supabase.co",
            "sub": "user-123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "email": "test@example.com",
            "role": "authenticated",
        }

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_hardened_settings):
            with patch("jwt.decode", return_value=payload):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI", "conversation_id": "conv-123"},
                    headers={"Authorization": "Bearer mock.supabase.jwt"},
                )

                assert response.status_code == 202
                data = response.json()
                assert "message_id" in data

    def test_api_endpoint_rejects_future_iat(self, client, mock_hardened_settings):
        """测试 API 端点拒绝 iat 过于未来的 JWT。"""
        payload = {
            "iss": "https://test.supabase.co",
            "sub": "user-123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()) + 200,  # 200秒后签发
            "email": "test@example.com",
        }

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_hardened_settings):
            with patch("jwt.decode", return_value=payload):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI"},
                    headers={"Authorization": "Bearer future.iat.jwt"},
                )

                assert response.status_code == 401
                data = response.json()
                assert data["code"] == "iat_too_future"
                assert data["status"] == 401
                assert "trace_id" in data

    def test_api_endpoint_rejects_unsupported_algorithm(self, client, mock_hardened_settings):
        """测试 API 端点拒绝不支持的算法。"""
        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_hardened_settings):
            with patch("jwt.get_unverified_header", return_value={"alg": "HS512", "kid": "test-kid"}):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI"},
                    headers={"Authorization": "Bearer unsupported.alg.jwt"},
                )

                assert response.status_code == 401
                data = response.json()
                assert data["code"] == "unsupported_alg"
                assert data["status"] == 401

    def test_api_endpoint_error_format_consistency(self, client, mock_hardened_settings):
        """测试 API 端点错误格式的一致性。"""
        test_cases = [
            # 缺失 token
            {"headers": {}, "expected_code": "token_missing"},
            # 无效 token
            {"headers": {"Authorization": "Bearer invalid"}, "expected_code": "invalid_token_header"},
            # 空 token
            {"headers": {"Authorization": "Bearer "}, "expected_code": "token_missing"},
        ]

        for case in test_cases:
            with patch("app.auth.jwt_verifier.get_settings", return_value=mock_hardened_settings):
                response = client.post("/api/v1/messages", json={"text": "Hello AI"}, headers=case["headers"])

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
        """测试错误响应中 trace_id 的传播。"""
        custom_trace_id = "custom-trace-12345"

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_hardened_settings):
            response = client.post(
                "/api/v1/messages",
                json={"text": "Hello AI"},
                headers={"Authorization": "Bearer invalid", "x-trace-id": custom_trace_id},
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
            "email": "test@example.com",
        }

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_hardened_settings):
            with patch("jwt.decode", return_value=payload):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI"},
                    headers={"Authorization": "Bearer skewed.time.jwt"},
                )

                assert response.status_code == 202

    def test_nbf_optional_but_validated_when_present(self, client, mock_hardened_settings):
        """测试 nbf 可选但存在时会被验证。"""
        # 测试 nbf 存在且有效的情况
        valid_nbf_payload = {
            "iss": "https://test.supabase.co",
            "sub": "user-123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "nbf": int(time.time()) - 10,  # 10秒前生效
            "email": "test@example.com",
        }

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_hardened_settings):
            with patch("jwt.decode", return_value=valid_nbf_payload):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI"},
                    headers={"Authorization": "Bearer valid.nbf.jwt"},
                )

                assert response.status_code == 202

        # 测试 nbf 无效的情况
        invalid_nbf_payload = valid_nbf_payload.copy()
        invalid_nbf_payload["nbf"] = int(time.time()) + 200  # 200秒后生效

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_hardened_settings):
            with patch("jwt.decode", return_value=invalid_nbf_payload):
                response = client.post(
                    "/api/v1/messages",
                    json={"text": "Hello AI"},
                    headers={"Authorization": "Bearer invalid.nbf.jwt"},
                )

                assert response.status_code == 401
                data = response.json()
                assert data["code"] == "token_not_yet_valid"

    def test_es256_algorithm_preference(self, client, mock_hardened_settings):
        """测试 ES256 算法的优先支持。"""
        payload = {
            "iss": "https://test.supabase.co",
            "sub": "user-123",
            "aud": "test-audience",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "email": "test@example.com",
        }

        with patch("app.auth.jwt_verifier.get_settings", return_value=mock_hardened_settings):
            with patch("jwt.get_unverified_header", return_value={"alg": "ES256", "kid": "test-kid"}):
                with patch("jwt.decode", return_value=payload):
                    response = client.post(
                        "/api/v1/messages",
                        json={"text": "Hello AI"},
                        headers={"Authorization": "Bearer es256.jwt"},
                    )

                    assert response.status_code == 202

    def test_comprehensive_error_scenarios(self, client, mock_hardened_settings):
        """测试各种错误场景的综合测试。"""
        error_scenarios = [
            {
                "name": "missing_issuer",
                "payload": {
                    "sub": "user-123",
                    "aud": "test-audience",
                    "exp": int(time.time()) + 3600,
                    "iat": int(time.time()),
                },
                "expected_code": "issuer_not_allowed",
            },
            {
                "name": "missing_subject",
                "payload": {
                    "iss": "https://test.supabase.co",
                    "aud": "test-audience",
                    "exp": int(time.time()) + 3600,
                    "iat": int(time.time()),
                },
                "expected_code": "subject_missing",
            },
            {
                "name": "wrong_issuer",
                "payload": {
                    "iss": "https://malicious.com",
                    "sub": "user-123",
                    "aud": "test-audience",
                    "exp": int(time.time()) + 3600,
                    "iat": int(time.time()),
                },
                "expected_code": "issuer_not_allowed",
            },
        ]

        for scenario in error_scenarios:
            with patch("app.auth.jwt_verifier.get_settings", return_value=mock_hardened_settings):
                with patch("jwt.decode", return_value=scenario["payload"]):
                    response = client.post(
                        "/api/v1/messages",
                        json={"text": "Hello AI"},
                        headers={"Authorization": f"Bearer {scenario['name']}.jwt"},
                    )

                    assert response.status_code == 401, f"Scenario {scenario['name']} should return 401"
                    data = response.json()
                    assert (
                        data["code"] == scenario["expected_code"]
                    ), f"Scenario {scenario['name']} should have code {scenario['expected_code']}"
                    assert "trace_id" in data
                    assert data["status"] == 401


# ============================================================================
# 第四部分：Provider 测试
# ============================================================================


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
            "ai_reply": "Hi there!",
        }

        provider.sync_chat_record(record)
        assert len(provider.records) == 1
        assert provider.records[0] == record


# ============================================================================
# 第五部分：API 端点测试
# ============================================================================


class TestAPIEndpoints:
    """API 端点测试。"""

    @pytest.fixture
    def client(self):
        """测试客户端。"""
        return TestClient(app)

    @pytest.fixture
    def mock_auth_user(self):
        """模拟认证用户。"""
        return AuthenticatedUser(uid="test-user-123", claims={"sub": "test-user-123", "email": "test@example.com"})

    def test_create_message_unauthorized(self, client):
        """测试未授权访问消息创建端点。"""
        response = client.post("/api/v1/messages", json={"text": "Hello"})
        assert response.status_code == 401

    @patch("app.auth.dependencies.get_jwt_verifier")
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
            headers=headers,
        )

        assert response.status_code == 202
        data = response.json()
        assert "message_id" in data
        assert len(data["message_id"]) > 0

    @patch("app.auth.dependencies.get_jwt_verifier")
    def test_stream_message_events_not_found(self, mock_get_verifier, client, mock_auth_user):
        """测试访问不存在的消息事件流。"""
        # Mock JWT 验证
        mock_verifier = Mock()
        mock_verifier.verify_token.return_value = mock_auth_user
        mock_get_verifier.return_value = mock_verifier

        headers = {"Authorization": "Bearer mock-jwt-token"}
        response = client.get("/api/v1/messages/nonexistent/events", headers=headers)

        assert response.status_code == 404


# ============================================================================
# 第六部分：错误类测试
# ============================================================================


class TestJWTErrorClass:
    """JWT 错误类测试。"""

    def test_jwt_error_to_dict(self):
        """测试 JWT 错误转换为字典。"""
        error = JWTError(
            status=401,
            code="test_error",
            message="Test message",
            trace_id="trace-123",
            hint="Test hint",
        )

        result = error.to_dict()
        expected = {
            "status": 401,
            "code": "test_error",
            "message": "Test message",
            "trace_id": "trace-123",
            "hint": "Test hint",
        }

        assert result == expected

    def test_jwt_error_to_dict_minimal(self):
        """测试 JWT 错误最小字段转换。"""
        error = JWTError(status=401, code="test_error", message="Test message")

        result = error.to_dict()
        expected = {"status": 401, "code": "test_error", "message": "Test message"}

        assert result == expected


if __name__ == "__main__":
    pytest.main([__file__])
