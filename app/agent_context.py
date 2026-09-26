"""Persistent, auditable Agent context without hidden chain-of-thought.

Each turn writes one immutable snapshot containing only explicit task state,
resolved identifiers, and evidence versions.  There is intentionally no
field for private reasoning, scratchpads, prompts, credentials, or model
provider payloads.
"""

from __future__ import annotations

import json
import re
from typing import Any

from . import storage

SCHEMA_VERSION = "agent-context-1.0"
SAFE_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
REFERENCE_KINDS = {"event", "asset", "document", "chunk", "source_version"}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _dedupe_strings(values: list[str], *, maximum: int, field: str) -> list[str]:
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


def _decode_snapshot(row) -> dict[str, Any]:  # noqa: ANN001
    result = dict(row)
    for field in ("inherited_constraints", "resolved_references", "chunk_ids", "source_versions"):
        result[field] = json.loads(result[field])
    result["focus"] = {
        "event_id": result.pop("focus_event_id"),
        "asset_id": result.pop("focus_asset_id"),
        "document_id": result.pop("focus_document_id"),
    }
    result["immutable"] = True
    return result


def create_thread(
    objective: str, *, thread_id: str | None = None,
    base_constraints: list[str] | None = None,
) -> dict[str, Any]:
    objective = objective.strip()
    if not objective or len(objective) > 2000:
        raise ValueError("task objective不能为空且不能超过2000字符")
    identifier = thread_id or storage.new_id("thread")
    if not SAFE_ID.fullmatch(identifier):
        raise ValueError("thread_id包含非法字符")
    constraints = _dedupe_strings(
        base_constraints or [], maximum=500, field="constraint",
    )
    created_at = storage.utcnow()
    with storage.connect() as conn:
        try:
            conn.execute(
                "INSERT INTO agent_threads (id, objective, base_constraints, created_at) VALUES (?, ?, ?, ?)",
                (identifier, objective, _json(constraints), created_at),
            )
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc):
                raise ValueError("thread_id已经存在") from exc
            raise
    return {
        "id": identifier, "objective": objective,
        "base_constraints": constraints, "created_at": created_at,
    }


def _assert_reference(conn, kind: str, identifier: str) -> None:  # noqa: ANN001
    queries = {
        "event": "SELECT 1 FROM events WHERE id=?",
        "asset": "SELECT 1 FROM assets WHERE id=?",
        "document": "SELECT 1 FROM rag_documents WHERE id=?",
        "chunk": "SELECT 1 FROM rag_chunks WHERE id=?",
        "source_version": "SELECT 1 FROM rag_document_versions WHERE id=?",
    }
    if kind not in queries:
        raise ValueError(f"不支持的引用类型：{kind}")
    if not conn.execute(queries[kind], (identifier,)).fetchone():
        raise ValueError(f"无法解析{kind}引用：{identifier}")


def _normalize_references(conn, references: list[dict[str, Any]]) -> list[dict[str, Any]]:  # noqa: ANN001
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in references:
        mention = str(item.get("mention") or "").strip()
        kind = str(item.get("kind") or "").strip()
        resolved_id = str(item.get("resolved_id") or "").strip()
        method = str(item.get("method") or "explicit").strip()
        if not mention or len(mention) > 500:
            raise ValueError("resolved reference的mention不能为空且不能超过500字符")
        if kind not in REFERENCE_KINDS:
            raise ValueError(f"不支持的引用类型：{kind}")
        if not resolved_id or len(resolved_id) > 200:
            raise ValueError("resolved reference的resolved_id无效")
        if len(method) > 80:
            raise ValueError("resolved reference的method不能超过80字符")
        _assert_reference(conn, kind, resolved_id)
        key = (mention, kind, resolved_id)
        if key not in seen:
            seen.add(key)
            result.append({
                "mention": mention, "kind": kind,
                "resolved_id": resolved_id, "method": method,
            })
    return result


