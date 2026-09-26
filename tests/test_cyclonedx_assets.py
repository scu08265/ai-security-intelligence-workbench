"""CycloneDX asset simulation import and assessment closure."""

from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from app import agents, storage
from app.api import app


def _bom() -> dict:
    return {
        "bomFormat": "CycloneDX", "specVersion": "1.6",
        "serialNumber": "urn:uuid:11111111-2222-3333-4444-555555555555", "version": 1,
        "metadata": {
            "timestamp": "2026-09-20T12:00:00Z",
            "tools": {"components": [
                {"type": "application", "vendor": "Anchore", "name": "syft", "version": "1.30.0"}
            ]},
            "component": {"type": "application", "bom-ref": "competition-app",
                          "name": "competition", "version": "1.0.0"},
        },
        "components": [
            {"type": "library", "bom-ref": "pkg:pypi/vllm@0.9.0", "name": "vllm",
             "version": "0.9.0", "purl": "pkg:pypi/vllm@0.9.0"},
            {"type": "library", "bom-ref": "pkg:pypi/vllm@0.9.0", "name": "vllm",
             "version": "0.9.0", "purl": "pkg:pypi/vllm@0.9.0"},
            {"type": "library", "bom-ref": "pkg:pypi/fastapi@0.1", "name": "fastapi",
             "version": "0.1", "purl": "pkg:pypi/fastapi@0.1"},
        ],
    }


def test_dry_run_validates_and_deduplicates_without_mutating():
    client = TestClient(app)
    body = client.post("/api/assets/cyclonedx/dry-run", json={"bom": _bom()}).json()
    assert body["dry_run"] is True and body["mutated"] is False
    assert body["input_component_count"] == 3
    assert body["deduplicated_asset_count"] == 2
    assert body["duplicate_component_count"] == 1
    assert body["assessment_relationship_count"] == 0
    assert storage.list_assets() == []
    vllm = next(item for item in body["assets"] if item["component"] == "vllm")
    assert vllm["sbom"]["bom_ref"] == "pkg:pypi/vllm@0.9.0"
    assert vllm["sbom"]["purl"] == "pkg:pypi/vllm@0.9.0"
    assert vllm["sbom"]["type"] == "library"
    assert vllm["sbom"]["inventory_timestamp"] == "2026-09-20T12:00:00Z"
    assert vllm["sbom"]["generation_tools"][0]["name"] == "syft"
    assert vllm["deployment_context"] == {
        "exposure": None, "business_criticality": None, "conditions": None,
        "status": "not_asserted_by_sbom",
    }


def test_import_is_idempotent_and_preserves_explicit_authorization_assertion():
    client = TestClient(app)
    first = client.post("/api/assets/cyclonedx/import",
                        json={"bom": _bom(), "authorized": True}).json()
    second = client.post("/api/assets/cyclonedx/import",
                         json={"bom": _bom(), "authorized": True}).json()
    assert first["created"] == 2 and first["updated"] == 0
    assert second["created"] == 0 and second["updated"] == 2
    assert second["idempotent"] is True
    assert len(storage.list_assets()) == 2
    assert {item["sbom"]["batch_id"] for item in storage.list_assets()} == {first["batch_id"]}
    assert all(item["authorization_assertion"]["source"] == "cyclonedx import request"
               for item in storage.list_assets())
    assert all("exposure" not in item and "business_criticality" not in item
               and "conditions" not in item for item in storage.list_assets())


def test_batch_assessment_returns_persisted_relations_and_decision_factors():
    agents.seed_research_cases()
    client = TestClient(app)
    imported = client.post("/api/assets/cyclonedx/import",
                           json={"bom": _bom(), "authorized": True}).json()
    body = client.post(f"/api/assets/cyclonedx/{imported['batch_id']}/assess").json()
    assert body["deduplicated_asset_count"] == 2
    assert body["assessment_relationship_count"] >= 1
    assert sum(body["status_counts"].values()) == body["assessment_relationship_count"]
    for relation in body["relationships"]:
        factors = relation["decision_factors"]
        assert factors["component_match"]["matched"] is True
        assert factors["inventory_identity"]["source"] == "CycloneDX SBOM"
        assert factors["deployment_context"]["status"] == "not_asserted_by_sbom"
        assert factors["authorization"]["source"] == "cyclonedx import request"
        assert factors["rule_result"]["status"] == relation["status"]
    stored = storage.list_assessments(limit=100)
    assert len(stored) == body["assessment_relationship_count"]
    assert all(item["sbom_batch_id"] == imported["batch_id"] for item in stored)
    assert all(item["decision_factors"] for item in stored)


