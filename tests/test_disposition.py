"""Disposition closure loop: state machine, re-verification and metrics."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import disposition, storage
from app.api import app


def _seed_case(version: str = "1.0.0", component: str = "demo-lib") -> tuple[str, str]:
    storage.upsert_event({
        "id": "CVE-2099-DISP", "kind": "vulnerability", "status": "published",
        "title": "disposition fixture", "component": component,
        "severity": "high",
        "affected": [{"source_id": "nvd:CVE-2099-DISP", "package": component,
                      "range": "<2.0.0", "fixed_version": "2.0.0"}],
        "sources": [{"id": "nvd:CVE-2099-DISP"}],
    })
    storage.upsert_asset({
        "id": "asset-disp", "name": "disposition asset", "component": component,
        "version": version, "authorized": True,
    })
    storage.save_assessment({
        "event_id": "CVE-2099-DISP", "asset_id": "asset-disp",
        "status": "affected", "priority": "high",
        "reasons": ["version matches affected range"],
        "evidence_ids": ["nvd:CVE-2099-DISP"],
    })
    return "CVE-2099-DISP", "asset-disp"


def test_update_requires_assignee_for_flow_states():
    event_id, asset_id = _seed_case()
    try:
        disposition.update_disposition(event_id, asset_id, status="in_progress")
    except disposition.DispositionError as exc:
        assert "处置人" in str(exc)
    else:
        raise AssertionError("expected DispositionError")
    assert disposition.get_disposition(event_id, asset_id)["status"] == "open"


def test_verified_requires_system_recheck_and_closes_when_version_is_safe():
    event_id, asset_id = _seed_case(version="2.5.0")
    result = disposition.update_disposition(
        event_id, asset_id, status="verified", assignee="alice", version_after="2.5.0",
    )
    assert result["applied_status"] == "verified"
    assert result["verification"]["passed"] is True
    record = storage.get_assessment_disposition(event_id, asset_id)
    assert record["status"] == "verified"
    assert record["closed_at"]


def test_failed_recheck_keeps_finding_open_with_audit_trail():
    event_id, asset_id = _seed_case(version="1.0.0")
    result = disposition.update_disposition(
        event_id, asset_id, status="verified", assignee="alice",
    )
    assert result["applied_status"] == "fixed"
    assert result["verification"]["passed"] is False
    record = storage.get_assessment_disposition(event_id, asset_id)
    assert record["status"] == "fixed"
    assert record["closed_at"] is None


def test_assessment_original_status_survives_disposition():
    event_id, asset_id = _seed_case(version="2.5.0")
    disposition.update_disposition(event_id, asset_id, status="verified", assignee="alice")
    assessment = next(item for item in storage.list_assessments() if item["event_id"] == event_id)
    assert assessment["status"] == "affected"
    assert assessment["disposition_status"] == "verified"


def test_api_put_and_metrics_reflect_closure():
    event_id, asset_id = _seed_case(version="2.5.0")
    client = TestClient(app)
    response = client.put(
        f"/api/dispositions/{event_id}/{asset_id}",
        json={"event_id": event_id, "asset_id": asset_id, "status": "verified",
              "assignee": "alice", "version_after": "2.5.0"},
    )
    assert response.status_code == 200
    assert response.json()["applied_status"] == "verified"
    metrics = client.get("/api/dispositions/metrics").json()
    assert metrics["high_priority_total"] == 1
    assert metrics["high_priority_closed"] == 1
    assert metrics["closure_rate"] == 1.0
    scorecard = client.get("/api/competition/scorecard").json()
    assert scorecard["disposition"]["high_priority_closed"] == 1


def test_advice_bridge_returns_recommendation_for_a_real_finding():
    event_id, asset_id = _seed_case(version="1.0.0")
    advice = disposition.advice(event_id, asset_id)
    assert advice["available"] is True
    assert advice["link_status"] == "affected"
    assert any(a.get("action") for a in advice["recommended_actions"])
    # 未配置策略时，破坏性动作必须进入 blocked_actions，不能默认推荐执行
    assert any(a.get("action") == "apply_patch" for a in advice["blocked_actions"])


def test_advice_endpoint_exposes_bridge_output():
    event_id, asset_id = _seed_case(version="1.0.0")
    client = TestClient(app)
    response = client.get(f"/api/dispositions/{event_id}/{asset_id}/advice")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["disclaimer"]


def test_unknown_status_is_rejected():
    event_id, asset_id = _seed_case()
    client = TestClient(app)
    response = client.put(
        f"/api/dispositions/{event_id}/{asset_id}",
        json={"event_id": event_id, "asset_id": asset_id, "status": "bogus"},
    )
    assert response.status_code == 422
