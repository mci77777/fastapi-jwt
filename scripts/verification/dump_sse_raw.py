#!/usr/bin/env python3
"""
用途：确认 /api/v1/messages/{message_id}/events 是否存在“envelope 直传/二次转义”。

要求（本脚本默认满足）：
- 逐行输出原始 SSE 响应：包括每行 event:、每行 data:、以及事件边界空行
- 单独截取并原样展示 completed 的 data: payload（不做 JSON 反序列化/pretty）
- 标注 payload 是否出现 \\\" 与 \\\\n（用字节模式匹配，避免编码差异）
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPSConnection
from urllib.parse import urlparse

_LABEL_DOUBLE_ESCAPED_QUOTE = r'\\\"'
_LABEL_DOUBLE_ESCAPED_NEWLINE = r"\\\\n"
_PATTERN_DOUBLE_ESCAPED_QUOTE = b'\\\\\"'
_PATTERN_DOUBLE_ESCAPED_NEWLINE = b"\\\\\\\\n"

def _write_line(text: str) -> None:
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))
    sys.stdout.buffer.flush()


@dataclass
class CompletedPayloadProbe:
    data_lines: list[bytes]

    def add_data_line(self, raw_line: bytes) -> None:
        self.data_lines.append(raw_line)

    def payload_bytes(self) -> bytes:
        # SSE 规范：多行 data: 之间用 \n 拼接
        return b"\n".join(self.data_lines)

    def has_double_escaped_quote(self) -> bool:
        # 文本里出现 \\\"（两个反斜杠 + 引号）
        return _PATTERN_DOUBLE_ESCAPED_QUOTE in self.payload_bytes()

    def has_double_escaped_newline(self) -> bool:
        # 文本里出现 \\\\n（四个反斜杠 + n）
        return _PATTERN_DOUBLE_ESCAPED_NEWLINE in self.payload_bytes()


def _dump_sse_raw(
    *,
    base_url: str,
    message_id: str,
    token: str | None,
    timeout_s: float,
) -> int:
    parsed = urlparse(base_url)
    scheme = (parsed.scheme or "http").lower()
    if scheme not in {"http", "https"}:
        sys.stderr.write(f"[error] unsupported base url scheme: {scheme}\n")
        return 2

    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if scheme == "https" else 80)
    path_prefix = parsed.path.rstrip("/")
    path = f"{path_prefix}/api/v1/messages/{message_id}/events"

    headers = {"Accept": "text/event-stream"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    conn_cls = HTTPSConnection if scheme == "https" else HTTPConnection
    conn = conn_cls(host, port, timeout=timeout_s)

    # 只做“逐行转发”；不做 JSON 反序列化/pretty
    current_event: bytes | None = None
    completed_probe: CompletedPayloadProbe | None = None

    try:
        conn.request("GET", path, headers=headers)
        resp = conn.getresponse()
    except Exception as e:
        sys.stderr.write(f"[error] SSE connect failed: {e}\n")
        return 2

    if resp.status != 200:
        sys.stderr.write(f"[error] SSE connect failed: {resp.status}\n")
        try:
            body = resp.read(4096) or b""
            if body:
                sys.stderr.buffer.write(body + b"\n")
        except Exception:
            pass
        return 2

    buffer = b""
    while True:
        chunk = resp.read(4096)
        if not chunk:
            break
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            # 兼容 CRLF：避免 \r 影响终端输出
            if line.endswith(b"\r"):
                line = line[:-1]

            # 原样输出“逐行 SSE”（包含 event:/data:/空行）
            sys.stdout.buffer.write(line + b"\n")
            sys.stdout.buffer.flush()

            # 事件边界：空行
            if line == b"":
                if current_event == b"completed" and completed_probe is not None:
                    payload = completed_probe.payload_bytes()
                    _write_line("")
                    _write_line("=== completed data: payload (raw) ===")
                    sys.stdout.buffer.write(payload + b"\n")
                    sys.stdout.buffer.flush()
                    _write_line(
                        f"contains {_LABEL_DOUBLE_ESCAPED_QUOTE} : "
                        f"{'YES' if completed_probe.has_double_escaped_quote() else 'NO'}"
                    )
                    _write_line(
                        f"contains {_LABEL_DOUBLE_ESCAPED_NEWLINE} : "
                        f"{'YES' if completed_probe.has_double_escaped_newline() else 'NO'}"
                    )
                    return 0

                current_event = None
                completed_probe = None
                continue

            if line.startswith(b"event:"):
                # event: <name>
                current_event = line[len(b"event:") :].lstrip()
                if current_event == b"completed":
                    completed_probe = CompletedPayloadProbe(data_lines=[])
                continue

            if line.startswith(b"data:"):
                if current_event == b"completed" and completed_probe is not None:
                    completed_probe.add_data_line(line[len(b"data:") :].lstrip())
                continue

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump raw SSE lines (no JSON decode) for /messages/{id}/events.")
    parser.add_argument("--base-url", default="http://localhost:9999", help="API base url, default http://localhost:9999")
    parser.add_argument("--message-id", required=True, help="message_id returned by POST /api/v1/messages")
    parser.add_argument("--token", default=None, help="optional Bearer token (JWT)")
    parser.add_argument("--timeout-s", type=float, default=60.0, help="HTTP timeout seconds (default 60)")
    args = parser.parse_args()

    try:
        return _dump_sse_raw(
            base_url=str(args.base_url),
            message_id=str(args.message_id),
            token=str(args.token) if args.token else None,
            timeout_s=float(args.timeout_s),
        )
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
