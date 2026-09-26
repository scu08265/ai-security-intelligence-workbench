"""Persistent, reviewable task plans expressed as a bounded DAG.

The module records observable work only: objectives, acceptance criteria,
allowed tool candidates, budgets, checkpoints, dependencies and handoffs.  It
does not store prompts, model scratchpads, credentials, or hidden reasoning.
Completed nodes and settled handoffs are immutable at the SQLite layer.
"""

from __future__ import annotations

import json
import re
from typing import Any

from . import storage


TASK_STATUSES = {"planned", "running", "blocked", "completed", "cancelled"}
NODE_STATUSES = {"planned", "running", "blocked", "completed", "skipped"}
CHECKPOINT_STATUSES = {"recorded", "passed", "failed"}
HANDOFF_STATUSES = {"proposed", "accepted", "rejected"}
SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _strings(values: list[str] | None, *, field: str, maximum: int = 500, count: int = 50) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list) or len(values) > count:
        raise ValueError(f"{field}必须是至多{count}项的列表")
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = str(raw).strip()
        if not value:
            continue
        if len(value) > maximum:
            raise ValueError(f"{field}单项不能超过{maximum}字符")
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _tools(value: list[Any] | None) -> list[Any]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 50:
        raise ValueError("tool_candidates必须是至多50项的列表")
    clean: list[Any] = []
    for item in value:
        if isinstance(item, str):
            name = item.strip()
            if not name or len(name) > 160:
                raise ValueError("tool_candidates名称无效")
            clean.append(name)
        elif isinstance(item, dict):
            encoded = _json(item)
            if len(encoded) > 2000:
                raise ValueError("tool_candidates单项不能超过2000字符")
            clean.append(item)
        else:
            raise ValueError("tool_candidates只能包含名称或对象")
    return clean


