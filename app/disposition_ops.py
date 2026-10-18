"""Daily disposition sweep: queue -> assign -> re-check -> close / accept risk.

This is the orchestration the closure rate was missing.  It does **not** close
anything by itself -- closing still requires a per-asset system re-check through
``disposition.update_disposition`` -- but it turns the flow into a schedulable
run with a step trace, the same way collection does.

Each run records:

* the queue composition (pending / in progress / awaiting re-check / closed /
  accepted risk),
* which items are overdue for a decision and which are due for re-verification,
* one trace entry per stage, so every step of the flow can be checked from the
  run ledger instead of only existing inside a script.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from . import disposition, observability, storage

DEFAULT_TASK_ID = "daily-disposition-queue"
DEFAULT_OVERDUE_HOURS = 24
DEFAULT_RECHECK_DUE_HOURS = 24


def _now() -> str:
    return storage.utcnow()


def _hours_since(stamp: Any, *, now: datetime) -> float | None:
    if not stamp:
        return None
    text = str(stamp).replace("Z", "+00:00")
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return round((now - moment).total_seconds() / 3600, 2)


def queue_snapshot() -> dict[str, Any]:
    """Who is in the queue right now, by stage."""
    metrics = disposition.metrics()
    pending = disposition.pending_cohort(limit=1000)
    rows = disposition.list_dispositions(limit=5000)["items"]
    cohort = [row for row in rows
              if row.get("opened_priority") in {"critical", "high"}]
    by_status: dict[str, list[dict[str, Any]]] = {}
    for row in cohort:
        by_status.setdefault(str(row.get("status") or "open"), []).append(row)
    return {
        "generated_at": _now(),
        "pending_total": pending.get("pending_total"),
        "pending_by_priority": pending.get("by_priority"),
        "registered_total": metrics.get("high_priority_registered"),
        "queue_total": metrics.get("high_priority_total"),
        "closure_rate": metrics.get("closure_rate"),
        "registered_closure_rate": metrics.get("registered_closure_rate"),
        "status_counts": {key: len(value) for key, value in by_status.items()},
        "items": cohort,
    }


def _brief(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": row.get("event_id"),
        "asset_id": row.get("asset_id"),
        "status": row.get("status"),
        "assignee": row.get("assignee"),
        "opened_at": row.get("opened_at"),
        "version_before": row.get("version_before"),
    }


def run_disposition_ops(
    *,
    task_id: str = DEFAULT_TASK_ID,
    planned_at: str | None = None,
    trigger: str = "scheduled",
    overdue_hours: int = DEFAULT_OVERDUE_HOURS,
    recheck_due_hours: int = DEFAULT_RECHECK_DUE_HOURS,
) -> dict[str, Any]:
    """Walk the queue once and persist the sweep as a run record."""
    storage.init_db()
    planned = planned_at or _now()
    started_at = _now()
    now = datetime.now(timezone.utc)
    snapshot = queue_snapshot()
    items = snapshot.pop("items")
    steps: list[dict[str, Any]] = []

    def step(name: str, status: str, detail: Any) -> None:
        steps.append({
            "step": len(steps) + 1,
            "stage": name,
            "status": status,
            "at": _now(),
            "detail": detail,
        })

    step("queue", "ok", {
        "pending_total": snapshot.get("pending_total"),
        "queue_total": snapshot.get("queue_total"),
        "registered_total": snapshot.get("registered_total"),
        "status_counts": snapshot.get("status_counts"),
    })

    # Stage 2: assignment check plus overdue reminder.  Entering the flow
    # requires a human on the record, so an unassigned in-progress item is a
    # configuration problem and is reported separately from lateness.
    unassigned = [_brief(row) for row in items
                  if row.get("status") in {"in_progress", "fixed"}
                  and not row.get("assignee")]
    overdue: list[dict[str, Any]] = []
    for row in items:
        if row.get("status") not in {"in_progress", "fixed"}:
            continue
        age = _hours_since(row.get("opened_at"), now=now)
        if age is not None and age >= overdue_hours:
            overdue.append({**_brief(row), "open_hours": age})
    step("assign", "ok" if not (unassigned or overdue) else "attention", {
        "unassigned": unassigned,
        "overdue": overdue,
        "overdue_hours": overdue_hours,
    })

    # Stage 3: re-check due scan.  ``fixed`` means "repaired, awaiting
    # verification" and is never closed automatically; closing still goes
    # through the per-asset system re-check.
    recheck_due: list[dict[str, Any]] = []
    for row in items:
        if row.get("status") != "fixed":
            continue
        age = _hours_since(row.get("updated_at") or row.get("opened_at"), now=now)
        if age is None or age >= recheck_due_hours:
            recheck_due.append({**_brief(row), "waiting_hours": age})
    step("recheck", "ok" if not recheck_due else "attention", {
        "recheck_due": recheck_due,
        "recheck_due_hours": recheck_due_hours,
        "note": "本轮只做到期扫描，不自动关闭；关闭仍走单条复测入口。",
    })

    # Stage 4: read-only summary of what has been closed or accepted.
    closed = [_brief(row) for row in items if row.get("status") == "verified"]
    accepted = [_brief(row) for row in items if row.get("status") == "accepted"]
    step("close_or_accept", "ok", {
        "closed": closed,
        "accepted_risk": accepted,
        "accepted_note": "接受风险是处置决策，不代表风险已消除。",
    })

    alerts: list[dict[str, Any]] = []
    for row in overdue:
        observability.emit_alert(
            "disposition_overdue",
            f"{row['event_id']} 已开单 {row['open_hours']} 小时仍未关闭",
            severity="warning",
            context=row,
        )
        alerts.append({"kind": "disposition_overdue", "event_id": row["event_id"]})
    for row in recheck_due:
        observability.emit_alert(
            "disposition_recheck_due",
            f"{row['event_id']} 标记已修复但尚未复测关闭",
            severity="warning",
            context=row,
        )
        alerts.append({"kind": "disposition_recheck_due", "event_id": row["event_id"]})

    run_id = storage.new_id("run")
    status = "completed" if not (unassigned or overdue or recheck_due) else "attention"
    summary = (
        f"处置队列巡检：待处置 {snapshot.get('pending_total')}，"
        f"处置中 {snapshot.get('status_counts', {}).get('in_progress', 0)}，"
        f"待复测 {snapshot.get('status_counts', {}).get('fixed', 0)}，"
        f"逾期 {len(overdue)} 条"
    )
    detail = {
        "task_id": task_id,
        "trigger": trigger,
        "scheduler": {
            "task_id": task_id,
            "planned_at": planned,
            "actual_at": started_at,
            "trigger_source": ("windows_task_scheduler_or_cron" if trigger == "scheduled"
                               else "manual_or_api"),
        },
        "queue": snapshot,
        "steps": steps,
        "scheduler_trace": steps,
        "unassigned": unassigned,
        "overdue": overdue,
        "recheck_due": recheck_due,
        "alerts": alerts,
        "policy": {
            "auto_close": False,
            "overdue_hours": overdue_hours,
            "recheck_due_hours": recheck_due_hours,
            "note": (
                "本轮编排只做巡检、提醒与到期扫描；关闭必须走单条 verified 并由系统复测。"
                "接受风险不改变原始受影响事实。"
            ),
        },
    }
    storage.save_run({
        "id": run_id,
        "kind": "disposition",
        "status": status,
        "started_at": started_at,
        "finished_at": _now(),
        "summary": summary,
        "detail": detail,
    })
    observability.log_event(
        "disposition_sweep_finished",
        run_id=run_id, task_id=task_id, status=status,
        pending_total=snapshot.get("pending_total"), overdue=len(overdue),
        recheck_due=len(recheck_due),
    )
    return {
        "run_id": run_id,
        "task_id": task_id,
        "status": status,
        "started_at": started_at,
        "finished_at": _now(),
        "planned_at": planned,
        "queue": snapshot,
        "steps": steps,
        "scheduler_trace": steps,
        "unassigned": unassigned,
        "overdue": overdue,
        "recheck_due": recheck_due,
        "alerts": alerts,
        "summary": summary,
    }


def default_planned_at() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def due_soon(*, hours: int = 24) -> list[dict[str, Any]]:
    """Items that will be overdue within ``hours`` (used by the reminder text)."""
    now = datetime.now(timezone.utc)
    horizon = timedelta(hours=hours)
    out: list[dict[str, Any]] = []
    for row in disposition.list_dispositions(limit=5000)["items"]:
        if row.get("status") not in {"in_progress", "fixed"}:
            continue
        opened = row.get("opened_at")
        if not opened:
            continue
        try:
            moment = datetime.fromisoformat(str(opened).replace("Z", "+00:00"))
        except ValueError:
            continue
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        remaining = (moment + horizon) - now
        if timedelta(0) <= remaining <= horizon:
            out.append({**_brief(row), "due_in_hours": round(remaining.total_seconds() / 3600, 2)})
    return out
