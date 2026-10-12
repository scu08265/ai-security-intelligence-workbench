"""Synthetic RAG tests for refusal, fallback and replaceable ranking paths."""

import hashlib

from app.intelligence import answer_question
from app.rag import (
    SearchHit, answer_with_rag, chunks_from_records, events_to_documents,
    retrieve_chunks,
)


def _record(document_id: str, text: str) -> dict:
    return {
        "document_id": document_id, "chunk_id": f"{document_id}#0",
        "text": text, "char_start": 0, "char_end": len(text),
        "snapshot_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "provenance": "fulltext", "corpus_class": "synthetic",
    }


def test_no_evidence_refuses_before_generator_is_called():
    called = False

    def generator(question, context, citations):
        nonlocal called
        called = True
        return "invented"

    result = answer_with_rag(
        "量子天气预报是什么？",
        chunks=[_record("SYNTHETIC-1", "Widget parser memory safety advisory.")],
        generator=generator,
    )
    assert result["refused"] is True
    assert result["refusal_reason"] == "no_retrievable_evidence"
    assert result["citations"] == []
    assert called is False


def test_single_generic_security_word_does_not_create_a_false_answer():
    result = answer_with_rag(
        "量子奶酪漏洞怎么修复？",
        chunks=[_record("SYNTHETIC-1", "A vulnerability disclosure and remediation policy.")],
    )
    assert result["refused"] is True
    assert result["citations"] == []


def _chunk(document_id: str, index: int, text: str) -> dict:
    return {
        "document_id": document_id, "chunk_id": f"{document_id}#{index}",
        "text": text, "char_start": 0, "char_end": len(text),
        "snapshot_hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "provenance": "fulltext", "corpus_class": "synthetic",
    }


def test_a_question_word_does_not_outrank_the_subject_it_asks_about():
    """论文 expands to paper/study/arxiv, so scoring each synonym separately
    lets a question word decide the ranking.

    In the B corpus that pushed the paper actually about multi-agent out of the
    top 8 while the same question phrased with 文章 retrieved it first.  The
    corpus lives outside the repository (and is absent in CI), so the shape is
    reproduced here instead, with the same statistics: the question's synonyms
    are rarer than the subject term, the subject chunks also carry one synonym,
    and enough chunks match the synonyms alone to fill the result page.  Twelve
    such chunks beat the ten subject chunks only because three synonyms were
    counted three times; grouped, they beat nothing.
    """
    padding = [
        _chunk(f"paper:PAD-{index}", index,
               "An unrelated survey of deployment practice and reporting.")
        for index in range(380)
    ]
    filler = [
        _chunk(f"paper:FILLER-{index // 3}", index,
               "This paper studies a study published on arxiv with evidence.")
        for index in range(12)
    ]
    subject = [
        _chunk("paper:TARGET", index,
               "Codetta keeps multi-agent collusion undetectable; "
               "the arxiv record holds the details.")
        for index in range(10)
    ]
    hits = retrieve_chunks(
        "multi-agent 主题出现在哪些论文中？",
        chunks_from_records(padding + filler + subject), limit=8,
    )
    assert "paper:TARGET" in {hit.chunk.document_id for hit in hits}


def test_replaceable_reranker_controls_order_without_inventing_hits():
    first = _record("SYNTHETIC-A", "Prompt injection reaches an unsafe tool call.")
    second = _record("SYNTHETIC-B", "Prompt injection changes the agent plan.")

    def prefer_b_reranker(query: str, hits: tuple[SearchHit, ...]):
        return sorted(hits, key=lambda hit: hit.chunk.document_id != "SYNTHETIC-B")

    result = answer_with_rag("提示词注入", chunks=[first, second], reranker=prefer_b_reranker)
    assert result["retrieval"]["reranked"] is True
    assert result["citations"][0]["document_id"] == "SYNTHETIC-B"
    assert {item["document_id"] for item in result["citations"]} == {"SYNTHETIC-A", "SYNTHETIC-B"}


def test_summary_fallback_is_explicit_and_never_labelled_fulltext():
    documents = events_to_documents([{
        "id": "SYNTHETIC-SUMMARY", "summary": "Synthetic agent memory poisoning case.",
        "is_demo": True, "sources": [],
    }])
    assert len(documents) == 1
    assert documents[0].provenance == "summary_fallback"
    assert documents[0].corpus_class == "synthetic"


def test_existing_answer_question_contract_gains_document_citations_additively():
    source_text = "CVE-2026-77777 affects Widget AI and is fixed in version 2.0."
    event = {
        "id": "CVE-2026-77777", "kind": "vulnerability", "status": "confirmed",
        "title": "Synthetic Widget advisory", "summary": source_text,
        "component": "Widget-AI", "affected": [], "conditions": [], "relationships": [],
        "sources": [{
            "id": "fixture:77777", "url": "https://example.invalid/77777",
            "title": "Synthetic source", "excerpt": source_text,
            "content_hash": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            "trust": "fixture",
        }],
    }
    result = answer_question("CVE-2026-77777 是什么？", [event], [])
    # Established fields remain present and unchanged in meaning.
    assert result["related_event_ids"] == ["CVE-2026-77777"]
    assert result["citations"][0]["id"] == "fixture:77777"
    # New P1 fields provide exact document evidence.
    assert result["rag"]["refused"] is False
    assert result["document_citations"][0]["document_id"]
    assert result["document_citations"][0]["chunk_id"]
    assert result["document_citations"][0]["snapshot_hash"]
