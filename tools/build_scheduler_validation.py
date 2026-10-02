"""Write the real Windows Task Scheduler/cron evidence from persisted runs."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import config, storage  # noqa: E402


def _run_payload(run: dict[str, Any]) -> dict[str, Any]:
    detail = run.get("detail") or {}
    scheduler = detail.get("scheduler") or {}
    return {
        "id": run.get("id"),
        "run_id": run.get("id"),
        "status": run.get("status"),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "task_id": scheduler.get("task_id"),
        "planned_at": scheduler.get("planned_at"),
        "actual_at": scheduler.get("actual_at"),
        "trigger_source": scheduler.get("trigger_source"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="reports/scheduler-validation.json")
    args = parser.parse_args()

    storage.init_db()
    runs = [
        run for run in storage.list_runs(limit=2000)
        if run.get("kind") == "collect"
        and (run.get("detail") or {}).get("trigger") == "scheduled"
    ]
    task_ids = Counter(
        str(((run.get("detail") or {}).get("scheduler") or {}).get("task_id") or "")
        for run in runs
    )
    task_ids.pop("", None)
    days = sorted({str(run.get("started_at") or "")[:10] for run in runs})
    payload = {
        "version": config.APP_VERSION,
        "generated_at": storage.utcnow(),
        "evidence_source": "persisted runs with detail.trigger=scheduled",
        "scheduled_run_count": len(runs),
        "scheduled_run_days": len(days),
        "first_scheduled_run": _run_payload(runs[-1]) if runs else None,
        "latest_scheduled_run": _run_payload(runs[0]) if runs else None,
        "task_ids": dict(sorted(task_ids.items())),
        "acceptance": {
            "has_scheduled_trigger": bool(runs),
            "has_hourly_task_id": any(
                task_id == "hourly-recommended-sources" for task_id in task_ids
            ),
            "scheduled_run_days_grew_from_zero": len(days) > 0,
        },
        "runs": [_run_payload(run) for run in runs[:100]],
    }
    output = (ROOT / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "scheduled_run_count": payload["scheduled_run_count"],
        "scheduled_run_days": payload["scheduled_run_days"],
        "acceptance": payload["acceptance"],
    }, ensure_ascii=True, indent=2))
    return 0 if all(payload["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
