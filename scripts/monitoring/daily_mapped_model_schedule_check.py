#!/usr/bin/env python3
"""
Schedule gate for daily mapped-model JWT E2E (message-only).

Exit codes:
  0 - due to run
  3 - skip (not scheduled time or already ran today)
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TIME = "05:00"
USER_TYPES = ("anonymous", "permanent")


def _parse_hhmm(value: str) -> tuple[int, int] | None:
    text = str(value or "").strip()
    if not re.match(r"^\d{2}:\d{2}$", text):
        return None
    hour = int(text[:2])
    minute = int(text[3:])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour, minute


def _parse_iso_to_local_date(raw: Any) -> datetime.date | None:
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
    return dt.astimezone().date()


def _load_config_time(conn: sqlite3.Connection) -> str:
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
        candidate = str(payload.get("e2e_daily_time") or "").strip()
        parsed = _parse_hhmm(candidate)
        if parsed:
            return candidate
    return DEFAULT_TIME


def _latest_run_dates(conn: sqlite3.Connection) -> dict[str, datetime.date | None]:
    latest: dict[str, datetime.date | None] = {user_type: None for user_type in USER_TYPES}
    try:
        rows = conn.execute(
            """
            SELECT user_type, started_at, created_at
            FROM e2e_mapped_model_runs
            WHERE user_type IN ('anonymous', 'permanent')
            ORDER BY created_at DESC
            """
        ).fetchall()
    except Exception:
        return latest

    for user_type, started_at, created_at in rows:
        key = str(user_type or "").strip()
        if key not in latest or latest[key] is not None:
            continue
        date_value = _parse_iso_to_local_date(started_at)
        if date_value is None:
            date_value = _parse_iso_to_local_date(created_at)
        latest[key] = date_value
        if all(latest.values()):
            break
    return latest


def _should_run(db_path: Path, now_local: datetime) -> tuple[bool, str]:
    if not db_path.exists():
        schedule_time = DEFAULT_TIME
        hour, minute = _parse_hhmm(schedule_time) or (5, 0)
        scheduled = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return (now_local >= scheduled), "no_db"

    try:
        conn = sqlite3.connect(str(db_path))
    except Exception:
        schedule_time = DEFAULT_TIME
        hour, minute = _parse_hhmm(schedule_time) or (5, 0)
        scheduled = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return (now_local >= scheduled), "db_open_failed"

    try:
        schedule_time = _load_config_time(conn)
        parsed = _parse_hhmm(schedule_time) or (5, 0)
        scheduled = now_local.replace(hour=parsed[0], minute=parsed[1], second=0, microsecond=0)
        if now_local < scheduled:
            return False, "not_time"

        latest = _latest_run_dates(conn)
        today = now_local.date()
        for user_type in USER_TYPES:
            last_date = latest.get(user_type)
            if last_date != today:
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
