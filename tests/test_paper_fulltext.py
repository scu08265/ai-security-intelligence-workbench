"""Offline tests for the bounded arXiv PDF full-text tool."""

from __future__ import annotations

import httpx

from app import agents, collectors, normalize, paper_fulltext, rag_corpus, storage


def _text_pdf(*pages: str) -> bytes:
    """Build a tiny valid PDF without introducing a test-only dependency."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{index} 0 R' for index in range(3, 3 + len(pages) * 2, 2))}] /Count {len(pages)} >>".encode(),
    ]
    font_obj = 3 + len(pages) * 2
    for page_number, text in enumerate(pages):
        page_obj = 3 + page_number * 2
        content_obj = page_obj + 1
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 14 Tf 30 100 Td ({escaped}) Tj ET".encode()
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 320 160] /Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_obj} 0 R >>".encode()
        )
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    payload = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    payload.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    payload.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(payload)


def _paper_event(url: str = "https://arxiv.org/abs/2099.00001v1") -> dict:
    event = normalize.arxiv_entry_to_event({
        "id": url, "link": url, "title": "Synthetic Agent Security Paper",
        "summary": "Synthetic paper about large language model security.",
        "published": "2099-01-01T00:00:00Z", "categories": ["cs.CR"],
        "primary_category": "cs.CR",
    })
    assert event is not None
    event["paper"] = {"arxiv_id": "2099.00001v1", "pdf_url": "https://arxiv.org/pdf/2099.00001v1"}
    return event


def test_pdf_ingestion_preserves_page_and_extracted_character_locators():
    result = rag_corpus.ingest_bytes(
        _text_pdf("Prompt injection evidence on page one.", "Mitigation evidence on page two."),
        source_id="arxiv", document_key="paper:2099.00001v1", title="Fixture paper",
        media_type="application/pdf",
    )
    matches = rag_corpus.search("mitigation evidence")
    assert matches
    chunk = rag_corpus.get_chunk(matches[0]["chunk_id"])
    assert chunk and chunk["metadata"] == {"page_start": 2, "page_end": 2}
    with storage.connect() as conn:
        extracted = conn.execute(
            "SELECT extracted_text FROM rag_document_versions WHERE id=?", (result["version_id"],)
        ).fetchone()["extracted_text"]
    assert extracted[chunk["char_start"]:chunk["char_end"]] == chunk["text"]


def test_fulltext_tool_accepts_only_arxiv_and_creates_real_pdf_snapshot(monkeypatch):
    raw = _text_pdf("Prompt injection defense evidence.")
    requested: list[str] = []

    def request(method: str, url: str, **kwargs):  # noqa: ANN001
        requested.append(url)
        return httpx.Response(200, content=raw, headers={"content-type": "application/pdf"})

    monkeypatch.setattr(paper_fulltext, "http_request", request)
    result = paper_fulltext.ingest_arxiv_paper(_paper_event())
    assert requested == ["https://arxiv.org/pdf/2099.00001v1"]
    assert result["status"] == "fulltext"
    assert result["has_full_text"] is True
    assert storage.snapshot_path("arxiv", result["snapshot_hash"], "pdf").exists()
    assert rag_corpus.get_document(result["document_id"])["metadata"]["arxiv_id"] == "2099.00001v1"


def test_bad_or_untrusted_pdf_is_not_marked_as_fulltext(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(paper_fulltext, "http_request", lambda *args, **kwargs: calls.append("called"))
    untrusted = _paper_event("https://example.invalid/abs/2099.00001v1")
    untrusted["paper"] = {}
    rejected = paper_fulltext.ingest_arxiv_paper(untrusted)
    assert rejected["status"] == "failed" and rejected["has_full_text"] is False
    assert calls == []

    monkeypatch.setattr(paper_fulltext, "http_request", lambda *args, **kwargs: httpx.Response(200, content=b"%PDF-not-a-real-pdf"))
    malformed = paper_fulltext.ingest_arxiv_paper(_paper_event())
    assert malformed["status"] == "failed" and malformed["has_full_text"] is False
    assert rag_corpus.list_documents() == []


def test_collection_agent_invokes_bounded_paper_tool_and_records_result(monkeypatch):
    event = _paper_event()
    outcome = collectors.CollectOutcome(source_id="arxiv", status="ok", events=[event], fetched=1)
    monkeypatch.setattr(collectors, "collect", lambda *args, **kwargs: outcome)
    monkeypatch.setattr(paper_fulltext, "ingest_arxiv_paper", lambda _event: {
        "arxiv_id": "2099.00001v1", "pdf_url": "https://arxiv.org/pdf/2099.00001v1",
        "status": "fulltext", "has_full_text": True, "chunks": 3,
        "document_id": "doc-fixture", "version_id": "ver-fixture", "attempted_at": storage.utcnow(),
    })
    result = agents.run_collection(["arxiv"])
    source = result["results"][0]
    assert source["paper_fulltext_attempted"] == 1
    assert source["events"][0]["paper_fulltext"]["status"] == "fulltext"
    assert any(call["action"] == "ingest_arxiv_fulltext" for call in result["tool_calls"])
    stored = storage.get_event(event["id"])
    assert stored["paper"]["full_text"]["has_full_text"] is True
