from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


SENSITIVE_HEADER_KEYS = {
    "authorization",
    "apikey",
    "x-api-key",
    "proxy-authorization",
}

SENSITIVE_BODY_KEYS = {
    "access_token",
    "refresh_token",
    "provider_token",
    "provider_refresh_token",
    "token",
    "password",
    "api_key",
    "apikey",
    "authorization",
    "email",
}


def _redact_headers(headers: Dict[str, Any]) -> Dict[str, Any]:
    redacted: Dict[str, Any] = {}
    for k, v in (headers or {}).items():
        key = str(k).strip()
        if key.lower() in SENSITIVE_HEADER_KEYS:
            redacted[key] = "<redacted>"
        else:
            redacted[key] = v
    return redacted


def _redact_body(obj: Any) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if str(k).lower() in SENSITIVE_BODY_KEYS:
                out[k] = "<redacted>"
            else:
                out[k] = _redact_body(v)
        return out
    if isinstance(obj, list):
        return [_redact_body(v) for v in obj]
    return obj


def _safe_sse_event(event: str, data: Any) -> Dict[str, Any]:
    safe_data: Any = data
    if event == "content_delta" and isinstance(data, dict):
        delta = str(data.get("delta") or "")
        safe_data = {
            "message_id": data.get("message_id"),
            "delta_len": len(delta),
            "delta_preview": delta[:20],
            "request_id": data.get("request_id"),
        }
    elif event == "completed" and isinstance(data, dict):
        reply = str(data.get("reply") or "")
        reply_len = data.get("reply_len")
        if not isinstance(reply_len, int):
            reply_len = len(reply)
        safe_data = {
            "message_id": data.get("message_id"),
            "reply_len": reply_len,
            "reply_preview": reply[:40] if reply else None,
            "request_id": data.get("request_id"),
        }
    elif event == "error" and isinstance(data, dict):
        safe_data = {
            "message_id": data.get("message_id"),
            "error": data.get("error"),
            "code": data.get("code"),
            "request_id": data.get("request_id"),
        }
    return {"event": event, "data": _redact_body(safe_data)}


@dataclass
class TraceStep:
    name: str
    ok: bool
    started_at: float
    finished_at: float
    request: Dict[str, Any] = field(default_factory=dict)
    response: Dict[str, Any] = field(default_factory=dict)
    notes: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return round((self.finished_at - self.started_at) * 1000, 3)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["duration_ms"] = self.duration_ms
        return d


@dataclass
class TraceReport:
    request_id: str
    started_at: float = field(default_factory=lambda: time.time())
    finished_at: Optional[float] = None
    context: Dict[str, Any] = field(default_factory=dict)
    steps: list[TraceStep] = field(default_factory=list)

    def add_step(self, step: TraceStep) -> None:
        self.steps.append(step)

    def to_dict(self) -> Dict[str, Any]:
        finished = self.finished_at or time.time()
        return {
            "request_id": self.request_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_s": round(finished - self.started_at, 3),
            "context": _redact_body(self.context),
            "steps": [s.to_dict() for s in self.steps],
        }

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


class TraceLogger:
    """
    轻量 trace logger：
    - stdout：统一 key `request_id=`
    - file：产出脱敏 JSON trace
    """

    def __init__(self, report: TraceReport, *, verbose: bool = True) -> None:
        self.report = report
        self.verbose = verbose

    def log(self, msg: str) -> None:
        if not self.verbose:
            return
        print(f"request_id={self.report.request_id} {msg}")

    def step(
        self,
        name: str,
        *,
        ok: bool,
        started_at: float,
        finished_at: float,
        request: Optional[Dict[str, Any]] = None,
        response: Optional[Dict[str, Any]] = None,
        notes: Optional[Dict[str, Any]] = None,
    ) -> None:
        sanitized_request: Dict[str, Any] = dict(request or {})
        if isinstance(sanitized_request.get("headers"), dict):
            sanitized_request["headers"] = _redact_headers(sanitized_request["headers"])
        if isinstance(sanitized_request.get("request_headers"), dict):
            sanitized_request["request_headers"] = _redact_headers(sanitized_request["request_headers"])

        step = TraceStep(
            name=name,
            ok=ok,
            started_at=started_at,
            finished_at=finished_at,
            request=_redact_body(sanitized_request),
            response=_redact_body(response or {}),
            notes=_redact_body(notes or {}),
        )
        self.report.add_step(step)
        self.log(f"step={name} ok={ok} duration_ms={step.duration_ms}")


__all__ = [
    "TraceLogger",
    "TraceReport",
    "_redact_body",
    "_redact_headers",
    "_safe_sse_event",
]
