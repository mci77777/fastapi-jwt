"""SSE parsing helpers (provider adapters)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Optional

import httpx


async def iter_sse_frames(response: httpx.Response) -> AsyncIterator[tuple[Optional[str], str]]:
    """Iterate SSE frames (event_name, data_text)."""

    current_event: Optional[str] = None
    data_lines: list[str] = []

    async def flush() -> AsyncIterator[tuple[Optional[str], str]]:
        nonlocal current_event, data_lines
        if not data_lines:
            current_event = None
            return
        raw_text = "\n".join(data_lines).strip()
        data_lines = []
        event_name = (current_event or "").strip() or None
        current_event = None
        if raw_text:
            yield event_name, raw_text

    async for line in response.aiter_lines():
        if line is None:
            continue
        if not line:
            async for item in flush():
                yield item
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            current_event = line[len("event:") :].strip()
            continue
        if line.startswith("data:"):
            data_lines.append(line[len("data:") :].strip())
            continue

    async for item in flush():
        yield item

