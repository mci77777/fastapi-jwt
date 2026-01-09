#!/usr/bin/env python3
"""
目标：确认是否存在“envelope 直传/二次转义”。

做法（严格不反序列化 SSE data）：
1) 获取 JWT（默认：用 Dashboard admin 的 /api/v1/base/access_token）
2) 拉取 /api/v1/llm/models 并选取一个可用 model
3) POST /api/v1/messages 创建 message
4) GET /api/v1/messages/{message_id}/events：逐行输出 event:/data:/空行边界
5) 单独截取并原样展示 completed 的 data: payload（原始字节），并标注是否出现 \\\" 与 \\\\n
"""

from __future__ import annotations

import argparse
import json
import sys
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlparse


_LABEL_DOUBLE_ESCAPED_QUOTE = r'\\\"'
_LABEL_DOUBLE_ESCAPED_NEWLINE = r"\\\\n"
_PATTERN_DOUBLE_ESCAPED_QUOTE = b'\\\\\"'
_PATTERN_DOUBLE_ESCAPED_NEWLINE = b"\\\\\\\\n"

def _write_line(text: str) -> None:
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


def _conn_from_base_url(base_url: str, timeout_s: float) -> tuple[HTTPConnection | HTTPSConnection, str]:
    parsed = urlparse(base_url)
    scheme = (parsed.scheme or "http").lower()
    if scheme not in {"http", "https"}:
        raise ValueError(f"unsupported base url scheme: {scheme}")

    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if scheme == "https" else 80)
    path_prefix = parsed.path.rstrip("/")

    conn_cls = HTTPSConnection if scheme == "https" else HTTPConnection
    return conn_cls(host, port, timeout=timeout_s), path_prefix


def _http_json(
    *,
    base_url: str,
    method: str,
    path: str,
    token: str | None,
    timeout_s: float,
    body_obj: dict | None = None,
) -> tuple[int, dict]:
    conn, prefix = _conn_from_base_url(base_url, timeout_s)
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    body: bytes | None = None
    if body_obj is not None:
        body = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"

    conn.request(method.upper(), f"{prefix}{path}", body=body, headers=headers)
    resp = conn.getresponse()
    raw = resp.read() or b""
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        data = {"_raw": raw.decode("utf-8", errors="replace")}
    return int(resp.status), data


def _get_admin_jwt(*, base_url: str, username: str, password: str, timeout_s: float) -> str:
    status, data = _http_json(
        base_url=base_url,
        method="POST",
        path="/api/v1/base/access_token",
        token=None,
        timeout_s=timeout_s,
        body_obj={"username": username, "password": password},
    )
    if status != 200:
        raise RuntimeError(f"access_token failed: status={status} body={data}")
    token = (((data or {}).get("data") or {}).get("access_token") or "").strip()
    if not token:
        raise RuntimeError("access_token missing in response")
    return token


def _pick_first_model(*, base_url: str, token: str, timeout_s: float) -> str:
    status, data = _http_json(
        base_url=base_url,
        method="GET",
        path="/api/v1/llm/models",
        token=token,
        timeout_s=timeout_s,
        body_obj=None,
    )
    if status != 200:
        raise RuntimeError(f"list models failed: status={status} body={data}")

    items = (data or {}).get("data")
    if not isinstance(items, list) or not items:
        raise RuntimeError("models list empty")

    first = items[0]
    if not isinstance(first, dict):
        raise RuntimeError("models[0] not an object")

    name = str(first.get("name") or first.get("model") or "").strip()
    if not name:
        raise RuntimeError("model name missing")
    return name


def _create_message(*, base_url: str, token: str, timeout_s: float, model: str, text: str) -> str:
    status, data = _http_json(
        base_url=base_url,
        method="POST",
        path="/api/v1/messages",
        token=token,
        timeout_s=timeout_s,
        body_obj={"model": model, "text": text},
    )
    if status != 202:
        raise RuntimeError(f"create message failed: status={status} body={data}")

    message_id = str(((data or {}).get("message_id") or "")).strip()
    if not message_id:
        message_id = str(((data or {}).get("data") or {}).get("message_id") or "").strip()
    if not message_id:
        raise RuntimeError("message_id missing in response")
    return message_id


