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

    def recovered_run(source_ids, **kwargs):
        storage.update_source_state("nvd", status="ok", last_error=None)
        return {
            "run_id": "run-recovered",
            "status": "completed",
            "results": [],
        }

    monkeypatch.setattr(
        self_healing.agents,
        "run_collection",
        recovered_run,
    )
    result = self_healing.run_self_healing(["nvd"])
    assert result["recovered"]
    assert result["decisions"][0]["failure_class"] == "upstream_timeout"
    run = storage.latest_run("self_healing")
    assert run["status"] == "completed"
    assert run["detail"]["recovered"][0]["source_id"] == "nvd"


def test_stale_run_status_does_not_claim_recovery(monkeypatch):
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
            "run_id": "run-still-failed",
            "status": "completed",
            "results": [],
        },
    )
    result = self_healing.run_self_healing(["nvd"])
    assert result["recovered"] == []
    assert result["failed_after_retry"][0]["source_id"] == "nvd"
    assert result["failed_after_retry"][0]["recovered"] is False


def test_ghsa_without_token_is_not_auto_retried():
    storage.update_source_state("ghsa", status="failed", last_error="missing token")
    decision = self_healing.recovery_decision("ghsa", storage.source_state("ghsa"))
    assert decision["retry"] is False
    assert "GITHUB_TOKEN" in decision["reason"]


def _collect_run(source_id: str, status: str, day: int) -> None:
    stamp = f"2099-01-{day:02d}T00:00:00Z"
    storage.save_run({
        "id": f"run-{source_id}-{day}", "kind": "collect", "status": "partial",
        "started_at": stamp, "finished_at": stamp, "summary": None,
        "detail": {"results": [{"source_id": source_id, "status": status}]},
    })


def test_consecutive_failures_counts_only_the_trailing_attempts():
    _collect_run("osv", "failed", 1)
    _collect_run("osv", "ok", 2)
    _collect_run("osv", "failed", 3)
    _collect_run("osv", "stale", 4)
    assert self_healing.consecutive_failures("osv") == 2
    # Never attempted is a streak of zero, not a streak of success.
    assert self_healing.consecutive_failures("msrc") == 0


def test_a_source_without_a_substitute_is_dropped_from_the_unattended_set():
    for day in (1, 2, 3):
        _collect_run("osv", "failed", day)
    decision = self_healing.degradation_for("osv", 3)
    assert decision["action"] == "reduce_frequency"
    storage.save_source_degradation({**decision, "expires_at": self_healing._expiry()})

    selected, notes = self_healing.apply_degradation_policy(["nvd", "osv"])
    assert selected == ["nvd"]
    assert notes == [{
        "source_id": "osv", "action": "reduce_frequency", "substituted_with": [],
        "reason": decision["reason"], "expires_at": storage.source_degradation("osv")["expires_at"],
    }]


def test_a_source_with_a_declared_substitute_hands_over_to_it():
    decision = self_healing.degradation_for("arxiv", 3)
    assert decision["action"] == "switch_backup"
    assert decision["backup_sources"] == ["openalex"]
    storage.save_source_degradation({**decision, "expires_at": self_healing._expiry()})

    selected, notes = self_healing.apply_degradation_policy(["arxiv"])
    assert selected == ["openalex"]
    assert notes[0]["substituted_with"] == ["openalex"]


def test_below_the_threshold_nothing_is_degraded():
    assert self_healing.degradation_for("osv", 2) is None
    selected, notes = self_healing.apply_degradation_policy(["nvd", "osv"])
    assert selected == ["nvd", "osv"]
    assert notes == []


def test_recovery_clears_an_active_cooldown(monkeypatch):
    for day in (1, 2, 3):
        _collect_run("nvd", "failed", day)
    storage.update_source_state("nvd", status="failed", last_error="HTTP 503 timeout")
    storage.save_source_degradation({
        "source_id": "nvd", "action": "reduce_frequency",
        "consecutive_failures": 3, "expires_at": self_healing._expiry(),
    })

    def recovered_run(source_ids, **kwargs):
        storage.update_source_state("nvd", status="ok", last_error=None)
        _collect_run("nvd", "ok", 5)
        return {"run_id": "run-recovered", "status": "completed", "results": []}

    monkeypatch.setattr(self_healing.agents, "run_collection", recovered_run)
    result = self_healing.run_self_healing(["nvd"])

    assert result["recovered"]
    assert result["degradations"] == []
    assert result["degradations_cleared"] == ["nvd"]
    assert storage.source_degradation("nvd") is None
