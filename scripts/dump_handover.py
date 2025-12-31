import argparse
import json
import sqlite3
from typing import Any


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


def main() -> int:
    parser = argparse.ArgumentParser(description="按 trace_id / message_id 导出最小交接数据（脱敏）")
    parser.add_argument("--db", default="db.sqlite3", help="SQLite DB 路径（默认 db.sqlite3）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--trace-id", dest="trace_id", help="目标 trace_id（32位hex等）")
    group.add_argument("--message-id", dest="message_id", help="目标 message_id（通常为32位hex）")
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, user_id, message_id, request_payload, response_payload, model_used, latency_ms, status, error_message, created_at
        FROM conversation_logs
        ORDER BY created_at DESC
        LIMIT 200
        """
    )
    rows = cur.fetchall()
    conn.close()

    target = None
    for row in rows:
        req = _safe_json_loads(row["request_payload"])
        resp = _safe_json_loads(row["response_payload"])

        if args.trace_id:
            if req.get("trace_id") == args.trace_id:
                target = (row, req, resp)
                break
            sse = resp.get("sse") if isinstance(resp, dict) else None
            if isinstance(sse, dict) and sse.get("trace_id") == args.trace_id:
                target = (row, req, resp)
                break
        else:
            if row["message_id"] == args.message_id:
                target = (row, req, resp)
                break

    if not target:
        print("未找到匹配记录。提示：先触发一次 POST /api/v1/messages + GET /api/v1/messages/{id}/events 再重试。")
        return 2

    row, req, resp = target
    req_parsed = req.get("request_parsed") if isinstance(req, dict) else {}
    selection = resp.get("selection") if isinstance(resp, dict) else {}
    llm = resp.get("llm") if isinstance(resp, dict) else {}
    sse = resp.get("sse") if isinstance(resp, dict) else {}
    supabase = resp.get("supabase") if isinstance(resp, dict) else None
    llm_called = bool(resp.get("llm_called")) if isinstance(resp, dict) else False
    sources = resp.get("sse_event_sources") if isinstance(resp.get("sse_event_sources"), dict) else {}

    print("最小交接数据（脱敏）")
    print(f"- trace_id: {req.get('trace_id') or (sse.get('trace_id') if isinstance(sse, dict) else None)}")
    print(f"- message_id: {_redact(row['message_id'], 12)}")
    print(f"- user_id: {_redact(row['user_id'], 8)}")
    print(f"- conversation_id: {_redact(req.get('conversation_id'), 8)}")
    print("")

    print("请求解析（反序列化后）")
    print(f"- text_len: {req_parsed.get('text_len')}")
    print(f"- conversation_id_raw_empty: {req_parsed.get('conversation_id_raw_empty')}")
    print(f"- metadata_type: {req_parsed.get('metadata_type')}")
    print(f"- metadata_keys_count: {req_parsed.get('metadata_keys_count')}")
    print(f"- skip_prompt: {req_parsed.get('skip_prompt')}")
    print(f"- additional_properties_policy: {req_parsed.get('additional_properties_policy')}")
    print(f"- additional_properties_violation: {req_parsed.get('additional_properties_violation')}")
    print("")

    print("路由与模型选择（关键）")
    if isinstance(selection, dict):
        print(f"- provider: {selection.get('provider')}")
        print(f"- endpoint_id: {selection.get('endpoint_id')}")
        print(f"- model: {selection.get('model')}")
        prompt = selection.get("prompt") if isinstance(selection.get("prompt"), dict) else {}
        print(f"- prompt: id={prompt.get('prompt_id')} name={prompt.get('name')} version={prompt.get('version')}")
        print(f"- temperature: {selection.get('temperature')}")
        mapping = selection.get("mapping") if isinstance(selection.get("mapping"), dict) else {}
        print(f"- mapping.reason: {mapping.get('reason')}")
        hit = mapping.get("hit") if isinstance(mapping.get("hit"), dict) else None
        print(f"- mapping.hit: {hit}")
    print("")

    print("是否真实调用 LLM")
    print(f"- llm_called: {llm_called}")
    if isinstance(llm, dict):
        print(f"- called: {llm.get('called')}")
        print(f"- reason_code: {llm.get('reason_code')}")
        print(f"- reason_detail: {llm.get('reason_detail')}")
        print(f"- request_id: {_redact(llm.get('request_id'), 12)}")
        print(f"- started_at: {llm.get('started_at')}")
        print(f"- ended_at: {llm.get('ended_at')}")
        print(f"- duration_ms: {llm.get('duration_ms')}")
        print(f"- upstream_status: {llm.get('upstream_status')}")
        usage = llm.get("usage")
        if isinstance(usage, dict):
            print(f"- usage: {usage}")
    print("")

    print("SSE 实际发出的帧（脱敏摘要）")
    if isinstance(sse, dict):
        print(f"- duration_s: {sse.get('duration_s')} end_reason: {sse.get('end_reason')}")
        frames = sse.get("frames")
        if isinstance(frames, list):
            for item in frames[:50]:
                if not isinstance(item, dict):
                    continue
                print(f"  - event: {item.get('event')} data: {item.get('data')}")
            if len(frames) > 50:
                print(f"  - ...（共 {len(frames)} 帧，仅展示前 50）")
    print("")

    print("DB SSOT（摘要）")
    if isinstance(supabase, dict):
        conv = supabase.get("conversations") if isinstance(supabase.get("conversations"), dict) else {}
        print(f"- conversations.id: {_redact(conv.get('id'), 8)}")
        msgs = supabase.get("messages") if isinstance(supabase.get("messages"), dict) else {}
        print(f"- messages.inserted: {msgs.get('inserted')}")
        if "assistant_content_len" in msgs:
            print(f"- assistant_content_len: {msgs.get('assistant_content_len')} preview: {msgs.get('assistant_preview')}")
    else:
        print("- supabase: 未配置/未返回写入摘要（可开启 DEBUG=true 且 SUPABASE_RETURN_REPRESENTATION=true）")

    completed = resp.get("completed") if isinstance(resp.get("completed"), dict) else None
    print(f"- completed.source: {(completed.get('source') if isinstance(completed, dict) else None) or sources.get('completed')}")
    print(f"- completed.reply_preview: {completed.get('reply_preview') if isinstance(completed, dict) else None}")
    ssot = resp.get("ssot") if isinstance(resp.get("ssot"), dict) else {}
    print(f"- assistant_reply_matches_completed: {ssot.get('assistant_reply_matches_completed')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
