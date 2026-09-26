from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import agent_context, rag_corpus, storage
from app.api import app


@pytest.fixture
def client():
    return TestClient(app)


def _evidence() -> dict:
    storage.upsert_event({
        "id": "CVE-2099-CONTEXT", "title": "Context fixture",
        "status": "confirmed", "kind": "vulnerability", "sources": [],
    })
    asset = storage.upsert_asset({
        "id": "asset-context", "name": "Context host", "component": "example",
        "authorized": True,
    })
    ingested = rag_corpus.ingest_bytes(
        b"# Advisory\n\nUpgrade Example because CVE-2099-CONTEXT is exploitable.",
        source_id="vendor", document_key="context-advisory",
        title="Vendor advisory", media_type="text/markdown",
    )
    chunk = rag_corpus.search("CVE-2099-CONTEXT")[0]
    return {"asset": asset, "document": ingested, "chunk": chunk}


def test_turn_snapshot_captures_explicit_context_and_exact_source_version():
    evidence = _evidence()
    thread = agent_context.create_thread(
        "判断漏洞是否影响受管资产", thread_id="thread-context",
        base_constraints=["只使用有来源的事实", "未知时拒答"],
    )
    result = agent_context.append_turn(
        thread["id"], visible_user_input="它是否影响这台主机？",
        visible_assistant_output="需要比对版本后判断。",
        focus_event_id="CVE-2099-CONTEXT", focus_asset_id=evidence["asset"]["id"],
        focus_document_id=evidence["document"]["document_id"],
        constraints=["不要假定运行配置"],
        resolved_references=[{
            "mention": "它", "kind": "event",
            "resolved_id": "CVE-2099-CONTEXT", "method": "previous_focus",
        }],
        chunk_ids=[evidence["chunk"]["chunk_id"]],
    )
    snapshot = result["context_snapshot"]

    assert result["turn"]["turn_index"] == 1
    assert snapshot["objective"] == "判断漏洞是否影响受管资产"
    assert snapshot["focus"] == {
        "event_id": "CVE-2099-CONTEXT", "asset_id": "asset-context",
        "document_id": evidence["document"]["document_id"],
    }
    assert snapshot["inherited_constraints"] == [
        "只使用有来源的事实", "未知时拒答", "不要假定运行配置",
    ]
    assert snapshot["resolved_references"][0]["resolved_id"] == "CVE-2099-CONTEXT"
    assert snapshot["chunk_ids"] == [evidence["chunk"]["chunk_id"]]
    assert snapshot["source_versions"][0]["version_id"] == evidence["document"]["version_id"]
    assert snapshot["source_versions"][0]["parser_version"] == rag_corpus.PARSER_VERSION
    assert snapshot["created_at"].endswith("Z")
    assert len(snapshot["content_hash"]) == 64
    assert snapshot["immutable"] is True


def test_next_turn_inherits_objective_focus_and_constraints_but_not_evidence_usage():
    evidence = _evidence()
    thread = agent_context.create_thread("初始目标", base_constraints=["约束A"])
    first = agent_context.append_turn(
        thread["id"], focus_event_id="CVE-2099-CONTEXT",
        focus_document_id=evidence["document"]["document_id"],
        objective="细化后的目标", constraints=["约束B"],
        chunk_ids=[evidence["chunk"]["chunk_id"]],
    )
    second = agent_context.append_turn(
        thread["id"], visible_user_input="继续", constraints=["约束C"],
    )

    assert first["turn"]["turn_index"] == 1
    assert second["turn"]["turn_index"] == 2
    snapshot = second["context_snapshot"]
    assert snapshot["objective"] == "细化后的目标"
    assert snapshot["focus"]["event_id"] == "CVE-2099-CONTEXT"
    assert snapshot["focus"]["document_id"] == evidence["document"]["document_id"]
    assert snapshot["inherited_constraints"] == ["约束A", "约束B", "约束C"]
    assert snapshot["chunk_ids"] == []
    assert snapshot["source_versions"] == []


def test_context_snapshot_is_immutable_at_database_level():
    thread = agent_context.create_thread("不可变测试")
    snapshot = agent_context.append_turn(thread["id"])["context_snapshot"]
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        with storage.connect() as conn:
            conn.execute(
                "UPDATE agent_context_snapshots SET objective='tampered' WHERE id=?",
                (snapshot["id"],),
            )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        with storage.connect() as conn:
            conn.execute("DELETE FROM agent_context_snapshots WHERE id=?", (snapshot["id"],))
    assert agent_context.get_snapshot(snapshot["id"])["objective"] == "不可变测试"


def test_invalid_evidence_reference_rolls_back_entire_turn():
    thread = agent_context.create_thread("引用校验")
    with pytest.raises(ValueError, match="chunk"):
        agent_context.append_turn(thread["id"], chunk_ids=["chunk-missing"])
    loaded = agent_context.get_thread(thread["id"])
    assert loaded["turns"] == []
    assert loaded["context_snapshots"] == []


def test_agent_context_api_reads_snapshots_by_thread_and_rejects_reasoning_field(client):
    created = client.post("/api/agent/threads", json={
        "thread_id": "api-thread", "objective": "核验API上下文",
        "base_constraints": ["引用必须可复核"],
    })
    assert created.status_code == 200

    rejected = client.post("/api/agent/threads/api-thread/turns", json={
        "visible_user_input": "检查", "hidden_reasoning": "不应存储",
    })
    assert rejected.status_code == 422

    appended = client.post("/api/agent/threads/api-thread/turns", json={
        "visible_user_input": "检查", "visible_assistant_output": "已检查",
        "constraints": ["保持保守结论"], "resolved_references": [],
    })
    assert appended.status_code == 200
    snapshot_id = appended.json()["context_snapshot"]["id"]
    response = client.get("/api/agent/threads/api-thread/context-snapshots")
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["id"] == snapshot_id
    thread = client.get("/api/agent/threads/api-thread").json()
    assert thread["stores_hidden_reasoning"] is False
    assert all("reasoning" not in turn for turn in thread["turns"])
    assert all("reasoning" not in snapshot for snapshot in thread["context_snapshots"])