def _canonical_versions(conn, version_ids: list[str], chunk_ids: list[str]) -> list[dict[str, Any]]:  # noqa: ANN001
    requested = _dedupe_strings(version_ids, maximum=160, field="source_version_id")
    for chunk_id in chunk_ids:
        row = conn.execute("SELECT version_id FROM rag_chunks WHERE id=?", (chunk_id,)).fetchone()
        if not row:
            raise ValueError(f"无法解析chunk引用：{chunk_id}")
        if row["version_id"] not in requested:
            requested.append(row["version_id"])
    result: list[dict[str, Any]] = []
    for version_id in requested:
        row = conn.execute(
            """SELECT v.id AS version_id, v.document_id, d.source_id,
                      v.snapshot_hash, v.content_hash, v.extracted_hash,
                      v.parser_version, v.created_at
               FROM rag_document_versions v JOIN rag_documents d ON d.id=v.document_id
               WHERE v.id=?""",
            (version_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"无法解析source version：{version_id}")
        result.append(dict(row))
    return result


def append_turn(
    thread_id: str, *, visible_user_input: str = "",
    visible_assistant_output: str = "", objective: str | None = None,
    focus_event_id: str | None = None, focus_asset_id: str | None = None,
    focus_document_id: str | None = None, inherit_focus: bool = True,
    constraints: list[str] | None = None,
    resolved_references: list[dict[str, Any]] | None = None,
    chunk_ids: list[str] | None = None,
    source_version_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Append one completed visible turn and its immutable context snapshot."""
    if len(visible_user_input) > 10000 or len(visible_assistant_output) > 30000:
        raise ValueError("可见轮次内容超过长度限制")
    created_at = storage.utcnow()
    turn_id = storage.new_id("turn")
    with storage.connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        thread = conn.execute("SELECT * FROM agent_threads WHERE id=?", (thread_id,)).fetchone()
        if not thread:
            raise KeyError("thread不存在")
        previous = conn.execute(
            """SELECT s.* FROM agent_context_snapshots s
               JOIN agent_turns t ON t.id=s.turn_id
               WHERE s.thread_id=? ORDER BY t.turn_index DESC LIMIT 1""",
            (thread_id,),
        ).fetchone()
        index_row = conn.execute(
            "SELECT COALESCE(MAX(turn_index), 0) + 1 AS next_index FROM agent_turns WHERE thread_id=?",
            (thread_id,),
        ).fetchone()
        turn_index = int(index_row["next_index"])

        previous_constraints = (
            json.loads(previous["inherited_constraints"]) if previous
            else json.loads(thread["base_constraints"])
        )
        inherited = _dedupe_strings(
            [*previous_constraints, *(constraints or [])], maximum=500, field="constraint",
        )
        effective_objective = (objective or (previous["objective"] if previous else thread["objective"])).strip()
        if not effective_objective or len(effective_objective) > 2000:
            raise ValueError("task objective不能为空且不能超过2000字符")

        previous_focus = {
            "event": previous["focus_event_id"] if previous else None,
            "asset": previous["focus_asset_id"] if previous else None,
            "document": previous["focus_document_id"] if previous else None,
        }
        effective_focus = {
            "event": focus_event_id or (previous_focus["event"] if inherit_focus else None),
            "asset": focus_asset_id or (previous_focus["asset"] if inherit_focus else None),
            "document": focus_document_id or (previous_focus["document"] if inherit_focus else None),
        }
        for kind, identifier in effective_focus.items():
            if identifier:
                _assert_reference(conn, kind, identifier)

        canonical_chunks = _dedupe_strings(chunk_ids or [], maximum=160, field="chunk_id")
        source_versions = _canonical_versions(conn, source_version_ids or [], canonical_chunks)
        references = _normalize_references(conn, resolved_references or [])
        snapshot_body = {
            "thread_id": thread_id, "turn_id": turn_id,
            "objective": effective_objective, "focus": effective_focus,
            "inherited_constraints": inherited,
            "resolved_references": references, "chunk_ids": canonical_chunks,
            "source_versions": source_versions, "schema_version": SCHEMA_VERSION,
            "created_at": created_at,
        }
        digest = storage.content_hash(_json(snapshot_body))
        snapshot_id = f"ctx-{digest[:24]}"
        conn.execute(
            """INSERT INTO agent_turns
               (id, thread_id, turn_index, visible_user_input, visible_assistant_output, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (turn_id, thread_id, turn_index, visible_user_input,
             visible_assistant_output, created_at),
        )
        conn.execute(
            """INSERT INTO agent_context_snapshots
               (id, thread_id, turn_id, objective, focus_event_id, focus_asset_id,
                focus_document_id, inherited_constraints, resolved_references,
                chunk_ids, source_versions, schema_version, content_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (snapshot_id, thread_id, turn_id, effective_objective,
             effective_focus["event"], effective_focus["asset"], effective_focus["document"],
             _json(inherited), _json(references), _json(canonical_chunks),
             _json(source_versions), SCHEMA_VERSION, digest, created_at),
        )
        row = conn.execute("SELECT * FROM agent_context_snapshots WHERE id=?", (snapshot_id,)).fetchone()
    return {
        "turn": {
            "id": turn_id, "thread_id": thread_id, "turn_index": turn_index,
            "visible_user_input": visible_user_input,
            "visible_assistant_output": visible_assistant_output,
            "created_at": created_at,
        },
        "context_snapshot": _decode_snapshot(row),
    }


def get_snapshot(snapshot_id: str) -> dict[str, Any] | None:
    with storage.connect() as conn:
        row = conn.execute(
            "SELECT * FROM agent_context_snapshots WHERE id=?", (snapshot_id,),
        ).fetchone()
    return _decode_snapshot(row) if row else None


def snapshots_for_thread(thread_id: str) -> list[dict[str, Any]]:
    with storage.connect() as conn:
        rows = conn.execute(
            """SELECT s.* FROM agent_context_snapshots s
               JOIN agent_turns t ON t.id=s.turn_id
               WHERE s.thread_id=? ORDER BY t.turn_index""",
            (thread_id,),
        ).fetchall()
    return [_decode_snapshot(row) for row in rows]


def get_thread(thread_id: str) -> dict[str, Any] | None:
    with storage.connect() as conn:
        thread = conn.execute("SELECT * FROM agent_threads WHERE id=?", (thread_id,)).fetchone()
        if not thread:
            return None
        turns = conn.execute(
            "SELECT * FROM agent_turns WHERE thread_id=? ORDER BY turn_index", (thread_id,),
        ).fetchall()
    result = dict(thread)
    result["base_constraints"] = json.loads(result["base_constraints"])
    result["turns"] = [dict(row) for row in turns]
    result["context_snapshots"] = snapshots_for_thread(thread_id)
    result["stores_hidden_reasoning"] = False
    return result
