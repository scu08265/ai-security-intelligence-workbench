"""Run one scheduled disposition sweep for Windows Task Scheduler or cron."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config, disposition_ops, observability  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the disposition queue sweep once.")
    parser.add_argument("--task-id", default=disposition_ops.DEFAULT_TASK_ID)
    parser.add_argument("--planned-at", default="")
    parser.add_argument("--trigger", default="scheduled",
                        choices=["scheduled", "manual"])
    parser.add_argument("--overdue-hours", type=int,
                        default=disposition_ops.DEFAULT_OVERDUE_HOURS)
    parser.add_argument("--recheck-due-hours", type=int,
                        default=disposition_ops.DEFAULT_RECHECK_DUE_HOURS)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    config.ensure_dirs()
    try:
        result = disposition_ops.run_disposition_ops(
            task_id=args.task_id,
            planned_at=args.planned_at or disposition_ops.default_planned_at(),
            trigger=args.trigger,
            overdue_hours=args.overdue_hours,
            recheck_due_hours=args.recheck_due_hours,
        )
    except Exception as exc:  # noqa: BLE001 - a scheduled job must leave an alert
        message = f"{type(exc).__name__}: {exc}"
        observability.emit_alert(
            "scheduled_disposition_exception", message,
            severity="error", context={"task_id": args.task_id},
        )
        print(json.dumps({"status": "failed", "error": message}, ensure_ascii=False))
        return 1

    if args.json_out:
        output = Path(args.json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    print(json.dumps({
        "run_id": result.get("run_id"),
        "task_id": result.get("task_id"),
        "status": result.get("status"),
        "planned_at": result.get("planned_at"),
        "summary": result.get("summary"),
        "queue": result.get("queue"),
        "steps": [{item.get("step"): item.get("stage")} for item in result.get("steps") or []],
        "overdue": len(result.get("overdue") or []),
        "recheck_due": len(result.get("recheck_due") or []),
    }, ensure_ascii=False, indent=2))
    return 0 if result.get("status") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
