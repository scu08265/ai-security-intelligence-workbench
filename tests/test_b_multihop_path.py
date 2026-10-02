"""B 任务：多跳路径检索器与验证器的测试。

覆盖：正例（路径存在）、反例（节点不存在 / 不连通）、缺失证据、
重复边去重、跳数上限，以及产物自身的证据完整性。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from multihop_path_retriever import Graph, _resolve, validate  # noqa: E402

ARTIFACTS = ROOT / "artifacts" / "b_eval"
VALIDATION = ARTIFACTS / "multihop_path_validation.json"


def _graph() -> Graph:
    graph = Graph()
    graph.add_node("event:E1", "event")
    graph.add_node("component:vllm", "component")
    graph.add_node("doc:paper:x", "document")
    graph.add_node("doc:paper:y", "document")
    graph.add_edge("event:E1", "component:vllm", "component_is",
                   {"type": "event_field", "event_id": "E1"})
    graph.add_edge("component:vllm", "doc:paper:x", "mentioned_in",
                   {"type": "chunk", "chunk_id": "chunk-1"})
    return graph


# --------------------------------------------------------------------------
# 正例 / 反例
# --------------------------------------------------------------------------

def test_two_hop_path_is_found_with_evidence():
    path = _graph().find_path("event:E1", "doc:paper:x")
    assert path is not None and len(path) == 2
    assert [e["relation"] for e in path] == ["component_is", "mentioned_in"]
    assert path[1]["evidence"]["chunk_id"] == "chunk-1"


def test_unknown_start_node_returns_none():
    assert _graph().find_path("event:DOES-NOT-EXIST", "doc:paper:x") is None


def test_unreachable_target_returns_none():
    """没有文档到文档的边，因此 A 文档到 B 文档必然不连通。"""
    assert _graph().find_path("doc:paper:x", "doc:paper:y") is None


def test_max_hops_is_respected():
    graph = _graph()
    graph.add_node("doc:paper:z", "document")
    graph.add_edge("doc:paper:x", "doc:paper:z", "mentioned_in",
                   {"type": "chunk", "chunk_id": "chunk-2"})
    assert graph.find_path("event:E1", "doc:paper:z", max_hops=1) is None
    assert graph.find_path("event:E1", "doc:paper:z", max_hops=3) is not None


# --------------------------------------------------------------------------
# 重复边与缺失证据
# --------------------------------------------------------------------------

def test_duplicate_edges_are_deduplicated():
    graph = Graph()
    graph.add_node("a", "component")
    graph.add_node("b", "document")
    for _ in range(3):
        graph.add_edge("a", "b", "mentioned_in", {"type": "chunk", "chunk_id": "c1"})
    assert len(graph.edges) == 1
    assert len(graph.adj["a"]) == 1


def test_edges_with_different_evidence_are_kept_separately():
    graph = Graph()
    graph.add_node("a", "component")
    graph.add_node("b", "document")
    graph.add_edge("a", "b", "mentioned_in", {"type": "chunk", "chunk_id": "c1"})
    graph.add_edge("a", "b", "mentioned_in", {"type": "chunk", "chunk_id": "c2"})
    assert len(graph.edges) == 2


def test_validate_reports_reason_when_endpoint_missing():
    case = {"question_id": "X", "chain_type": "two_hop",
            "reasoning_path": ["event:NOPE", "component:nope", "doc:paper:x"]}
    result = validate(case, _graph())
    assert result["path_found"] is False
    assert "找不到端点" in result["failure_reason"]


def test_validate_reports_reason_when_not_connected():
    case = {"question_id": "X", "chain_type": "cross_document",
            "reasoning_path": ["doc:paper:x", "doc:paper:y"]}
    result = validate(case, _graph())
    assert result["path_found"] is False
    assert "不连通" in result["failure_reason"]


def test_validate_returns_nodes_and_evidence_for_a_real_path():
    case = {"question_id": "X", "chain_type": "two_hop",
            "reasoning_path": ["E1", "vllm", "paper:x"]}
    result = validate(case, _graph())
    assert result["path_found"] is True
    assert result["hops"] == 2
    assert result["path_nodes"] == ["event:E1", "component:vllm", "doc:paper:x"]
    assert result["evidence_ids"] == ["E1", "chunk-1"]


def test_resolve_accepts_bare_identifiers_only_as_known_prefixes():
    assert "doc:paper:x" in _resolve("paper:x")
    assert "event:CVE-1" in _resolve("CVE-1")


# --------------------------------------------------------------------------
# 产物
# --------------------------------------------------------------------------

def test_validation_artifact_covers_all_candidates():
    if not VALIDATION.is_file():
        pytest.skip("先运行 tools/multihop_path_retriever.py")
    payload = json.loads(VALIDATION.read_text(encoding="utf-8"))
    assert payload["counts"]["candidates"] == 31
    assert payload["graph"]["edge_kinds"] == ["component_is", "mentioned_in"]
    for case in payload["cases"]:
        if case["path_found"]:
            assert case["path_edges"], case["question_id"]
            assert all(edge["relation"] for edge in case["path_edges"])
            assert all(e for e in case["evidence_ids"]), case["question_id"]
            assert case["hops"] <= 4
        else:
            assert case["failure_reason"], case["question_id"]


def test_two_hop_candidates_are_all_connected_and_cross_document_are_not():
    """如实记录当前数据能力：跨文档题缺边，必然不连通。"""
    if not VALIDATION.is_file():
        pytest.skip("先运行 tools/multihop_path_retriever.py")
    payload = json.loads(VALIDATION.read_text(encoding="utf-8"))
    by_type = payload["counts"]["by_chain_type"]
    assert by_type["two_hop"]["path_found"] == by_type["two_hop"]["total"] == 10
    assert by_type["cross_document"]["no_path"] == by_type["cross_document"]["total"] == 21
