"""The pipeline state machine and the bounded gap-closing scheduler."""

from __future__ import annotations

import httpx

from app import agents, collectors, evaluation, intelligence, storage

from fixtures import KEV_SYNTHETIC, OSV_SYNTHETIC


def _event(event_id="CVE-2099-00001", **updates):
    base = {
        "id": event_id, "kind": "vulnerability", "status": "confirmed",
        "title": "Synthetic scheduler fixture", "summary": "Synthetic.",
        "component": "vllm", "ecosystem": "PyPI",
        "published_at": "2099-01-01T00:00:00Z", "collected_at": storage.utcnow(),
        "withdrawn": False, "aliases": [], "affected": [], "conditions": [],
        "severity": None, "cvss": [], "cwes": [], "sources": [], "references": [],
        "poc": [], "relationships": [], "tags": [],
        "ai_relevance": {"included": True, "reason": "synthetic"},
        "content_hash": "synthetic-hash",
    }
    base.update(updates)
    return base


def test_planner_maps_gap_labels_to_tools():
    gaps, _ = intelligence.enrich_event(_event())["enrichment"]["gaps"] or [], None
    gaps = intelligence.enrich_event(_event())["enrichment"]["gaps"]
    assert gaps, "an empty event should report gaps"
    plan = agents.plan_gap_closure(_event(), gaps, set())
    assert plan, "the planner must find at least one tool for real gap labels"


def test_planner_matching_is_case_insensitive():
    plan = agents.plan_gap_closure(_event(), ["POC资料与验证状态"], set())
    assert "kev_status" in plan


def test_planner_does_not_repeat_tools_already_tried():
    gaps = intelligence.enrich_event(_event())["enrichment"]["gaps"]
    first = agents.plan_gap_closure(_event(), gaps, set())
    second = agents.plan_gap_closure(_event(), gaps, set(first))
    assert not set(first) & set(second)


def test_scheduler_stops_when_a_lookup_yields_nothing_new():
    """A miss must be recorded as a checked fact, not as evidence of safety."""
    def kev_miss(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=KEV_SYNTHETIC)

    collectors.set_transport(httpx.MockTransport(kev_miss))
    result = agents.close_evidence_gaps(_event())
    assert result["tool_calls"] >= 1
    assert "未取得新证据" in result["stop_reason"] or "没有可用工具" in result["stop_reason"]
    notes = " ".join(step["result"] for step in result["trace"])
    if "未收录" in notes:
        assert "不等于未被利用" in notes, "a KE V miss must never imply safety"


def test_scheduler_records_tool_failure_without_raising():
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "upstream down"})

    collectors.set_transport(httpx.MockTransport(broken))
    result = agents.close_evidence_gaps(_event())
    assert result["event"]["id"] == "CVE-2099-00001"
    assert any("失败" in step["result"] for step in result["trace"])


def test_scheduler_never_exceeds_its_budget():
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "down"})

    collectors.set_transport(httpx.MockTransport(broken))
    result = agents.close_evidence_gaps(_event(), max_rounds=5, budget=2)
    assert result["tool_calls"] <= 2


def test_pipeline_records_every_transition():
    processed = agents.process_event(_event(), close_gaps=False)
    pipeline = processed["pipeline"]
    states = [step["state"] for step in pipeline["history"]]
    assert "discovered" in states and "normalized" in states
    assert all(step.get("role") and step.get("note") for step in pipeline["history"])


def test_pipeline_does_not_claim_completeness_when_enrichment_was_skipped():
    """Skipping enrichment leaves gaps unknown -- not zero."""
    processed = agents.process_event(_event(), close_gaps=False)
    assert processed["pipeline"]["state"] == "pending_enrichment"
    notes = " ".join(step["note"] for step in processed["pipeline"]["history"])
    assert "尚未评估" in notes
    assert "证据齐备" not in notes


def test_withdrawn_events_are_invalidated():
    processed = agents.process_event(
        _event(withdrawn=True, status="withdrawn"), close_gaps=False)
    assert any(s["state"] == "invalidated" for s in processed["pipeline"]["history"])
    assert processed["pipeline"]["state"] == "invalidated"


def test_seeding_demo_assets_labels_them_synthetic_and_scopes_authorization():
    agents.seed_demo_assets()
    assets = storage.list_assets()
    assert assets and all(a["is_demo"] for a in assets)
    assert any(not a["authorized"] for a in assets)


def test_demo_asset_conditions_come_from_stored_events():
    agents.seed_research_cases()
    agents.seed_demo_assets()
    ollama = next(a for a in storage.list_assets() if a["component"] == "Ollama")
    assert ollama["conditions"], "conditions should be derived from the stored advisory"
    assert all(v is True for v in ollama["conditions"].values())


def test_research_seeding_is_idempotent():
    first = agents.seed_research_cases()
    second = agents.seed_research_cases()
    assert first["seeded"] == second["seeded"] == 3
    assert storage.count_events()["events"] == 3


def test_assessment_run_covers_all_four_states():
    agents.seed_research_cases()
    agents.seed_demo_assets()
    agents.run_assessment()
    statuses = {a["status"] for a in storage.list_assessments()}
    assert statuses == {"affected", "not_affected", "needs_confirmation", "not_applicable"}


def test_monitoring_summary_counts_only_sources_with_data():
    summary = agents.monitoring_summary()
    assert summary["coverage"]["endpoints_with_data"] == 0
    assert summary["coverage"]["endpoints_without_data"] == len(summary["items"])

    storage.update_source_state("nvd", events_count=5)
    assert agents.monitoring_summary()["coverage"]["endpoints_with_data"] == 1


def test_answer_records_a_run_and_never_leaks_the_key(monkeypatch):
    agents.seed_research_cases()
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-should-not-appear")
    # Force local mode so no request is attempted.
    monkeypatch.setattr(agents.config, "model_config", lambda: {})
    result = agents.answer("CVE-2026-7482 是否影响我的资产？")
    assert "sk-should-not-appear" not in str(result)
    run = storage.latest_run("chat")
    assert run and run["status"] == "completed"


def test_collection_does_not_run_the_gap_scheduler_by_default(monkeypatch):
    """Bulk collection stays cheap; enrichment is a separate pass."""
    called = {"n": 0}
    real = agents.close_evidence_gaps

    def spy(*args, **kwargs):
        called["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(agents, "close_evidence_gaps", spy)
    event = _event()
    agents.process_and_store(event, close_gaps=False)
    assert called["n"] == 0
    agents.process_and_store(_event("CVE-2099-00002"), close_gaps=True)
    assert called["n"] == 1


def test_research_case_evaluation_binds_each_case_version():
    agents.seed_research_cases()
    result = evaluation.run_evaluation()
    assert result["metrics"]["real_case_count"] > 0
    assert result["metrics"]["cases_failed"] == 0
