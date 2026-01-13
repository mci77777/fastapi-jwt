"""Prompt/Tools 组装（SSOT：/messages 与 Prompt Test 复用同一套规则）。"""

from __future__ import annotations

from typing import Any, Optional


def assemble_system_prompt(system_prompt_text: Optional[str], tools_prompt_text: Optional[str]) -> Optional[str]:
    parts: list[str] = []
    for part in (system_prompt_text, tools_prompt_text):
        if isinstance(part, str) and part.strip():
            parts.append(part.strip())
    return "\n\n".join(parts) if parts else None


def extract_tools_schema(tools_json: Any) -> Optional[list[Any]]:
    if tools_json is None:
        return None
    if isinstance(tools_json, dict):
        raw = tools_json.get("tools")
        if isinstance(raw, list) and raw:
            return raw
        return None
    if isinstance(tools_json, list) and tools_json:
        return tools_json
    return None


def gate_active_tools_schema(
    *,
    tools_schema: Optional[list[Any]],
    tools_from_active_prompt: bool,
    tool_choice: Any,
) -> Optional[list[Any]]:
    if tools_schema is None:
        return None
    if tools_from_active_prompt and tool_choice is None:
        return None
    return tools_schema