def test_vllm_010_outside_affected_range_keeps_not_affected_and_skips_conditions():
    storage.upsert_event({
        "id": "CVE-2026-54235", "kind": "vulnerability", "status": "published",
        "title": "temperature validation", "component": "vllm", "sources": [{"id": "src-1"}],
        "affected": [{"package": "vllm", "range": "<=0.8.5",
                      "fixed_version": "0.24.0", "source_id": "src-1"}],
        "conditions": [{"name": "non_finite_temperature", "value": True,
                        "description": "request reaches sampling", "source_id": "src-1"}],
    })
    bom = _bom()
    bom["components"] = [{
        "type": "library", "bom-ref": "pkg:pypi/vllm@0.10.0", "name": "vllm",
        "version": "0.10.0", "purl": "pkg:pypi/vllm@0.10.0",
    }]
    client = TestClient(app)
    imported = client.post("/api/assets/cyclonedx/import",
                           json={"bom": bom, "authorized": True}).json()
    body = client.post(f"/api/assets/cyclonedx/{imported['batch_id']}/assess").json()
    assert body["assessment_relationship_count"] == 1
    relation = body["relationships"][0]
    assert relation["status"] == "not_affected"
    condition = relation["decision_factors"]["condition_evaluation"]
    assert condition["applicable"] is False
    assert condition["status"] == "not_applicable_version_outside_range"
    assert "版本明确不在" in condition["reason"]
    assert not any("关键配置" in reason
                   for reason in relation["decision_factors"]["rule_result"]["reasons"])


def test_unauthorized_import_is_declined_not_silently_assessed():
    agents.seed_research_cases()
    client = TestClient(app)
    imported = client.post("/api/assets/cyclonedx/import",
                           json={"bom": _bom(), "authorized": False}).json()
    body = client.post(f"/api/assets/cyclonedx/{imported['batch_id']}/assess").json()
    assert body["assessment_relationship_count"] >= 1
    assert body["status_counts"] == {"not_applicable": body["assessment_relationship_count"]}
    assert all("未标记为授权" in "".join(item["decision_factors"]["rule_result"]["reasons"])
               for item in body["relationships"])


def test_invalid_cyclonedx_and_conflicting_refs_are_rejected():
    client = TestClient(app)
    assert client.post("/api/assets/cyclonedx/dry-run", json={"bom": {}}).status_code == 400
    missing_ref = _bom()
    missing_ref["components"][0].pop("bom-ref")
    assert client.post("/api/assets/cyclonedx/dry-run", json={"bom": missing_ref}).status_code == 400
    conflict = _bom()
    conflict["components"][1]["version"] = "9.9.9"
    response = client.post("/api/assets/cyclonedx/dry-run", json={"bom": conflict})
    assert response.status_code == 400
    assert "身份冲突" in response.json()["detail"]


def test_batch_identity_changes_with_inventory_and_missing_batch_is_404():
    client = TestClient(app)
    first = client.post("/api/assets/cyclonedx/dry-run", json={"bom": _bom()}).json()
    changed = deepcopy(_bom())
    changed["metadata"]["timestamp"] = "2026-09-21T12:00:00Z"
    second = client.post("/api/assets/cyclonedx/dry-run", json={"bom": changed}).json()
    assert first["batch_id"] != second["batch_id"]
    assert client.post("/api/assets/cyclonedx/cdx-missing/assess").status_code == 404


def test_cyclonedx_endpoints_do_not_leak_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-cdx-canary")
    client = TestClient(app)
    for path, payload in (
        ("/api/assets/cyclonedx/dry-run", {"bom": _bom()}),
        ("/api/assets/cyclonedx/import", {"bom": _bom(), "authorized": True}),
    ):
        response = client.post(path, json=payload)
        assert response.status_code == 200
        assert "sk-cdx-canary" not in response.text
