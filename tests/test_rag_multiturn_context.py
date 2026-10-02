"""Regression tests for context-aware RAG follow-up questions."""

from __future__ import annotations

from app import intelligence


def _chunk(text: str, *, chunk_id: str, document_id: str, title: str) -> dict:
    return {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "text": text,
        "char_start": 0,
        "char_end": len(text),
        "snapshot_hash": "a" * 64,
        "source_id": "paper",
        "title": title,
        "provenance": "fulltext",
        "corpus_class": "collected_source",
    }


def _distillguard_text() -> str:
    return (
        "DistillGuard detects model inversion attacks during inference. "
        "It reports confidence and supporting evidence for each detection. "
    ) * 3


def test_pronoun_follow_up_inherits_subject_from_previous_user_question():
    result = intelligence.answer_question(
        "它检测什么？", [], [],
        history=[{"role": "user", "content": "DistillGuard 这篇论文是什么？"}],
        rag_chunks=[_chunk(
            _distillguard_text(), chunk_id="c-distill", document_id="d-distill",
            title="DistillGuard Paper",
        )],
    )
    assert result["document_citations"]
    assert "distillguard" in result["rag"]["retrieval"]["query"].casefold()
    assert "model inversion" in result["answer"].casefold()
    assert result["claims"][0]["evidence_ids"] == ["c-distill"]


def test_previous_document_focus_is_used_for_follow_up():
    result = intelligence.answer_question(
        "它检测什么？", [], [],
        context_snapshot={"selected_document_ids": ["d-distill"]},
        rag_chunks=[
            _chunk(_distillguard_text(), chunk_id="c-distill", document_id="d-distill",
                   title="DistillGuard Paper"),
            _chunk("Unrelated database tuning guidance. " * 8,
                   chunk_id="c-other", document_id="d-other", title="Other Paper"),
        ],
    )
    assert [item["document_id"] for item in result["document_citations"]] == ["d-distill"]
    assert result["rag"]["retrieval"]["focused_retrieval"] is True


def test_missing_previous_anchor_refuses_instead_of_unrelated_detect_hit():
    result = intelligence.answer_question(
        "它检测什么？", [], [],
        history=[{"role": "user", "content": "DistillGuard 这篇论文是什么？"}],
        rag_chunks=[_chunk(
            "The authority may detect and investigate unlawful conduct. " * 8,
            chunk_id="c-law", document_id="d-law", title="Unrelated law",
        )],
    )
    assert result["document_citations"] == []
    assert result["rag"]["retrieval"]["required_terms"] == ["distillguard"]


def test_topic_switch_does_not_expand_with_previous_subject():
    result = intelligence.answer_question(
        "换个话题，提示词注入是什么？", [], [],
        history=[{"role": "user", "content": "DistillGuard 这篇论文是什么？"}],
        rag_chunks=[_chunk(
            "Prompt injection manipulates model instructions. " * 8,
            chunk_id="c-prompt", document_id="d-prompt", title="Prompt Injection Guide",
        )],
    )
    assert "distillguard" not in result["rag"]["retrieval"]["query"].casefold()
    assert result["document_citations"]
