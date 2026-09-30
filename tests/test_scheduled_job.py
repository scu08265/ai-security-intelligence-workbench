"""External scheduler runs must carry task, planned, and actual times."""

from __future__ import annotations

from app import scheduled_job


def test_scheduled_job_records_trigger_and_metadata(monkeypatch):
    calls: list[dict] = []

    def fake_run_collection(source_ids=None, **kwargs):
        calls.append({"source_ids": source_ids, **kwargs})
        return {
            "run_id": "run-scheduled-test",
            "status": "partial",
            "events_added": 1,
            "events_updated": 0,
            "results": [{"source_id": "nvd", "status": "partial"}],
        }

    monkeypatch.setattr(scheduled_job.agents, "run_collection", fake_run_collection)
    result = scheduled_job.run_scheduled_collection(
        task_id="task-123",
        planned_at="2099-01-01T02:30:00Z",
        source_ids=["nvd"],
    )

    assert calls[0]["source_ids"] == ["nvd"]
    assert calls[0]["trigger"] == "scheduled"
    assert calls[0]["scheduler"]["task_id"] == "task-123"
    assert calls[0]["scheduler"]["planned_at"] == "2099-01-01T02:30:00Z"
    assert calls[0]["scheduler"]["actual_at"]
    assert result["task_id"] == "task-123"
    assert result["planned_at"] == "2099-01-01T02:30:00Z"


def test_structured_logs_redact_secret_values():
    from app import observability

    payload = observability.log_event(
        "test", api_key="should-not-leak", nested={"GITHUB_TOKEN": "secret"},
    )
    assert payload["api_key"] == "[redacted]"
    assert payload["nested"]["GITHUB_TOKEN"] == "[redacted]"
    alerts = observability.recent_alerts()
    assert alerts["items"] == []


def test_scheduled_partial_run_invokes_self_healing(monkeypatch):
    healing_calls: list[list] = []
    monkeypatch.setattr(
        scheduled_job.agents,
        "run_collection",
        lambda source_ids, **kwargs: {
            "run_id": "run-partial",
            "status": "partial",
            "results": [
                {"source_id": "msrc", "status": "stale"},
                {"source_id": "nvd", "status": "ok"},
            ],
        },
    )
    monkeypatch.setattr(
        scheduled_job.self_healing,
        "run_self_healing",
        lambda source_ids, **kwargs: healing_calls.append(source_ids) or {"status": "completed"},
    )
    result = scheduled_job.run_scheduled_collection(task_id="heal-task")
    assert healing_calls == [["msrc"]]
    assert result["self_healing"]["status"] == "completed"
