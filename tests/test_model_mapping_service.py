from pathlib import Path

import pytest

from app.db import SQLiteManager
from app.services.model_mapping_service import ModelMappingService


class FakeAIConfigService:
    def __init__(self) -> None:
        self.prompts = [
            {
                "id": 1,
                "name": "Test Prompt",
                "version": "v1",
                "category": "general",
                "tools_json": {},
            }
        ]
        self.updated_payload: dict[int, dict[str, object]] = {}

    async def list_prompts(self, *, page: int, page_size: int, **_: object):
        return self.prompts, len(self.prompts)

    async def get_prompt(self, prompt_id: int) -> dict[str, object]:
        for prompt in self.prompts:
            if prompt["id"] == prompt_id:
                return prompt
        raise ValueError("prompt_not_found")

    async def update_prompt(self, prompt_id: int, payload: dict[str, object]) -> None:
        self.updated_payload[prompt_id] = payload
        for prompt in self.prompts:
            if prompt["id"] == prompt_id:
                prompt.update(payload)
                break


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def _new_service(tmp_path: Path) -> tuple[ModelMappingService, FakeAIConfigService, SQLiteManager]:
    ai_service = FakeAIConfigService()
    db = SQLiteManager(tmp_path / "db.sqlite3")
    await db.init()
    return ModelMappingService(ai_service, db, tmp_path), ai_service, db


@pytest.mark.anyio("asyncio")
async def test_list_mappings(tmp_path: Path) -> None:
    """测试映射列表查询功能"""
    service, ai_service, db = await _new_service(tmp_path)
    try:
        # 创建 prompt 映射
        await service.upsert_mapping(
            {
                "scope_type": "prompt",
                "scope_key": "1",
                "name": "Test Prompt",
                "default_model": "gpt-4o-mini",
                "candidates": ["gpt-4o-mini", "gpt-4o"],
                "is_active": True,
                "metadata": {"env": "test"},
            }
        )

        # 创建 fallback 映射
        await service.upsert_mapping(
            {
                "scope_type": "module",
                "scope_key": "chat",
                "name": "Chat Module",
                "default_model": "gpt-3.5-turbo",
                "candidates": ["gpt-3.5-turbo"],
                "is_active": True,
                "metadata": {},
            }
        )

        # 测试列出所有映射
        all_items = await service.list_mappings()
        assert len(all_items) == 2

        # 测试按 scope_type 过滤
        prompt_items = await service.list_mappings(scope_type="prompt")
        assert len(prompt_items) == 1
        assert prompt_items[0]["scope_type"] == "prompt"
        assert prompt_items[0]["scope_key"] == "1"
        assert prompt_items[0]["source"] == "prompt"

        # 测试按 scope_key 过滤
        chat_items = await service.list_mappings(scope_key="chat")
        assert len(chat_items) == 1
        assert chat_items[0]["scope_type"] == "module"
        assert chat_items[0]["scope_key"] == "chat"
        assert chat_items[0]["source"] == "sqlite"
    finally:
        await db.close()


@pytest.mark.anyio("asyncio")
async def test_upsert_mapping(tmp_path: Path) -> None:
    """测试映射创建和更新功能"""
    service, ai_service, db = await _new_service(tmp_path)
    try:
        # 测试创建 prompt 映射
        result = await service.upsert_mapping(
            {
                "scope_type": "prompt",
                "scope_key": "1",
                "name": "Test Prompt",
                "default_model": "gpt-4o-mini",
                "candidates": ["gpt-4o-mini", "gpt-4o"],
                "is_active": True,
                "metadata": {"env": "test"},
            }
        )

        assert result["scope_type"] == "prompt"
        assert result["scope_key"] == "1"
        assert result["default_model"] == "gpt-4o-mini"
        assert set(result["candidates"]) == {"gpt-4o-mini", "gpt-4o"}
        assert result["is_active"] is True
        assert result["source"] == "prompt"

        # 验证 AI 服务中的数据
        assert 1 in ai_service.updated_payload
        stored_first = ai_service.updated_payload[1]["tools_json"]
        assert isinstance(stored_first, dict)
        assert stored_first["__model_mapping"]["default_model"] == "gpt-4o-mini"

        # 测试更新映射 (改变默认模型)
        updated_result = await service.upsert_mapping(
            {
                "scope_type": "prompt",
                "scope_key": "1",
                "name": "Test Prompt",
                "default_model": "gpt-4o",
                "candidates": ["gpt-4o-mini", "gpt-4o"],
                "is_active": True,
                "metadata": {"env": "test"},
            }
        )

        assert updated_result["default_model"] == "gpt-4o"
        # 重新获取更新后的数据
        stored_updated = ai_service.updated_payload[1]["tools_json"]
        assert stored_updated["__model_mapping"]["default_model"] == "gpt-4o"

        # 测试创建 fallback 映射
        fallback_result = await service.upsert_mapping(
            {
                "scope_type": "module",
                "scope_key": "chat",
                "name": "Chat Module",
                "default_model": "gpt-3.5-turbo",
                "candidates": ["gpt-3.5-turbo"],
                "is_active": True,
                "metadata": {},
            }
        )

        assert fallback_result["scope_type"] == "module"
        assert fallback_result["source"] == "sqlite"
        stored = await db.fetchone("SELECT id FROM llm_model_mappings WHERE id = ?", ("module:chat",))
        assert stored and stored.get("id") == "module:chat"
    finally:
        await db.close()


