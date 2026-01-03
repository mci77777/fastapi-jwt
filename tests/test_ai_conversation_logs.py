"""测试 AI 对话日志记录功能。"""

import json
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from app.db.sqlite_manager import SQLiteManager
from app.auth.provider import UserDetails
from app.services.ai_service import AIMessageInput, AIService, MessageEventBroker

# 配置 pytest-asyncio
pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def sqlite_manager(tmp_path):
    """创建临时 SQLite 数据库。"""
    db_path = tmp_path / "test.db"
    manager = SQLiteManager(db_path)
    await manager.init()
    yield manager
    await manager.close()


@pytest.fixture
def mock_supabase_provider():
    """Mock Supabase provider。"""
    provider = MagicMock()
    provider.get_user_details.return_value = UserDetails(uid="test-user-123", email="test@example.com")
    provider.sync_chat_record = MagicMock()
    return provider


@pytest_asyncio.fixture
async def ai_service(sqlite_manager, mock_supabase_provider):
    """创建 AIService 实例。"""
    return AIService(provider=mock_supabase_provider, db_manager=sqlite_manager)


async def test_log_conversation_success(sqlite_manager):
    """测试成功记录对话日志。"""
    request_payload = {
        "message_id": "msg-123",
        "user_id": "user-456",
        "text": "Hello AI",
        "model": "gpt-4o",
    }
    response_payload = {
        "message_id": "msg-123",
        "reply": "Hello! How can I help you?",
    }

    await sqlite_manager.log_conversation(
        user_id="user-456",
        message_id="msg-123",
        request_id=None,
        request_payload=json.dumps(request_payload),
        response_payload=json.dumps(response_payload),
        model_used="gpt-4o",
        latency_ms=250,
        status="success",
        error_message=None,
    )

    # 验证记录已保存
    logs = await sqlite_manager.get_conversation_logs(limit=10)
    assert len(logs) == 1
    assert logs[0]["user_id"] == "user-456"
    assert logs[0]["message_id"] == "msg-123"
    assert logs[0]["model_used"] == "gpt-4o"
    assert logs[0]["latency_ms"] == 250
    assert logs[0]["status"] == "success"
    assert logs[0]["error_message"] is None

    # 验证 payload 可以解析
    req = json.loads(logs[0]["request_payload"])
    assert req["text"] == "Hello AI"
    resp = json.loads(logs[0]["response_payload"])
    assert resp["reply"] == "Hello! How can I help you?"


async def test_log_conversation_error(sqlite_manager):
    """测试记录错误对话日志。"""
    request_payload = {
        "message_id": "msg-789",
        "user_id": "user-456",
        "text": "Test error",
    }

    await sqlite_manager.log_conversation(
        user_id="user-456",
        message_id="msg-789",
        request_id=None,
        request_payload=json.dumps(request_payload),
        response_payload=None,
        model_used=None,
        latency_ms=100,
        status="error",
        error_message="API rate limit exceeded",
    )

    logs = await sqlite_manager.get_conversation_logs(limit=10)
    assert len(logs) == 1
    assert logs[0]["status"] == "error"
    assert logs[0]["error_message"] == "API rate limit exceeded"
    assert logs[0]["response_payload"] is None


async def test_circular_buffer_maintains_100_records(sqlite_manager):
    """测试循环缓冲区维护最多 100 条记录。"""
    # 插入 105 条记录
    for i in range(105):
        await sqlite_manager.log_conversation(
            user_id=f"user-{i}",
            message_id=f"msg-{i}",
            request_id=None,
            request_payload=json.dumps({"text": f"Message {i}"}),
            response_payload=json.dumps({"reply": f"Reply {i}"}),
            model_used="gpt-4o-mini",
            latency_ms=100 + i,
            status="success",
            error_message=None,
        )

    # 验证只保留最新的 100 条
    logs = await sqlite_manager.get_conversation_logs(limit=200)
    assert len(logs) == 100

    # 验证保留的是最新的记录（msg-5 到 msg-104）
    message_ids = [log["message_id"] for log in logs]
    assert "msg-0" not in message_ids  # 最早的 5 条应该被删除
    assert "msg-4" not in message_ids
    assert "msg-5" in message_ids  # 从第 6 条开始保留
    assert "msg-104" in message_ids  # 最新的记录


