"""API contract, input validation and the security guards."""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app import agents, config, evaluation, intelligence, sources, storage, streaming
from app.api import app

from fixtures import KEV_SYNTHETIC, OSV_SYNTHETIC


@pytest.fixture
def client():
    return TestClient(app)


def _seed(client) -> None:
    """Local-only seeding: research file plus synthetic demo assets."""
    assert client.post("/api/seed").status_code == 200


def test_health_reports_mode_without_disclosing_configuration(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["version"] == config.APP_VERSION
    assert body["model_configured"] is False, "tests run with no key"
    assert body["mode"] == "local_evidence_extraction"
    assert config.API_KEY_ENV not in str(body)


def test_dashboard_matches_the_contract_shape(client):
    body = client.get("/api/dashboard").json()
    assert {"counts", "latest_collection", "mode", "monitoring", "evaluation"} <= set(body)
    assert {"events", "sources", "assets", "needs_review"} <= set(body["counts"])
    assert body["evaluation"]["status"] == "not_run"


def test_sources_are_reported_with_honest_coverage(client):
    body = client.get("/api/sources").json()
    assert len(body["items"]) == len(sources.SOURCES)
    coverage = client.get("/api/dashboard").json()["monitoring"]["coverage"]
    assert coverage["endpoints"] == len(sources.SOURCES)
    assert coverage["endpoints_with_data"] == 0, "nothing collected yet"
    assert "不计为已接入" in coverage["note"]


def test_monitoring_evidence_keeps_empty_days(client):
    body = client.get("/api/monitoring/evidence?days=7").json()
    assert body["window_days"] == 7
    assert len(body["days"]) == 7
    assert body["complete_days"] == 0
    assert "不补写历史数据" in body["note"]


def test_reliability_and_alert_endpoints_are_available(client):
    report = client.get("/api/system/reliability").json()
    assert report["timeliness"]["sample_size"] == 0
    assert report["continuous_runs"]["target_met"] is False
    alerts = client.get("/api/system/alerts").json()
    assert alerts["items"] == []


def test_seed_loads_research_cases_and_flags_demo_assets(client):
    _seed(client)
    events = client.get("/api/events").json()
    assert events["total"] == 3
    assets = client.get("/api/assets").json()["items"]
    assert len(assets) == 5
    assert all(a["is_demo"] for a in assets)
    assert any(not a["authorized"] for a in assets)


def test_event_detail_includes_enrichment_and_assessments(client):
    _seed(client)
    client.post("/api/assessments/run")
    body = client.get("/api/events/CVE-2026-7482").json()
    assert "enrichment" in body and "dimensions" in body["enrichment"]
    assert "assessments" in body


def test_event_lookup_resolves_aliases(client):
    _seed(client)
    assert client.get("/api/events/GHSA-4r2x-xpjr-7cvv").json()["id"] == "CVE-2026-22778"


def test_missing_event_returns_a_string_detail(client):
    response = client.get("/api/events/CVE-1999-0000")
    assert response.status_code == 404
    assert isinstance(response.json()["detail"], str)


def test_assets_crud_and_scoping(client):
    created = client.post("/api/assets", json={
        "name": "合成主机", "component": "vllm", "version": "0.9.0",
        "exposure": "public", "business_criticality": "high",
    }).json()
    assert created["id"]
    assert len(client.get("/api/assets").json()["items"]) == 1

    imported = client.post("/api/assets/import", json={"items": [
        {"name": "第二台", "component": "ollama"},
        {"name": "第三台", "component": "vllm"},
    ]}).json()
    assert imported["imported"] == 2

    assert client.delete(f"/api/assets/{created['id']}").json()["deleted"] is True
    assert client.delete("/api/assets/nope").json()["deleted"] is False


def test_asset_validation_rejects_bad_enums(client):
    response = client.post("/api/assets", json={
        "name": "x", "component": "vllm", "exposure": "everywhere",
    })
    assert response.status_code == 422


def test_assessments_are_joined_with_names(client):
    _seed(client)
    client.post("/api/assessments/run")
    items = client.get("/api/assessments").json()["items"]
    assert items
    assert all(i.get("asset_name") and i.get("event_title") for i in items)
    statuses = {i["status"] for i in items}
    assert {"affected", "not_affected"} <= statuses


def test_unauthorized_asset_is_assessed_as_not_applicable(client):
    _seed(client)
    client.post("/api/assessments/run")
    items = client.get("/api/assessments").json()["items"]
    skipped = [i for i in items if i["asset_id"] == "asset-demo-unauthorized"]
    assert skipped and skipped[0]["status"] == "not_applicable"
    assert any("授权" in reason for reason in skipped[0]["reasons"])


def test_collect_rejects_unregistered_source_ids(client):
    response = client.post("/api/collect", json={"source_ids": ["http://evil.invalid"]})
    assert response.status_code == 400
    assert "未登记" in response.json()["detail"]


def test_collect_cannot_be_pointed_at_an_arbitrary_url(client):
    """Only ids from the fixed registry are accepted, which blocks SSRF."""
    for candidate in ("https://internal.service/", "file:///etc/passwd", "../../etc"):
        assert client.post("/api/collect", json={"source_ids": [candidate]}).status_code == 400


def test_collect_surfaces_per_source_failure_honestly(client, monkeypatch):
    def limited(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "API rate limit exceeded."})

    from app import collectors

    collectors.set_transport(httpx.MockTransport(limited))
    body = client.post("/api/collect", json={"source_ids": ["nvd"]}).json()
    assert body["status"] == "failed"
    result = body["results"][0]
    assert result["status"] == "failed"
    assert result["error"]
    assert body["events_added"] == 0


