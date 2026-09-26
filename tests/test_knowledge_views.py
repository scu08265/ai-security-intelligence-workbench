"""Read-only knowledge graph and agent-workbench API projections."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import agents, sources, storage
from app.api import app


def _seed() -> None:
    agents.seed_research_cases()
    agents.seed_demo_assets()


def test_knowledge_overview_and_documents_are_grounded():
    _seed()
    client = TestClient(app)
    overview = client.get("/api/knowledge/overview").json()
    documents = client.get("/api/knowledge/documents").json()

    events, total = storage.list_events(limit=500)
    expected_documents = sum(len(event.get("sources") or []) for event in events)
    assert overview["counts"]["events"] == total
    assert overview["counts"]["documents"] == expected_documents
    assert documents["total"] == expected_documents
    assert all(item["provenance"] == "stored_event_source" for item in documents["items"])
    assert all(item["event_id"] for item in documents["items"])
    assert "不会补写" in documents["note"]


def test_document_source_filter_only_accepts_registered_ids():
    _seed()
    client = TestClient(app)
    assert client.get("/api/knowledge/documents", params={"source_id": "https://evil.test"}).status_code == 400
    response = client.get("/api/knowledge/documents", params={"source_id": "nvd"})
    assert response.status_code == 200
    assert all(item["registered_source_id"] == "nvd" for item in response.json()["items"])


def test_knowledge_view_data_dependencies_are_available_together():
    """The knowledge screen loads these three read endpoints as one view."""
    client = TestClient(app)
    responses = [
        client.get("/api/knowledge/documents", params={"limit": 200}),
        client.get("/api/rag/documents", params={"limit": 200}),
        client.get("/api/sources"),
    ]

    assert [response.status_code for response in responses] == [200, 200, 200]
    assert all(isinstance(response.json().get("items"), list) for response in responses)


def test_graph_contains_only_stored_sources_and_evidence_bound_claims():
    event = {
        "id": "CVE-2099-0001", "kind": "vulnerability", "status": "published",
        "title": "grounded graph case", "component": "demo", "sources": [{
            "id": "nvd:proof-1", "title": "NVD proof", "url": "https://nvd.nist.gov/example",
        }],
        "relationships": [
            {"subject": "a", "predicate": "causes", "object": "b",
             "evidence_ids": ["nvd:proof-1"]},
            {"subject": "invented", "predicate": "causes", "object": "edge",
             "evidence_ids": []},
            {"subject": "missing", "predicate": "cites", "object": "unknown",
             "evidence_ids": ["nvd:not-stored"]},
        ],
    }
    storage.upsert_event(event)
    body = TestClient(app).get("/api/knowledge/graph").json()
    event_edges = [edge for edge in body["edges"] if "CVE-2099-0001" in edge["id"]]
    assert {edge["basis"] for edge in event_edges} == {"event.sources", "event.relationships"}
    assert len([edge for edge in event_edges if edge["type"] == "has_claim"]) == 1
    assert all(edge["evidence_ids"] for edge in event_edges)
    assert "不推断边" in body["policy"]


def test_graph_adds_asset_edge_only_after_persisted_assessment():
    _seed()
    client = TestClient(app)
    before = client.get("/api/knowledge/graph").json()
    assert not any(edge["type"] == "assessed_against" for edge in before["edges"])

    agents.run_assessment()
    after = client.get("/api/knowledge/graph").json()
    assessment_edges = [edge for edge in after["edges"] if edge["type"] == "assessed_against"]
    assert assessment_edges
    assert all(edge["basis"] == "persisted_assessment" for edge in assessment_edges)


def test_agent_workbench_separates_layers_and_reports_real_tool_state():
    body = TestClient(app).get("/api/agent/workbench").json()
    assert [layer["id"] for layer in body["layers"]] == ["input", "orchestration", "tool"]
    tools = body["layers"][2]["items"]
    assert len(tools) == len(sources.SOURCES)
    assert all({"status", "last_run", "last_success", "last_error", "events_count"} <= set(tool)
               for tool in tools)
    assert body["scheduling"]["max_rounds"] == agents.MAX_ROUNDS
    assert body["scheduling"]["tool_budget"] == agents.TOOL_BUDGET
    assert "单进程" in body["runtime_note"]


def test_new_read_views_do_not_leak_environment_secrets(monkeypatch):
    _seed()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-knowledge-view-canary")
    client = TestClient(app)
    for path in ("/api/knowledge/overview", "/api/knowledge/documents",
                 "/api/knowledge/graph", "/api/agent/workbench"):
        response = client.get(path)
        assert response.status_code == 200
        assert "sk-knowledge-view-canary" not in response.text
