"""Run an interval scheduler for local validation or hourly collection."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import scheduled_job  # noqa: E402


def _planned_at() -> str:
    now = datetime.now(timezone.utc)
    planned = now.replace(minute=0, second=0, microsecond=0)
    return planned.isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", default="hourly-recommended-sources")
    parser.add_argument("--interval-seconds", type=int, default=3600)
    parser.add_argument("--cycles", type=int, default=0, help="0 means run forever")
    parser.add_argument("--source-id", action="append", default=[])
    args = parser.parse_args()
    if args.interval_seconds < 30:
        parser.error("--interval-seconds must be at least 30")

    completed = 0
    while True:
        cycle = completed + 1
        task_id = args.task_id if completed == 0 else f"{args.task_id}-{cycle}"
        result = scheduled_job.run_scheduled_collection(
            task_id=task_id,
            planned_at=_planned_at(),
            source_ids=args.source_id or None,
        )
        print(json.dumps({
            "cycle": cycle,
            "run_id": result.get("run_id"),
            "status": result.get("status"),
            "task_id": task_id,
            "planned_at": result.get("planned_at"),
            "actual_at": result.get("actual_at"),
        }, ensure_ascii=False), flush=True)
        completed += 1
        if args.cycles and completed >= args.cycles:
            break
        time.sleep(args.interval_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
