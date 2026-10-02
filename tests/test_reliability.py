"""A-owner metrics must use first discovery and preserve unknown states."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import reliability, storage


def _event(event_id: str, published: str, discovered: str) -> dict:
    return {
        "id": event_id,
        "published_at": published,
        "monitoring_observations": [
            {
                "source_id": "nvd",
                "source_published_at": published,
                "discovered_at": discovered,
                "publication_to_discovery_seconds": None,
            },
        ],
    }


def test_timeliness_uses_only_the_first_observation_per_event():
    event = {
        "id": "CVE-2099-RELIABILITY",
        "published_at": "2099-01-01T00:00:00Z",
        "monitoring_observations": [
            {
                "source_id": "nvd",
                "source_published_at": "2099-01-01T00:00:00Z",
                "discovered_at": "2099-01-01T07:00:00Z",
            },
            {
                "source_id": "nvd",
                "source_published_at": "2099-01-01T00:00:00Z",
                "discovered_at": "2099-01-03T00:00:00Z",
            },
        ],
    }
    result = reliability.timeliness_stats([event])
    assert result["computable_samples"] == 1
    assert result["within_6h"]["count"] == 0
    assert result["within_12h"]["count"] == 1
    assert result["records"][0]["latency_hours"] == 7.0


def test_placeholder_and_future_publisher_times_are_unknown():
    now = datetime.now(timezone.utc)
    events = [
        _event("DOC-PLACEHOLDER", "0001-01-01T00:00:00Z", "2099-01-01T00:00:00Z"),
        _event("DOC-FUTURE", (now + timedelta(hours=2)).isoformat(), now.isoformat()),
    ]
    result = reliability.timeliness_stats(events)
    assert result["computable_samples"] == 0
    assert result["unknown_samples"] == 2
    assert result["unknown_reasons"]["invalid_or_missing_publisher_time"] == 1
    assert result["unknown_reasons"]["publisher_time_after_discovery"] == 1


def test_first_run_backfill_is_not_counted_as_monitoring_latency():
    event = _event(
        "CVE-2099-BACKFILL",
        "2099-01-01T00:00:00Z",
        "2099-01-03T00:00:00Z",
    )
    started = datetime(2099, 1, 2, tzinfo=timezone.utc)
    result = reliability.timeliness_stats([event], monitoring_started_at=started)
    assert result["computable_samples"] == 0
    assert result["effective_denominator"] == 0
    assert result["post_monitoring_samples"] == 1
    assert result["baseline_excluded_samples"] == 1


def test_source_health_distinguishes_failure_with_historical_data():
    storage.update_source_state(
        "nvd", status="failed", events_count=3,
        last_success="2099-01-01T00:00:00Z", last_error="HTTP 503",
    )
    runs = [{
        "id": "run-health", "kind": "collect", "status": "partial",
        "started_at": "2099-01-02T00:00:00Z", "finished_at": "2099-01-02T00:00:01Z",
        "detail": {
            "trigger": "scheduled",
            "results": [{
                "source_id": "nvd", "status": "failed",
                "duration_ms": 1250, "error": "HTTP 503",
            }],
        },
    }]
    item = next(
        item for item in reliability.source_health(runs)["items"]
        if item["id"] == "nvd"
    )
    assert item["health_class"] == "real_failure_historical_data_available"
    assert item["success_rate"] == 0.0
    assert item["duration_ms_p50"] == 1250.0


def test_source_health_treats_stale_as_failure_with_historical_data():
    storage.update_source_state(
        "openalex", status="stale", events_count=41,
        last_success="2099-01-01T00:00:00Z",
        last_error="ConnectTimeout: SSL handshake timed out",
    )
    runs = [{
        "id": "run-stale", "kind": "collect", "status": "partial",
        "started_at": "2099-01-02T00:00:00Z",
        "finished_at": "2099-01-02T00:00:01Z",
        "detail": {
            "trigger": "scheduled",
            "results": [{
                "source_id": "openalex", "status": "stale",
                "duration_ms": 241608,
                "error": "ConnectTimeout: SSL handshake timed out",
            }],
        },
    }]
    item = next(
        item for item in reliability.source_health(runs)["items"]
        if item["id"] == "openalex"
    )
    assert item["current_status"] == "stale"
    assert item["health_class"] == "real_failure_historical_data_available"
    assert item["success_rate"] == 0.0
    assert item["failed_attempts"] == 0
    assert item["stale_attempts"] == 1
    assert item["failure_reason"] == "ConnectTimeout: SSL handshake timed out"


def test_continuous_run_evidence_requires_scheduled_trigger():
    today = datetime.now(timezone.utc)
    runs = []
    for offset in (1, 0):
        stamp = (today - timedelta(days=offset)).isoformat()
        runs.append({
            "id": f"run-scheduled-{offset}",
            "kind": "collect",
            "status": "completed",
            "started_at": stamp,
            "finished_at": stamp,
            "detail": {"trigger": "scheduled", "results": []},
        })
    manual = {
        "id": "run-manual", "kind": "collect", "status": "completed",
        "started_at": today.isoformat(), "finished_at": today.isoformat(),
        "detail": {"trigger": "manual", "results": []},
    }
    result = reliability.continuous_run_evidence(7, [manual, *runs])
    assert result["actual_run_days"] == 2
    assert result["scheduled_run_days"] == 2
    assert result["consecutive_executed_days"] == 2
    assert result["target_met"] is False
    assert result["scheduled_run_count"] == 2
    today_ledger = result["ledger"][-1]
    assert today_ledger["actual_run_count"] == 2
    assert today_ledger["scheduled_run_count"] == 1
