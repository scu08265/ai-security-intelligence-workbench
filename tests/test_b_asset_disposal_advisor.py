"""B 任务四：策略感知资产处置建议的功能测试（覆盖验收要求的 12 个场景）。

测试里的资产与事件都是**合成数据**，只用于验证逻辑；真实数据的结果见
`artifacts/b_eval/asset_disposal_demo.json`（合成资产 + 真实事件）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import asset_disposal_advisor as advisor  # noqa: E402

ARTIFACTS = ROOT / "artifacts" / "b_eval"
DEMO = ARTIFACTS / "asset_disposal_demo.json"


# --------------------------------------------------------------------------
# 合成数据构造
# --------------------------------------------------------------------------

def _event(event_id="CVE-TEST-0001", component="pkg", range_="< 2.0", fixed="2.0",
           severity="high", score=9.0, kev=False, poc=False, source_id="test:abc123"):
    relationships = []
    if kev:
        relationships.append({"subject": event_id, "predicate": "known_exploited",
                              "object": "CISA KEV catalog",
                              "evidence_ids": ["kev:deadbeef"]})
    return {
        "id": event_id,
        "title": f"{component} 测试漏洞",
        "component": component,
        "ecosystem": "PyPI",
        "severity": severity,
        "cvss": [{"version": "3.1", "score": score, "source_id": source_id}]
        if score is not None else [],
        "affected": [{"package": component, "ecosystem": "PyPI", "range": range_,
                      "fixed_version": fixed, "source_id": source_id}],
        "sources": [{"id": source_id, "url": "https://example.invalid/x",
                     "title": "test source"}],
        "conditions": [],
        "references": [],
        "poc": [{"status": "public", "source_id": "poc:1"}] if poc else [],
        "relationships": relationships,
    }


def _asset(asset_id="asset-test", component="pkg", version="1.0", exposure="internal",
           criticality="medium", authorized=True):
    return {"id": asset_id, "name": asset_id, "component": component,
            "ecosystem": "PyPI", "version": version, "exposure": exposure,
            "business_criticality": criticality, "authorized": authorized,
            "synthetic": True, "conditions": {}}


def _policy(asset_id="asset-test", **overrides) -> advisor.Policy:
    raw = {
        "maintenance_window": {"weekday": "Sun", "start": "02:00", "end": "05:00",
                               "timezone": "Asia/Shanghai"},
        "business_importance": "high",
        "prohibited_actions": [],
        "owner": "team@example.invalid",
        "acceptable_downtime_minutes": 30,
    }
    raw.update(overrides)
    return advisor.parse_policy(asset_id, raw)


def _findings(asset, policy, events):
    return advisor.advise(asset, policy, events)["findings"]


# --------------------------------------------------------------------------
# 1 / 2：业务重要性与同漏洞不同资产
# --------------------------------------------------------------------------

def test_business_importance_changes_priority():
    event = _event()
    events = {event["id"]: event}
    high = _findings(_asset(criticality="critical"), _policy(business_importance="critical"),
                     events)[0]
    low = _findings(_asset(criticality="low"), _policy(business_importance="low"),
                    events)[0]
    assert high["priority"]["score"] > low["priority"]["score"]
    assert high["priority"]["components"]["business_importance"] == 20
    assert low["priority"]["components"]["business_importance"] == 3


def test_same_event_different_assets_rank_by_facts_and_policy():
    event = _event()
    events = {event["id"]: event}
    prod = advisor.advise(_asset("asset-prod", criticality="high"),
                          _policy("asset-prod", business_importance="high"), events)
    lab = advisor.advise(_asset("asset-lab", criticality="low"),
                         _policy("asset-lab", business_importance="low"), events)
    assert prod["findings"][0]["priority"]["score"] > lab["findings"][0]["priority"]["score"]
    # 两者的证据 ID 相同（同一事件），差异来自策略与业务事实
    assert prod["findings"][0]["evidence_ids"] == lab["findings"][0]["evidence_ids"]


# --------------------------------------------------------------------------
# 3 / 4 / 5：维护窗口、禁止动作、可接受停机
# --------------------------------------------------------------------------

def test_maintenance_window_and_missing_window_change_scheduling():
    event = _event()
    events = {event["id"]: event}
    inside = _findings(_asset(), _policy(), events)[0]
    patch = next(a for a in inside["recommended_actions"] if a["action"] == "apply_patch")
    assert patch["scheduling"]["status"] == "inside_declared_window_only"
    assert patch["scheduling"]["allowed_from"] == "Sun 02:00"
    assert patch["scheduling"]["timezone"] == "Asia/Shanghai"

    no_window = _findings(_asset(), _policy(maintenance_window=None), events)[0]
    patch = next(a for a in no_window["recommended_actions"] if a["action"] == "apply_patch")
    assert patch["scheduling"]["status"] == "needs_window"


def test_prohibited_action_blocks_recommendation_and_explains_conflict():
    event = _event()
    findings = _findings(_asset(), _policy(prohibited_actions=["apply_patch"]),
                         {event["id"]: event})
    item = findings[0]
    assert "apply_patch" not in {a["action"] for a in item["recommended_actions"]}
    blocked = {a["action"]: a for a in item["blocked_actions"]}
    assert "prohibited_actions" in blocked["apply_patch"]["blocked_reason"]
    assert item["conflicts"] and item["needs_human_review"] is True


def test_acceptable_downtime_limits_unconditional_recommendation():
    event = _event()
    findings = _findings(_asset(), _policy(acceptable_downtime_minutes=5),
                         {event["id"]: event})
    patch = next(a for a in findings[0]["recommended_actions"] if a["action"] == "apply_patch")
    assert patch["estimated_downtime_minutes"] == 15
    assert "可接受停机" in patch["constraint_warning"]
    assert findings[0]["needs_human_review"] is True


# --------------------------------------------------------------------------
# 6 / 7 / 8：负责人缺失、修复版本缺失、CVSS/POC 缺失
# --------------------------------------------------------------------------

def test_missing_owner_and_missing_policy_are_marked_not_guessed():
    event = _event()
    findings = _findings(_asset(), _policy(owner=None), {event["id"]: event})
    assert findings[0]["owner"] is None
    assert findings[0]["owner_known"] is False
    assert findings[0]["needs_human_review"] is True

    fallback = advisor.default_policy("asset-no-policy")
    assert fallback.explicit is False
    assert fallback.acceptable_downtime_minutes == 0
    assert "apply_patch" in fallback.prohibited_actions
    item = _findings(_asset("asset-no-policy"), fallback, {event["id"]: event})[0]
    assert item["policy_explicit"] is False
    assert item["conflicts"], "无策略时破坏性动作必须被拦下并解释"


def test_missing_fixed_version_switches_to_verification_and_monitoring():
    event = _event(fixed=None)
    findings = _findings(_asset(), _policy(), {event["id"]: event})
    actions = {a["action"] for a in findings[0]["recommended_actions"]}
    assert "apply_patch" not in actions
    assert {"verify_version", "enhanced_monitoring", "further_verification"} <= actions


def test_missing_cvss_and_poc_are_recorded_as_gaps_not_scores():
    event = _event(severity=None, score=None)
    findings = _findings(_asset(), _policy(), {event["id"]: event})
    priority = findings[0]["priority"]
    assert priority["components"]["severity"] == 0
    assert priority["components"]["exploitation"] == 0
    assert any("严重性" in g for g in priority["gaps"])
    assert any("POC" in g for g in priority["gaps"])


# --------------------------------------------------------------------------
# 9 / 10：证据不足不得断言受影响、策略冲突需人工确认
# --------------------------------------------------------------------------

def test_unknown_version_is_needs_confirmation_without_score():
    event = _event()
    findings = _findings(_asset(version="unknown"), _policy(), {event["id"]: event})
    item = findings[0]
    assert item["link_status"] == "needs_confirmation"
    assert item["priority"]["level"] == "待核实"
    assert item["priority"]["score"] is None
    assert item["priority"]["score_is_provisional"] is True
    assert item["confidence"] == "inferred"


def test_component_mismatch_is_not_attributed_to_the_asset():
    event = _event(component="otherpkg")
    result = advisor.advise(_asset(component="pkg"), _policy(), {event["id"]: event})
    assert result["findings"] == []
    assert result["summary"]["findings"] == 0


def test_conflicting_policy_requires_human_review_with_reason():
    event = _event(kev=True)
    findings = _findings(_asset(criticality="critical"),
                         _policy(prohibited_actions=["apply_patch", "limit_exposure"]),
                         {event["id"]: event})
    item = findings[0]
    assert item["needs_human_review"] is True
    assert item["conflicts"]
    assert all("blocked_reason" in a for a in item["blocked_actions"])


# --------------------------------------------------------------------------
# 11：证据可追溯
# --------------------------------------------------------------------------

def test_evidence_ids_and_asset_identity_are_traceable():
    event = _event(source_id="osv:acca1ed12f", kev=True)
    findings = _findings(_asset("asset-trace"), _policy("asset-trace"),
                         {event["id"]: event})
    item = findings[0]
    assert item["asset_id"] == "asset-trace"
    assert "osv:acca1ed12f" in item["evidence_ids"]
    assert "kev:deadbeef" in item["evidence_ids"]
    assert item["event_id"] == event["id"]
    actions = item["recommended_actions"]
    assert all(a["evidence_ids"] for a in actions), "每条建议都必须绑定证据"


# --------------------------------------------------------------------------
# 12：空输入、非法策略、无匹配资产
# --------------------------------------------------------------------------

def test_invalid_policy_fields_are_rejected():
    with pytest.raises(advisor.PolicyError):
        advisor.parse_policy("a", {"business_importance": "very-high"})
    with pytest.raises(advisor.PolicyError):
        advisor.parse_policy("a", {"maintenance_window": {"weekday": "Funday",
                                                          "start": "02:00", "end": "03:00",
                                                          "timezone": "UTC"}})
    with pytest.raises(advisor.PolicyError):
        advisor.parse_policy("a", {"maintenance_window": {"weekday": "Sun",
                                                          "start": "05:00", "end": "02:00",
                                                          "timezone": "UTC"}})
    with pytest.raises(advisor.PolicyError):
        advisor.parse_policy("a", {"acceptable_downtime_minutes": -5})
    with pytest.raises(advisor.PolicyError):
        advisor.parse_policy("", {})


def test_empty_inputs_degrade_gracefully():
    result = advisor.build([], {}, {})
    assert result["totals"]["assets"] == 0
    assert result["totals"]["findings"] == 0
    # 没有事件时，资产仍然输出结构化结果（findings 为空），不报错
    only_asset = advisor.build([_asset()], {"asset-test": _policy()}, {})
    assert only_asset["assets"][0]["findings"] == []
    assert only_asset["assets"][0]["summary"]["findings"] == 0


def test_policy_file_duplicate_ids_are_rejected(tmp_path):
    path = tmp_path / "policies.json"
    path.write_text(json.dumps({"policies": [
        {"asset_id": "a", "business_importance": "low"},
        {"asset_id": "a", "business_importance": "high"},
    ]}), encoding="utf-8")
    with pytest.raises(advisor.PolicyError):
        advisor.load_policies(path)


# --------------------------------------------------------------------------
# 演示产物：合成资产 + 真实事件
# --------------------------------------------------------------------------

def test_demo_artifact_separates_synthetic_assets_and_real_events():
    if not DEMO.is_file():
        pytest.skip("演示产物不存在（先运行 tools/asset_disposal_advisor.py --demo）")
    payload = json.loads(DEMO.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "b-asset-disposal-1.0"
    assert len(payload["assets"]) >= 5
    for asset in payload["assets"]:
        assert asset["asset"]["synthetic"] is True, "演示资产必须标记为合成"
    # 三个演示案例齐备
    assert set(payload["demo"]) == {
        "case_A_high_priority", "case_B_policy_difference",
        "case_C_insufficient_evidence_or_conflict"}
    case_a = payload["demo"]["case_A_high_priority"]["findings"]
    assert case_a and case_a[0]["link_status"] == "affected"
    assert case_a[0]["priority"]["score"] is not None
    assert case_a[0]["evidence_ids"]
    # 案例 C 必须包含待核实与冲突两类降级输出
    case_c = payload["demo"]["case_C_insufficient_evidence_or_conflict"]
    levels = [f["priority"]["level"] for f in case_c["copilot_findings"]]
    assert levels and set(levels) == {"待核实"}
    assert case_c["openwebui_findings"][0]["blocked_actions"]
    assert case_c["openwebui_findings"][0]["conflicts"]
    # 案例 B 展示同一漏洞在三种策略下的差异
    case_b = payload["demo"]["case_B_policy_difference"]
    assert len(case_b["assets"]) == 3
    assert case_b["edge_findings"][0]["conflicts"], "停机约束必须产生冲突说明"
