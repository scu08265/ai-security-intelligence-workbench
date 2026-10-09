"""Competition scorecard must report measured evidence and preserve unknowns."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import agents, evaluation, storage
from app.api import app


def _seed() -> None:
    agents.seed_research_cases()
    agents.seed_demo_assets()


def test_empty_scorecard_uses_null_for_unmeasured_metrics():
    body = TestClient(app).get("/api/competition/scorecard").json()
    assert body["sources"]["actual_producing_sources"]["value"] == 0
    assert body["monitoring_7d"]["actual_run_days"]["value"] == 0
    assert body["monitoring_7d"]["scheduled_run_days"]["value"] == 0
    assert body["monitoring_7d"]["within_24h_rate"]["value"] is None
    qa = body["question_answer_evaluation"]
    assert qa["status"] == "not_run"
    assert all(qa[key] is None for key in (
        "retrieval_precision", "retrieval_recall", "answer_accuracy",
        "citation_accuracy", "refusal_accuracy", "response_duration_ms"))
    assert body["agent_execution"]["external_automation_verified"]["value"] is None
    assert "无证据" in body["evidence_policy"]


def test_source_scores_count_only_sources_that_produced_data():
    storage.update_source_state("nvd", status="ok", events_count=3,
                                last_success=storage.utcnow())
    storage.update_source_state("arxiv", status="ok", events_count=2,
                                last_success=storage.utcnow())
    body = TestClient(app).get("/api/competition/scorecard").json()["sources"]
    assert body["actual_producing_sources"]["value"] == 2
    assert {item["id"] for item in body["items"]} == {"nvd", "arxiv"}
    assert body["actual_categories"]["value"] == 2
    assert body["registered_sources"]["value"] > 2


def test_seven_day_monitoring_uses_persisted_observations_and_runs():
    now = storage.utcnow()
    storage.save_run({
        "id": "run-scorecard-collect", "kind": "collect", "status": "completed",
        "started_at": now, "finished_at": now, "summary": "measured",
        "detail": {"results": [{"source_id": "nvd", "status": "ok"}]},
    })
    storage.upsert_event({
        "id": "CVE-2099-SCORE", "kind": "vulnerability", "status": "published",
        "title": "latency sample", "sources": [],
        "monitoring_observations": [
            {"discovered_at": now, "publication_to_discovery_seconds": 3600},
            {"discovered_at": now, "publication_to_discovery_seconds": 90000},
            {"discovered_at": now, "publication_to_discovery_seconds": None},
        ],
    })
    result = TestClient(app).get("/api/competition/scorecard").json()["monitoring_7d"]
    assert result["actual_run_days"]["value"] == 1
    assert result["scheduled_run_days"]["value"] == 0
    assert result["monitoring_started_at"]["value"] == now
    # Latency counts the first discovery per event, not every later update.
    assert result["observed_events"]["value"] == 1
    assert result["publication_latency_samples"]["value"] == 1
    assert result["within_24h_samples"]["value"] == 1
    assert result["within_24h_rate"]["value"] == 1.0
    assert result["within_24h_rate"]["sample_size"] == 1



def test_cumulative_collection_days_survive_rolling_window_expiry():
    today = datetime.now(timezone.utc)
    for offset in (0, 1, 2, 8, 9, 10, 11, 12):
        stamp = (today - timedelta(days=offset)).isoformat()
        storage.save_run({
            "id": f"run-cumulative-{offset}", "kind": "collect", "status": "completed",
            "started_at": stamp, "finished_at": stamp, "summary": "cumulative",
            "detail": {"trigger": "scheduled" if offset < 3 else "manual", "results": []},
        })
    result = TestClient(app).get("/api/competition/scorecard").json()["monitoring_7d"]
    assert result["cumulative_actual_run_days"]["value"] == 8
    assert result["cumulative_scheduled_run_days"]["value"] == 3
    assert result["cumulative_first_collection_date"]["value"] == (today - timedelta(days=12)).isoformat()[:10]
    assert result["cumulative_last_collection_date"]["value"] == today.isoformat()[:10]
    # The rolling seven-day window sees three days; the cumulative count keeps all eight.
    assert sum(1 for day in result["days"] if day["collection_runs"] > 0) == 3

def test_enrichment_coverage_uses_exact_stored_fields():
    storage.upsert_event({
        "id": "CVE-2099-DIMS", "kind": "vulnerability", "status": "published",
        "title": "dimension sample", "sources": [{"id": "arxiv:paper", "title": "paper"}],
        "poc": [{"source_id": "arxiv:paper", "status": "reported"}],
        "cvss": [{"source_id": "arxiv:paper", "score": 8.0}],
        "affected": [{"source_id": "arxiv:paper", "fixed_version": "2.0.0"}],
        "relationships": [{"subject": "x", "predicate": "causes", "object": "y",
                           "evidence_ids": ["arxiv:paper"]}],
    })
    storage.upsert_asset({"id": "asset-score", "name": "asset", "component": "x",
                          "authorized": True})
    storage.save_assessment({"event_id": "CVE-2099-DIMS", "asset_id": "asset-score",
                             "status": "affected", "priority": "high",
                             "evidence_ids": ["arxiv:paper"]})
    dimensions = TestClient(app).get("/api/competition/scorecard").json()["enrichment"]["dimensions"]
    for name in ("paper_link", "asset_assessment", "poc", "cvss", "fixed_version",
                 "evidence_relationship"):
        assert dimensions[name]["present_events"] == 1
        assert dimensions[name]["coverage"] == 1.0


def test_completed_evaluation_metrics_and_duration_are_reported():
    _seed()
    executed = evaluation.run_evaluation()
    qa = TestClient(app).get("/api/competition/scorecard").json()["question_answer_evaluation"]
    assert qa["status"] == "completed"
    assert qa["retrieval_precision"] == executed["metrics"]["retrieval_precision"]
    assert qa["retrieval_recall"] == executed["metrics"]["retrieval_recall"]
    assert qa["answer_accuracy"] == executed["metrics"]["answer_accuracy"]
    assert qa["citation_accuracy"] == executed["metrics"]["citation_accuracy"]
    assert qa["refusal_accuracy"] == executed["metrics"]["refusal_accuracy"]
    assert qa["response_duration_ms"] == executed["metrics"]["qa_response_duration_ms"]
    assert qa["response_duration_ms"]["samples"] > 0
    assert qa["sample_counts"]


def test_agent_evidence_counts_only_persisted_roles_and_tool_calls():
    storage.upsert_event({
        "id": "CVE-2099-AGENT", "kind": "vulnerability", "status": "published",
        "title": "agent trace", "sources": [], "pipeline": {
            "history": [{"role": "collector"}, {"role": "normalizer"}],
            "scheduler_trace": [{"role": "retriever", "tool": "nvd"}],
        },
    })
    now = storage.utcnow()
    storage.save_run({
        "id": "run-scorecard-enrich", "kind": "enrich", "status": "completed",
        "started_at": now, "finished_at": now, "summary": "called tools",
        "detail": {"tool_calls": 4},
    })
    result = TestClient(app).get("/api/competition/scorecard").json()["agent_execution"]
    assert {item["role"] for item in result["observed_roles"]} == {
        "collector", "normalizer", "retriever"}
    assert result["tool_calls"]["value"] == 4
    assert result["tool_calls"]["sample_size"] == 1
    assert result["runs_by_kind"] == {"enrich": 1}


def test_scorecard_does_not_leak_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-scorecard-canary")
    response = TestClient(app).get("/api/competition/scorecard")
    assert response.status_code == 200
    assert "sk-scorecard-canary" not in response.text


def test_active_multihop_uses_v2_batch_and_exposes_missing_edges():
    body = TestClient(app).get("/api/competition/scorecard").json()["b_evaluation"]
    active = body["active_multihop"]
    assert active["available"] is True
    assert active["cross_document_found"] == 10
    assert active["cross_document_total"] == 21
    assert active["two_hop_found"] == 10
    assert active["term_reachable"] == 29
    assert active["missing_edge_kinds"]["document_to_document"] == 52
    # 旧冻结基线保留，不覆盖
    assert body["multihop"]["cross_document_found"] == 0


def test_active_relation_uses_gold_score_and_exposes_recall():
    body = TestClient(app).get("/api/competition/scorecard").json()["b_evaluation"]
    active = body["active_relation"]
    # 页面自动选用最新的 relation_score_gold_<日期>.json：
    # 2026-10-06 批次补齐了 5 条 cvss 漏检的可抽取内容并完成人工核验，
    # 10-04 的冻结基线仍原样保留（见 tests/test_b_relation_cvss_recheck.py）。
    assert active["source"].endswith("relation_score_gold_20261006.json")
    assert active["precision"] == 1.0
    assert active["recall"] == 0.9123
    assert active["f1"] == 0.9541
    assert (active["tp"], active["fp"], active["fn"]) == (52, 0, 5)
    assert active["missing_relation_ids"] == 5
    # 旧冻结基线保留：没有金标准时 Recall 仍不可计算
    assert body["relation"]["recall"] is None

def test_b_evaluation_artifacts_are_exposed_without_rounding_unknowns():
    body = TestClient(app).get("/api/competition/scorecard").json()["b_evaluation"]
    assert body["available"] is True
    assert body["active_batch"]["batch_id"] == "20261002"
    assert body["active_qa_quality"]["human_judged_cases"] == 50
    assert body["active_qa_quality"]["answer_accuracy"] == 0.1316
    assert body["active_qa_quality"]["citation_support"] == 0.0833
    assert body["active_qa_quality"]["refusal_recall"] == 0.3333
    # Legacy fields stay on the old 2026-09-30 baseline for backward compatibility.
    assert body["qa_quality"]["human_judged_cases"] == 50
    assert body["qa_quality"]["answer_accuracy"] == 0.2121
    assert body["qa_quality"]["citation_support"] == 0.0323
    assert body["qa_quality"]["refusal_recall"] == 0.5
    assert body["relation"]["precision"] == 1.0
    assert body["relation"]["recall"] is None
    assert body["multihop"]["cross_document_found"] == 0
    assert body["multihop"]["cross_document_total"] == 21
    assert body["qa_performance"]["timeouts"] == 0
    assert body["qa_performance"]["errors"] == 0
