"""测试请求追踪配置功能。"""
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
async def test_get_tracing_config_default(db):
    """测试获取默认追踪配置（默认关闭）。"""
    enabled = await db.get_tracing_enabled()
    assert enabled is False, "默认应关闭请求追踪"


@pytest.mark.asyncio
async def test_set_tracing_config(db):
    """测试设置追踪配置。"""
    await db.set_tracing_enabled(True)
    enabled = await db.get_tracing_enabled()
    assert enabled is True, "追踪开关应设置为开启"

    await db.set_tracing_enabled(False)
    enabled = await db.get_tracing_enabled()
    assert enabled is False, "追踪开关应设置为关闭"
