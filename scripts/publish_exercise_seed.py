#!/usr/bin/env python3
"""发布/更新官方动作库种子（写入 sqlite.exercise_library_snapshots）。"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.db.sqlite_manager import SQLiteManager
from app.services.exercise_library_service import ExerciseLibraryService, ExerciseDto


async def _run(db_path: Path, seed_path: Path) -> int:
    sqlite_manager = SQLiteManager(db_path)
    await sqlite_manager.init()
    try:
        service = ExerciseLibraryService(sqlite_manager, seed_path=seed_path)
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
        items = [ExerciseDto.model_validate(item) for item in raw]
        meta = await service.publish(items)
        print(meta.model_dump(mode="json"))
        return 0
    finally:
        await sqlite_manager.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", default="db.sqlite3")
    parser.add_argument("--seed-path", default="assets/exercise_library/seed.json")
    args = parser.parse_args()

    return asyncio.run(_run(Path(args.db_path), Path(args.seed_path)))


if __name__ == "__main__":
    raise SystemExit(main())

