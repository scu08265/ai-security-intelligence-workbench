"""Run one scheduled collection for Windows Task Scheduler or cron."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config, observability, scheduled_job  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the recommended source collection once.")
    parser.add_argument("--task-id", default="daily-recommended-sources")
    parser.add_argument("--planned-at", default="")
    parser.add_argument("--source-id", action="append", default=[])
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    config.ensure_dirs()
    try:
        result = scheduled_job.run_scheduled_collection(
            task_id=args.task_id,
            planned_at=args.planned_at or scheduled_job.default_planned_at(),
            source_ids=args.source_id or None,
        )
    except Exception as exc:  # noqa: BLE001 - scheduled jobs must leave an alert
        message = f"{type(exc).__name__}: {exc}"
        observability.emit_alert(
            "scheduled_job_exception", message,
            severity="error", context={"task_id": args.task_id},
        )
        print(json.dumps({"status": "failed", "error": message}, ensure_ascii=False))
        return 1

    if args.json_out:
        output = Path(args.json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "run_id": result.get("run_id"),
        "status": result.get("status"),
        "task_id": result.get("task_id"),
        "planned_at": result.get("planned_at"),
        "actual_at": result.get("actual_at"),
        "events_added": result.get("events_added"),
        "events_updated": result.get("events_updated"),
        "source_results": [{
            "source_id": item.get("source_id"),
            "status": item.get("status"),
            "error": item.get("error"),
            "duration_ms": item.get("duration_ms"),
        } for item in result.get("results") or []],
    }, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