@pytest.mark.anyio("asyncio")
async def test_activate_default(tmp_path: Path) -> None:
    """测试激活默认模型功能"""
    service, ai_service, db = await _new_service(tmp_path)
    try:
        # 创建映射
        await service.upsert_mapping(
            {
                "scope_type": "prompt",
                "scope_key": "1",
                "name": "Test Prompt",
                "default_model": "gpt-4o-mini",
                "candidates": ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
                "is_active": True,
                "metadata": {"env": "test"},
            }
        )

        # 激活新的默认模型
        result = await service.activate_default("prompt:1", "gpt-4o")

        assert result["default_model"] == "gpt-4o"
        assert result["is_active"] is True
        assert "gpt-4o" in result["candidates"]

        # 验证存储中的数据已更新
        stored = ai_service.updated_payload[1]["tools_json"]
        assert stored["__model_mapping"]["default_model"] == "gpt-4o"

        # 测试激活不存在的映射
        try:
            await service.activate_default("prompt:999", "gpt-4o")
            assert False, "Expected ValueError"
        except ValueError as e:
            assert str(e) == "mapping_not_found"
    finally:
        await db.close()


@pytest.mark.anyio("asyncio")
async def test_prompt_mapping_roundtrip(tmp_path: Path) -> None:
    service, ai_service, db = await _new_service(tmp_path)
    try:
        result = await service.upsert_mapping(
            {
                "scope_type": "prompt",
                "scope_key": "1",
                "name": "Test Prompt",
                "default_model": "gpt-4o-mini",
                "candidates": ["gpt-4o-mini", "gpt-4o"],
                "is_active": True,
                "metadata": {"env": "test"},
            }
        )

        assert result["scope_type"] == "prompt"
        assert result["default_model"] == "gpt-4o-mini"
        assert 1 in ai_service.updated_payload
        stored = ai_service.updated_payload[1]["tools_json"]
        assert isinstance(stored, dict)
        assert stored["__model_mapping"]["default_model"] == "gpt-4o-mini"

        items = await service.list_mappings()
        assert len(items) == 1
        assert items[0]["scope_key"] == "1"
    finally:
        await db.close()


@pytest.mark.anyio("asyncio")
async def test_fallback_mapping(tmp_path: Path) -> None:
    service, ai_service, db = await _new_service(tmp_path)
    try:
        payload = {
            "scope_type": "module",
            "scope_key": "chat",
            "name": "Chat Module",
            "default_model": "gpt-4o-mini",
            "candidates": ["gpt-4o-mini"],
            "is_active": True,
            "metadata": {},
        }
        await service.upsert_mapping(payload)

        items = await service.list_mappings(scope_type="module")
        assert len(items) == 1
        assert items[0]["scope_key"] == "chat"
        assert items[0]["source"] == "sqlite"
        stored = await db.fetchone("SELECT id FROM llm_model_mappings WHERE id = ?", ("module:chat",))
        assert stored and stored.get("id") == "module:chat"
    finally:
        await db.close()


@pytest.mark.anyio("asyncio")
async def test_resolve_model_key_skips_blocked(tmp_path: Path) -> None:
    service, _ai_service, db = await _new_service(tmp_path)
    try:
        await service.upsert_mapping(
            {
                "scope_type": "module",
                "scope_key": "chat",
                "name": "Chat Module",
                "default_model": "gpt-4o-mini",
                "candidates": ["gpt-4o-mini", "gpt-4o"],
                "is_active": True,
                "metadata": {},
            }
        )

        # 屏蔽默认模型后，应自动回退到下一个候选
        await service.upsert_blocked_models([{"model": "gpt-4o-mini", "blocked": True}])
        resolved = await service.resolve_model_key("module:chat")
        assert resolved["hit"] is True
        assert resolved["resolved_model"] == "gpt-4o"

        # 全部候选被屏蔽：应返回 hit=true 且 resolved_model=None（由调用方 fallback）
        await service.upsert_blocked_models([{"model": "gpt-4o", "blocked": True}])
        resolved2 = await service.resolve_model_key("module:chat")
        assert resolved2["hit"] is True
        assert resolved2["resolved_model"] is None
    finally:
        await db.close()


@pytest.mark.anyio("asyncio")
async def test_import_local_mappings(tmp_path: Path) -> None:
    service, ai_service, db = await _new_service(tmp_path)
    try:
        result = await service.import_local_mappings(
            [
                {
                    "scope_type": "module",
                    "scope_key": "chat",
                    "name": "Chat Module",
                    "default_model": "gpt-4o-mini",
                    "candidates": ["gpt-4o-mini"],
                    "is_active": True,
                    "metadata": {},
                },
                {
                    "id": "prompt:1",
                    "default_model": "gpt-4o",
                    "candidates": ["gpt-4o"],
                    "is_active": True,
                    "metadata": {"env": "test"},
                },
                {"scope_type": "", "scope_key": ""},
            ]
        )

        assert result["imported_count"] == 2
        assert result["skipped_count"] == 1
        assert len(result["errors"]) == 1

        items = await service.list_mappings()
        assert any(item.get("id") == "module:chat" for item in items)
        assert 1 in ai_service.updated_payload
    finally:
        await db.close()
