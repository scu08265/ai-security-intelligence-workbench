from __future__ import annotations

import pytest

from app import dag_executor


def test_bounded_plan_rejects_unknown_source_and_records_dependencies():
    with pytest.raises(dag_executor.PlanError, match="已登记"):
        dag_executor.build_plan({"source_ids": ["https://bad.example"]})
    plan = dag_executor.build_plan({"source_ids": ["nvd"], "question": "给出结论"})
    nodes = {item["id"]: item for item in plan["nodes"]}
    assert nodes["enrich"]["depends_on"] == ["collect"]
    assert nodes["answer"]["depends_on"] == ["assess"]


def test_executor_skips_dependents_after_a_failure_without_other_tools():
    plan = dag_executor.build_plan({"source_ids": ["nvd"], "question": "给出结论"})
    result = dag_executor.execute_plan(plan, actions={
        "collect_registered_sources": lambda source_ids: {"status": "failed", "error": "upstream"},
        "enrich_pending_events": lambda limit: {"status": "completed"},
        "assess_authorized_assets": lambda: {"status": "completed"},
        "answer_from_evidence": lambda question, thread_id=None: {"answer": "unused"},
    })
    nodes = {item["node_id"]: item for item in result["nodes"]}
    assert nodes["collect"]["status"] == "failed"
    assert nodes["enrich"]["status"] == nodes["assess"]["status"] == nodes["answer"]["status"] == "skipped"
