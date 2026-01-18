"""测试请求追踪数据库功能。"""
import pytest
import pytest_asyncio
from app.db.sqlite_manager import SQLiteManager
from pathlib import Path
import tempfile
import json


@pytest_asyncio.fixture
async def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        manager = SQLiteManager(db_path)
        await manager.init()
        yield manager
        await manager.close()


@pytest.mark.asyncio
async def test_conversation_logs_has_detailed_columns(db):
    """测试 conversation_logs 表包含详细追踪字段。"""
    cursor = await db._conn.execute("PRAGMA table_info(conversation_logs)")
    columns = {row[1]: row[2] for row in await cursor.fetchall()}

    # 验证新增字段存在
    assert "request_detail_json" in columns, "缺少 request_detail_json 字段"
    assert "response_detail_json" in columns, "缺少 response_detail_json 字段"
    assert "conversation_id" in columns, "缺少 conversation_id 字段"


@pytest.mark.asyncio
async def test_insert_conversation_log_with_details(db):
    """测试插入带详细信息的对话日志。"""
    request_detail = {
        "text": "测试请求",
        "model": "gpt-4",
        "metadata": {"source": "app"}
    }
    response_detail = {
        "reply": "测试响应",
        "usage": {"prompt_tokens": 10, "completion_tokens": 20}
    }

    await db._conn.execute(
        """INSERT INTO conversation_logs
           (user_id, message_id, request_id, conversation_id,
            request_detail_json, response_detail_json,
            model_used, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            "user123", "msg123", "req123", "conv123",
            json.dumps(request_detail), json.dumps(response_detail),
            "gpt-4", "completed"
        )
    )
    await db._conn.commit()

    cursor = await db._conn.execute(
        "SELECT * FROM conversation_logs WHERE message_id = ?",
        ("msg123",)
    )
    row = await cursor.fetchone()
    assert row is not None
    assert json.loads(row["request_detail_json"]) == request_detail
    assert json.loads(row["response_detail_json"]) == response_detail