def _budget(value: dict[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > 30:
        raise ValueError("budget必须是至多30项的对象")
    encoded = _json(value)
    if len(encoded) > 4000:
        raise ValueError("budget不能超过4000字符")
    return value


def _identifier(value: str | None, prefix: str) -> str:
    identifier = value or storage.new_id(prefix)
    if not SAFE_ID.fullmatch(identifier):
        raise ValueError("id包含非法字符")
    return identifier


def _decode_task(row) -> dict[str, Any]:  # noqa: ANN001
    item = dict(row)
    for field in ("success_criteria", "tool_candidates", "budget", "constraints"):
        item[field] = json.loads(item[field])
    item["immutable_when_completed"] = item["status"] in {"completed", "cancelled"}
    return item


def _decode_plan(row) -> dict[str, Any]:  # noqa: ANN001
    item = dict(row)
    item["immutable"] = True
    return item


def _decode_node(row, dependencies: list[str] | None = None) -> dict[str, Any]:  # noqa: ANN001
    item = dict(row)
    for field in ("success_criteria", "tool_candidates", "budget", "result"):
        item[field] = json.loads(item[field])
    item["depends_on"] = dependencies or []
    item["immutable"] = item["status"] in {"completed", "skipped"}
    return item


def _decode_checkpoint(row) -> dict[str, Any]:  # noqa: ANN001
    item = dict(row)
    item["evidence_refs"] = json.loads(item["evidence_refs"])
    item["immutable"] = True
    return item


def _decode_handoff(row) -> dict[str, Any]:  # noqa: ANN001
    item = dict(row)
    item["payload"] = json.loads(item["payload"])
    item["immutable"] = item["status"] in {"accepted", "rejected"}
    return item


def create_task(
    objective: str, *, task_id: str | None = None,
    success_criteria: list[str] | None = None,
    tool_candidates: list[Any] | None = None,
    budget: dict[str, Any] | None = None,
    constraints: list[str] | None = None,
) -> dict[str, Any]:
    objective = objective.strip()
    if not objective or len(objective) > 2000:
        raise ValueError("task objective不能为空且不能超过2000字符")
    identifier = _identifier(task_id, "task")
    criteria = _strings(success_criteria, field="success_criteria")
    tools = _tools(tool_candidates)
    limits = _budget(budget)
    rules = _strings(constraints, field="constraints")
    now = storage.utcnow()
    with storage.connect() as conn:
        try:
            conn.execute(
                """INSERT INTO agent_tasks
                   (id, objective, status, success_criteria, tool_candidates, budget,
                    constraints, created_at, updated_at)
                   VALUES (?, ?, 'planned', ?, ?, ?, ?, ?, ?)""",
                (identifier, objective, _json(criteria), _json(tools), _json(limits),
                 _json(rules), now, now),
            )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise ValueError("task_id已经存在") from exc
            raise
        row = conn.execute("SELECT * FROM agent_tasks WHERE id=?", (identifier,)).fetchone()
    return _decode_task(row)


def _get_task(conn, task_id: str):  # noqa: ANN001
    row = conn.execute("SELECT * FROM agent_tasks WHERE id=?", (task_id,)).fetchone()
    if not row:
        raise KeyError("task不存在")
    return row


def create_plan(task_id: str, title: str, *, summary: str = "", plan_id: str | None = None) -> dict[str, Any]:
    title, summary = title.strip(), summary.strip()
    if not title or len(title) > 500 or len(summary) > 4000:
        raise ValueError("plan标题或摘要长度无效")
    identifier = _identifier(plan_id, "plan")
    now = storage.utcnow()
    with storage.connect() as conn:
        _get_task(conn, task_id)
        revision = int(conn.execute(
            "SELECT COALESCE(MAX(revision), 0) + 1 AS next_revision FROM agent_task_plans WHERE task_id=?",
            (task_id,),
        ).fetchone()["next_revision"])
        try:
            conn.execute(
                "INSERT INTO agent_task_plans (id, task_id, revision, title, summary, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (identifier, task_id, revision, title, summary, now),
            )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise ValueError("plan_id已经存在") from exc
            raise
        row = conn.execute("SELECT * FROM agent_task_plans WHERE id=?", (identifier,)).fetchone()
    return _decode_plan(row)


def _validate_dependencies(conn, task_id: str, node_id: str, dependencies: list[str]) -> None:  # noqa: ANN001
    for dependency in dependencies:
        if dependency == node_id:
            raise ValueError("节点不能依赖自身")
        row = conn.execute("SELECT task_id FROM agent_task_nodes WHERE id=?", (dependency,)).fetchone()
        if not row:
            raise ValueError(f"依赖节点不存在：{dependency}")
        if row["task_id"] != task_id:
            raise ValueError("依赖节点必须属于同一task")
        # Adding node -> dependency is invalid if dependency can already reach node.
        frontier = [dependency]
        seen: set[str] = set()
        while frontier:
            current = frontier.pop()
            if current == node_id:
                raise ValueError("依赖关系会形成环")
            if current in seen:
                continue
            seen.add(current)
            rows = conn.execute(
                "SELECT depends_on_id FROM agent_task_node_dependencies WHERE node_id=?", (current,),
            ).fetchall()
            frontier.extend(str(item["depends_on_id"]) for item in rows)


def create_node(
    task_id: str, plan_id: str, title: str, *, node_id: str | None = None,
    depends_on: list[str] | None = None, success_criteria: list[str] | None = None,
    tool_candidates: list[Any] | None = None, budget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    title = title.strip()
    if not title or len(title) > 500:
        raise ValueError("node标题不能为空且不能超过500字符")
    identifier = _identifier(node_id, "node")
    dependencies = _strings(depends_on, field="depends_on", maximum=160, count=100)
    criteria, tools, limits = _strings(success_criteria, field="success_criteria"), _tools(tool_candidates), _budget(budget)
    now = storage.utcnow()
    with storage.connect() as conn:
        _get_task(conn, task_id)
        plan = conn.execute("SELECT task_id FROM agent_task_plans WHERE id=?", (plan_id,)).fetchone()
        if not plan:
            raise ValueError("plan不存在")
        if plan["task_id"] != task_id:
            raise ValueError("plan必须属于同一task")
        _validate_dependencies(conn, task_id, identifier, dependencies)
        try:
            conn.execute(
                """INSERT INTO agent_task_nodes
                   (id, task_id, plan_id, title, status, success_criteria, tool_candidates,
                    budget, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 'planned', ?, ?, ?, ?, ?)""",
                (identifier, task_id, plan_id, title, _json(criteria), _json(tools), _json(limits), now, now),
            )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise ValueError("node_id已经存在") from exc
            raise
        for dependency in dependencies:
            conn.execute(
                "INSERT INTO agent_task_node_dependencies (node_id, depends_on_id) VALUES (?, ?)",
                (identifier, dependency),
            )
        row = conn.execute("SELECT * FROM agent_task_nodes WHERE id=?", (identifier,)).fetchone()
    return _decode_node(row, dependencies)


def add_checkpoint(
    task_id: str, node_id: str, label: str, *, status: str = "recorded",
    evidence_refs: list[str] | None = None, note: str = "",
) -> dict[str, Any]:
    label, note = label.strip(), note.strip()
    if not label or len(label) > 500 or len(note) > 4000:
        raise ValueError("checkpoint标签或说明长度无效")
    if status not in CHECKPOINT_STATUSES:
        raise ValueError("checkpoint状态无效")
    evidence = _strings(evidence_refs, field="evidence_refs", maximum=500, count=100)
    with storage.connect() as conn:
        node = conn.execute("SELECT task_id FROM agent_task_nodes WHERE id=?", (node_id,)).fetchone()
        if not node or node["task_id"] != task_id:
            raise KeyError("task node不存在")
        ordinal = int(conn.execute(
            "SELECT COALESCE(MAX(ordinal), 0) + 1 AS next_ordinal FROM agent_task_checkpoints WHERE node_id=?",
            (node_id,),
        ).fetchone()["next_ordinal"])
        identifier = storage.new_id("checkpoint")
        now = storage.utcnow()
        conn.execute(
            """INSERT INTO agent_task_checkpoints
               (id, node_id, ordinal, label, status, evidence_refs, note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (identifier, node_id, ordinal, label, status, _json(evidence), note, now),
        )
        row = conn.execute("SELECT * FROM agent_task_checkpoints WHERE id=?", (identifier,)).fetchone()
    return _decode_checkpoint(row)


def set_node_status(
    task_id: str, node_id: str, status: str, *, checkpoint_note: str = "", result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if status not in NODE_STATUSES:
        raise ValueError("node状态无效")
    if len(checkpoint_note.strip()) > 4000:
        raise ValueError("checkpoint_note不能超过4000字符")
    outcome = result or {}
    if not isinstance(outcome, dict) or len(_json(outcome)) > 12000:
        raise ValueError("result必须是至多12000字符的对象")
    now = storage.utcnow()
    with storage.connect() as conn:
        row = conn.execute("SELECT * FROM agent_task_nodes WHERE id=?", (node_id,)).fetchone()
        if not row or row["task_id"] != task_id:
            raise KeyError("task node不存在")
        if row["status"] in {"completed", "skipped"}:
            raise ValueError("已完成节点不可修改")
        if status == "completed":
            remaining = conn.execute(
                """SELECT n.id FROM agent_task_node_dependencies d
                   JOIN agent_task_nodes n ON n.id=d.depends_on_id
                   WHERE d.node_id=? AND n.status NOT IN ('completed', 'skipped')""",
                (node_id,),
            ).fetchall()
            if remaining:
                raise ValueError("依赖节点尚未完成，不能完成当前节点")
        conn.execute(
            """UPDATE agent_task_nodes
               SET status=?, checkpoint_note=?, result=?, updated_at=?,
                   completed_at=CASE WHEN ? IN ('completed', 'skipped') THEN ? ELSE NULL END
               WHERE id=?""",
            (status, checkpoint_note.strip(), _json(outcome), now, status, now, node_id),
        )
        updated = conn.execute("SELECT * FROM agent_task_nodes WHERE id=?", (node_id,)).fetchone()
        dependencies = [item["depends_on_id"] for item in conn.execute(
            "SELECT depends_on_id FROM agent_task_node_dependencies WHERE node_id=? ORDER BY depends_on_id", (node_id,),
        ).fetchall()]
    return _decode_node(updated, dependencies)


def set_task_status(task_id: str, status: str) -> dict[str, Any]:
    if status not in TASK_STATUSES:
        raise ValueError("task状态无效")
    now = storage.utcnow()
    with storage.connect() as conn:
        row = _get_task(conn, task_id)
        if row["status"] in {"completed", "cancelled"}:
            raise ValueError("已结束task不可修改")
        if status == "completed":
            pending = conn.execute(
                "SELECT id FROM agent_task_nodes WHERE task_id=? AND status NOT IN ('completed', 'skipped')",
                (task_id,),
            ).fetchall()
            if pending:
                raise ValueError("仍有未完成节点，不能完成task")
        conn.execute(
            """UPDATE agent_tasks SET status=?, updated_at=?,
               completed_at=CASE WHEN ? IN ('completed', 'cancelled') THEN ? ELSE NULL END WHERE id=?""",
            (status, now, status, now, task_id),
        )
        updated = conn.execute("SELECT * FROM agent_tasks WHERE id=?", (task_id,)).fetchone()
    return _decode_task(updated)


def create_handoff(
    task_id: str, from_node_id: str, to_node_id: str, *, payload: dict[str, Any] | None = None,
    handoff_id: str | None = None,
) -> dict[str, Any]:
    if from_node_id == to_node_id:
        raise ValueError("交接两端不能是同一节点")
    details = payload or {}
    if not isinstance(details, dict) or len(_json(details)) > 12000:
        raise ValueError("handoff payload必须是至多12000字符的对象")
    identifier, now = _identifier(handoff_id, "handoff"), storage.utcnow()
    with storage.connect() as conn:
        _get_task(conn, task_id)
        rows = conn.execute(
            "SELECT id, task_id FROM agent_task_nodes WHERE id IN (?, ?)", (from_node_id, to_node_id),
        ).fetchall()
        if len(rows) != 2 or any(row["task_id"] != task_id for row in rows):
            raise ValueError("交接节点必须属于同一task")
        try:
            conn.execute(
                """INSERT INTO agent_task_handoffs
                   (id, task_id, from_node_id, to_node_id, status, payload, created_at)
                   VALUES (?, ?, ?, ?, 'proposed', ?, ?)""",
                (identifier, task_id, from_node_id, to_node_id, _json(details), now),
            )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise ValueError("handoff_id已经存在") from exc
            raise
        row = conn.execute("SELECT * FROM agent_task_handoffs WHERE id=?", (identifier,)).fetchone()
    return _decode_handoff(row)


def decide_handoff(task_id: str, handoff_id: str, decision: str, *, decision_note: str = "") -> dict[str, Any]:
    if decision not in {"accepted", "rejected"}:
        raise ValueError("handoff decision只能为accepted或rejected")
    note = decision_note.strip()
    if len(note) > 4000:
        raise ValueError("decision_note不能超过4000字符")
    now = storage.utcnow()
    with storage.connect() as conn:
        row = conn.execute("SELECT * FROM agent_task_handoffs WHERE id=?", (handoff_id,)).fetchone()
        if not row or row["task_id"] != task_id:
            raise KeyError("handoff不存在")
        if row["status"] != "proposed":
            raise ValueError("handoff已经决定")
        conn.execute(
            "UPDATE agent_task_handoffs SET status=?, decision_note=?, decided_at=? WHERE id=?",
            (decision, note, now, handoff_id),
        )
        updated = conn.execute("SELECT * FROM agent_task_handoffs WHERE id=?", (handoff_id,)).fetchone()
    return _decode_handoff(updated)


def get_task(task_id: str) -> dict[str, Any] | None:
    with storage.connect() as conn:
        task = conn.execute("SELECT * FROM agent_tasks WHERE id=?", (task_id,)).fetchone()
        if not task:
            return None
        plans = conn.execute("SELECT * FROM agent_task_plans WHERE task_id=? ORDER BY revision", (task_id,)).fetchall()
        # SQLite rowid preserves insertion order when multiple nodes share the
        # same second-resolution timestamp; it makes replay output stable.
        nodes = conn.execute("SELECT * FROM agent_task_nodes WHERE task_id=? ORDER BY created_at, rowid", (task_id,)).fetchall()
        dependencies = conn.execute(
            """SELECT d.node_id, d.depends_on_id FROM agent_task_node_dependencies d
               JOIN agent_task_nodes n ON n.id=d.node_id WHERE n.task_id=? ORDER BY d.depends_on_id""",
            (task_id,),
        ).fetchall()
        checkpoints = conn.execute(
            """SELECT c.* FROM agent_task_checkpoints c JOIN agent_task_nodes n ON n.id=c.node_id
               WHERE n.task_id=? ORDER BY c.node_id, c.ordinal""", (task_id,),
        ).fetchall()
        handoffs = conn.execute("SELECT * FROM agent_task_handoffs WHERE task_id=? ORDER BY created_at, id", (task_id,)).fetchall()
    by_node: dict[str, list[str]] = {}
    for item in dependencies:
        by_node.setdefault(item["node_id"], []).append(item["depends_on_id"])
    checkpoints_by_node: dict[str, list[dict[str, Any]]] = {}
    for item in checkpoints:
        checkpoints_by_node.setdefault(item["node_id"], []).append(_decode_checkpoint(item))
    decoded_nodes = []
    for item in nodes:
        node = _decode_node(item, by_node.get(item["id"], []))
        node["checkpoints"] = checkpoints_by_node.get(item["id"], [])
        decoded_nodes.append(node)
    result = _decode_task(task)
    result.update({
        "plans": [_decode_plan(item) for item in plans],
        "nodes": decoded_nodes,
        "handoffs": [_decode_handoff(item) for item in handoffs],
        "stores_hidden_reasoning": False,
    })
    return result


def list_tasks(*, limit: int = 100) -> list[dict[str, Any]]:
    with storage.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_tasks ORDER BY updated_at DESC, id LIMIT ?", (max(1, min(limit, 500)),),
        ).fetchall()
    return [_decode_task(row) for row in rows]