def _dump_events_and_probe_completed(
    *,
    base_url: str,
    token: str,
    timeout_s: float,
    message_id: str,
) -> int:
    conn, prefix = _conn_from_base_url(base_url, timeout_s)
    path = f"{prefix}/api/v1/messages/{message_id}/events"
    headers = {"Accept": "text/event-stream", "Authorization": f"Bearer {token}"}

    conn.request("GET", path, headers=headers)
    resp = conn.getresponse()
    if resp.status != 200:
        sys.stderr.write(f"[error] SSE connect failed: {resp.status}\n")
        try:
            body = resp.read(2048) or b""
            if body:
                sys.stderr.buffer.write(body + b"\n")
        except Exception:
            pass
        return 2

    current_event: bytes | None = None
    completed_data_lines: list[bytes] = []

    buffer = b""
    while True:
        chunk = resp.read(4096)
        if not chunk:
            break
        buffer += chunk

        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            if line.endswith(b"\r"):
                line = line[:-1]

            # 逐行输出（原样）
            sys.stdout.buffer.write(line + b"\n")
            sys.stdout.buffer.flush()

            # 事件边界：空行
            if line == b"":
                if current_event == b"completed":
                    payload = b"\n".join(completed_data_lines)
                    _write_line("")
                    _write_line("=== completed data: payload (raw) ===")
                    sys.stdout.buffer.write(payload + b"\n")
                    sys.stdout.buffer.flush()
                    _write_line(
                        f"contains {_LABEL_DOUBLE_ESCAPED_QUOTE} : "
                        f"{'YES' if _PATTERN_DOUBLE_ESCAPED_QUOTE in payload else 'NO'}"
                    )
                    _write_line(
                        f"contains {_LABEL_DOUBLE_ESCAPED_NEWLINE} : "
                        f"{'YES' if _PATTERN_DOUBLE_ESCAPED_NEWLINE in payload else 'NO'}"
                    )
                    return 0
                current_event = None
                completed_data_lines = []
                continue

            if line.startswith(b"event:"):
                current_event = line[len(b"event:") :].lstrip()
                continue

            if line.startswith(b"data:"):
                if current_event == b"completed":
                    completed_data_lines.append(line[len(b"data:") :].lstrip())
                continue

    sys.stderr.write("[warn] stream ended before completed event boundary\n")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe SSE raw lines for double escaping (no JSON decode for SSE data).")
    parser.add_argument("--base-url", default="http://localhost:9999", help="API base url (default http://localhost:9999)")
    parser.add_argument("--timeout-s", type=float, default=60.0, help="HTTP timeout seconds (default 60)")
    parser.add_argument("--token", default=None, help="optional Bearer token; if omitted, login via /base/access_token")
    parser.add_argument("--username", default="admin", help="dashboard username for /base/access_token (default admin)")
    parser.add_argument("--password", default="123456", help="dashboard password for /base/access_token (default 123456)")
    parser.add_argument("--model", default=None, help="optional model name; if omitted, pick first from /llm/models")
    parser.add_argument(
        "--text",
        default="请输出一段包含双引号、反斜杠、以及换行的文本；尽量原样保留字符本身，不要做额外解释。",
        help="message text",
    )
    args = parser.parse_args()

    base_url = str(args.base_url)
    timeout_s = float(args.timeout_s)

    token = str(args.token).strip() if args.token else None
    if not token:
        token = _get_admin_jwt(base_url=base_url, username=str(args.username), password=str(args.password), timeout_s=timeout_s)

    model = str(args.model).strip() if args.model else ""
    if not model:
        model = _pick_first_model(base_url=base_url, token=token, timeout_s=timeout_s)

    _write_line(f"[info] model: {model}")
    message_id = _create_message(base_url=base_url, token=token, timeout_s=timeout_s, model=model, text=str(args.text))
    _write_line(f"[info] message_id: {message_id}")

    return _dump_events_and_probe_completed(base_url=base_url, token=token, timeout_s=timeout_s, message_id=message_id)


if __name__ == "__main__":
    raise SystemExit(main())
