from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import config, rag, rag_corpus, storage
from app.api import app


@pytest.fixture
def client():
    return TestClient(app)


def test_html_ingestion_records_stable_citable_chunks():
    raw = """<html><head><style>hidden</style></head><body>
    <h1>修复指南</h1><p>CVE-2099-1234 影响 Example 1.0。</p>
    <h2>处置</h2><p>升级到 1.1，并检查公网暴露。</p><script>ignore()</script>
    </body></html>""".encode()
    first = rag_corpus.ingest_bytes(
        raw, source_id="fixture", document_key="guide", title="安全指南",
        media_type="text/html", snapshot_hash=storage.content_hash(raw),
    )
    second = rag_corpus.ingest_bytes(
        raw, source_id="fixture", document_key="guide", title="安全指南",
        media_type="text/html", snapshot_hash=storage.content_hash(raw),
    )

    assert first["document_id"] == second["document_id"]
    assert first["version_id"] == second["version_id"]
    assert first["version_created"] is True
    assert second["version_created"] is False
    document = rag_corpus.get_document(first["document_id"])
    assert document["current_version_id"] == first["version_id"]
    assert len(document["versions"]) == 1
    matches = rag_corpus.search("升级 公网暴露")
    assert matches and matches[0]["version_id"] == first["version_id"]
    chunk = rag_corpus.get_chunk(matches[0]["chunk_id"])
    assert chunk["text"] == "升级到 1.1，并检查公网暴露。"
    assert chunk["section_path"] == ["修复指南", "处置"]
    with storage.connect() as conn:
        extracted = conn.execute(
            "SELECT extracted_text FROM rag_document_versions WHERE id=?",
            (first["version_id"],),
        ).fetchone()["extracted_text"]
    assert extracted[chunk["char_start"]:chunk["char_end"]] == chunk["text"]
    adapter_chunks = rag.chunks_from_records(rag_corpus.list_chunk_records())
    assert any(item.chunk_id == chunk["id"] for item in adapter_chunks)


def test_changed_document_creates_version_without_breaking_old_chunk_reference():
    old = rag_corpus.ingest_bytes(
        b"# Advisory\n\nUpgrade to 1.1.", source_id="fixture", document_key="advisory",
        media_type="text/markdown",
    )
    old_match = rag_corpus.search("Upgrade 1.1")[0]
    new = rag_corpus.ingest_bytes(
        b"# Advisory\n\nUpgrade to 1.2.", source_id="fixture", document_key="advisory",
        media_type="text/markdown",
    )

    assert old["document_id"] == new["document_id"]
    assert old["version_id"] != new["version_id"]
    document = rag_corpus.get_document(old["document_id"])
    assert document["current_version_id"] == new["version_id"]
    assert len(document["versions"]) == 2
    assert rag_corpus.get_chunk(old_match["chunk_id"])["text"] == "Upgrade to 1.1."
    assert rag_corpus.search("1.1", current_only=True) == []
    assert rag_corpus.search("1.1", current_only=False)[0]["version_id"] == old["version_id"]


def test_xml_and_text_parsers_preserve_section_paths():
    xml = b"<feed><entry><title>Paper A</title><summary>Graph based reasoning.</summary></entry></feed>"
    xml_result = rag_corpus.ingest_bytes(
        xml, source_id="arxiv", document_key="feed", media_type="application/xml",
    )
    assert xml_result["chunks"] >= 2
    assert any("entry: Paper A" in "/".join(item["section_path"])
               for item in rag_corpus.search("reasoning"))

    sections, encoding = rag_corpus.parse_document(
        "# 中文说明\n\n这是第一段。\n\n## 修复\n\n升级组件。".encode(), "text/markdown"
    )
    assert encoding == "utf-8-sig"
    assert sections[-1].path == ("中文说明", "修复")


