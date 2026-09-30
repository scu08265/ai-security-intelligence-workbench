"""B 任务阶段 C：跨文档 / 多跳**候选**题集的证据完整性测试。

这些测试不评价系统的多跳能力（当前系统没有多跳推理），只校验候选题库本身：
每条边引用的 `chunk_id`、`document_key`、事件 ID 是否真实存在，坐标是否与原文一致，
以及"跨文档"是否真的跨了 ≥2 篇文档。

语料只在**数据库副本**上读取。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app import config, storage

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / "evaluation" / "b_multihop_candidates.json"
B_DATA_DIR = Path(r"D:\ICT\intel-data-b")


def _load() -> dict:
    return json.loads(CANDIDATES.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def b_db_copy(tmp_path_factory):
    if not (B_DATA_DIR / "intel.sqlite").is_file():
        pytest.skip(f"B 任务语料目录不存在：{B_DATA_DIR}")
    target = tmp_path_factory.mktemp("b_multihop")
    (target / "snapshots").mkdir()
    shutil.copy2(B_DATA_DIR / "intel.sqlite", target / "intel.sqlite")
    return target


@pytest.fixture()
def b_corpus(monkeypatch, b_db_copy):
    monkeypatch.setattr(config, "DATA_DIR", b_db_copy)
    monkeypatch.setattr(config, "SNAPSHOT_DIR", b_db_copy / "snapshots")
    monkeypatch.setattr(config, "DB_PATH", b_db_copy / "intel.sqlite")
    return b_db_copy


@pytest.fixture()
def chunk_index(b_corpus) -> dict[str, dict]:
    with storage.connect() as conn:
        rows = conn.execute(
            """SELECT c.id, c.document_id, c.char_start, c.char_end, c.text,
                      d.document_key, v.extracted_text
               FROM rag_chunks c
               JOIN rag_documents d ON d.id=c.document_id
               JOIN rag_document_versions v ON v.id=c.version_id
               WHERE c.version_id=d.current_version_id"""
        ).fetchall()
    return {row["id"]: dict(row) for row in rows}


# --------------------------------------------------------------------------
struct = None


def test_candidate_file_declares_its_own_limitations():
    payload = _load()
    assert payload["schema_version"].startswith("b-multihop-candidates")
    assert payload["limitations"], "候选集必须自带局限说明"
    assert "多跳" in " ".join(payload["limitations"])


def test_has_at_least_thirty_candidates_with_unique_texts():
    cases = _load()["cases"]
    assert len(cases) >= 30, f"候选题不足 30，实际 {len(cases)}"
    ids = [c["question_id"] for c in cases]
    questions = [c["question"] for c in cases]
    assert len(set(ids)) == len(ids)
    assert len(set(questions)) == len(questions), "存在重复问题文本（不允许复制凑数）"


def test_every_candidate_is_pending_human_review():
    for case in _load()["cases"]:
        assert case["verification_status"] == "pending_human_review", case["question_id"]


def test_every_edge_has_evidence(chunk_index):
    """每条边都必须带证据；结构化证据必须真的能在库里找到。"""
    problems: list[str] = []
    for case in _load()["cases"]:
        for edge in case["edges"]:
            evidence = edge.get("evidence") or {}
            kind = evidence.get("type")
            assert kind, f"{case['question_id']} 的边缺少证据类型"
            if kind == "chunk":
                chunk = chunk_index.get(evidence["chunk_id"])
                if chunk is None:
                    problems.append(f"{case['question_id']}: 分块 {evidence['chunk_id']} 不存在")
                    continue
                if chunk["document_key"] != evidence["document_key"]:
                    problems.append(f"{case['question_id']}: 文档归属不一致")
                if (evidence["char_end"] - evidence["char_start"]) != len(chunk["text"]):
                    problems.append(f"{case['question_id']}: 分块坐标与文本长度不一致")
                if chunk["extracted_text"][evidence["char_start"]:evidence["char_end"]] != chunk["text"]:
                    problems.append(f"{case['question_id']}: 分块坐标无法定位到原文")
            elif kind == "event_field":
                if storage.get_event(evidence["event_id"]) is None:
                    problems.append(f"{case['question_id']}: 事件 {evidence['event_id']} 不存在")
            else:
                problems.append(f"{case['question_id']}: 未知证据类型 {kind}")
    assert not problems, "; ".join(problems[:5])


def test_cross_document_cases_really_span_multiple_documents():
    for case in _load()["cases"]:
        if case["chain_type"] != "cross_document":
            continue
        documents = {edge["evidence"]["document_key"] for edge in case["edges"]}
        assert len(documents) >= 2, f"{case['question_id']} 不是真正的跨文档"
        assert set(case["documents"]) == documents


def test_two_hop_cases_have_a_field_edge_and_a_chunk_edge():
    for case in _load()["cases"]:
        if case["chain_type"] != "two_hop":
            continue
        kinds = [edge["evidence"]["type"] for edge in case["edges"]]
        assert kinds.count("event_field") == 1, case["question_id"]
        assert kinds.count("chunk") >= 1, case["question_id"]
        assert len(case["reasoning_path"]) >= 3, "两跳至少需要三个节点"
        assert case.get("notes"), "两跳题必须说明第二跳是共现而非论断"


def test_candidate_chain_types_are_limited_to_what_the_data_supports():
    types = {case["chain_type"] for case in _load()["cases"]}
    assert types <= {"two_hop", "cross_document"}


def test_dataset_does_not_claim_verified_relations():
    """候选集里不允许出现被标成已确认的关系。"""
    for case in _load()["cases"]:
        for edge in case["edges"]:
            assert edge.get("verified") is not True, case["question_id"]
        assert case.get("human_verified") is not True, case["question_id"]
