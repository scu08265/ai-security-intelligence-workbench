"""The Agent must plan and audit bounded actions, even without a model."""

from __future__ import annotations

from app import agent_orchestration, agents, collectors


def test_answer_plan_keeps_required_evidence_actions_when_model_omits_them(monkeypatch):
    monkeypatch.setattr(
        agent_orchestration, "_call_json_planner",
        lambda *_args, **_kwargs: (["load_authorized_assets", "not_allowed"], None),
    )
    plan = agent_orchestration.answer_plan("资产是否受影响", has_assets=True, model={"planner": True})
    assert plan["planner"] == "model"
    assert plan["actions"][-1] == "answer_from_evidence"
    assert {"load_event_evidence", "load_knowledge_evidence", "load_authorized_assets"} <= set(plan["actions"])
    assert "not_allowed" not in plan["actions"]


def test_collection_plan_never_allows_model_to_expand_source_scope(monkeypatch):
    monkeypatch.setattr(
        agent_orchestration, "_call_json_planner",
        lambda *_args, **_kwargs: (["collect_registered_source"], None),
    )
    plan = agent_orchestration.collection_plan(["nvd"], {"planner": True})
    assert plan["actions"] == [{"action": "collect_registered_source", "source_id": "nvd"}]
    assert "collect_registered_source" in plan["allowed_actions"]
    assert set(plan["allowed_actions"]) <= agent_orchestration.COLLECTION_ACTIONS


def test_answer_persists_agent_plan_and_observable_tool_records():
    result = agents.answer("不存在的组件风险是什么？")
    assert result["agent_plan"]["planner"] == "deterministic"
    assert [item["action"] for item in result["tool_calls"]][-1] == "answer_from_evidence"
    run = agents.storage.latest_run("chat")
    assert run["detail"]["agent_plan"]["kind"] == "answer"
    assert run["detail"]["tool_calls"] == result["tool_calls"]


def test_collection_persists_per_source_action_audit(monkeypatch):
    monkeypatch.setattr(
        collectors, "collect",
        lambda source_id, since=None: collectors.CollectOutcome(source_id=source_id, status="ok"),
    )
    result = agents.run_collection(["nvd"])
    assert result["agent_plan"]["kind"] == "collection"
    assert result["tool_calls"][0]["action"] == "collect_registered_source"
    run = agents.storage.latest_run("collect")
    assert "collect_registered_source" in run["detail"]["agent_plan"]["allowed_actions"]


def test_default_collection_uses_recommended_sources(monkeypatch):
    monkeypatch.setattr(
        collectors, "collect",
        lambda source_id, since=None: collectors.CollectOutcome(source_id=source_id, status="ok"),
    )
    result = agents.run_collection()
    source_ids = {item["source_id"] for item in result["results"]}
    assert "openalex" in source_ids
    assert "arxiv" not in source_ids
    assert "ghsa" not in source_ids
