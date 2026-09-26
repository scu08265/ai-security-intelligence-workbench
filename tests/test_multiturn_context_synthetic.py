"""Synthetic branch coverage for ambiguous and corrected multi-turn focus."""

from app.conversation_context import resolve_conversation_context
from app.intelligence import answer_question


def _event(event_id: str, component: str = "WidgetAI") -> dict:
    return {
        "id": event_id, "aliases": [], "kind": "vulnerability", "status": "confirmed",
        "title": f"Synthetic {event_id}", "summary": "Synthetic context fixture.",
        "component": component, "affected": [], "conditions": [], "relationships": [],
        "sources": [{
            "id": f"fixture:{event_id}", "url": "https://example.invalid/context",
            "title": "Synthetic source", "excerpt": f"Synthetic evidence for {event_id}.",
            "trust": "fixture",
        }],
    }


def _asset(asset_id: str, name: str) -> dict:
    return {
        "id": asset_id, "name": name, "component": "WidgetAI", "version": "1.0",
        "conditions": {}, "authorized": True, "is_demo": True,
    }


def test_pronoun_with_multiple_event_candidates_requires_confirmation():
    events = [_event("CVE-2099-10001"), _event("CVE-2099-10002")]
    snapshot = {"selected_event_ids": [event["id"] for event in events], "turn_id": 1}
    result = answer_question("它的修复版本是什么？", events, [], context_snapshot=snapshot)
    assert result["needs_clarification"] is True
    assert result["mode"] == "clarification_required"
    assert result["related_event_ids"] == []
    assert result["claims"] == []
    assert result["rag"]["refusal_reason"] == "ambiguous_context"
    assert result["clarification"]["candidate_ids"] == ["CVE-2099-10001", "CVE-2099-10002"]


def test_component_with_multiple_events_requires_confirmation_unless_plural():
    events = [_event("CVE-2099-10001"), _event("CVE-2099-10002")]
    singular = answer_question("WidgetAI 的这个漏洞如何修复？", events, [])
    plural = answer_question("WidgetAI 有哪些漏洞？", events, [])
    assert singular["needs_clarification"] is True
    assert plural["needs_clarification"] is False
    assert set(plural["related_event_ids"]) == {"CVE-2099-10001", "CVE-2099-10002"}


def test_user_correction_chooses_replacement_focus():
    events = [_event("CVE-2099-10001"), _event("CVE-2099-10002")]
    snapshot = {"selected_event_ids": ["CVE-2099-10001"], "turn_id": 1}
    resolved = resolve_conversation_context(
        "更正，不是 CVE-2099-10001，而是 CVE-2099-10002。", events, [],
        context_snapshot=snapshot,
    )
    assert resolved["needs_clarification"] is False
    assert resolved["corrected"] is True
    assert resolved["context_snapshot"]["selected_event_ids"] == ["CVE-2099-10002"]


def test_multiple_matching_assets_require_confirmation():
    event = _event("CVE-2099-10001")
    assets = [_asset("asset-a", "演示节点A"), _asset("asset-b", "演示节点B")]
    result = answer_question("CVE-2099-10001 是否影响我的资产？", [event], assets, context_snapshot={})
    assert result["needs_clarification"] is True
    assert result["clarification"]["type"] == "asset"
    assert result["clarification"]["candidate_ids"] == ["asset-a", "asset-b"]
    assert result["assessments"] == []


def test_legacy_text_history_remains_compatible_but_does_not_create_constraints():
    event = _event("CVE-2099-10001")
    history = [{"role": "assistant", "content": "此前讨论 CVE-2099-10001，它可能很严重。"}]
    result = answer_question("它是什么？", [event], [], history=history)
    assert result["related_event_ids"] == ["CVE-2099-10001"]
    assert result["context_resolution"]["context_source"] == "legacy_history_identifiers"
    assert result["context_snapshot"]["inherited_constraints"] == {}
