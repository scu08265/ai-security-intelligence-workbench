"""A2：处置队列巡检是一条可调度的运行，而不是脚本里的临时动作。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import disposition, disposition_ops, observability, storage


def _seed(event_id: str = "CVE-2099-OPS", version: str = "1.0.0") -> tuple[str, str]:
    storage.upsert_event({
        "id": event_id, "kind": "vulnerability", "status": "published",
        "title": "ops fixture", "component": "ops-lib", "severity": "high",
        "affected": [{"source_id": f"nvd:{event_id}", "package": "ops-lib",
                      "range": "<2.0.0", "fixed_version": "2.0.0"}],
        "sources": [{"id": f"nvd:{event_id}"}],
    })
    storage.upsert_asset({
        "id": "asset-ops", "name": "ops asset", "component": "ops-lib",
        "version": version, "authorized": True,
    })
    storage.save_assessment({
        "event_id": event_id, "asset_id": "asset-ops",
        "status": "affected", "priority": "high",
        "reasons": ["version matches affected range"],
        "evidence_ids": [f"nvd:{event_id}"],
    })
    return event_id, "asset-ops"


def _ago(hours: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()


def test_the_sweep_is_a_schedulable_run_with_a_stage_trace():
    event_id, asset_id = _seed()
    disposition.update_disposition(event_id, asset_id, status="in_progress",
                                   assignee="alice")

    result = disposition_ops.run_disposition_ops(trigger="scheduled")

    run = storage.latest_run("disposition")
    assert run is not None, "巡检必须留下一条 disposition 运行记录"
    detail = run["detail"]
    assert detail["scheduler"]["task_id"] == disposition_ops.DEFAULT_TASK_ID
    assert detail["scheduler"]["trigger_source"] == "windows_task_scheduler_or_cron"
    assert [item["stage"] for item in detail["scheduler_trace"]] == [
        "queue", "assign", "recheck", "close_or_accept",
    ]
    assert result["run_id"] == run["id"]
    assert result["queue"]["queue_total"] == 1
    assert result["queue"]["registered_total"] == 1


def test_the_sweep_records_the_queue_reading_at_run_time():
    """``/api/dispositions/pending`` 的读数必须随运行一起被记下来。"""
    _seed("CVE-2099-OPS-A")
    _seed("CVE-2099-OPS-B", version="1.0.0")

    result = disposition_ops.run_disposition_ops(trigger="manual")

    assert result["queue"]["pending_total"] == 2
    run = storage.latest_run("disposition")
    assert run["detail"]["queue"]["pending_total"] == 2
    assert run["detail"]["scheduler"]["trigger_source"] == "manual_or_api"


def test_an_overdue_item_is_reported_and_alerted():
    event_id, asset_id = _seed()
    # ``opened_at`` is frozen by storage once the row exists, so build the
    # "opened 30 hours ago" record directly instead of editing it afterwards.
    storage.save_assessment_disposition({
        "event_id": event_id, "asset_id": asset_id, "status": "in_progress",
        "assignee": "alice", "opened_at": _ago(30), "updated_at": _ago(30),
        "opened_priority": "high", "opened_assessment_status": "affected",
    })

    result = disposition_ops.run_disposition_ops(overdue_hours=24)

    assert [row["event_id"] for row in result["overdue"]] == [event_id]
    alerts = observability.recent_alerts(limit=20)["items"]
    assert any(item["code"] == "disposition_overdue" for item in alerts)
    assert result["status"] == "attention"


def test_a_fixed_item_becomes_recheck_due_after_the_window():
    event_id, asset_id = _seed()
    storage.save_assessment_disposition({
        "event_id": event_id, "asset_id": asset_id, "status": "fixed",
        "assignee": "alice", "opened_at": _ago(30), "updated_at": _ago(30),
        "opened_priority": "high", "opened_assessment_status": "affected",
        "version_before": "1.0.0", "version_after": "1.0.0",
    })

    result = disposition_ops.run_disposition_ops(recheck_due_hours=24)

    assert [row["event_id"] for row in result["recheck_due"]] == [event_id]
    assert result["steps"][2]["stage"] == "recheck"
    alerts = observability.recent_alerts(limit=20)["items"]
    assert any(item["code"] == "disposition_recheck_due" for item in alerts)


def test_the_sweep_never_closes_anything_by_itself():
    """编排不做自动关闭：巡检前后状态与闭环率必须一模一样。"""
    event_id, asset_id = _seed()
    disposition.update_disposition(event_id, asset_id, status="in_progress",
                                   assignee="alice")
    before = disposition.metrics()

    result = disposition_ops.run_disposition_ops()

    after = disposition.metrics()
    assert result["steps"][3]["detail"]["closed"] == []
    assert before["status_breakdown"] == after["status_breakdown"]
    assert before["closure_rate"] == after["closure_rate"]
    assert storage.latest_run("disposition")["detail"]["policy"]["auto_close"] is False


def test_an_in_progress_item_without_an_assignee_is_reported():
    """处置人缺失是配置问题，巡检要单独报出来，而不是算成"处置慢"。"""
    event_id, asset_id = _seed()
    storage.save_assessment_disposition({
        "event_id": event_id, "asset_id": asset_id, "status": "in_progress",
        "assignee": None, "opened_at": storage.utcnow(),
        "opened_priority": "high", "opened_assessment_status": "affected",
        "updated_at": storage.utcnow(),
    })

    result = disposition_ops.run_disposition_ops()

    assert [row["event_id"] for row in result["unassigned"]] == [event_id]
    assert result["status"] == "attention"
