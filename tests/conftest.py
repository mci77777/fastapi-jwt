from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest


@pytest.fixture(scope="session")
def event_loop() -> AsyncIterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
