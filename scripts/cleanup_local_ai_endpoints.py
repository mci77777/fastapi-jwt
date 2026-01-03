#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


TEST_NAME_PREFIXES = ("test-", "test_", "env-default-")
EXTRA_TEST_NAMES = {"guard-test"}


def _utc_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


@dataclass(frozen=True)
class EndpointRow:
    id: int
    name: str
    base_url: str
    model: str | None
    is_active: int
    is_default: int
    api_key: str | None
    status: str | None
    updated_at: str | None
    created_at: str | None


def _looks_like_test_endpoint(row: EndpointRow) -> bool:
    name = (row.name or "").strip().lower()
    if not name:
        return False
    if name.startswith(TEST_NAME_PREFIXES):
        return True
    if name in EXTRA_TEST_NAMES:
        return True
    return False


def _looks_like_openai_test_endpoint(row: EndpointRow) -> bool:
    base_url = (row.base_url or "").strip().lower()
    if "api.openai.com" not in base_url:
        return False
    name = (row.name or "").strip().lower()
    # 本地跑测试时会创建这些端点；通常 model 为空且状态为 offline
    if name in {"openai-default", "test-openai-default", "guard-test"} or name.startswith("test-openai-default"):
        return True
    return False


def _backup_db_files(db_path: Path) -> Path:
    slug = _utc_slug()
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_base = backup_dir / f"{db_path.name}.{slug}.bak"
    shutil.copy2(db_path, backup_base)
    for ext in (".wal", ".shm"):
        sidecar = db_path.with_suffix(db_path.suffix + ext)
        if sidecar.exists():
            shutil.copy2(sidecar, backup_dir / f"{db_path.name}{ext}.{slug}.bak")
    return backup_base


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup local ai_endpoints test rows (safe by default)")
    parser.add_argument("--db", default="data/db.sqlite3", help="SQLite db path (default: data/db.sqlite3)")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default: dry-run)")
    parser.add_argument(
        "--keep-default-id",
        type=int,
        default=None,
        help="Keep this endpoint as default (if exists after cleanup)",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"db not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id,name,base_url,model,is_active,is_default,api_key,status,updated_at,created_at
        FROM ai_endpoints
        ORDER BY id ASC
        """
    )
    rows = [
        EndpointRow(
            id=int(r["id"]),
            name=str(r["name"] or ""),
            base_url=str(r["base_url"] or ""),
            model=(str(r["model"]) if r["model"] is not None else None),
            is_active=int(r["is_active"] or 0),
            is_default=int(r["is_default"] or 0),
            api_key=(str(r["api_key"]) if r["api_key"] is not None else None),
            status=(str(r["status"]) if r["status"] is not None else None),
            updated_at=(str(r["updated_at"]) if r["updated_at"] is not None else None),
            created_at=(str(r["created_at"]) if r["created_at"] is not None else None),
        )
        for r in cur.fetchall()
    ]

    to_delete: list[EndpointRow] = []
    for r in rows:
        if _looks_like_test_endpoint(r):
            to_delete.append(r)
            continue
        if _looks_like_openai_test_endpoint(r):
            to_delete.append(r)

    # 仅作为保险：按 (name,base_url,model) 去重，保留最新一条
    keep_ids: set[int] = set()
    by_key: dict[tuple[str, str, str], EndpointRow] = {}
    for r in rows:
        key = (r.name.strip().lower(), r.base_url.strip().lower(), (r.model or "").strip().lower())
        prev = by_key.get(key)
        if prev is None or r.id > prev.id:
            by_key[key] = r
    keep_ids = {r.id for r in by_key.values()}

    delete_ids = {r.id for r in to_delete}
    # delete_ids 以“测试清理”为主；去重清理只在其余场景下才动手（避免误删）
    dedupe_delete_ids = {r.id for r in rows if r.id not in keep_ids and r.id not in delete_ids and _looks_like_test_endpoint(r)}
    delete_ids |= dedupe_delete_ids

    remaining = [r for r in rows if r.id not in delete_ids]

    def _best_default_candidate(candidates: list[EndpointRow]) -> EndpointRow | None:
        active = [r for r in candidates if r.is_active]
        if not active:
            return None
        online = [r for r in active if (r.status or "").lower() == "online"]
        if online:
            return sorted(online, key=lambda x: x.id, reverse=True)[0]
        return sorted(active, key=lambda x: x.id, reverse=True)[0]

    desired_default_id = None
    if args.keep_default_id is not None and any(r.id == args.keep_default_id for r in remaining):
        desired_default_id = args.keep_default_id
    else:
        desired_default_id = (_best_default_candidate(remaining) or EndpointRow(0, "", "", None, 0, 0, None, None, None, None)).id or None

    print(f"DB: {db_path} total={len(rows)} delete={len(delete_ids)} remaining={len(remaining)} apply={args.apply}")
    if delete_ids:
        print("Will delete endpoint ids:", ",".join(str(i) for i in sorted(delete_ids)))
    if desired_default_id is not None:
        print("Desired default endpoint id:", desired_default_id)

    if not args.apply:
        print("Dry-run only. Re-run with --apply to execute.")
        conn.close()
        return 0

    backup = _backup_db_files(db_path)
    print("Backup created:", backup)

    conn.execute("BEGIN")
    try:
        if delete_ids:
            conn.execute(
                f"DELETE FROM ai_endpoints WHERE id IN ({','.join(['?']*len(delete_ids))})",
                list(sorted(delete_ids)),
            )

        # 规范化 default：只保留一个 is_default=1
        conn.execute("UPDATE ai_endpoints SET is_default = 0")
        if desired_default_id is not None:
            conn.execute("UPDATE ai_endpoints SET is_default = 1 WHERE id = ?", [desired_default_id])

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print("Cleanup applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

