"""One-shot collection entry point for Task Scheduler and cron."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import agents, observability, sources, storage


def run_scheduled_collection(
    *, task_id: str = "daily-recommended-sources",
    planned_at: str | None = None, source_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Run the recommended source set and persist scheduler metadata."""
    storage.init_db()
    agents.refresh_source_event_counts()
    planned = planned_at or storage.utcnow()
    selected = source_ids or list(sources.recommended_sources())
    observability.log_event(
        "scheduled_collection_started", task_id=task_id,
        planned_at=planned, source_ids=selected,
    )
    result = agents.run_collection(
        selected,
        trigger="scheduled",
        scheduler={
            "task_id": task_id,
            "planned_at": planned,
            "actual_at": storage.utcnow(),
            "trigger_source": "windows_task_scheduler_or_cron",
        },
    )
    if result.get("status") == "failed":
        observability.emit_alert(
            "scheduled_collection_failed",
            "每日计划采集失败",
            severity="error",
            context={
                "run_id": result.get("run_id"),
                "task_id": task_id,
                "planned_at": planned,
                "status": result.get("status"),
            },
        )
    elif result.get("status") == "partial":
        observability.emit_alert(
            "scheduled_collection_partial",
            "每日计划采集部分成功",
            severity="warning",
            context={
                "run_id": result.get("run_id"),
                "task_id": task_id,
                "planned_at": planned,
                "status": result.get("status"),
            },
        )
    observability.log_event(
        "scheduled_collection_finished",
        task_id=task_id,
        run_id=result.get("run_id"),
        status=result.get("status"),
        events_added=result.get("events_added"),
        events_updated=result.get("events_updated"),
    )
    result["task_id"] = task_id
    result["planned_at"] = planned
    result["actual_at"] = result.get("started_at") or storage.utcnow()
    return result


def default_planned_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
