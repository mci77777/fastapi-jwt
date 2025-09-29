from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest
from tortoise import Tortoise


@pytest.fixture(scope="session")
def event_loop() -> AsyncIterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def tortoise_setup():
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.models.ai", "app.models.admin"]},
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()