def test_snapshot_and_local_file_ingestion(client, tmp_path):
    raw = b"<html><body><h1>Evidence</h1><p>Patch version 9.9.</p></body></html>"
    digest = storage.save_snapshot("vendor", raw, suffix="html")
    response = client.post("/api/rag/ingest/snapshot", json={
        "source_id": "vendor", "snapshot_hash": digest, "suffix": "html",
        "document_key": "vendor-advisory", "title": "Vendor advisory",
    })
    assert response.status_code == 200
    document_id = response.json()["document_id"]
    assert client.get(f"/api/rag/documents/{document_id}").status_code == 200
    assert client.get("/api/rag/search", params={"q": "Patch version"}).json()["total"] == 1

    local = tmp_path / "notes.txt"
    local.write_text("本地研判记录：需要升级。", encoding="utf-8")
    denied = client.post("/api/rag/ingest/file", json={"path": str(local), "authorized": False})
    assert denied.status_code == 400
    accepted = client.post("/api/rag/ingest/file", json={"path": str(local), "authorized": True})
    assert accepted.status_code == 200
    assert storage.snapshot_path("rag_local", accepted.json()["content_hash"], "txt").exists()


def test_latest_snapshot_batch_uses_source_state_last_hash(client):
    for index, source_id in enumerate(("source_a", "source_b", "source_c", "source_json")):
        suffix = "json" if source_id == "source_json" else "html"
        raw = (f'{{"n": {index}}}' if suffix == "json" else
               f"<html><body><p>Real snapshot {index}</p></body></html>")
        digest = storage.save_snapshot(source_id, raw, suffix=suffix)
        storage.update_source_state(
            source_id, status="ok", last_hash=digest,
            last_success=f"2099-01-01T00:00:0{index}Z",
        )
    response = client.post("/api/rag/ingest/latest", json={"limit": 3})
    assert response.status_code == 200
    payload = response.json()
    assert payload["ingested"] == 3
    assert {item["source_id"] for item in payload["items"]} == {
        "source_a", "source_b", "source_c",
    }
    assert any(item["source_id"] == "source_json" for item in payload["skipped"])
    assert len(client.get("/api/rag/documents").json()["items"]) == 3


def test_snapshot_filename_hash_is_verified_before_ingestion():
    digest = "a" * 64
    path = config.SNAPSHOT_DIR / "vendor" / f"{digest}.txt"
    path.parent.mkdir(parents=True)
    path.write_text("tampered", encoding="utf-8")
    try:
        rag_corpus.ingest_snapshot(
            source_id="vendor", snapshot_hash=digest, suffix="txt",
        )
    except ValueError as exc:
        assert "SHA-256" in str(exc)
    else:
        raise AssertionError("tampered snapshot must not be ingested")


def test_pdf_extraction_does_not_use_layout_mode(monkeypatch):
    """PDF 抽取必须走 pypdf 默认的内容流顺序。

    ``extraction_mode="layout"`` 会保留视觉版式，双栏论文因此变成"左栏一行 + 右栏一行"
    交替，抽出来的句子读不通（见 docs/B_PDF_EXTRACTION_FIX_20261018.md 的 before/after）。
    这里用假的 PdfReader 记录调用参数，确保没有人再把 layout 加回来。
    """
    import pypdf

    calls: list[dict] = []

    class FakePage:
        def extract_text(self, *args, **kwargs):
            calls.append(dict(kwargs))
            return "first column line\nsecond column line\n"

    class FakeReader:
        is_encrypted = False
        pages = [FakePage()]

    monkeypatch.setattr(pypdf, "PdfReader", lambda raw: FakeReader())
    sections = rag_corpus._parse_pdf(b"%PDF-1.4 fixture")
    assert sections and "first column line" in sections[0].text
    assert calls == [{}], f"抽取不该传 extraction_mode：{calls}"


def test_two_column_interleaving_is_measurable():
    """把"分栏交错"写成可量化判据：交错文本的长空白（栏间距）占比明显更高。

    这是判定"哪一份更干净"的口径。真实双栏 PDF 属外部语料、不入库，
    所以这里做文本级断言——覆盖的是**判据本身**，不是 PDF 解析链路（后者由上一条测试守）。
    """
    import re

    def gap_share(text: str) -> float:
        lines = [ln for ln in text.splitlines() if ln.strip()]
        return sum(1 for ln in lines if re.search(r"\S {3,}\S", ln)) / len(lines)

    interleaved = (
        "GRPO (Shao et al.,2024) and DAPO (Yu et al.,      outcome rewards and estimates the per-\n"
        "2026), has demonstrated strong effectiveness      token advantage as the group-normalized reward:\n"
    )
    columnwise = (
        "GRPO (Shao et al., 2024) and DAPO (Yu et al.,\n"
        "2026), has demonstrated strong effectiveness\n"
    )
    assert gap_share(interleaved) > 0.5
    assert gap_share(columnwise) == 0.0