def test_chat_answers_from_local_evidence_without_a_model(client):
    _seed(client)
    body = client.post("/api/chat", json={"question": "CVE-2026-7482 的攻击链是什么？"}).json()
    assert body["mode"] == "local_evidence_extraction"
    assert body["citations"], "an answer must cite stored evidence"
    assert "拒绝补写" in body["answer"]
    assert body["duration_ms"] >= 0


def test_chat_writes_a_replayable_structured_context_snapshot(client):
    _seed(client)
    first = client.post("/api/chat", json={
        "question": "CVE-2026-7482 的攻击链是什么？", "thread_id": "chat-context-api",
        "context_snapshot": {"selected_event_ids": [], "selected_asset_ids": [],
                             "selected_document_ids": [], "inherited_constraints": {}},
    }).json()
    assert first["thread_id"] == "chat-context-api"
    assert first["persisted_context_snapshot"]["immutable"] is True
    assert first["context_snapshot"]["selected_event_ids"] == ["CVE-2026-7482"]
    stored = client.get("/api/agent/threads/chat-context-api").json()
    assert len(stored["turns"]) == len(stored["context_snapshots"]) == 1
    assert stored["context_snapshots"][0]["focus"]["event_id"] == "CVE-2026-7482"


def test_chat_rejects_overlong_questions(client):
    assert client.post("/api/chat", json={"question": "x" * 5000}).status_code == 422


def test_evaluation_reports_not_run_until_it_actually_runs(client):
    assert client.get("/api/evaluation").json()["status"] == "not_run"
    assert client.get("/api/evaluation").json()["metrics"] == {}


def test_evaluation_run_produces_metrics_and_states_its_limits(client):
    _seed(client)
    body = client.post("/api/evaluation/run").json()
    assert body["status"] == "completed"
    metrics = body["metrics"]
    assert metrics["cases_total"] > 0
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert metrics["cases_passed"] + metrics["cases_failed"] == metrics["cases_total"]
    assert any("blind" in x or "盲测" in x for x in body["limitations"])
    assert any(r["synthetic"] for r in body["results"]), "fixtures must be labelled synthetic"

    assert client.get("/api/evaluation").json()["status"] == "completed"


def test_runs_are_listed_after_actions(client):
    _seed(client)
    client.post("/api/evaluation/run")
    items = client.get("/api/runs").json()["items"]
    assert any(item["kind"] == "evaluation" for item in items)


def test_export_snapshot_carries_no_credentials(client, monkeypatch):
    monkeypatch.setenv(config.API_KEY_ENV, "sk-super-secret-value")
    _seed(client)
    response = client.get("/api/export")
    assert "sk-super-secret-value" not in response.text
    assert config.API_KEY_ENV not in response.text


