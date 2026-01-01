import argparse
import json
import sqlite3
from typing import Any, Optional


def _safe_json_loads(text: Any) -> dict[str, Any]:
    if not isinstance(text, str) or not text.strip():
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _redact(value: Any, keep: int = 8) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if len(value) <= keep:
        return "<redacted>"
    return f"{value[:keep]}…"


def _get_sse_block(resp: dict[str, Any]) -> dict[str, Any] | None:
    sse = resp.get("sse")
    return sse if isinstance(sse, dict) else None


def _match_by_request_id(resp: dict[str, Any], request_id: str) -> bool:
    sse = _get_sse_block(resp)
    return bool(sse and sse.get("request_id") == request_id)


def _print_frames(sse: dict[str, Any]) -> None:
    frames = sse.get("frames")
    if not isinstance(frames, list):
        return
    for item in frames[:50]:
        if not isinstance(item, dict):
            continue
        print(f"  - event: {item.get('event')} data: {item.get('data')}")
    if len(frames) > 50:
        print(f"  - ...（共 {len(frames)} 帧，仅展示前 50）")


def main() -> int:
    parser = argparse.ArgumentParser(description="按 request_id / message_id 导出最小交接数据（脱敏）")
    parser.add_argument("--db", default="db.sqlite3", help="SQLite DB 路径（默认 db.sqlite3）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--request-id", dest="request_id", help="目标 request_id（32位hex等）")
    group.add_argument("--message-id", dest="message_id", help="目标 message_id（通常为32位hex）")
    group.add_argument(
        "--trace-id",
        dest="trace_id_deprecated",
        help="(deprecated) 兼容旧参数，等价于 --request-id",
    )
    args = parser.parse_args()

    wanted_request_id: Optional[str] = args.request_id or args.trace_id_deprecated
    wanted_message_id: Optional[str] = args.message_id

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, user_id, message_id, request_payload, response_payload, model_used, latency_ms, status, error_message, created_at
        FROM conversation_logs
        ORDER BY id DESC
        LIMIT 200
        """
    )
    rows = cur.fetchall()
    conn.close()

    target: tuple[Any, dict[str, Any], dict[str, Any]] | None = None
    for row in rows:
        req = _safe_json_loads(row["request_payload"])
        resp = _safe_json_loads(row["response_payload"])

        if wanted_request_id and _match_by_request_id(resp, wanted_request_id):
            target = (row, req, resp)
            break
        if wanted_message_id and row["message_id"] == wanted_message_id:
            target = (row, req, resp)
            break

    if not target:
        print("未找到匹配记录。提示：先触发一次 POST /api/v1/messages + GET /api/v1/messages/{id}/events 再重试。")
        return 2

    row, req, resp = target
    sse = _get_sse_block(resp) or {}

    print("最小交接数据（脱敏）")
    print(f"- request_id: {sse.get('request_id')}")
    print(f"- message_id: {_redact(row['message_id'], 12)}")
    print(f"- user_id: {_redact(row['user_id'], 8)}")
    print(f"- conversation_id: {_redact(req.get('conversation_id'), 8)}")
    print(f"- status: {row['status']} latency_ms: {row['latency_ms']}")
    if row["error_message"]:
        print(f"- error_message: {row['error_message']}")
    print("")

    print("请求（反序列化后）")
    print(f"- model: {req.get('model')}")
    msgs = req.get("messages")
    print(f"- messages_count: {len(msgs) if isinstance(msgs, list) else None}")
    text = req.get("text")
    print(f"- text_len: {len(text) if isinstance(text, str) else None}")
    print("")

    print("SSE（脱敏摘要）")
    print(f"- duration_s: {sse.get('duration_s')} end_reason: {sse.get('end_reason')}")
    print(f"- frames_count: {len(sse.get('frames')) if isinstance(sse.get('frames'), list) else None}")
    _print_frames(sse)
    print("")

    print("上游响应（脱敏摘要）")
    if isinstance(resp, dict):
        upstream_request_id = None
        if isinstance(req.get("metadata"), dict):
            upstream_request_id = req["metadata"].get("upstream_request_id")
        if not upstream_request_id and isinstance(resp, dict):
            upstream_request_id = resp.get("request_id") or resp.get("id")
        print(f"- upstream_request_id: {_redact(upstream_request_id, 12)}")
        choices = resp.get("choices")
        print(f"- choices_count: {len(choices) if isinstance(choices, list) else None}")
        usage = resp.get("usage")
        if isinstance(usage, dict):
            print(f"- usage: {usage}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