async def test_get_conversation_logs_limit(sqlite_manager):
    """测试获取日志的 limit 参数。"""
    # 插入 50 条记录
    for i in range(50):
        await sqlite_manager.log_conversation(
            user_id=f"user-{i}",
            message_id=f"msg-{i}",
            request_id=None,
            request_payload=json.dumps({"text": f"Message {i}"}),
            response_payload=json.dumps({"reply": f"Reply {i}"}),
            model_used="gpt-4o-mini",
            latency_ms=100,
            status="success",
            error_message=None,
        )

    # 测试不同的 limit 值
    logs_10 = await sqlite_manager.get_conversation_logs(limit=10)
    assert len(logs_10) == 10

    logs_25 = await sqlite_manager.get_conversation_logs(limit=25)
    assert len(logs_25) == 25

    logs_all = await sqlite_manager.get_conversation_logs(limit=100)
    assert len(logs_all) == 50  # 只有 50 条记录


async def test_ai_service_logs_conversation(ai_service, sqlite_manager, mock_supabase_provider):
    """测试 AIService 在 run_conversation 中记录日志。"""
    from app.auth import AuthenticatedUser

    request_payload = json.dumps(
        {
            "conversation_id": "conv-123",
            "text": "Hello AI",
            "model": "gpt-4o",
            "messages": [
                {"role": "system", "content": "You are GymBro's AI assistant."},
                {"role": "user", "content": "Hello AI"},
            ],
        },
        ensure_ascii=False,
    )
    response_payload = json.dumps(
        {"choices": [{"message": {"content": "This is a test reply from AI"}}]},
        ensure_ascii=False,
    )

    with patch.object(
        ai_service,
        "_generate_reply",
        return_value=("This is a test reply from AI", "gpt-4o", request_payload, response_payload, "up-req-1", None),
    ):
        user = AuthenticatedUser(uid="test-user-123", claims={}, user_type="permanent")

        message = AIMessageInput(text="Hello AI", conversation_id="conv-123", model="gpt-4o", metadata={"save_history": True})

        broker = MessageEventBroker()
        message_id = "msg-test-123"
        await broker.create_channel(message_id, owner_user_id="test-user-123", conversation_id="conv-123")

        await ai_service.run_conversation(message_id, user, message, broker)

        # 验证日志已记录
        logs = await sqlite_manager.get_conversation_logs(limit=10)
        assert len(logs) == 1
        assert logs[0]["user_id"] == "test-user-123"
        assert logs[0]["message_id"] == message_id
        assert logs[0]["model_used"] == "gpt-4o"
        assert logs[0]["status"] == "success"

        # 验证 request payload
        req = json.loads(logs[0]["request_payload"])
        assert req["text"] == "Hello AI"
        assert req["model"] == "gpt-4o"
        assert req["conversation_id"] == "conv-123"

        # 验证 response payload
        resp = json.loads(logs[0]["response_payload"])
        assert resp["choices"][0]["message"]["content"] == "This is a test reply from AI"


async def test_ai_service_logs_error(ai_service, sqlite_manager, mock_supabase_provider):
    """测试 AIService 在错误时记录日志。"""
    from app.auth import AuthenticatedUser

    with patch.object(ai_service, "_generate_reply", side_effect=Exception("API error")):
        user = AuthenticatedUser(uid="test-user-456", claims={}, user_type="permanent")
        message = AIMessageInput(text="Test error", conversation_id="conv-456", model="gpt-4o-mini", metadata={})

        broker = MessageEventBroker()
        message_id = "msg-error-123"
        await broker.create_channel(message_id, owner_user_id="test-user-456", conversation_id="conv-456")

        await ai_service.run_conversation(message_id, user, message, broker)

    logs = await sqlite_manager.get_conversation_logs(limit=10)
    assert len(logs) == 1
    assert logs[0]["status"] == "error"
    assert logs[0]["error_message"] is not None
    assert "API error" in logs[0]["error_message"]
    assert logs[0]["response_payload"] is None
