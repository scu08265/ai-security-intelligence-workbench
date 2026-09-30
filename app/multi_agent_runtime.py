"""Independent Agent instances connected by an explicit message bus.

Each agent owns its own inbox, local state and emitted messages.  No agent
reaches into another agent's private state or global scratchpad.  The scheduler
is the only component allowed to interpret role handoffs and request bounded
replanning.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from . import storage


MAX_REPLANNING_ROUNDS = 2
ACTION_FALLBACKS: dict[str, tuple[str, ...]] = {
    "collect_registered_source": ("collect_registered_source_retry", "read_cached_snapshot"),
    "answer_from_evidence": ("request_clarification",),
}


@dataclass(frozen=True)
class AgentMessage:
    id: str
    sender: str
    recipient: str
    kind: str
    payload: dict[str, Any]
    at: str


@dataclass
class AgentState:
    agent_id: str
    role: str
    inbox: list[AgentMessage] = field(default_factory=list)
    sent: list[AgentMessage] = field(default_factory=list)
    local: dict[str, Any] = field(default_factory=dict)


class AgentBus:
    """Immutable message log with per-agent delivery."""

    def __init__(self) -> None:
        self.log: list[AgentMessage] = []
        self.mailboxes: dict[str, list[AgentMessage]] = defaultdict(list)

    def publish(
        self, sender: str, recipient: str, kind: str, payload: dict[str, Any]
    ) -> AgentMessage:
        message = AgentMessage(
            id=storage.new_id("msg"),
            sender=sender,
            recipient=recipient,
            kind=kind,
            payload=dict(payload or {}),
            at=storage.utcnow(),
        )
        self.log.append(message)
        self.mailboxes[recipient].append(message)
        return message

    def receive(self, recipient: str) -> list[AgentMessage]:
        return list(self.mailboxes.get(recipient, []))


class Agent:
    """Base agent with private state and explicit message handling."""

    def __init__(self, agent_id: str, role: str) -> None:
        self.state = AgentState(agent_id=agent_id, role=role)

    @property
    def agent_id(self) -> str:
        return self.state.agent_id

    def send(self, bus: AgentBus, recipient: str, kind: str, payload: dict[str, Any]) -> AgentMessage:
        message = bus.publish(self.agent_id, recipient, kind, payload)
        self.state.sent.append(message)
        return message

    def receive(self, bus: AgentBus) -> None:
        for message in bus.receive(self.agent_id):
            self.state.inbox.append(message)


class PlannerAgent(Agent):
    def plan(self, bus: AgentBus, objective: str, allowed_actions: list[str]) -> dict[str, Any]:
        plan = {
            "objective": objective,
            "revision": int(self.state.local.get("revision", 0)),
            "nodes": [
                {
                    "id": f"node-{index + 1}",
                    "action": action,
                    "params": {},
                    "success_criteria": ["result must not be failed"],
                }
                for index, action in enumerate(allowed_actions)
            ],
        }
        self.state.local["last_plan"] = plan
        self.send(bus, "scheduler", "plan_proposed", plan)
        return plan


class WorkerAgent(Agent):
    def execute(
        self,
        bus: AgentBus,
        node: dict[str, Any],
        registry: dict[str, Callable[..., dict[str, Any]]],
    ) -> dict[str, Any]:
        action = str(node.get("action") or "")
        tool = registry.get(action)
        if tool is None:
            result = {"status": "failed", "error": f"未登记工具：{action}"}
        else:
            try:
                result = tool(**(dict(node.get("params") or {})))
            except Exception as exc:  # noqa: BLE001 - audit boundary records it
                result = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        result = dict(result)
        result["node_id"] = node.get("id")
        result["action"] = action
        self.send(bus, "auditor", "execution_result", result)
        return result


class AuditorAgent(Agent):
    def review(
        self, bus: AgentBus, node: dict[str, Any], result: dict[str, Any]
    ) -> dict[str, Any]:
        status = str(result.get("status") or "").casefold()
        conflicts = bool(result.get("conflicts"))
        has_evidence = bool(
            result.get("evidence_ids")
            or result.get("snapshot_hash")
            or result.get("tool_calls")
            or status == "ok"
        )
        if conflicts:
            decision = {
                "verdict": "conflict_preserved",
                "reason": "不同来源或计划之间存在冲突，不静默合并，等待证据审核",
                "node_id": node.get("id"),
            }
        elif status == "ok" and has_evidence:
            decision = {
                "verdict": "accepted",
                "reason": "工具执行成功且包含可核验结果",
                "node_id": node.get("id"),
            }
        else:
            decision = {
                "verdict": "rejected",
                "reason": result.get("error") or "结果缺少状态或可核验证据",
                "node_id": node.get("id"),
            }
        self.state.local.setdefault("decisions", []).append(decision)
        self.send(bus, "scheduler", "audit_decision", decision)
        return decision


class ReplannerAgent(Agent):
    def revise(
        self,
        bus: AgentBus,
        node: dict[str, Any],
        decision: dict[str, Any],
        registry: dict[str, Callable[..., dict[str, Any]]],
    ) -> dict[str, Any]:
        action = str(node.get("action") or "")
        fallback = ACTION_FALLBACKS.get(action)
        revised = dict(node)
        if decision.get("verdict") == "conflict_preserved":
            revised["success_criteria"] = ["conflicts must remain visible"]
            reason = "保留冲突并继续"
        elif fallback and any(item for item in fallback if item in registry):
            revised["action"] = next(item for item in fallback if item in registry)
            reason = f"{action} 被驳回，切换为 {revised['action']}"
        else:
            revised["params"] = {
                **(revised.get("params") or {}),
                "retry": int((revised.get("params") or {}).get("retry", 0)) + 1,
            }
            reason = "在工具参数边界内重试"
        revision = {
            "node": revised,
            "reason": reason,
            "previous_decision": decision.get("verdict"),
        }
        self.state.local.setdefault("revisions", []).append(revision)
        self.send(bus, "scheduler", "plan_revision", revision)
        return revision


class SchedulerAgent(Agent):
    def run(
        self,
        bus: AgentBus,
        objective: str,
        allowed_actions: list[str],
        registry: dict[str, Callable[..., dict[str, Any]]],
    ) -> dict[str, Any]:
        planner = PlannerAgent("planner", "planner")
        worker = WorkerAgent("worker", "tool_executor")
        auditor = AuditorAgent("auditor", "evidence_auditor")
        replanner = ReplannerAgent("replanner", "replanner")
        plan = planner.plan(bus, objective, allowed_actions)
        trace: list[dict[str, Any]] = []
        accepted: list[str] = []
        rejected: list[str] = []
        conflicts: list[str] = []

        for round_index in range(MAX_REPLANNING_ROUNDS + 1):
            pending = False
            for node in plan.get("nodes") or []:
                if node.get("id") in accepted or node.get("id") in conflicts:
                    continue
                result = worker.execute(bus, node, registry)
                decision = auditor.review(bus, node, result)
                trace.append({
                    "round": round_index,
                    "node_id": node.get("id"),
                    "action": result.get("action"),
                    "status": result.get("status"),
                    "audit": decision.get("verdict"),
                    "reason": decision.get("reason"),
                })
                if decision.get("verdict") == "accepted":
                    rejected = [item for item in rejected if item != node.get("id")]
                    conflicts = [item for item in conflicts if item != node.get("id")]
                    accepted.append(str(node.get("id")))
                elif decision.get("verdict") == "conflict_preserved":
                    rejected = [item for item in rejected if item != node.get("id")]
                    accepted = [item for item in accepted if item != node.get("id")]
                    conflicts.append(str(node.get("id")))
                else:
                    accepted = [item for item in accepted if item != node.get("id")]
                    conflicts = [item for item in conflicts if item != node.get("id")]
                    rejected.append(str(node.get("id")))
                    revision = replanner.revise(bus, node, decision, registry)
                    node.update(revision["node"])
                    pending = True
            if not pending:
                break

        plan["status"] = "completed" if not rejected else "needs_human_review"
        plan["accepted_nodes"] = accepted
        plan["conflict_nodes"] = conflicts
        plan["rejected_nodes"] = rejected
        plan["trace"] = trace
        self.state.local["last_run"] = plan
        return {
            "plan": plan,
            "agents": {
                "planner": planner.state.local,
                "auditor": auditor.state.local,
                "replanner": replanner.state.local,
            },
            "messages": [message.__dict__ for message in bus.log],
            "runtime": (
                "Agent 是同一运行体内的独立实例，通过显式消息总线通信；"
                "每个实例只拥有自己的收件箱和私有状态。"
            ),
        }


def run_multi_agent_task(
    objective: str,
    allowed_actions: list[str],
    registry: dict[str, Callable[..., dict[str, Any]]],
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    bus = AgentBus()
    scheduler = SchedulerAgent("scheduler", "scheduler")
    result = scheduler.run(bus, objective, allowed_actions, registry)
    identifier = run_id or storage.new_id("run")
    storage.save_run({
        "id": identifier,
        "kind": "multi_agent",
        "status": "completed",
        "started_at": storage.utcnow(),
        "finished_at": storage.utcnow(),
        "summary": f"多 Agent 任务：{objective[:60]}",
        "detail": result,
    })
    result["run_id"] = identifier
    return result
