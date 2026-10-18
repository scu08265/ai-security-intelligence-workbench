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


def test_remediated_finding_stays_in_the_closure_denominator():
    """Fixing the asset must not shrink the denominator.

    Regression: the cohort used to mean 'currently affected', so a verified
    closure followed by a re-assessment (which flips the asset to
    not_affected) removed the finding from both numerator and denominator and
    collapsed the closure rate to zero right after a successful fix.
    """
    event_id, asset_id = _seed_case(version="2.5.0")
    disposition.update_disposition(event_id, asset_id, status="verified", assignee="alice")
    before = disposition.metrics()
    assert before["high_priority_total"] == 1
    assert before["closure_rate"] == 1.0

    # Simulate a later re-assessment flipping the live status.
    storage.save_assessment({"event_id": event_id, "asset_id": asset_id,
                             "status": "not_affected", "priority": "low"})

    after = disposition.metrics()
    assert after["high_priority_total"] == 1, "closed finding must stay in the cohort"
    assert after["high_priority_closed"] == 1
    assert after["closure_rate"] == 1.0


def test_unknown_status_is_rejected():
    event_id, asset_id = _seed_case()
    client = TestClient(app)
    response = client.put(
        f"/api/dispositions/{event_id}/{asset_id}",
        json={"event_id": event_id, "asset_id": asset_id, "status": "bogus"},
    )
    assert response.status_code == 422


def test_accepted_is_resolved_but_not_verified():
    event_id, asset_id = _seed_case(version="1.0.0")
    disposition.update_disposition(
        event_id, asset_id, status="accepted", assignee="risk-owner",
        note="Accepted for the current maintenance window.",
    )
    metrics = disposition.metrics()
    assert metrics["high_priority_closed"] == 1
    assert metrics["high_priority_verified"] == 0
    assert metrics["closure_rate"] == 1.0
    assert metrics["verified_rate"] == 0.0


def test_empty_closure_denominator_returns_null():
    metrics = disposition.metrics()
    assert metrics["high_priority_total"] == 0
    assert metrics["closure_rate"] is None
    assert metrics["verified_rate"] is None


def test_opened_at_is_stable_across_updates():
    event_id, asset_id = _seed_case(version="1.0.0")
    first = disposition.update_disposition(
        event_id, asset_id, status="in_progress", assignee="alice",
    )["disposition"]
    second = disposition.update_disposition(
        event_id, asset_id, status="fixed", assignee="alice",
        note="upgrade scheduled",
    )["disposition"]
    assert first["opened_at"] == second["opened_at"]


def test_metrics_separate_the_whole_queue_from_the_opened_rows():
    """A single ratio hides "nobody opened it". Both denominators must be exposed."""
    event_id, asset_id = _seed_case()
    untouched = disposition.metrics()
    assert untouched["high_priority_total"] == 1
    assert untouched["high_priority_registered"] == 0
    assert untouched["high_priority_unopened"] == 1
    assert untouched["closure_rate"] == 0.0
    assert untouched["registered_closure_rate"] is None

    disposition.update_disposition(event_id, asset_id, status="in_progress", assignee="alice")
    opened = disposition.metrics()
    assert opened["high_priority_registered"] == 1
    assert opened["high_priority_unopened"] == 0
    assert opened["closure_rate"] == 0.0
    assert opened["registered_closure_rate"] == 0.0

    disposition.update_disposition(event_id, asset_id, status="accepted", assignee="alice")
    resolved = disposition.metrics()
    assert resolved["closure_rate"] == 1.0
    assert resolved["registered_closure_rate"] == 1.0
    assert resolved["high_priority_verified"] == 0


def test_pending_cohort_lists_only_findings_without_a_disposition():
    event_id, asset_id = _seed_case()
    queue = disposition.pending_cohort()
    assert queue["pending_total"] == 1
    assert queue["by_priority"] == {"high": 1}
    assert queue["items"][0]["event_id"] == event_id
    assert queue["items"][0]["asset_id"] == asset_id

    disposition.update_disposition(event_id, asset_id, status="in_progress", assignee="alice")
    assert disposition.pending_cohort()["pending_total"] == 0
    assert disposition.pending_cohort()["items"] == []


