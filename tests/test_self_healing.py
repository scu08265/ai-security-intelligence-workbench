"""Bounded automatic recovery and failure classification."""

from __future__ import annotations

from app import self_healing, storage


def test_failure_classification_is_explicit():
    assert self_healing.classify_failure("failed", "HTTP 429 rate limit") == "rate_limit"
    assert self_healing.classify_failure("failed", "HTTP 503 no healthy upstream") == "upstream_timeout"
    assert self_healing.classify_failure("failed", "missing GITHUB_TOKEN") == "authentication"
    assert self_healing.classify_failure("failed", "incomplete chunked read") == "connection_reset"


def test_failed_source_recovers_once_and_records_evidence(monkeypatch):
    storage.update_source_state(
        "nvd",
        status="failed",
        last_error="HTTP 503 timeout",
        events_count=3,
    )
    monkeypatch.setattr(
        self_healing.agents,
        "run_collection",
        lambda source_ids, **kwargs: {
            "run_id": "run-recovered",
            "status": "completed",
            "results": [],
        },
    )
    result = self_healing.run_self_healing(["nvd"])
    assert result["recovered"]
    assert result["decisions"][0]["failure_class"] == "upstream_timeout"
    run = storage.latest_run("self_healing")
    assert run["status"] == "completed"
    assert run["detail"]["recovered"][0]["source_id"] == "nvd"


def test_ghsa_without_token_is_not_auto_retried():
    storage.update_source_state("ghsa", status="failed", last_error="missing token")
    decision = self_healing.recovery_decision("ghsa", storage.source_state("ghsa"))
    assert decision["retry"] is False
    assert "GITHUB_TOKEN" in decision["reason"]
