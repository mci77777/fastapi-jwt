from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.monitoring.daily_mapped_model_schedule_check import _should_run


def _create_schedule_db(path: Path, *, interval_hours: int, last_run_hours_ago: float) -> None:
    now_utc = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    last_utc = now_utc - timedelta(hours=float(last_run_hours_ago))

    conn = sqlite3.connect(str(path))
    try:
        conn.execute(
            """
            CREATE TABLE dashboard_config (
                id INTEGER PRIMARY KEY,
                config_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE e2e_mapped_model_runs (
                user_type TEXT,
                started_at TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO dashboard_config (id, config_json) VALUES (1, ?)",
            (json.dumps({"e2e_interval_hours": int(interval_hours)}, ensure_ascii=False),),
        )
        for user_type in ("anonymous", "permanent"):
            conn.execute(
                "INSERT INTO e2e_mapped_model_runs (user_type, started_at, created_at) VALUES (?, ?, ?)",
                (
                    user_type,
                    last_utc.isoformat(),
                    last_utc.strftime("%Y-%m-%d %H:%M:%S"),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def test_schedule_gate_due_when_no_db(tmp_path: Path) -> None:
    db_path = tmp_path / "no_db.sqlite3"
    now_local = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).astimezone()
    should_run, reason = _should_run(db_path, now_local)
    assert should_run is True
    assert reason == "no_db"


def test_schedule_gate_skips_when_within_interval(tmp_path: Path) -> None:
    db_path = tmp_path / "schedule.sqlite3"
    _create_schedule_db(db_path, interval_hours=3, last_run_hours_ago=2)
    now_local = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).astimezone()
    should_run, reason = _should_run(db_path, now_local)
    assert should_run is False
    assert reason == "not_due"


def test_schedule_gate_due_when_reaches_interval(tmp_path: Path) -> None:
    db_path = tmp_path / "schedule_due.sqlite3"
    _create_schedule_db(db_path, interval_hours=3, last_run_hours_ago=3)
    now_local = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc).astimezone()
    should_run, reason = _should_run(db_path, now_local)
    assert should_run is True
    assert reason == "due"

