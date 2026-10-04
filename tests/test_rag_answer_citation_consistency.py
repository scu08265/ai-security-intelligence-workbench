"""B 任务 D-4 回归测试：答案文案与文档引用必须语义一致。

缺陷：`intelligence.answer_question` 中结构化事件路径与 RAG 文档路径并行。
当事件路径拒答时，`with_rag` 仍会把 RAG 命中的文档引用挂到响应上，于是响应
同时出现"未找到可匹配的事件，无法可靠回答"和 5–6 条文档引用。

修复后：事件路径拒答但文档路径确有原文证据时，以文档证据为准（答案换成有依据的
文档答案、保留真实引用、追加 trace 与 limitation）；文档无证据时拒答行为不变；
事件路径已有答案时不被覆盖，文档引用也不会被清空。

本文件完全离线：用合成 `rag_chunks` 记录驱动 RAG 路径，不读写任何数据库。
"""

from __future__ import annotations

from app import intelligence

REFUSAL_FRAGMENT = "未找到可匹配的事件"
SYNTHETIC_TEXT = (
    "TrustedGuard enforces a signed allow list for every model asset before loading. " * 3
)
SNAPSHOT_HASH = "c" * 64


def _chunk(text: str, *, chunk_id: str = "chunk-syn-1",
           document_id: str = "doc-syn-1", start: int = 0) -> dict:
    return {
        "document_id": document_id, "chunk_id": chunk_id, "text": text,
        "char_start": start, "char_end": start + len(text),
        "snapshot_hash": SNAPSHOT_HASH, "source_id": "synthetic",
        "title": "Synthetic document", "provenance": "fulltext",
        "corpus_class": "collected_source",
    }


def _event() -> dict:
    return {
        "id": "CVE-2099-0001", "title": "Synthetic issue",
        "summary": "Synthetic summary about SynthServe.", "component": "SynthServe",
        "aliases": [], "relationships": [], "sources": [], "status": "confirmed",
        "withdrawn": False, "affected": [], "conditions": [],
    }


def test_refusal_text_is_replaced_when_document_evidence_exists():
    """事件路径拒答、但文档路径有证据时，不得再现"拒答 + 引用"并存。"""
    result = intelligence.answer_question(
        "TrustedGuard", [], [], rag_chunks=[_chunk(SYNTHETIC_TEXT)]
    )
    assert result["related_event_ids"] == []
    assert len(result["document_citations"]) == 1, "真实文档引用必须保留"
    assert REFUSAL_FRAGMENT not in (result["answer"] or ""), "不应再返回拒答文案"
    assert "TrustedGuard" in result["answer"]


def test_document_answer_records_why_event_path_was_overridden():
    result = intelligence.answer_question(
        "TrustedGuard", [], [], rag_chunks=[_chunk(SYNTHETIC_TEXT)]
    )
    last_step = result["trace"][-1]
    assert last_step["action"] == "answer_from_document_evidence"
    assert "文档证据" in last_step["result"]
    assert any("文档" in item for item in result["limitations"])


def test_offtopic_question_still_refuses_without_citations():
    """无关问题：拒答行为不得被削弱，也不得凭空产生引用。"""
    result = intelligence.answer_question("明天的天气怎么样？", [], [], rag_chunks=[])
    assert REFUSAL_FRAGMENT in result["answer"]
    assert result["document_citations"] == []
    assert result["rag"]["refused"] is True


def test_no_document_evidence_keeps_refusal():
    """检索无结果时仍然是拒答，不能因为放宽阈值而编造答案。"""
    result = intelligence.answer_question("TrustedGuard", [], [], rag_chunks=[])
    assert REFUSAL_FRAGMENT in result["answer"]
    assert result["document_citations"] == []


def test_event_backed_answer_is_not_overwritten_by_document_path():
    """事件路径有答案时，文档路径不得覆盖它。"""
    result = intelligence.answer_question("CVE-2099-0001 是什么？", [_event()], [],
                                          rag_chunks=[])
    assert result["related_event_ids"] == ["CVE-2099-0001"]
    assert "CVE-2099-0001" in result["answer"]
    assert REFUSAL_FRAGMENT not in result["answer"]


def test_document_citations_are_preserved_alongside_event_evidence():
    """事件与文档都有证据时，两者都要保留（不得为了消除矛盾而清空引用）。"""
    result = intelligence.answer_question(
        "CVE-2099-0001 TrustedGuard", [_event()], [],
        rag_chunks=[_chunk(SYNTHETIC_TEXT)],
    )
    assert result["related_event_ids"] == ["CVE-2099-0001"]
    assert "CVE-2099-0001" in result["answer"]
    assert len(result["document_citations"]) == 1


def test_document_citation_is_traceable_to_the_original_text():
    """引用必须能回溯到原文切片，且 chunk_id / snapshot_hash 不被改写。"""
    result = intelligence.answer_question(
        "TrustedGuard", [], [], rag_chunks=[_chunk(SYNTHETIC_TEXT)]
    )
    citation = result["document_citations"][0]
    assert citation["chunk_id"] == "chunk-syn-1"
    assert citation["document_id"] == "doc-syn-1"
    assert citation["snapshot_hash"] == SNAPSHOT_HASH
    assert citation["char_end"] - citation["char_start"] == len(citation["quote"])
    assert SYNTHETIC_TEXT[citation["char_start"]:citation["char_end"]] == citation["quote"]


def test_response_structure_is_unchanged():
    """修复不得改变公开返回字段（调用方与前端依赖这些键）。"""
    result = intelligence.answer_question(
        "TrustedGuard", [], [], rag_chunks=[_chunk(SYNTHETIC_TEXT)]
    )
    for key in ("answer", "citations", "claims", "trace", "limitations", "mode",
                "related_event_ids", "assessments", "rag", "document_citations",
                "context_snapshot", "context_resolution", "needs_clarification",
                "clarification"):
        assert key in result, f"缺少既有返回字段：{key}"
    assert isinstance(result["document_citations"], list)
    assert isinstance(result["answer"], str)
