"""RAG contract checks using source-attributed (non-synthetic) evidence.

These tests are offline snapshots of public-source style records.  They are
kept separate from deliberately invented fixtures so evaluation denominators
can distinguish collected-source behavior from synthetic branch coverage.
"""

import hashlib

from app.rag import answer_with_rag, chunk_documents, events_to_documents, retrieve_chunks


NVD_TEXT = (
    "CVE-2026-41000 affects Example Gateway versions before 1.4.2. "
    "The issue can allow remote code execution when the upload API is enabled. "
    "The vendor fixed the vulnerability in version 1.4.2."
)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_persisted_chunk_contract_is_preferred_and_fully_traceable():
    persisted = [{
        "document_id": "NVD:CVE-2026-41000",
        "chunk_id": "NVD:CVE-2026-41000#chunk-0000",
        "text": NVD_TEXT,
        "char_start": 0,
        "char_end": len(NVD_TEXT),
        "snapshot_hash": _digest(NVD_TEXT),
        "snapshot_origin": "document_text_sha256",
        "source_id": "nvd:CVE-2026-41000",
        "title": "CVE-2026-41000",
        "url": "https://nvd.nist.gov/vuln/detail/CVE-2026-41000",
        "provenance": "fulltext",
        "corpus_class": "collected_source",
    }]
    # An unrelated event proves persisted chunks are the primary input rather
    # than an event projection silently replacing the storage result.
    result = answer_with_rag(
        "CVE-2026-41000 的修复版本是什么？",
        [{"id": "UNRELATED", "summary": "unrelated"}],
        chunks=persisted,
    )
    assert result["refused"] is False
    assert result["retrieval"]["input_mode"] == "persisted_chunks"
    assert result["retrieval"]["documents"] == 0
    citation = result["citations"][0]
    assert citation["document_id"] == "NVD:CVE-2026-41000"
    assert citation["chunk_id"] == "NVD:CVE-2026-41000#chunk-0000"
    assert NVD_TEXT[citation["char_start"]:citation["char_end"]] == citation["quote"]
    assert citation["snapshot_hash"] == _digest(NVD_TEXT)
    assert citation["provenance"] == "fulltext"
    assert citation["corpus_class"] == "collected_source"


def test_event_compatibility_projection_labels_excerpt_instead_of_fulltext():
    event = {
        "id": "CVE-2026-41000",
        "kind": "vulnerability",
        "title": "Example Gateway advisory",
        "sources": [{
            "id": "nvd:CVE-2026-41000", "title": "NVD record",
            "url": "https://nvd.nist.gov/vuln/detail/CVE-2026-41000",
            "publisher": "NVD", "trust": "government",
            "excerpt": NVD_TEXT, "content_hash": "upstream-normalized-hash",
        }],
    }
    document = events_to_documents([event])[0]
    assert document.provenance == "source_excerpt"
    assert document.corpus_class == "collected_source"
    assert document.snapshot_hash == _digest(NVD_TEXT)
    assert document.metadata["upstream_snapshot_hash"] == "upstream-normalized-hash"
    chunks = chunk_documents([document], chunk_size=100, overlap=20)
    hits = retrieve_chunks("remote code execution upload API", chunks)
    assert hits
    top = hits[0].chunk
    assert document.text[top.char_start:top.char_end] == top.text


def test_context_budget_truncates_quote_and_character_range_together():
    record = {
        "document_id": "NVD:CVE-2026-41000", "chunk_id": "nvd#0",
        "text": NVD_TEXT, "char_start": 0, "char_end": len(NVD_TEXT),
        "snapshot_hash": _digest(NVD_TEXT), "provenance": "fulltext",
        "corpus_class": "collected_source",
    }
    result = answer_with_rag("remote code execution", chunks=[record], max_context_chars=80)
    citation = result["citations"][0]
    assert result["context"]["used_chars"] <= 80
    assert result["context"]["truncated"] is True
    assert citation["char_end"] - citation["char_start"] == len(citation["quote"])
    assert NVD_TEXT[citation["char_start"]:citation["char_end"]] == citation["quote"]

