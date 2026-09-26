"""Multi-turn context tests using public-source shaped vulnerability records."""

from app.intelligence import answer_question


def _event(event_id: str, component: str, affected_range: str, fixed: str) -> dict:
    excerpt = f"{event_id} affects {component} {affected_range}; fixed in {fixed}."
    return {
        "id": event_id, "aliases": [], "kind": "vulnerability", "status": "confirmed",
        "title": f"NVD record for {event_id}", "summary": excerpt, "component": component,
        "withdrawn": False, "severity": "high", "cvss": [], "relationships": [],
        "affected": [{
            "package": component, "range": affected_range, "fixed_version": fixed,
            "source_id": f"nvd:{event_id}",
        }],
        "conditions": [{"name": "remote_api", "value": True, "source_id": f"nvd:{event_id}"}],
        "sources": [{
            "id": f"nvd:{event_id}", "url": f"https://nvd.nist.gov/vuln/detail/{event_id}",
            "title": f"NVD {event_id}", "publisher": "NVD", "trust": "government",
            "excerpt": excerpt,
        }],
    }


def _asset() -> dict:
    return {
        "id": "asset-prod-gateway-a", "name": "生产网关A", "component": "ExampleGateway",
        "version": "1.3.0", "conditions": {}, "exposure": "internal",
        "business_criticality": "high", "authorized": True, "is_demo": False,
    }


def test_real_source_four_turn_focus_constraint_correction_and_topic_switch():
    first_event = _event("CVE-2026-41000", "ExampleGateway", ">=1.0,<1.4.2", "1.4.2")
    second_event = _event("CVE-2026-42000", "OtherGateway", ">=2.0,<2.1", "2.1")
    events, assets = [first_event, second_event], [_asset()]

    turn1 = answer_question("CVE-2026-41000 是否影响生产网关A？", events, assets)
    assert turn1["needs_clarification"] is False
    assert turn1["context_snapshot"]["selected_event_ids"] == ["CVE-2026-41000"]
    assert turn1["context_snapshot"]["selected_asset_ids"] == ["asset-prod-gateway-a"]
    assert turn1["assessments"][0]["status"] == "needs_confirmation"

    turn2 = answer_question(
        "假设 remote_api 已开启，它受影响时如何修复？", events, assets,
        context_snapshot=turn1["context_snapshot"],
    )
    assert turn2["assessments"][0]["status"] == "affected"
    assert {item["field"] for item in turn2["assessments"][0]["context_assumptions"]} == {"conditions.remote_api"}
    assert turn2["context_snapshot"]["inherited_constraints"]["asset_overrides"]["asset-prod-gateway-a"]["conditions"]["remote_api"] is True

    turn3 = answer_question(
        "更正：remote_api 已关闭，它还受影响吗？", events, assets,
        context_snapshot=turn2["context_snapshot"],
    )
    assert turn3["context_resolution"]["corrected"] is True
    assert turn3["assessments"][0]["status"] == "not_affected"
    assert turn3["context_snapshot"]["inherited_constraints"]["asset_overrides"]["asset-prod-gateway-a"]["conditions"]["remote_api"] is False

    turn4 = answer_question(
        "换个话题，改看 CVE-2026-42000 的修复版本。", events, assets,
        context_snapshot=turn3["context_snapshot"],
    )
    assert turn4["context_resolution"]["topic_switched"] is True
    assert turn4["context_snapshot"]["selected_event_ids"] == ["CVE-2026-42000"]
    assert turn4["context_snapshot"]["selected_asset_ids"] == []
    assert turn4["context_snapshot"]["inherited_constraints"] == {}
    assert "2.1" in turn4["answer"]


def test_nested_context_snapshot_alias_is_accepted():
    event = _event("CVE-2026-41000", "ExampleGateway", ">=1.0,<1.4.2", "1.4.2")
    snapshot = {
        "task_id": "task-real-1", "turn_id": 3,
        "focus": {"event_ids": ["CVE-2026-41000"], "asset_ids": ["asset-prod-gateway-a"]},
        "constraints": {"asset_overrides": {"asset-prod-gateway-a": {"conditions": {"remote_api": True}}}},
    }
    result = answer_question("它影响该资产吗？", [event], [_asset()], context_snapshot=snapshot)
    assert result["context_snapshot"]["task_id"] == "task-real-1"
    assert result["context_snapshot"]["turn_id"] == 4
    assert result["assessments"][0]["status"] == "affected"

