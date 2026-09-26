from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import storage, task_dag
from app.api import app


def test_task_plan_nodes_checkpoints_and_handoff_are_replayable():
    task = task_dag.create_task(
        "核验一条漏洞情报并形成可交接的结论",
        task_id="task-dag", success_criteria=["结论有证据", "交接被接受"],
        tool_candidates=["nvd", {"id": "rag_search", "purpose": "查证正文"}],
        budget={"tool_calls": 4, "rounds": 2}, constraints=["未知时说明未知"],
    )
    assert task["status"] == "planned"
    plan = task_dag.create_plan(task["id"], "首版核验计划", summary="先取证，再判断，再交接", plan_id="plan-dag")
    gather = task_dag.create_node(
        task["id"], plan["id"], "收集证据", node_id="node-gather",
        success_criteria=["记录来源版本"], tool_candidates=["nvd"], budget={"tool_calls": 2},
    )
    assess = task_dag.create_node(
        task["id"], plan["id"], "判断影响", node_id="node-assess",
        depends_on=[gather["id"]], success_criteria=["给出条件结论"],
    )
    checkpoint = task_dag.add_checkpoint(
        task["id"], gather["id"], "已保存来源快照", status="passed",
        evidence_refs=["snapshot:sha256:abc"], note="可复现",
    )
    assert checkpoint["immutable"] is True
    with pytest.raises(ValueError, match="依赖节点尚未完成"):
        task_dag.set_node_status(task["id"], assess["id"], "completed")
    done = task_dag.set_node_status(task["id"], gather["id"], "completed", result={"sources": 1})
    assert done["immutable"] is True
    task_dag.set_node_status(task["id"], assess["id"], "completed", result={"conclusion": "needs_confirmation"})
    handoff = task_dag.create_handoff(
        task["id"], gather["id"], assess["id"], payload={"evidence": ["snapshot:sha256:abc"]},
    )
    accepted = task_dag.decide_handoff(task["id"], handoff["id"], "accepted", decision_note="证据可用")
    assert accepted["status"] == "accepted"
    loaded = task_dag.get_task(task["id"])
    assert loaded and loaded["plans"][0]["immutable"] is True
    assert loaded["nodes"][1]["depends_on"] == [gather["id"]]
    assert loaded["nodes"][0]["checkpoints"][0]["evidence_refs"] == ["snapshot:sha256:abc"]
    assert loaded["handoffs"][0]["immutable"] is True
    assert loaded["stores_hidden_reasoning"] is False
    assert task_dag.set_task_status(task["id"], "completed")["immutable_when_completed"] is True


def test_completed_records_are_immutable_and_cross_task_dependencies_are_rejected():
    first = task_dag.create_task("第一个任务")
    second = task_dag.create_task("第二个任务")
    first_plan = task_dag.create_plan(first["id"], "计划")
    second_plan = task_dag.create_plan(second["id"], "计划")
    node = task_dag.create_node(first["id"], first_plan["id"], "完成节点")
    task_dag.set_node_status(first["id"], node["id"], "completed")
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        with storage.connect() as conn:
            conn.execute("UPDATE agent_task_nodes SET title='篡改' WHERE id=?", (node["id"],))
    with pytest.raises(ValueError, match="同一task"):
        task_dag.create_node(second["id"], second_plan["id"], "错误依赖", depends_on=[node["id"]])
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        with storage.connect() as conn:
            conn.execute("UPDATE agent_task_plans SET title='篡改' WHERE id=?", (first_plan["id"],))


def test_task_dag_api_exposes_bounded_structured_records():
    client = TestClient(app)
    created = client.post("/api/agent/tasks", json={
        "task_id": "api-dag", "objective": "验证任务图接口",
        "success_criteria": ["节点可追溯"], "tool_candidates": ["local_search"],
        "budget": {"tool_calls": 3}, "constraints": ["不保存推理过程"],
    })
    assert created.status_code == 200
    plan = client.post("/api/agent/tasks/api-dag/plans", json={"plan_id": "api-plan", "title": "计划"})
    assert plan.status_code == 200
    node = client.post("/api/agent/tasks/api-dag/nodes", json={
        "node_id": "api-node", "plan_id": "api-plan", "title": "节点",
        "success_criteria": ["有检查点"],
    })
    assert node.status_code == 200
    checkpoint = client.post("/api/agent/tasks/api-dag/nodes/api-node/checkpoints", json={
        "label": "检查", "status": "passed", "evidence_refs": ["run:1"],
    })
    assert checkpoint.status_code == 200
    rejected = client.post("/api/agent/tasks/api-dag/nodes", json={
        "plan_id": "api-plan", "title": "非法字段", "hidden_reasoning": "禁止",
    })
    assert rejected.status_code == 422
    listed = client.get("/api/agent/tasks").json()
    assert listed["total"] == 1
    detail = client.get("/api/agent/tasks/api-dag")
    assert detail.status_code == 200
    assert detail.json()["nodes"][0]["checkpoints"][0]["label"] == "检查"