def test_batch_keeps_going_when_one_row_is_invalid():
    """One bad row must not roll back the rest of the queue."""
    event_id, asset_id = _seed_case()
    result = disposition.update_many([
        {"event_id": event_id, "asset_id": asset_id, "status": "in_progress", "assignee": "alice"},
        {"event_id": event_id, "asset_id": "asset-no-assessment", "status": "in_progress", "assignee": "alice"},
        {"event_id": event_id, "asset_id": asset_id, "status": "bogus", "assignee": "alice"},
    ])
    assert result["requested"] == 3
    assert result["applied"] == 1
    assert result["failed"] == 2
    assert [entry["ok"] for entry in result["results"]] == [True, False, False]
    assert result["results"][1]["error"]
    assert result["results"][2]["error"]
    assert disposition.get_disposition(event_id, asset_id)["status"] == "in_progress"
    assert result["metrics"]["high_priority_registered"] == 1


def test_batch_endpoint_reports_each_item_outcome():
    event_id, asset_id = _seed_case(version="2.5.0")
    client = TestClient(app)
    response = client.post("/api/dispositions/batch", json={"items": [
        {"event_id": event_id, "asset_id": asset_id, "status": "verified", "assignee": "alice",
         "version_after": "2.5.0"},
        {"event_id": event_id, "asset_id": "asset-no-assessment", "status": "in_progress",
         "assignee": "alice"},
    ]})
    assert response.status_code == 200
    body = response.json()
    assert body["applied"] == 1
    assert body["failed"] == 1
    assert body["results"][0]["applied_status"] == "verified"
    assert body["results"][0]["verification_passed"] is True
    assert body["results"][1]["ok"] is False

    pending = client.get("/api/dispositions/pending").json()
    assert "pending_total" in pending


def test_closure_scope_is_documented_verbatim():
    """两个比率与四条限定必须逐字出现在口径文档里，不能只存在于代码。"""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    doc = (root / "docs" / "DISPOSITION_CLOSURE.md").read_text(encoding="utf-8")
    metrics = disposition.metrics()
    for line in metrics["limitations"]:
        assert line in doc, f"口径文档缺这一句，或改写了标点：{line}"
    # 两个分母、从未登记数、以及"不可互换"的措辞都要在文档里
    for token in ("closure_rate", "registered_closure_rate",
                  "high_priority_registered", "high_priority_unopened", "不可互换"):
        assert token in doc, f"口径文档缺字段或口径说明：{token}"


def test_scorecard_disposition_matches_the_metrics_endpoint():
    """页面卡片口径必须与 /api/dispositions/metrics 逐字段一致，且内部自洽。

    一致性核对沿用 tools/check_b_scorecard_consistency.py 的方式（同一份只读脚本），
    因此这里不另写一套比较逻辑，避免两边判定标准漂移。
    """
    import importlib.util
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "check_b_scorecard_consistency", root / "tools" / "check_b_scorecard_consistency.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    payload = module.build()
    disposition_checks = [c for c in payload["checks"] if c["field"].startswith("disposition.")]
    assert disposition_checks, "一致性核对里没有 disposition 段"
    assert [c for c in disposition_checks if not c["match"]] == []

    client = TestClient(app)
    body = client.get("/api/competition/scorecard").json()["disposition"]
    # 页面处置闭环卡片实际读取的三个字段必须在位（改名要在这里断，而不是页面上显示“—”）
    for field in ("closure_rate", "registered_closure_rate", "high_priority_unopened"):
        assert field in body, f"分数卡缺页面读取的字段：{field}"
    assert field_is_consistent(body)

    # 内部自洽：状态分布求和 = 全队列；已登记 + 未登记 = 全队列
    total = body["high_priority_total"]
    assert sum((body.get("status_breakdown") or {}).values()) == total
    assert body["high_priority_registered"] + body["high_priority_unopened"] == total


def field_is_consistent(body: dict) -> bool:
    """两个比率必须能由各自的分子分母重算出来（分母不同，不能互换）。"""
    total = body["high_priority_total"]
    registered = body["high_priority_registered"]
    closed = body["high_priority_closed"]
    expected = round(closed / total, 4) if total else None
    assert body["closure_rate"] == expected
    if registered:
        assert body["registered_closure_rate"] == round(closed / registered, 4)
    else:
        assert body["registered_closure_rate"] is None
    return True