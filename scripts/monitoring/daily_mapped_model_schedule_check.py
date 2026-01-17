#!/usr/bin/env python3
"""
Schedule gate for daily mapped-model JWT E2E (message-only).

Exit codes:
  0 - due to run
  3 - skip (not due yet)
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TIME = "05:00"
MIN_INTERVAL_HOURS = 3
MAX_INTERVAL_HOURS = 24
USER_TYPES = ("anonymous", "permanent")


def _parse_datetime_local(raw: Any) -> datetime | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def _normalize_interval_hours(value: Any) -> int | None:
    try:
        hours = int(value)
    except Exception:
        return None
    if hours < MIN_INTERVAL_HOURS or hours > MAX_INTERVAL_HOURS:
        return None
    return hours


def _parse_hhmm(value: Any) -> tuple[int, int] | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) != 5 or text[2] != ":":
        return None
    try:
        hour = int(text[:2])
        minute = int(text[3:])
    except Exception:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour, minute


def _load_interval_hours(conn: sqlite3.Connection) -> int | None:
    try:
        row = conn.execute("SELECT config_json FROM dashboard_config WHERE id = 1").fetchone()
    except Exception:
        return None
    if not row or not row[0]:
        return None
    try:
        payload = json.loads(row[0])
    except Exception:
        return None
    if isinstance(payload, dict):
        parsed = _normalize_interval_hours(payload.get("e2e_interval_hours"))
        if parsed is not None:
            return parsed
    return None


def _load_schedule_time(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute("SELECT config_json FROM dashboard_config WHERE id = 1").fetchone()
    except Exception:
        return DEFAULT_TIME
    if not row or not row[0]:
        return DEFAULT_TIME
    try:
        payload = json.loads(row[0])
    except Exception:
        return DEFAULT_TIME
    if isinstance(payload, dict):
        candidate = payload.get("e2e_daily_time")
        if _parse_hhmm(candidate) is not None:
            return str(candidate).strip()
    return DEFAULT_TIME


def _latest_run_times(conn: sqlite3.Connection) -> dict[str, datetime | None]:
    latest: dict[str, datetime | None] = {user_type: None for user_type in USER_TYPES}
    try:
        rows = conn.execute(
            """
            SELECT user_type, finished_at, started_at, created_at
            FROM e2e_mapped_model_runs
            WHERE user_type IN ('anonymous', 'permanent')
            ORDER BY created_at DESC
            """
        ).fetchall()
    except Exception:
        return latest

    for user_type, finished_at, started_at, created_at in rows:
        key = str(user_type or "").strip()
        if key not in latest or latest[key] is not None:
            continue
        dt_value = _parse_datetime_local(finished_at)
        if dt_value is None:
            dt_value = _parse_datetime_local(started_at)
        if dt_value is None:
            dt_value = _parse_datetime_local(created_at)
        latest[key] = dt_value
        if all(latest.values()):
            break
    return latest


def _should_run(db_path: Path, now_local: datetime) -> tuple[bool, str]:
    if not db_path.exists():
        schedule_time = DEFAULT_TIME
        parsed = _parse_hhmm(schedule_time) or (5, 0)
        scheduled = now_local.replace(hour=parsed[0], minute=parsed[1], second=0, microsecond=0)
        return (now_local >= scheduled), "no_db"

    try:
        conn = sqlite3.connect(str(db_path))
    except Exception:
        schedule_time = DEFAULT_TIME
        parsed = _parse_hhmm(schedule_time) or (5, 0)
        scheduled = now_local.replace(hour=parsed[0], minute=parsed[1], second=0, microsecond=0)
        return (now_local >= scheduled), "db_open_failed"

    try:
        interval_hours = _load_interval_hours(conn)
        latest = _latest_run_times(conn)

        if interval_hours is not None:
            for user_type in USER_TYPES:
                last_run = latest.get(user_type)
                if last_run is None:
                    return True, "never_ran"
                delta = now_local - last_run
                if delta.total_seconds() >= float(interval_hours) * 3600.0:
                    return True, "due"
            return False, "not_due"

        schedule_time = _load_schedule_time(conn)
        parsed = _parse_hhmm(schedule_time) or (5, 0)
        scheduled = now_local.replace(hour=parsed[0], minute=parsed[1], second=0, microsecond=0)
        if now_local < scheduled:
            return False, "not_time"

        today = now_local.date()
        for user_type in USER_TYPES:
            last_run = latest.get(user_type)
            if last_run is None or last_run.date() != today:
                return True, "due"
        return False, "already_ran"
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main() -> int:
    db_path = Path(str(os.getenv("SQLITE_DB_PATH", "data/db.sqlite3")))
    now_local = datetime.now().astimezone()
    should_run, reason = _should_run(db_path, now_local)
    if should_run:
        return 0
    sys.stdout.write(f"Daily E2E skipped: {reason}\\n")
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
