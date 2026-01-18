#!/usr/bin/env python3
"""
本地 E2E（mock 上游，不出网）：
1) /api/v1/base/access_token 获取 Dashboard admin JWT
2) 将 assets/prompts/{serp_prompt.md,tool.md} 写入 /api/v1/llm/prompts 并 activate（SSOT：SQLite）
3) POST /api/v1/messages + GET /events 消费 GymBro SSE
4) 由 content_delta 拼装最终 reply，并按 docs/ai预期响应结构.md 的 ThinkingML 规则做校验

特点：
- 不依赖 Supabase / 真上游模型 / 外网
- 便于在 CI/本地快速验证“端到端 SSE + prompt 注入 + reply 结构”
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


def _set_local_env() -> None:
    # 运行隔离：避免污染本地 data/db.sqlite3 与 storage
    os.environ.setdefault("SQLITE_DB_PATH", "tmp_test/local_e2e_db.sqlite3")
    os.environ.setdefault("AI_RUNTIME_STORAGE_DIR", "tmp_test/local_e2e_ai_runtime")

    # 禁止外部依赖与后台任务
    os.environ.setdefault("SUPABASE_KEEPALIVE_ENABLED", "false")
    os.environ.setdefault("SUPABASE_PROVIDER_ENABLED", "false")
    os.environ.setdefault("ENDPOINT_MONITOR_PROBE_ENABLED", "false")
    os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

    # 允许 env-default endpoint + minimal global mapping
    os.environ.setdefault("ALLOW_TEST_AI_ENDPOINTS", "true")
    os.environ.setdefault("AI_PROVIDER", "openai")
    os.environ.setdefault("AI_API_KEY", "test-ai-key")
    os.environ.setdefault("AI_MODEL", "mock-model")
    # base_url 仅用于落表与路由选择；上游调用会被 mock 掉
    os.environ.setdefault("AI_API_BASE_URL", "https://example.invalid")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _load_prompt_assets() -> tuple[dict[str, Any], str, str]:
    profile = json.loads(_read_text(REPO_ROOT / "assets" / "prompts" / "standard_serp_v2.json"))
    serp_prompt = _read_text(REPO_ROOT / "assets" / "prompts" / "serp_prompt.md")
    tool_prompt = _read_text(REPO_ROOT / "assets" / "prompts" / "tool.md")
    return profile, serp_prompt, tool_prompt


_TOOL_NAME_RE = re.compile(r"^\s*-\s*`([^`]+)`：\s*(.*)\s*$")
_TOOL_PARAMS_RE = re.compile(r"参数：\s*(.*)\s*$")


def _parse_tools_from_tool_md(tool_md: str) -> list[dict[str, Any]]:
    """从 assets/prompts/tool.md 解析成 OpenAI tools schema（KISS：全部参数按 string 处理）。"""
    tools: list[dict[str, Any]] = []

    current_name: str | None = None
    current_desc: str = ""

    for raw_line in (tool_md or "").splitlines():
        line = raw_line.rstrip()
        m = _TOOL_NAME_RE.match(line)
        if m:
            current_name = str(m.group(1) or "").strip()
            current_desc = str(m.group(2) or "").strip()
            continue

        m = _TOOL_PARAMS_RE.search(line)
        if not m or not current_name:
            continue

        params_text = str(m.group(1) or "")
        params = [p.strip() for p in re.findall(r"`([^`]+)`", params_text) if str(p).strip()]

        properties = {p: {"type": "string", "description": p} for p in params}
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": current_name,
                    "description": current_desc or f"GymBro tool: {current_name}",
                    "parameters": {"type": "object", "properties": properties, "additionalProperties": False},
                },
            }
        )

        current_name = None
        current_desc = ""

    return tools


ALLOWED_TAGS = {"think", "serp", "thinking", "phase", "title", "final"}
TAG_RE = re.compile(r"<\s*/?\s*([a-zA-Z]+)(?:\s+[^>]*)?>")
PHASE_OPEN_RE = re.compile(r'<phase\s+id="(\d+)">')
PHASE_BLOCK_RE = re.compile(r'(<phase\s+id="(\d+)">)(.*?)(</phase>)', re.DOTALL)
SERP_QUERIES_BLOCK_RE = re.compile(
    r"<!--\s*<serp_queries>\s*\n(?P<json>\[.*?\])\s*\n</serp_queries>\s*-->\s*$",
    re.DOTALL,
)


def _extract_block(text: str, open_tag: str, close_tag: str) -> tuple[str | None, str | None]:
    start = text.find(open_tag)
    end = text.rfind(close_tag)
    if start < 0 or end < 0:
        return None, "missing_block"
    start += len(open_tag)
    if end < start:
        return None, "invalid_block_order"
    return text[start:end], None


def _validate_thinkingml(reply: str) -> tuple[bool, str]:
    text = (reply or "").strip()
    if not text:
        return False, "empty_reply"
    if text == "<<ParsingError>>":
        return False, "parsing_error_marker"

    # 1) 必须块存在且仅 1 次
    if text.count("<thinking>") != 1 or text.count("</thinking>") != 1:
        return False, "invalid_thinking_block_count"
    if text.count("<final>") != 1 or text.count("</final>") != 1:
        return False, "invalid_final_block_count"
    if text.count("<serp>") > 1 or text.count("</serp>") > 1:
        return False, "invalid_serp_block_count"
    if text.count("<think>") > 1 or text.count("</think>") > 1:
        return False, "invalid_think_block_count"

    thinking_open = text.find("<thinking>")
    thinking_close = text.find("</thinking>")
    final_open = text.find("<final>")
    final_close = text.find("</final>")
    if thinking_open < 0 or thinking_close < 0 or final_open < 0 or final_close < 0:
        return False, "missing_required_blocks"
    if thinking_open > thinking_close:
        return False, "invalid_thinking_order"
    if final_open > final_close:
        return False, "invalid_final_order"

    # 2) 顺序约束：<serp> 在 <thinking> 之前；</thinking> 后必须立刻出现 <final>（允许空白）
    if "<serp>" in text:
        serp_open = text.find("<serp>")
        if serp_open > thinking_open:
            return False, "invalid_sequence_serp_thinking"

    if thinking_close + len("</thinking>") > final_open:
        return False, "invalid_sequence_thinking_final"
    between = text[thinking_close + len("</thinking>") : final_open]
    if between.strip():
        return False, "final_not_immediately_after_thinking"

    # 3) 允许标签白名单（大小写敏感）
    for match in TAG_RE.finditer(text):
        tag = (match.group(1) or "").strip()
        if tag and tag not in ALLOWED_TAGS:
            return False, f"unexpected_tag:{tag}"

    # 4) <thinking>：phase id 严格递增，从 1 开始；每个 phase 含且仅含 1 个 title
    thinking_content, err = _extract_block(text, "<thinking>", "</thinking>")
    if err or thinking_content is None:
        return False, "missing_thinking_content"

    phase_ids = [int(x) for x in PHASE_OPEN_RE.findall(thinking_content)]
    if not phase_ids:
        return False, "missing_phase"
    if phase_ids[0] != 1:
        return False, "phase_id_not_start_from_1"
    for idx in range(1, len(phase_ids)):
        if phase_ids[idx] != phase_ids[idx - 1] + 1:
            return False, "phase_id_not_strict_increment"

    phase_blocks = list(PHASE_BLOCK_RE.finditer(thinking_content))
    if len(phase_blocks) != len(phase_ids):
        return False, "phase_block_mismatch"

    for m in phase_blocks:
        block_body = str(m.group(3) or "")
        if block_body.count("<title>") != 1 or block_body.count("</title>") != 1:
            return False, "invalid_title_count_in_phase"

    # 5) <final>：末尾必须有 serp_queries 注释块，且 JSON 数组合法
    final_content, err = _extract_block(text, "<final>", "</final>")
    if err or final_content is None:
        return False, "missing_final_content"

    final_stripped = final_content.strip()
    match = SERP_QUERIES_BLOCK_RE.search(final_stripped)
    if not match:
        return False, "missing_or_invalid_serp_queries_block"

    json_text = (match.group("json") or "").strip()
    try:
        queries = json.loads(json_text)
    except Exception:
        return False, "serp_queries_json_parse_error"
    if not isinstance(queries, list):
        return False, "serp_queries_not_array"
    if len(queries) > 5:
        return False, "serp_queries_too_many"
    if len({str(x) for x in queries}) != len(queries):
        return False, "serp_queries_not_deduped"
    for q in queries:
        if not isinstance(q, str):
            return False, "serp_queries_item_not_string"
        if len(q) > 80:
            return False, "serp_queries_item_too_long"

    return True, "ok"


def _mock_httpx_stream_json(mock_httpx: MagicMock, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> None:
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    if headers:
        response.headers.update(headers)
    response.raise_for_status = MagicMock()
    response.aread = AsyncMock(return_value=json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=response)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_httpx.return_value.__aenter__.return_value.stream = MagicMock(return_value=stream_ctx)


async def _collect_sse_events(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
    *,
    max_events: int = 2000,
) -> tuple[list[dict[str, Any]], str]:
    events: list[dict[str, Any]] = []
    reply_accum = ""

    async with client.stream("GET", url, headers=headers, timeout=10.0) as response:
        response.raise_for_status()

        current_event = "message"
        data_lines: list[str] = []

        async def flush() -> dict[str, Any] | None:
            nonlocal data_lines, reply_accum
            if not data_lines:
                return None
            raw = "\n".join(data_lines)
            data_lines = []
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = raw
            evt = {"event": current_event, "data": parsed}
            if current_event == "content_delta" and isinstance(parsed, dict) and parsed.get("delta"):
                reply_accum += str(parsed.get("delta"))
            return evt

        async for line in response.aiter_lines():
            if line is None:
                continue
            line = line.rstrip("\r")
            if line == "":
                evt = await flush()
                if evt:
                    events.append(evt)
                    if evt["event"] in {"completed", "error"}:
                        break
                    if len(events) >= max_events:
                        raise RuntimeError("SSE 事件数量超限（可能未正常结束）")
                current_event = "message"
                continue
            if line.startswith("event:"):
                current_event = line[len("event:") :].strip() or "message"
                continue
            if line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
                continue

        evt = await flush()
        if evt:
            events.append(evt)

    return events, reply_accum


def _build_sample_reply() -> str:
    return (
        "<serp>用户想要一份可执行的三分化训练方案（新手友好，含动作与频率建议）。</serp>\n"
        "<thinking>\n"
        "  <phase id=\"1\">\n"
        "    <title>目标与约束</title>\n"
        "    以增肌为主，兼顾动作学习与恢复；每周 3 次，推/拉/腿。\n"
        "  </phase>\n"
        "  <phase id=\"2\">\n"
        "    <title>计划结构</title>\n"
        "    每次 45–75 分钟：热身→主练→辅助→收操；强度按 RPE 7–8。\n"
        "  </phase>\n"
        "</thinking>\n"
        "<final>\n"
        "# 三分化训练方案（新手友好）\n"
        "\n"
        "## 频率\n"
        "- 周一：推（胸/肩/三头）\n"
        "- 周三：拉（背/二头）\n"
        "- 周五：腿（腿/臀/核心）\n"
        "\n"
        "## 推（示例）\n"
        "1. 平板哑铃卧推 3×8–12\n"
        "2. 坐姿哑铃肩推 3×8–12\n"
        "3. 俯卧撑（或器械夹胸）2×力竭前 1–2 次\n"
        "\n"
        "## 拉（示例）\n"
        "1. 高位下拉 3×8–12\n"
        "2. 坐姿划船 3×8–12\n"
        "3. 哑铃弯举 2×10–15\n"
        "\n"
        "## 腿（示例）\n"
        "1. 杠铃/壶铃深蹲 3×6–10\n"
        "2. 罗马尼亚硬拉 3×6–10\n"
        "3. 平板支撑 2×30–60 秒\n"
        "\n"
        "<!-- <serp_queries>\n"
        "[\"三分化训练计划 新手\",\"推拉腿 动作选择\",\"三分化 训练频率 恢复\"]\n"
        "</serp_queries> -->\n"
        "</final>"
    )


async def main() -> int:
    _set_local_env()

    # 清理上次运行的 sqlite/storage（只动 tmp_test）
    db_path = Path(os.environ["SQLITE_DB_PATH"])
    runtime_dir = Path(os.environ["AI_RUNTIME_STORAGE_DIR"])
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir, ignore_errors=True)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    # 防止启动期把仓库内 legacy storage/ai_runtime 的历史映射拷贝进来（保持本次 E2E 纯净、可复现）
    (runtime_dir / ".legacy_import_done").write_text("local_mock_e2e", encoding="utf-8")
    if db_path.exists():
        db_path.unlink(missing_ok=True)

    from app.auth.provider import get_auth_provider
    from app.settings.config import get_settings

    get_settings.cache_clear()
    get_auth_provider.cache_clear()

    from app import app as fastapi_app

    profile, serp_prompt, tool_prompt = _load_prompt_assets()
    tools_schema = _parse_tools_from_tool_md(tool_prompt)
    profile_version = str(profile.get("version") or "").strip() or "v1"

    async with fastapi_app.router.lifespan_context(fastapi_app):
        transport = httpx.ASGITransport(app=fastapi_app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1) admin 登录
            request_id = uuid.uuid4().hex
            login = await client.post(
                "/api/v1/base/access_token",
                headers={"X-Request-Id": request_id},
                json={"username": "admin", "password": "123456"},
            )
            login.raise_for_status()
            login_body = login.json()
            token = (login_body.get("data") or {}).get("access_token")
            if not token:
                raise RuntimeError("无法从 /base/access_token 获取 access_token（请检查本地 admin 密码）")

            auth_headers_base = {"Authorization": f"Bearer {token}"}

            # 2) 写入并激活 prompts（system + tools）
            system_created = await client.post(
                "/api/v1/llm/prompts",
                headers={**auth_headers_base, "X-Request-Id": request_id},
                json={
                    "name": "standard_serp_v2_system",
                    "version": profile_version,
                    "category": "standard_serp_v2",
                    "description": "Seeded from assets/prompts/serp_prompt.md",
                    "prompt_type": "system",
                    "content": serp_prompt,
                    "is_active": False,
                },
            )
            system_created.raise_for_status()
            system_id = int((system_created.json().get("data") or {}).get("id") or 0)
            if not system_id:
                raise RuntimeError("创建 system prompt 失败（缺少 id）")

            tools_created = await client.post(
                "/api/v1/llm/prompts",
                headers={**auth_headers_base, "X-Request-Id": request_id},
                json={
                    "name": "standard_serp_v2_tools",
                    "version": profile_version,
                    "category": "standard_serp_v2",
                    "description": "Seeded from assets/prompts/tool.md",
                    "prompt_type": "tools",
                    "content": tool_prompt,
                    "tools_json": tools_schema,
                    "is_active": False,
                },
            )
            tools_created.raise_for_status()
            tools_id = int((tools_created.json().get("data") or {}).get("id") or 0)
            if not tools_id:
                raise RuntimeError("创建 tools prompt 失败（缺少 id）")

            activated_1 = await client.post(
                f"/api/v1/llm/prompts/{system_id}/activate", headers={**auth_headers_base, "X-Request-Id": request_id}
            )
            activated_1.raise_for_status()
            activated_2 = await client.post(
                f"/api/v1/llm/prompts/{tools_id}/activate", headers={**auth_headers_base, "X-Request-Id": request_id}
            )
            activated_2.raise_for_status()

            # 3) 获取模型白名单（SSOT），逐个 name 回归
            models = await client.get("/api/v1/llm/models?view=mapped", headers={**auth_headers_base, "X-Request-Id": request_id})
            models.raise_for_status()
            models_body = models.json()
            model_list = models_body.get("data") if isinstance(models_body, dict) else None
            if not isinstance(model_list, list) or not model_list:
                raise RuntimeError("模型白名单为空（请检查 ALLOW_TEST_AI_ENDPOINTS / AI_MODEL / AI_API_KEY）")
            model_keys: list[str] = []
            for item in model_list:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("name") or "").strip()
                if key and key not in model_keys:
                    model_keys.append(key)
            if not model_keys:
                raise RuntimeError("模型白名单缺少 data[].name")

            # 4) 发送消息 + 消费 SSE（mock 上游返回符合结构的 ThinkingML）
            reply = _build_sample_reply()

            results: list[dict[str, Any]] = []

            with patch("app.services.ai_service.httpx.AsyncClient") as mock_httpx:
                _mock_httpx_stream_json(
                    mock_httpx,
                    {"choices": [{"message": {"content": reply}}]},
                    headers={"x-request-id": "upstream-mock"},
                )

                for idx, model_key in enumerate(model_keys, start=1):
                    model_request_id = uuid.uuid4().hex
                    auth_headers = {**auth_headers_base, "X-Request-Id": model_request_id}

                    try:
                        created = await client.post(
                            "/api/v1/messages",
                            headers={**auth_headers, "Content-Type": "application/json"},
                            json={
                                "model": model_key,
                                "text": "给我一份三分化训练方案（新手友好）。",
                                "metadata": {"save_history": False, "client": "local_mock_e2e"},
                                # 本脚本验证的是 ThinkingML 结构与 content_delta 拼装，因此显式使用 xml_plaintext（避免受 Dashboard 默认值影响）
                                "result_mode": "xml_plaintext",
                                "tool_choice": "auto",
                            },
                        )
                        created.raise_for_status()
                        created_body = created.json()
                        message_id = str(created_body.get("message_id") or "").strip()
                        conversation_id = str(created_body.get("conversation_id") or "").strip()
                        if not message_id or not conversation_id:
                            raise RuntimeError("/messages 响应缺少 message_id/conversation_id")

                        events, reply_accum = await _collect_sse_events(
                            client,
                            f"/api/v1/messages/{message_id}/events?conversation_id={conversation_id}",
                            headers={**auth_headers, "Accept": "text/event-stream"},
                        )

                        ok, reason = _validate_thinkingml(reply_accum)

                        # 关键断言：prompt 注入来自 assets/prompts（只需验证 1 次）
                        if idx == 1:
                            call_args = mock_httpx.return_value.__aenter__.return_value.stream.call_args
                            upstream_payload = call_args[1]["json"] if call_args else {}
                            upstream_messages = (
                                upstream_payload.get("messages") if isinstance(upstream_payload, dict) else None
                            )
                            system_message = (
                                upstream_messages[0] if isinstance(upstream_messages, list) and upstream_messages else {}
                            )
                            system_content = (
                                str(system_message.get("content") or "") if isinstance(system_message, dict) else ""
                            )

                            assert "输出格式强制要求" in system_content
                            assert "GymBro ToolCall 工具指令集" in system_content
                            assert isinstance(upstream_payload.get("tools"), list) and upstream_payload.get("tools")
                            assert upstream_payload.get("tool_choice") == "auto"

                        event_names = [e.get("event") for e in events if isinstance(e, dict)]
                        results.append(
                            {
                                "model": model_key,
                                "request_id": model_request_id,
                                "message_id": message_id,
                                "events": event_names,
                                "reply_len": len(reply_accum),
                                "ok": ok,
                                "reason": reason,
                            }
                        )
                    except Exception as exc:
                        results.append(
                            {
                                "model": model_key,
                                "request_id": model_request_id,
                                "message_id": None,
                                "events": [],
                                "reply_len": 0,
                                "ok": False,
                                "reason": f"exception:{type(exc).__name__}",
                            }
                        )

            passed = [r for r in results if r.get("ok")]
            failed = [r for r in results if not r.get("ok")]

            for r in results:
                status = "PASS" if r.get("ok") else "FAIL"
                print(
                    f"{status} model={r.get('model')} request_id={r.get('request_id')} message_id={r.get('message_id')} reply_len={r.get('reply_len')} reason={r.get('reason')}"
                )

            print(f"SUMMARY total={len(results)} passed={len(passed)} failed={len(failed)}")
            if failed:
                failed_models = ",".join([str(r.get("model")) for r in failed])
                print(f"FAILED_MODELS {failed_models}")

            return 0 if not failed else 3


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
