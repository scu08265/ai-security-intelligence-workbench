"""SQLite persistence and raw-snapshot storage.

Two rules shape this module:

* An event is stored as a whole JSON document.  The relational columns beside
  it exist only for filtering, so no contract field can be lost by a schema
  that lags behind the data model.
* Every fetched payload is written to disk under its own SHA-256 before it is
  parsed, so any claim in the system can be traced back to the bytes it came
  from.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id            TEXT PRIMARY KEY,
    kind          TEXT NOT NULL DEFAULT 'vulnerability',
    status        TEXT NOT NULL,
    component     TEXT,
    ecosystem     TEXT,
    published_at  TEXT,
    modified_at   TEXT,
    collected_at  TEXT,
    withdrawn     INTEGER NOT NULL DEFAULT 0,
    content_hash  TEXT,
    ai_included   INTEGER NOT NULL DEFAULT 0,
    doc           TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_status    ON events(status);
CREATE INDEX IF NOT EXISTS idx_events_kind      ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_component ON events(component);
CREATE INDEX IF NOT EXISTS idx_events_published ON events(published_at);
CREATE INDEX IF NOT EXISTS idx_events_hash      ON events(content_hash);

CREATE TABLE IF NOT EXISTS event_aliases (
    alias    TEXT NOT NULL,
    event_id TEXT NOT NULL,
    PRIMARY KEY (alias, event_id)
);
CREATE INDEX IF NOT EXISTS idx_alias_event ON event_aliases(event_id);

CREATE TABLE IF NOT EXISTS source_state (
    id           TEXT PRIMARY KEY,
    status       TEXT,
    last_run     TEXT,
    last_success TEXT,
    last_error   TEXT,
    events_count INTEGER NOT NULL DEFAULT 0,
    cursor       TEXT,
    last_hash    TEXT
);

CREATE TABLE IF NOT EXISTS assets (
    id           TEXT PRIMARY KEY,
    name         TEXT,
    component    TEXT,
    ecosystem    TEXT,
    version      TEXT,
    is_demo      INTEGER NOT NULL DEFAULT 0,
    authorized   INTEGER NOT NULL DEFAULT 0,
    updated_at   TEXT,
    doc          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assessments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   TEXT NOT NULL,
    asset_id   TEXT NOT NULL,
    status     TEXT NOT NULL,
    priority   TEXT,
    created_at TEXT NOT NULL,
    doc        TEXT NOT NULL,
    UNIQUE(event_id, asset_id)
);
CREATE INDEX IF NOT EXISTS idx_assess_event ON assessments(event_id);
CREATE INDEX IF NOT EXISTS idx_assess_asset ON assessments(asset_id);

CREATE TABLE IF NOT EXISTS runs (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    status      TEXT NOT NULL,
    started_at  TEXT,
    finished_at TEXT,
    summary     TEXT,
    detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_started ON runs(started_at DESC);

CREATE TABLE IF NOT EXISTS duplicate_candidates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id     TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    reason       TEXT NOT NULL,
    score        REAL,
    created_at   TEXT NOT NULL,
    UNIQUE(event_id, candidate_id)
);

-- Immutable full-text corpus used by the RAG layer.  `documents` is the
-- stable logical identity; a changed payload creates a new version instead
-- of rewriting chunks that may already be cited by an answer.
CREATE TABLE IF NOT EXISTS rag_documents (
    id                 TEXT PRIMARY KEY,
    source_id          TEXT NOT NULL,
    document_key       TEXT NOT NULL,
    title              TEXT,
    canonical_url      TEXT,
    current_version_id TEXT,
    created_at         TEXT NOT NULL,
    updated_at         TEXT NOT NULL,
    metadata           TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, document_key)
);
CREATE INDEX IF NOT EXISTS idx_rag_documents_source ON rag_documents(source_id);

CREATE TABLE IF NOT EXISTS rag_document_versions (
    id                 TEXT PRIMARY KEY,
    document_id        TEXT NOT NULL,
    content_hash       TEXT NOT NULL,
    extracted_hash     TEXT NOT NULL,
    media_type         TEXT NOT NULL,
    parser_version     TEXT NOT NULL,
    snapshot_hash      TEXT,
    original_path      TEXT,
    created_at         TEXT NOT NULL,
    extracted_text     TEXT NOT NULL,
    provenance         TEXT NOT NULL DEFAULT '{}',
    UNIQUE(document_id, content_hash, parser_version),
    FOREIGN KEY(document_id) REFERENCES rag_documents(id)
);
CREATE INDEX IF NOT EXISTS idx_rag_versions_document ON rag_document_versions(document_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rag_versions_hash ON rag_document_versions(content_hash);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id             TEXT PRIMARY KEY,
    document_id    TEXT NOT NULL,
    version_id     TEXT NOT NULL,
    ordinal        INTEGER NOT NULL,
    section_path   TEXT NOT NULL,
    char_start     INTEGER NOT NULL,
    char_end       INTEGER NOT NULL,
    content_hash   TEXT NOT NULL,
    text           TEXT NOT NULL,
    metadata       TEXT NOT NULL DEFAULT '{}',
    UNIQUE(version_id, ordinal),
    FOREIGN KEY(document_id) REFERENCES rag_documents(id),
    FOREIGN KEY(version_id) REFERENCES rag_document_versions(id)
);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_version ON rag_chunks(version_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_rag_chunks_document ON rag_chunks(document_id);

-- Structured Agent context.  Snapshots contain only explicit task state and
-- evidence references; model hidden reasoning has no column and is never
-- accepted by the persistence API.
CREATE TABLE IF NOT EXISTS agent_threads (
    id               TEXT PRIMARY KEY,
    objective        TEXT NOT NULL,
    base_constraints TEXT NOT NULL DEFAULT '[]',
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_turns (
    id                       TEXT PRIMARY KEY,
    thread_id                TEXT NOT NULL,
    turn_index               INTEGER NOT NULL,
    visible_user_input       TEXT NOT NULL DEFAULT '',
    visible_assistant_output TEXT NOT NULL DEFAULT '',
    created_at               TEXT NOT NULL,
    UNIQUE(thread_id, turn_index),
    FOREIGN KEY(thread_id) REFERENCES agent_threads(id)
);
CREATE INDEX IF NOT EXISTS idx_agent_turns_thread ON agent_turns(thread_id, turn_index);

CREATE TABLE IF NOT EXISTS agent_context_snapshots (
    id                    TEXT PRIMARY KEY,
    thread_id             TEXT NOT NULL,
    turn_id               TEXT NOT NULL UNIQUE,
    objective             TEXT NOT NULL,
    focus_event_id        TEXT,
    focus_asset_id        TEXT,
    focus_document_id     TEXT,
    inherited_constraints TEXT NOT NULL DEFAULT '[]',
    resolved_references   TEXT NOT NULL DEFAULT '[]',
    chunk_ids             TEXT NOT NULL DEFAULT '[]',
    source_versions       TEXT NOT NULL DEFAULT '[]',
    schema_version        TEXT NOT NULL,
    content_hash          TEXT NOT NULL,
    created_at            TEXT NOT NULL,
    FOREIGN KEY(thread_id) REFERENCES agent_threads(id),
    FOREIGN KEY(turn_id) REFERENCES agent_turns(id)
);
CREATE INDEX IF NOT EXISTS idx_context_snapshots_thread ON agent_context_snapshots(thread_id, created_at);
CREATE TRIGGER IF NOT EXISTS immutable_context_snapshot_update
BEFORE UPDATE ON agent_context_snapshots
BEGIN SELECT RAISE(ABORT, 'context snapshots are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_context_snapshot_delete
BEFORE DELETE ON agent_context_snapshots
BEGIN SELECT RAISE(ABORT, 'context snapshots are immutable'); END;

-- Explicit task-DAG records.  These are deliberately separate from chat
-- context: a task is an observable piece of work, while a context snapshot is
-- a record of what an answer was allowed to use.
CREATE TABLE IF NOT EXISTS agent_tasks (
    id               TEXT PRIMARY KEY,
    objective        TEXT NOT NULL,
    status           TEXT NOT NULL,
    success_criteria TEXT NOT NULL DEFAULT '[]',
    tool_candidates  TEXT NOT NULL DEFAULT '[]',
    budget           TEXT NOT NULL DEFAULT '{}',
    constraints      TEXT NOT NULL DEFAULT '[]',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    completed_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status, updated_at DESC);

-- Plans are append-only revisions.  Editing a plan means creating its next
-- revision, which keeps a reviewer able to reconstruct the operative plan.
CREATE TABLE IF NOT EXISTS agent_task_plans (
    id          TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL,
    revision    INTEGER NOT NULL,
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    UNIQUE(task_id, revision),
    FOREIGN KEY(task_id) REFERENCES agent_tasks(id)
);
CREATE INDEX IF NOT EXISTS idx_task_plans_task ON agent_task_plans(task_id, revision);
CREATE TRIGGER IF NOT EXISTS immutable_task_plan_update
BEFORE UPDATE ON agent_task_plans
BEGIN SELECT RAISE(ABORT, 'task plans are immutable; create a revision'); END;
CREATE TRIGGER IF NOT EXISTS immutable_task_plan_delete
BEFORE DELETE ON agent_task_plans
BEGIN SELECT RAISE(ABORT, 'task plans are immutable'); END;

CREATE TABLE IF NOT EXISTS agent_task_nodes (
    id               TEXT PRIMARY KEY,
    task_id          TEXT NOT NULL,
    plan_id          TEXT NOT NULL,
    title            TEXT NOT NULL,
    status           TEXT NOT NULL,
    success_criteria TEXT NOT NULL DEFAULT '[]',
    tool_candidates  TEXT NOT NULL DEFAULT '[]',
    budget           TEXT NOT NULL DEFAULT '{}',
    checkpoint_note  TEXT NOT NULL DEFAULT '',
    result           TEXT NOT NULL DEFAULT '{}',
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    completed_at     TEXT,
    FOREIGN KEY(task_id) REFERENCES agent_tasks(id),
    FOREIGN KEY(plan_id) REFERENCES agent_task_plans(id)
);
CREATE INDEX IF NOT EXISTS idx_task_nodes_task ON agent_task_nodes(task_id, status, created_at);
CREATE TABLE IF NOT EXISTS agent_task_node_dependencies (
    node_id        TEXT NOT NULL,
    depends_on_id  TEXT NOT NULL,
    PRIMARY KEY(node_id, depends_on_id),
    FOREIGN KEY(node_id) REFERENCES agent_task_nodes(id),
    FOREIGN KEY(depends_on_id) REFERENCES agent_task_nodes(id)
);
CREATE INDEX IF NOT EXISTS idx_task_node_deps_target ON agent_task_node_dependencies(depends_on_id);
CREATE TRIGGER IF NOT EXISTS immutable_completed_task_node_update
BEFORE UPDATE ON agent_task_nodes
WHEN OLD.status IN ('completed', 'skipped')
BEGIN SELECT RAISE(ABORT, 'completed task nodes are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_completed_task_node_delete
BEFORE DELETE ON agent_task_nodes
WHEN OLD.status IN ('completed', 'skipped')
BEGIN SELECT RAISE(ABORT, 'completed task nodes are immutable'); END;

CREATE TABLE IF NOT EXISTS agent_task_checkpoints (
    id             TEXT PRIMARY KEY,
    node_id        TEXT NOT NULL,
    ordinal        INTEGER NOT NULL,
    label          TEXT NOT NULL,
    status         TEXT NOT NULL,
    evidence_refs  TEXT NOT NULL DEFAULT '[]',
    note           TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    UNIQUE(node_id, ordinal),
    FOREIGN KEY(node_id) REFERENCES agent_task_nodes(id)
);
CREATE INDEX IF NOT EXISTS idx_task_checkpoints_node ON agent_task_checkpoints(node_id, ordinal);
CREATE TRIGGER IF NOT EXISTS immutable_task_checkpoint_update
BEFORE UPDATE ON agent_task_checkpoints
BEGIN SELECT RAISE(ABORT, 'task checkpoints are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_task_checkpoint_delete
BEFORE DELETE ON agent_task_checkpoints
BEGIN SELECT RAISE(ABORT, 'task checkpoints are immutable'); END;

CREATE TABLE IF NOT EXISTS agent_task_handoffs (
    id            TEXT PRIMARY KEY,
    task_id       TEXT NOT NULL,
    from_node_id  TEXT NOT NULL,
    to_node_id    TEXT NOT NULL,
    status        TEXT NOT NULL,
    payload       TEXT NOT NULL DEFAULT '{}',
    decision_note TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    decided_at    TEXT,
    FOREIGN KEY(task_id) REFERENCES agent_tasks(id),
    FOREIGN KEY(from_node_id) REFERENCES agent_task_nodes(id),
    FOREIGN KEY(to_node_id) REFERENCES agent_task_nodes(id)
);
CREATE INDEX IF NOT EXISTS idx_task_handoffs_task ON agent_task_handoffs(task_id, created_at);
CREATE TRIGGER IF NOT EXISTS immutable_decided_task_handoff_update
BEFORE UPDATE ON agent_task_handoffs
WHEN OLD.status IN ('accepted', 'rejected')
BEGIN SELECT RAISE(ABORT, 'decided handoffs are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_decided_task_handoff_delete
BEFORE DELETE ON agent_task_handoffs
WHEN OLD.status IN ('accepted', 'rejected')
BEGIN SELECT RAISE(ABORT, 'decided handoffs are immutable'); END;
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def content_hash(payload: bytes | str) -> str:
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    return hashlib.sha256(data).hexdigest()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a short-lived connection.  Safe across FastAPI's worker threads."""
    config.ensure_dirs()
    conn = sqlite3.connect(config.DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


# --------------------------------------------------------------------------
# snapshots
# --------------------------------------------------------------------------

def save_snapshot(source_id: str, payload: bytes | str, *, suffix: str = "json") -> str:
    """Persist raw bytes verbatim and return their SHA-256.

    Identical payloads collapse to one file, which is what makes the hash a
    usable duplicate signal later on.
    """
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    digest = content_hash(data)
    directory = config.SNAPSHOT_DIR / source_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{digest}.{suffix}"
    if not path.exists():
        path.write_bytes(data)
    return digest


def snapshot_path(source_id: str, digest: str, suffix: str = "json"):
    return config.SNAPSHOT_DIR / source_id / f"{digest}.{suffix}"


# --------------------------------------------------------------------------
# events
# --------------------------------------------------------------------------

def _event_columns(event: dict) -> dict:
    return {
        "id": str(event.get("id") or ""),
        "kind": str(event.get("kind") or "vulnerability"),
        "status": str(event.get("status") or "confirmed"),
        "component": event.get("component"),
        "ecosystem": event.get("ecosystem"),
        "published_at": event.get("published_at"),
        "modified_at": event.get("modified_at"),
        "collected_at": event.get("collected_at"),
        "withdrawn": 1 if (event.get("withdrawn") or event.get("status") == "withdrawn") else 0,
        "content_hash": event.get("content_hash"),
        "ai_included": 1 if (event.get("ai_relevance") or {}).get("included") else 0,
    }


def upsert_event(event: dict) -> tuple[str, bool]:
    """Insert or replace an event.  Returns (id, created)."""
    columns = _event_columns(event)
    if not columns["id"]:
        raise ValueError("event requires an id")
    with connect() as conn:
        existing = conn.execute("SELECT 1 FROM events WHERE id = ?", (columns["id"],)).fetchone()
        conn.execute(
            """INSERT INTO events (id, kind, status, component, ecosystem, published_at,
                                   modified_at, collected_at, withdrawn, content_hash,
                                   ai_included, doc)
               VALUES (:id, :kind, :status, :component, :ecosystem, :published_at,
                       :modified_at, :collected_at, :withdrawn, :content_hash,
                       :ai_included, :doc)
               ON CONFLICT(id) DO UPDATE SET
                   kind=excluded.kind, status=excluded.status, component=excluded.component,
                   ecosystem=excluded.ecosystem, published_at=excluded.published_at,
                   modified_at=excluded.modified_at, collected_at=excluded.collected_at,
                   withdrawn=excluded.withdrawn, content_hash=excluded.content_hash,
                   ai_included=excluded.ai_included, doc=excluded.doc""",
            {**columns, "doc": json.dumps(event, ensure_ascii=False)},
        )
        for alias in event.get("aliases") or []:
            conn.execute(
                "INSERT OR IGNORE INTO event_aliases (alias, event_id) VALUES (?, ?)",
                (str(alias), columns["id"]),
            )
    return columns["id"], existing is None


def get_event(event_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT doc FROM events WHERE id = ?", (event_id,)).fetchone()
    return json.loads(row["doc"]) if row else None


def merge_event_poc(event_id: str, records: list[dict]) -> bool:
    """Add POC reference records to an existing event without replacing it."""
    event = get_event(event_id)
    if not event:
        return False
    existing = list(event.get("poc") or [])
    keys = {
        (str(item.get("source_id") or ""), str(item.get("url") or ""))
        for item in existing if isinstance(item, dict)
    }
    changed = False
    for item in records or []:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("source_id") or ""), str(item.get("url") or ""))
        if key in keys:
            continue
        existing.append(item)
        keys.add(key)
        changed = True
    if changed:
        event["poc"] = existing
        upsert_event(event)
    return changed