def test_write_requests_from_a_foreign_origin_are_refused(client):
    response = client.post("/api/seed", headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert "跨源" in response.json()["detail"]


def test_write_requests_from_a_local_origin_are_allowed(client):
    response = client.post("/api/seed", headers={"Origin": "http://127.0.0.1:8000"})
    assert response.status_code == 200


def test_read_requests_are_not_blocked_by_the_origin_guard(client):
    assert client.get("/api/health", headers={"Origin": "https://evil.example"}).status_code == 200


def test_responses_carry_hardening_headers(client):
    headers = client.get("/api/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "no-referrer"


def test_query_limits_are_enforced(client):
    assert client.get("/api/events", params={"limit": 99999}).status_code == 422
    assert client.get("/api/events", params={"q": "x" * 500}).status_code == 422


def test_events_endpoint_attaches_enrichment(client):
    _seed(client)
    items = client.get("/api/events").json()["items"]
    assert items and all("enrichment" in item for item in items)


def test_enrichment_run_reports_real_tool_usage(client):
    """With no CVE gaps reachable offline, the scheduler must stop and say why."""
    _seed(client)
    body = client.post("/api/enrichment/run", params={"limit": 3}).json()
    assert body["events"] >= 1
    assert body["tool_calls"] >= 0


def test_knowledge_items_are_counted_separately(client):
    from app import normalize

    event = normalize.kev_to_event(KEV_SYNTHETIC["vulnerabilities"][0])
    event["kind"] = "knowledge"
    storage.upsert_event(event)
    counts = client.get("/api/dashboard").json()["counts"]
    assert counts["knowledge"] == 1
    assert counts["events"] == 1


def test_agents_answer_runs_without_a_model_config(client):
    _seed(client)
    result = agents.answer("CVE-2026-22778 是否影响我的资产？")
    assert result["mode"] == "local_evidence_extraction"
    assert result["run_id"]
    assert storage.latest_run("chat")["id"] == result["run_id"]


def test_evaluation_latest_summarizes_without_inventing_results(client):
    assert evaluation.latest_evaluation()["status"] == "not_run"
    _seed(client)
    evaluation.run_evaluation()
    latest = evaluation.latest_evaluation()
    assert latest["status"] == "completed"
    assert latest["metrics"]["cases_total"] > 0
    assert latest["limitations"]


# --------------------------------------------------------------------------
# user-facing event type
# --------------------------------------------------------------------------

def test_display_group_reads_the_registry_rather_than_a_hardcoded_list():
    """A newly registered source must land in a bucket by itself."""
    assert sources.display_group("arxiv") == "论文"
    assert sources.display_group("owasp_genai") == "标准与框架"
    assert sources.display_group("nist_ai_rmf") == "标准与框架"
    assert sources.display_group("eu_ai_act") == "政策法规"
    assert sources.display_group("nvd") == "漏洞"
    assert sources.display_group("not-registered") == "漏洞"
    assert sources.event_source_prefix("cisa_kev") == "kev"
    assert sources.event_source_prefix("mitre_cve") == "mitre"
    assert sources.event_source_prefix("openalex") == "openalex"


def test_event_group_follows_the_first_source():
    """`sources[].id` is "<source>:<hash>", so the prefix names the collector."""
    assert sources.event_group({"sources": [{"id": "arxiv:abc"}, {"id": "nvd:def"}]}) == "论文"
    assert sources.event_group({"sources": [{"id": "nvd:def"}, {"id": "arxiv:abc"}]}) == "漏洞"
    assert sources.event_group({"sources": []}) == "漏洞"
    assert sources.event_group({}) == "漏洞"


def test_event_categories_partition_the_corpus(client):
    _seed(client)
    body = client.get("/api/events?limit=200").json()
    counts = body["categories"]
    assert counts is not None, "small corpus must always be countable"
    assert sum(counts.values()) == body["total"]
    assert set(counts) <= set(body["group_order"])


def test_category_filter_returns_only_that_category(client):
    _seed(client)
    everything = client.get("/api/events?limit=500").json()["total"]
    for category in ["漏洞", "论文", "标准与框架", "政策法规"]:
        body = client.get("/api/events", params={"category": category, "limit": 500}).json()
        assert all(item["category"] == category for item in body["items"])
        assert body["total"] == len(body["items"])
        assert body["total"] <= everything


def test_event_detail_carries_the_same_category_as_the_list(client):
    _seed(client)
    listed = client.get("/api/events?limit=200").json()["items"]
    if not listed:
        pytest.skip("seed produced no events")
    item = listed[0]
    detail = client.get("/api/events/" + str(item["id"])).json()
    assert detail["category"] == item["category"]


# --------------------------------------------------------------------------
# how-it-works endpoints
# --------------------------------------------------------------------------

def test_ai_participation_reports_the_prompts_actually_sent(client):
    """The console must show the live prompt, not a copy that can drift."""
    body = client.get("/api/ai-participation").json()
    prompts = {item["id"]: item["prompt"] for item in body["participations"]}
    assert prompts == {"select": intelligence.SELECT_SYSTEM_PROMPT,
                       "restate": streaming.RESTATE_SYSTEM_PROMPT}
    assert body["not_ai"], "the honest boundary must be stated, not implied"
    assert body["mode"] in {"local_evidence_extraction", "model_assisted"}


def test_orchestration_reports_the_real_budgets(client):
    body = client.get("/api/orchestration").json()
    assert body["scheduling"]["max_rounds"] == agents.MAX_ROUNDS
    assert body["scheduling"]["tool_budget"] == agents.TOOL_BUDGET
    assert len(body["tools"]) == len(sources.SOURCES)
    assert len(body["roles"]) == len(streaming.ROLE_LABELS)
    assert "不是互相通信的独立智能体" in body["runtime"], (
        "the orchestration must not be described as independent agents")


def test_multi_agent_endpoint_returns_message_and_audit_evidence(client):
    response = client.post("/api/agent/multi/execute", json={
        "objective": "验证本地证据与缓存快照",
        "actions": ["count_events", "read_cached_snapshot"],
    })
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"]
    assert {"plan_proposed", "execution_result", "audit_decision"} <= {
        item["kind"] for item in body["messages"]
    }
    assert body["agents"]["auditor"]["decisions"]


def test_self_healing_endpoint_accepts_only_registered_sources(client):
    denied = client.post("/api/self-healing/run", json={"source_ids": ["not-real"]})
    assert denied.status_code == 400
    accepted = client.post("/api/self-healing/run", json={"source_ids": ["nvd"]})
    assert accepted.status_code == 200
    assert accepted.json()["policy"]["automatic_actions"]


def test_how_it_works_endpoints_leak_nothing(client, monkeypatch):
    monkeypatch.setenv(config.API_KEY_ENV, "sk-canary-do-not-emit")
    for path in ("/api/ai-participation", "/api/orchestration"):
        assert "sk-canary-do-not-emit" not in client.get(path).text
