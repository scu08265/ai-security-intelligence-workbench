"""Deterministic executor for the project's bounded task DAG.

It is intentionally not a general autonomous tool runner.  A plan can invoke
only the five actions registered below; it cannot supply a URL, command or
callable.  Returned records are suitable for saving as task-node results.
"""

from __future__ import annotations

from typing import Any, Callable

from . import agents, rag_corpus, sources

ACTION_ROLES = {
    "collect_registered_sources": "collector",
    "enrich_pending_events": "evidence_retriever",
    "assess_authorized_assets": "asset_assessor",
    "read_current_documents": "knowledge_retriever",
    "answer_from_evidence": "answerer",
}
MAX_ENRICH = 20


class PlanError(ValueError):
    pass


def build_plan(request: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a fixed, inspectable dependency graph from bounded parameters."""
    request = dict(request or {})
    question = str(request.get("question") or "").strip()
    if len(question) > 2000:
        raise PlanError("question不能超过2000字符")
    collect = bool(request.get("collect", True))
    assess = bool(request.get("assess_assets", True))
    requested_sources = list(request.get("source_ids") or [item.id for item in sources.SOURCES])
    known = {item.id for item in sources.SOURCES}
    selected = list(dict.fromkeys(str(item) for item in requested_sources))
    unknown = [item for item in selected if item not in known]
    if collect and (not selected or unknown):
        raise PlanError("来源必须为已登记source_id：" + "、".join(unknown or ["无来源"]))
    limit = int(request.get("enrich_limit", 6))
    if not 0 <= limit <= MAX_ENRICH:
        raise PlanError(f"enrich_limit必须在0到{MAX_ENRICH}之间")
    nodes: list[dict[str, Any]] = []
    if collect:
        nodes += [
            {"id": "collect", "action": "collect_registered_sources", "role": ACTION_ROLES["collect_registered_sources"], "depends_on": [], "inputs": {"source_ids": selected}, "success_criteria": ["逐来源结果已保存"]},
            {"id": "enrich", "action": "enrich_pending_events", "role": ACTION_ROLES["enrich_pending_events"], "depends_on": ["collect"], "inputs": {"limit": limit}, "success_criteria": ["工具预算与停止原因已记录"]},
        ]
    if assess:
        nodes.append({"id": "assess", "action": "assess_authorized_assets", "role": ACTION_ROLES["assess_authorized_assets"], "depends_on": ["enrich"] if collect else [], "inputs": {}, "success_criteria": ["仅评估已授权资产"]})
    if question:
        nodes.append({"id": "answer", "action": "answer_from_evidence", "role": ACTION_ROLES["answer_from_evidence"], "depends_on": ["assess"] if assess else [], "inputs": {"question": question, "thread_id": request.get("thread_id")}, "success_criteria": ["结论带引用或拒答"]})
    if not nodes:
        raise PlanError("计划至少需要采集、资产研判或问答")
    return {"objective": str(request.get("objective") or "安全情报任务"), "nodes": nodes,
            "budget": {"max_nodes": len(nodes), "max_enrich_events": limit},
            "replanning_policy": "采集失败时停止依赖步骤；不会扩大来源、预算或工具集合。"}


def _actions() -> dict[str, Callable[..., dict[str, Any]]]:
    return {
        "collect_registered_sources": lambda source_ids: agents.run_collection(source_ids, close_gaps=False),
        "enrich_pending_events": lambda limit: agents.run_enrichment(limit=limit),
        "assess_authorized_assets": lambda: agents.run_assessment(),
        "read_current_documents": lambda: {"documents": rag_corpus.list_documents(limit=30)},
        "answer_from_evidence": lambda question, thread_id=None: agents.answer(question, thread_id=thread_id),
    }


def execute_plan(plan: dict[str, Any], *, actions: dict[str, Callable[..., dict[str, Any]]] | None = None) -> dict[str, Any]:
    """Run nodes in declared order, recording dependency skips and failures."""
    nodes = list(plan.get("nodes") or [])
    registry = _actions()
    if actions:
        registry.update(actions)
    results: dict[str, dict[str, Any]] = {}
    for node in nodes:
        node_id, action = str(node.get("id")), str(node.get("action"))
        if action not in ACTION_ROLES or node.get("role") != ACTION_ROLES[action]:
            raise PlanError("计划含未授权动作或角色不匹配")
        deps = list(node.get("depends_on") or [])
        if any(dep not in results for dep in deps):
            raise PlanError("节点依赖不存在或未按拓扑顺序声明")
        if any(results[dep]["status"] != "completed" for dep in deps):
            results[node_id] = {"node_id": node_id, "action": action, "role": node["role"], "status": "skipped", "reason": "前置节点未完成"}
            continue
        try:
            output = registry[action](**dict(node.get("inputs") or {}))
            failed = str((output or {}).get("status") or "").lower() in {"failed", "error"}
            results[node_id] = {"node_id": node_id, "action": action, "role": node["role"], "status": "failed" if failed else "completed", "output": output}
        except Exception as exc:
            results[node_id] = {"node_id": node_id, "action": action, "role": node["role"], "status": "failed", "error": str(exc)}
    values = list(results.values())
    return {"objective": plan.get("objective"), "nodes": values,
            "stop_reason": "存在失败或跳过节点" if any(item["status"] != "completed" for item in values) else "全部节点完成"}