def find_event_by_identifier(identifier: str) -> dict | None:
    """Resolve a CVE/GHSA id through both primary ids and aliases."""
    ident = (identifier or "").strip()
    if not ident:
        return None
    with connect() as conn:
        row = conn.execute(
            """SELECT e.doc FROM events e
               LEFT JOIN event_aliases a ON a.event_id = e.id
               WHERE e.id = ? OR a.alias = ? LIMIT 1""",
            (ident, ident),
        ).fetchone()
    return json.loads(row["doc"]) if row else None


def list_events(
    *,
    query: str = "",
    status: str = "",
    kind: str = "",
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return (events, total) applying the contract's q/status filters."""
    where: list[str] = []
    params: list[Any] = []
    if status:
        where.append("status = ?")
        params.append(status)
    if kind:
        where.append("kind = ?")
        params.append(kind)
    if query:
        like = f"%{query}%"
        where.append(
            """(id LIKE ? OR doc LIKE ? OR EXISTS (
                   SELECT 1 FROM event_aliases a
                   WHERE a.event_id = events.id AND a.alias LIKE ?))"""
        )
        params.extend([like, like, like])
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    with connect() as conn:
        total = conn.execute(f"SELECT COUNT(*) AS n FROM events {clause}", params).fetchone()["n"]
        rows = conn.execute(
            f"""SELECT doc FROM events {clause}
                ORDER BY COALESCE(published_at, collected_at) DESC, id
                LIMIT ? OFFSET ?""",
            [*params, max(1, min(limit, 500)), max(0, offset)],
        ).fetchall()
    return [json.loads(r["doc"]) for r in rows], int(total)


def all_events(limit: int = 2000) -> list[dict]:
    events, _ = list_events(limit=limit)
    return events


def count_events() -> dict[str, int]:
    with connect() as conn:
        rows = conn.execute("SELECT kind, status, COUNT(*) AS n FROM events GROUP BY kind, status").fetchall()
    counts = {"events": 0, "needs_review": 0, "withdrawn": 0, "knowledge": 0, "vulnerability": 0}
    for row in rows:
        counts["events"] += row["n"]
        counts[row["kind"]] = counts.get(row["kind"], 0) + row["n"]
        if row["status"] == "needs_review":
            counts["needs_review"] += row["n"]
        if row["status"] == "withdrawn":
            counts["withdrawn"] += row["n"]
    return counts


# --------------------------------------------------------------------------
# source state
# --------------------------------------------------------------------------

def source_state(source_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM source_state WHERE id = ?", (source_id,)).fetchone()
    if not row:
        return {"id": source_id, "status": "idle", "last_run": None, "last_success": None,
                "last_error": None, "events_count": 0, "cursor": None, "last_hash": None}
    return dict(row)


def all_source_states() -> dict[str, dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM source_state").fetchall()
    return {r["id"]: dict(r) for r in rows}


def count_events_for_source_prefix(source_prefix: str) -> int:
    """Count unique events that contain an evidence entry for one source."""
    pattern = f"{source_prefix}:%"
    with connect() as conn:
        row = conn.execute(
            """SELECT COUNT(DISTINCT e.id) AS n
               FROM events e, json_each(json_extract(e.doc, '$.sources')) s
               WHERE json_extract(s.value, '$.id') LIKE ?""",
            (pattern,),
        ).fetchone()
    return int(row["n"] or 0) if row else 0


def update_source_state(source_id: str, **fields: Any) -> None:
    allowed = {"status", "last_run", "last_success", "last_error", "events_count", "cursor", "last_hash"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO source_state (id) VALUES (?)", (source_id,))
        assignments = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE source_state SET {assignments} WHERE id = ?",
            [*updates.values(), source_id],
        )


# --------------------------------------------------------------------------
# assets
# --------------------------------------------------------------------------

def upsert_asset(asset: dict) -> dict:
    record = dict(asset)
    if not record.get("id"):
        record["id"] = new_id("asset")
    record.setdefault("updated_at", utcnow())
    columns = {
        "id": record["id"],
        "name": record.get("name"),
        "component": record.get("component"),
        "ecosystem": record.get("ecosystem"),
        "version": record.get("version"),
        "is_demo": 1 if record.get("is_demo") else 0,
        "authorized": 1 if record.get("authorized") else 0,
        "updated_at": record.get("updated_at"),
    }
    with connect() as conn:
        conn.execute(
            """INSERT INTO assets (id, name, component, ecosystem, version, is_demo,
                                   authorized, updated_at, doc)
               VALUES (:id, :name, :component, :ecosystem, :version, :is_demo,
                       :authorized, :updated_at, :doc)
               ON CONFLICT(id) DO UPDATE SET
                   name=excluded.name, component=excluded.component, ecosystem=excluded.ecosystem,
                   version=excluded.version, is_demo=excluded.is_demo,
                   authorized=excluded.authorized, updated_at=excluded.updated_at,
                   doc=excluded.doc""",
            {**columns, "doc": json.dumps(record, ensure_ascii=False)},
        )
    return record


def list_assets() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT doc FROM assets ORDER BY updated_at DESC, id").fetchall()
    return [json.loads(r["doc"]) for r in rows]


def get_asset(asset_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT doc FROM assets WHERE id = ?", (asset_id,)).fetchone()
    return json.loads(row["doc"]) if row else None


def delete_asset(asset_id: str) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        conn.execute("DELETE FROM assessments WHERE asset_id = ?", (asset_id,))
    return cursor.rowcount > 0


def count_assets() -> int:
    with connect() as conn:
        return int(conn.execute("SELECT COUNT(*) AS n FROM assets").fetchone()["n"])


# --------------------------------------------------------------------------
# assessments
# --------------------------------------------------------------------------

def save_assessment(assessment: dict) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO assessments (event_id, asset_id, status, priority, created_at, doc)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(event_id, asset_id) DO UPDATE SET
                   status=excluded.status, priority=excluded.priority,
                   created_at=excluded.created_at, doc=excluded.doc""",
            (
                assessment.get("event_id", ""),
                assessment.get("asset_id", ""),
                assessment.get("status", "needs_confirmation"),
                assessment.get("priority", "unknown"),
                utcnow(),
                json.dumps(assessment, ensure_ascii=False),
            ),
        )


def list_assessments(limit: int = 500) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """SELECT a.doc, e.id AS event_id, e.component AS event_component,
                      s.id AS asset_id, s.name AS asset_name, s.component AS asset_component
               FROM assessments a
               LEFT JOIN events e ON e.id = a.event_id
               LEFT JOIN assets s ON s.id = a.asset_id
               ORDER BY a.created_at DESC, a.id DESC LIMIT ?""",
            (max(1, min(limit, 2000)),),
        ).fetchall()
    items = []
    for row in rows:
        record = json.loads(row["doc"])
        event = get_event(row["event_id"]) if row["event_id"] else None
        record["asset_name"] = row["asset_name"] or row["asset_id"]
        record["event_title"] = (event or {}).get("title") or row["event_id"]
        items.append(record)
    return items


def assessments_for_event(event_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT doc FROM assessments WHERE event_id = ? ORDER BY created_at DESC", (event_id,)
        ).fetchall()
    return [json.loads(r["doc"]) for r in rows]


def count_assessments() -> int:
    with connect() as conn:
        return int(conn.execute("SELECT COUNT(*) AS n FROM assessments").fetchone()["n"])


def clear_assessments() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM assessments")


# --------------------------------------------------------------------------
# runs
# --------------------------------------------------------------------------

def save_run(run: dict) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO runs (id, kind, status, started_at, finished_at, summary, detail)
               VALUES (:id, :kind, :status, :started_at, :finished_at, :summary, :detail)
               ON CONFLICT(id) DO UPDATE SET
                   status=excluded.status, finished_at=excluded.finished_at,
                   summary=excluded.summary, detail=excluded.detail""",
            {
                "id": run["id"],
                "kind": run.get("kind", "collect"),
                "status": run.get("status", "running"),
                "started_at": run.get("started_at"),
                "finished_at": run.get("finished_at"),
                "summary": run.get("summary"),
                "detail": json.dumps(run.get("detail"), ensure_ascii=False) if run.get("detail") is not None else None,
            },
        )


def list_runs(limit: int = 30) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (max(1, min(limit, 200)),)
        ).fetchall()
    items = []
    for row in rows:
        record = dict(row)
        record["detail"] = json.loads(record["detail"]) if record["detail"] else None
        items.append(record)
    return items


def latest_run(kind: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE kind = ? ORDER BY started_at DESC LIMIT 1", (kind,)
        ).fetchone()
    if not row:
        return None
    record = dict(row)
    record["detail"] = json.loads(record["detail"]) if record["detail"] else None
    return record


# --------------------------------------------------------------------------
# dedupe candidates
# --------------------------------------------------------------------------

def save_duplicate_candidate(event_id: str, candidate_id: str, reason: str, score: float) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO duplicate_candidates
                   (event_id, candidate_id, reason, score, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (event_id, candidate_id, reason, score, utcnow()),
        )


def list_duplicate_candidates(limit: int = 200) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM duplicate_candidates ORDER BY score DESC LIMIT ?",
            (max(1, min(limit, 1000)),),
        ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# export
# --------------------------------------------------------------------------

def export_snapshot() -> dict:
    """Full data snapshot for `GET /api/export`.

    Only stored documents are included; the model key is never part of any of
    them because it is never written to storage in the first place.
    """
    events, total = list_events(limit=500)
    return {
        "exported_at": utcnow(),
        "version": config.APP_VERSION,
        "mode": config.mode_label(),
        "counts": {**count_events(), "assets": count_assets(), "assessments": count_assessments()},
        "events_total": total,
        "events": events,
        "assets": list_assets(),
        "assessments": list_assessments(limit=1000),
        "sources": [dict(s) for s in all_source_states().values()],
        "runs": list_runs(limit=50),
    }
