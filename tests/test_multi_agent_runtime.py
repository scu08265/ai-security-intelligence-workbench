"""Independent agent instances, message routing, audit, and replanning."""

from __future__ import annotations

from app import multi_agent_runtime, storage


def test_rejected_action_is_rerouted_by_replanner():
    calls: dict[str, int] = {}

    def collect():
        calls["collect"] = calls.get("collect", 0) + 1
        return {"status": "failed", "error": "upstream timeout"}

    def retry():
        calls["retry"] = calls.get("retry", 0) + 1
        return {"status": "ok", "evidence_ids": ["retry-evidence"]}

    result = multi_agent_runtime.run_multi_agent_task(
        "验证安全情报来源",
        ["collect_registered_source", "collect_registered_source_retry"],
        {
            "collect_registered_source": collect,
            "collect_registered_source_retry": retry,
        },
    )
    plan = result["plan"]
    assert plan["accepted_nodes"]
    assert plan["rejected_nodes"] == []
    assert calls["retry"] >= 1
    assert any(message["kind"] == "plan_revision" for message in result["messages"])
    run = storage.latest_run("multi_agent")
    assert run["id"] == result["run_id"]


def test_auditor_preserves_conflicts_without_silent_arbitration():
    result = multi_agent_runtime.run_multi_agent_task(
        "核对冲突来源",
        ["collect_registered_source"],
        {
            "collect_registered_source": lambda: {
                "status": "ok",
                "evidence_ids": ["source-a"],
                "conflicts": [{"field": "affected.range", "values": ["a", "b"]}],
            }
        },
    )
    assert result["plan"]["conflict_nodes"]
    assert any(
        item["audit"] == "conflict_preserved"
        for item in result["plan"]["trace"]
    )
    assert "不静默合并" in result["plan"]["trace"][0]["reason"]


def test_agents_have_private_state_and_explicit_messages():
    result = multi_agent_runtime.run_multi_agent_task(
        "读取缓存快照",
        ["read_cached_snapshot"],
        {
            "read_cached_snapshot": lambda: {
                "status": "ok",
                "snapshot_hash": "hash-1",
                "evidence_ids": ["snapshot"],
            }
        },
    )
    messages = result["messages"]
    assert {"plan_proposed", "execution_result", "audit_decision"} <= {
        item["kind"] for item in messages
    }
    assert result["agents"]["auditor"]["decisions"]
    assert result["agents"]["planner"]["last_plan"]
