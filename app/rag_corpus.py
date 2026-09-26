"""Versioned full-text corpus for retrieval-augmented generation.

This module deliberately stops at deterministic ingestion and lexical
retrieval.  A vector index can replace :class:`KeywordIndex` later without
changing document, version, chunk, or citation identifiers.
"""

from __future__ import annotations

import json
import math
import re
from io import BytesIO
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Protocol
from xml.etree import ElementTree

from . import config, storage

PARSER_VERSION = "fulltext-1.2"
MAX_INPUT_BYTES = 20 * 1024 * 1024
DEFAULT_CHUNK_CHARS = 1000
DEFAULT_OVERLAP_CHARS = 120
SAFE_SOURCE = re.compile(r"^[A-Za-z0-9_.-]{1,100}$")
SAFE_HASH = re.compile(r"^[a-fA-F0-9]{64}$")


@dataclass(frozen=True)
class Section:
    path: tuple[str, ...]
    text: str
    # PDFs have a stable page locator.  Other formats deliberately leave this
    # empty rather than manufacturing a page number.
    page: int | None = None


def _clean(value: str) -> str:
    lines = [re.sub(r"[\t\r\f\v ]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _decode(raw: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8-replace"


class _HTMLSections(HTMLParser):
    BLOCKS = {"p", "li", "pre", "blockquote", "td", "th", "dt", "dd"}
    IGNORED_CONTAINERS = {"script", "style", "noscript", "svg", "nav", "header", "footer", "aside", "form"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.headings: list[str] = []
        self.sections: list[Section] = []
        self._capture: str | None = None
        self._buffer: list[str] = []
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        tag = tag.casefold()
        if tag in self.IGNORED_CONTAINERS:
            self._ignored += 1
            return
        if self._ignored:
            return
        if re.fullmatch(r"h[1-6]", tag) or tag in self.BLOCKS:
            self._capture = tag
            self._buffer = []
        elif tag == "br" and self._capture:
            self._buffer.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in self.IGNORED_CONTAINERS and self._ignored:
            self._ignored -= 1
            return
        if self._ignored or self._capture != tag:
            return
        text = _clean("".join(self._buffer))
        if text and re.fullmatch(r"h[1-6]", tag):
            level = int(tag[1])
            self.headings = self.headings[: level - 1]
            while len(self.headings) < level - 1:
                self.headings.append("未命名章节")
            self.headings.append(text[:200])
        elif text:
            self.sections.append(Section(tuple(self.headings) or ("正文",), text))
        self._capture = None
        self._buffer = []

    def handle_data(self, data: str) -> None:
        if not self._ignored and self._capture:
            self._buffer.append(data)


def _parse_html(text: str) -> list[Section]:
    parser = _HTMLSections()
    parser.feed(text)
    parser.close()
    if parser.sections:
        return parser.sections
    fallback = _clean(re.sub(r"<[^>]+>", " ", text))
    return [Section(("正文",), fallback)] if fallback else []


def _xml_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_xml(text: str) -> list[Section]:
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise ValueError(f"XML正文无法解析：{exc}") from exc
    sections: list[Section] = []

    def visit(node: ElementTree.Element, path: tuple[str, ...]) -> None:
        tag = _xml_tag(node.tag)
        label = tag
        for child in node:
            if _xml_tag(child.tag).casefold() in {"title", "name", "id"}:
                candidate = _clean("".join(child.itertext()))
                if candidate:
                    label = f"{tag}: {candidate[:160]}"
                    break
        current = (*path, label)
        direct = _clean(node.text or "")
        if direct:
            sections.append(Section(current, direct))
        if not list(node):
            leaf = _clean("".join(node.itertext()))
            if leaf and leaf != direct:
                sections.append(Section(current, leaf))
        for child in node:
            visit(child, current)

    visit(root, ())
    return sections


def _parse_text(text: str) -> list[Section]:
    sections: list[Section] = []
    headings: list[str] = []
    pending: list[str] = []

    def flush() -> None:
        value = _clean("\n".join(pending))
        if value:
            sections.append(Section(tuple(headings) or ("正文",), value))
        pending.clear()

    for line in text.splitlines():
        match = re.match(r"^\s*(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush()
            level = len(match.group(1))
            headings[:] = headings[: level - 1]
            while len(headings) < level - 1:
                headings.append("未命名章节")
            headings.append(match.group(2)[:200])
        elif not line.strip():
            flush()
        else:
            pending.append(line)
    flush()
    return sections


def _parse_pdf(raw: bytes) -> list[Section]:
    """Extract one ordered section per PDF page.

    ``pypdf`` is used because it is pure Python and keeps the deployment
    lightweight.  The source PDF remains the immutable evidence; extracted
    text is only an indexable representation.  Scanned or encrypted papers
    therefore fail explicitly instead of being labelled as full text.
    """
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:  # pragma: no cover - requirements guarantees it
        raise ValueError("PDF解析依赖未安装：请安装 pypdf") from exc
    try:
        reader = PdfReader(BytesIO(raw))
        if reader.is_encrypted:
            raise ValueError("PDF已加密，无法提取正文")
        sections: list[Section] = []
        for number, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text(extraction_mode="layout") or ""
            except TypeError:  # Older pypdf versions have no layout option.
                text = page.extract_text() or ""
            text = _clean(text)
            if text:
                sections.append(Section((f"第 {number} 页",), text, page=number))
    except PdfReadError as exc:
        raise ValueError(f"PDF无法解析：{exc}") from exc
    if not sections:
        raise ValueError("PDF没有可提取文本（可能是扫描件或受保护文件），未入库为全文")
    return sections


def parse_document(raw: bytes, media_type: str) -> tuple[list[Section], str]:
    """Parse bytes into ordered sections and return the detected encoding."""
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError(f"正文超过 {MAX_INPUT_BYTES // 1024 // 1024}MB 限制")
    text, encoding = _decode(raw)
    kind = media_type.casefold().split(";", 1)[0]
    if kind in {"text/html", "application/xhtml+xml"}:
        sections = _parse_html(text)
    elif kind in {"application/xml", "text/xml", "application/atom+xml", "application/rss+xml"}:
        sections = _parse_xml(text)
    elif kind in {"text/plain", "text/markdown"}:
        sections = _parse_text(text)
    elif kind == "application/pdf":
        # Do not decode a binary PDF before extracting it.  Page text has its
        # own encoding inside the PDF and `_parse_pdf` handles that.
        sections = _parse_pdf(raw)
        encoding = "pdf-text"
    else:
        raise ValueError(f"不支持的正文类型：{media_type}")
    sections = [Section(s.path, _clean(s.text), page=s.page) for s in sections if _clean(s.text)]
    if not sections:
        raise ValueError("正文解析后没有可索引文本")
    return sections, encoding


def media_type_for_suffix(suffix: str) -> str:
    value = suffix.casefold().lstrip(".")
    mapping = {
        "html": "text/html", "htm": "text/html", "xhtml": "application/xhtml+xml",
        "xml": "application/xml", "atom": "application/atom+xml", "rss": "application/rss+xml",
        "txt": "text/plain", "md": "text/markdown", "markdown": "text/markdown",
        "pdf": "application/pdf",
    }
    if value not in mapping:
        raise ValueError(f"不支持的文件后缀：.{value}")
    return mapping[value]


def _stable_id(prefix: str, value: str, length: int = 24) -> str:
    return f"{prefix}-{storage.content_hash(value)[:length]}"


def _chunk_sections(
    sections: list[Section], *, version_id: str,
    max_chars: int = DEFAULT_CHUNK_CHARS, overlap: int = DEFAULT_OVERLAP_CHARS,
) -> tuple[str, list[dict[str, Any]]]:
    if max_chars < 100 or overlap < 0 or overlap >= max_chars:
        raise ValueError("chunk参数要求 max_chars>=100 且 0<=overlap<max_chars")
    full_parts: list[str] = []
    positions: list[tuple[Section, int]] = []
    cursor = 0
    for section in sections:
        if full_parts:
            full_parts.append("\n\n")
            cursor += 2
        positions.append((section, cursor))
        full_parts.append(section.text)
        cursor += len(section.text)
    extracted = "".join(full_parts)
    chunks: list[dict[str, Any]] = []
    ordinal = 0
    for section, base in positions:
        start = 0
        while start < len(section.text):
            end = min(len(section.text), start + max_chars)
            if end < len(section.text):
                boundary = max(section.text.rfind("\n", start + max_chars // 2, end),
                               section.text.rfind("。", start + max_chars // 2, end),
                               section.text.rfind(". ", start + max_chars // 2, end))
                if boundary > start:
                    end = boundary + 1
            chunk_text = section.text[start:end]
            absolute_start, absolute_end = base + start, base + end
            chunk_hash = storage.content_hash(chunk_text)
            identity = f"{version_id}\n{'/'.join(section.path)}\n{absolute_start}:{absolute_end}\n{chunk_hash}"
            chunks.append({
                "id": _stable_id("chunk", identity), "ordinal": ordinal,
                "section_path": list(section.path), "char_start": absolute_start,
                "char_end": absolute_end, "content_hash": chunk_hash, "text": chunk_text,
                "metadata": ({"page_start": section.page, "page_end": section.page}
                             if section.page is not None else {}),
            })
            ordinal += 1
            if end >= len(section.text):
                break
            start = max(start + 1, end - overlap)
    return extracted, chunks


def ingest_bytes(
    raw: bytes, *, source_id: str, document_key: str, title: str = "",
    canonical_url: str = "", media_type: str, snapshot_hash: str | None = None,
    original_path: str | None = None, metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not SAFE_SOURCE.fullmatch(source_id):
        raise ValueError("source_id只能包含字母、数字、点、下划线和连字符")
    document_key = document_key.strip()
    if not document_key or len(document_key) > 500:
        raise ValueError("document_key不能为空且不能超过500字符")
    raw_hash = storage.content_hash(raw)
    sections, encoding = parse_document(raw, media_type)
    document_id = _stable_id("doc", f"{source_id}\n{document_key}")
    version_id = _stable_id("ver", f"{document_id}\n{raw_hash}\n{PARSER_VERSION}")
    extracted, chunks = _chunk_sections(sections, version_id=version_id)
    extracted_hash = storage.content_hash(extracted)
    now = storage.utcnow()
    provenance = {
        "source_id": source_id, "snapshot_hash": snapshot_hash,
        "original_path": original_path, "encoding": encoding,
        "parser_version": PARSER_VERSION,
    }
    with storage.connect() as conn:
        existing = conn.execute(
            "SELECT id FROM rag_document_versions WHERE id = ?", (version_id,)
        ).fetchone()
        current = conn.execute("SELECT metadata FROM rag_documents WHERE id = ?", (document_id,)).fetchone()
        merged_metadata = json.loads(current["metadata"]) if current else {}
        merged_metadata.update(metadata or {})
        conn.execute(
            """INSERT INTO rag_documents
               (id, source_id, document_key, title, canonical_url, current_version_id,
                created_at, updated_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 title=CASE WHEN excluded.title <> '' THEN excluded.title ELSE rag_documents.title END,
                 canonical_url=CASE WHEN excluded.canonical_url <> '' THEN excluded.canonical_url ELSE rag_documents.canonical_url END,
                 current_version_id=excluded.current_version_id, updated_at=excluded.updated_at,
                 metadata=excluded.metadata""",
            (document_id, source_id, document_key, title, canonical_url, version_id,
             now, now, json.dumps(merged_metadata, ensure_ascii=False)),
        )
        conn.execute(
            """INSERT OR IGNORE INTO rag_document_versions
               (id, document_id, content_hash, extracted_hash, media_type, parser_version,
                snapshot_hash, original_path, created_at, extracted_text, provenance)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (version_id, document_id, raw_hash, extracted_hash, media_type, PARSER_VERSION,
             snapshot_hash, original_path, now, extracted,
             json.dumps(provenance, ensure_ascii=False)),
        )
        for chunk in chunks:
            conn.execute(
                """INSERT OR IGNORE INTO rag_chunks
                   (id, document_id, version_id, ordinal, section_path, char_start,
                    char_end, content_hash, text, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (chunk["id"], document_id, version_id, chunk["ordinal"],
                 json.dumps(chunk["section_path"], ensure_ascii=False), chunk["char_start"],
                 chunk["char_end"], chunk["content_hash"], chunk["text"],
                 json.dumps(chunk.get("metadata") or {}, ensure_ascii=False)),
            )
    return {
        "document_id": document_id, "version_id": version_id,
        "version_created": existing is None, "content_hash": raw_hash,
        "extracted_hash": extracted_hash, "parser_version": PARSER_VERSION,
        "sections": len(sections), "chunks": len(chunks), "characters": len(extracted),
    }


def _find_snapshot(source_id: str, digest: str, suffix: str | None) -> Path:
    if not SAFE_SOURCE.fullmatch(source_id) or not SAFE_HASH.fullmatch(digest):
        raise ValueError("非法的快照来源或SHA-256")
    directory = config.SNAPSHOT_DIR / source_id
    if suffix:
        safe_suffix = suffix.casefold().lstrip(".")
        if not re.fullmatch(r"[a-z0-9]{1,12}", safe_suffix):
            raise ValueError("非法的快照后缀")
        candidates = [directory / f"{digest}.{safe_suffix}"]
    else:
        candidates = sorted(directory.glob(f"{digest}.*")) if directory.exists() else []
    existing = [path for path in candidates if path.is_file()]
    if len(existing) != 1:
        raise FileNotFoundError("没有找到唯一匹配的原始快照，请提供suffix")
    return existing[0]


def ingest_snapshot(
    *, source_id: str, snapshot_hash: str, suffix: str | None = None,
    document_key: str | None = None, title: str = "", canonical_url: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = _find_snapshot(source_id, snapshot_hash, suffix)
    raw = path.read_bytes()
    if storage.content_hash(raw) != snapshot_hash.casefold():
        raise ValueError("快照文件内容与文件名中的SHA-256不一致，拒绝入库")
    return ingest_bytes(
        raw, source_id=source_id,
        document_key=document_key or f"source:{source_id}", title=title,
        canonical_url=canonical_url, media_type=media_type_for_suffix(path.suffix),
        snapshot_hash=snapshot_hash, metadata=metadata,
    )


def ingest_local_file(
    path: str, *, source_id: str = "local", document_key: str | None = None,
    title: str = "", canonical_url: str = "", metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("指定路径不是文件")
    raw = resolved.read_bytes()
    media_type = media_type_for_suffix(resolved.suffix)
    snapshot_hash = storage.save_snapshot("rag_local", raw, suffix=resolved.suffix.lstrip("."))
    return ingest_bytes(
        raw, source_id=source_id, document_key=document_key or str(resolved).casefold(),
        title=title or resolved.name, canonical_url=canonical_url, media_type=media_type,
        snapshot_hash=snapshot_hash, original_path=str(resolved), metadata=metadata,
    )


def ingest_latest_snapshots(
    *, source_ids: list[str] | None = None, limit: int = 3,
) -> dict[str, Any]:
    """Ingest up to ``limit`` real payloads referenced by source_state.last_hash.

    Unsupported snapshots (currently JSON and binaries) are reported as
    skipped.  We never substitute an event summary when the original snapshot
    cannot be parsed as full text.
    """
    if not 1 <= limit <= 20:
        raise ValueError("limit必须在1到20之间")
    requested = set(source_ids or [])
    if any(not SAFE_SOURCE.fullmatch(item) for item in requested):
        raise ValueError("source_ids中存在非法值")
    states = list(storage.all_source_states().values())
    states.sort(key=lambda item: item.get("last_success") or "", reverse=True)
    if requested:
        states = [state for state in states if state.get("id") in requested]
    results: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    for state in states:
        if len(results) >= limit:
            break
        source_id = str(state.get("id") or "")
        digest = str(state.get("last_hash") or "")
        if not digest:
            skipped.append({"source_id": source_id, "reason": "source_state没有last_hash"})
            continue
        try:
            path = _find_snapshot(source_id, digest, None)
            media_type_for_suffix(path.suffix)
            result = ingest_snapshot(
                source_id=source_id, snapshot_hash=digest,
                suffix=path.suffix, document_key=f"source:{source_id}",
                title=source_id, metadata={"ingestion": "source_state.last_hash"},
            )
            results.append({"source_id": source_id, "snapshot_hash": digest, **result})
        except (FileNotFoundError, OSError, ValueError) as exc:
            skipped.append({"source_id": source_id, "reason": str(exc)})
    return {
        "requested_limit": limit, "ingested": len(results), "items": results,
        "skipped": skipped,
        "note": "仅入库source_state.last_hash指向的真实原始快照；不以事件摘要替代正文。",
    }


def list_documents(limit: int = 100) -> list[dict[str, Any]]:
    with storage.connect() as conn:
        rows = conn.execute(
            """SELECT d.*, COUNT(v.id) AS version_count,
                      (SELECT COUNT(*) FROM rag_chunks c WHERE c.version_id=d.current_version_id) AS chunk_count
               FROM rag_documents d LEFT JOIN rag_document_versions v ON v.document_id=d.id
               GROUP BY d.id ORDER BY d.updated_at DESC LIMIT ?""", (limit,),
        ).fetchall()
        items = []
        for row in rows:
            chunks = conn.execute(
                """SELECT id AS chunk_id, document_id, section_path, char_start, char_end,
                          text, content_hash, metadata
                     FROM rag_chunks WHERE version_id=? ORDER BY ordinal LIMIT 8""",
                (row["current_version_id"],),
            ).fetchall()
            normalized_chunks = [
                {**dict(chunk), "section_path": json.loads(chunk["section_path"]),
                 "metadata": json.loads(chunk["metadata"])}
                for chunk in chunks
            ]
            sections = list(dict.fromkeys(
                " / ".join(chunk["section_path"])
                for chunk in normalized_chunks if chunk["section_path"]
            ))
            items.append({
                **dict(row), "metadata": json.loads(row["metadata"]),
                "content_scope": "fulltext", "has_full_text": True,
                "category": "全文资料", "chunks": normalized_chunks,
                "sections": [{"title": section} for section in sections],
                "section_count": len(sections),
            })
    return items


def get_document(document_id: str) -> dict[str, Any] | None:
    with storage.connect() as conn:
        row = conn.execute("SELECT * FROM rag_documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            return None
        versions = conn.execute(
            """SELECT id, content_hash, extracted_hash, media_type, parser_version,
                      snapshot_hash, original_path, created_at, provenance,
                      (SELECT COUNT(*) FROM rag_chunks c WHERE c.version_id=v.id) AS chunk_count
               FROM rag_document_versions v WHERE document_id=? ORDER BY created_at DESC, id DESC""",
            (document_id,),
        ).fetchall()
    result = {**dict(row), "metadata": json.loads(row["metadata"])}
    result["versions"] = [
        {**dict(item), "provenance": json.loads(item["provenance"])} for item in versions
    ]
    return result


def get_chunk(chunk_id: str) -> dict[str, Any] | None:
    with storage.connect() as conn:
        row = conn.execute("SELECT * FROM rag_chunks WHERE id = ?", (chunk_id,)).fetchone()
    if not row:
        return None
    return {**dict(row), "section_path": json.loads(row["section_path"]),
            "metadata": json.loads(row["metadata"])}


def list_chunk_records(*, current_only: bool = True, limit: int = 5000) -> list[dict[str, Any]]:
    """Return the plain-record contract consumed by ``app.rag``.

    Character ranges address ``rag_document_versions.extracted_text``;
    consequently ``snapshot_hash`` is the extracted-text hash, while the raw
    upstream payload hash remains available in metadata.
    """
    where = "WHERE c.version_id=d.current_version_id" if current_only else ""
    with storage.connect() as conn:
        rows = conn.execute(
            f"""SELECT c.*, d.title, d.source_id, d.canonical_url,
                       v.extracted_hash, v.content_hash AS upstream_content_hash,
                       v.parser_version, v.provenance
                FROM rag_chunks c
                JOIN rag_documents d ON d.id=c.document_id
                JOIN rag_document_versions v ON v.id=c.version_id
                {where} ORDER BY d.updated_at DESC, c.ordinal LIMIT ?""",
            (max(1, min(limit, 20000)),),
        ).fetchall()
    records: list[dict[str, Any]] = []
    for row in rows:
        provenance = json.loads(row["provenance"])
        records.append({
            "document_id": row["document_id"], "chunk_id": row["id"],
            "text": row["text"], "char_start": row["char_start"],
            "char_end": row["char_end"], "snapshot_hash": row["extracted_hash"],
            "snapshot_origin": "parsed_document_text_sha256",
            "source_id": row["source_id"], "title": row["title"],
            "url": row["canonical_url"], "provenance": "fulltext",
            "corpus_class": "collected_source" if row["source_id"] != "local" else "local_file",
            "metadata": {
                "version_id": row["version_id"],
                "section_path": json.loads(row["section_path"]),
                "chunk_content_hash": row["content_hash"],
                "upstream_content_hash": row["upstream_content_hash"],
                "parser_version": row["parser_version"],
                "upstream_snapshot_hash": provenance.get("snapshot_hash"),
                **json.loads(row["metadata"]),
            },
        })
    return records


class SearchIndex(Protocol):
    def search(self, query: str, *, limit: int = 10, current_only: bool = True) -> list[dict[str, Any]]: ...


def _terms(text: str) -> list[str]:
    lowered = text.casefold()
    words = re.findall(r"[a-z0-9][a-z0-9_.:+/-]{1,}|[\u3400-\u9fff]+", lowered)
    result: list[str] = []
    for word in words:
        if re.fullmatch(r"[\u3400-\u9fff]+", word) and len(word) > 2:
            result.extend(word[index:index + 2] for index in range(len(word) - 1))
        else:
            result.append(word)
    return list(dict.fromkeys(term for term in result if term.strip()))


class KeywordIndex:
    """Dependency-free baseline implementing the replaceable search contract."""

    def search(self, query: str, *, limit: int = 10, current_only: bool = True) -> list[dict[str, Any]]:
        terms = _terms(query)
        if not terms:
            return []
        where = "WHERE c.version_id=d.current_version_id" if current_only else ""
        with storage.connect() as conn:
            rows = conn.execute(
                f"""SELECT c.*, d.title, d.source_id, d.canonical_url
                     FROM rag_chunks c JOIN rag_documents d ON d.id=c.document_id
                     {where} ORDER BY d.updated_at DESC, c.ordinal LIMIT 5000"""
            ).fetchall()
        documents_with_term = {
            term: sum(1 for row in rows if term in (row["text"] or "").casefold()) for term in terms
        }
        scored: list[tuple[float, Any]] = []
        for row in rows:
            body = (row["text"] or "").casefold()
            title = (row["title"] or "").casefold()
            score = 0.0
            for term in terms:
                frequency = body.count(term)
                if not frequency and term not in title:
                    continue
                inverse = math.log((len(rows) + 1) / (documents_with_term[term] + 1)) + 1
                score += (1 + math.log(max(1, frequency))) * inverse
                if term in title:
                    score += 1.5 * inverse
            if query.casefold() in body:
                score += 3.0
            if score:
                scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1]["id"]))
        return [{
            "chunk_id": row["id"], "document_id": row["document_id"],
            "version_id": row["version_id"], "source_id": row["source_id"],
            "title": row["title"], "canonical_url": row["canonical_url"],
            "section_path": json.loads(row["section_path"]),
            "char_start": row["char_start"], "char_end": row["char_end"],
            "content_hash": row["content_hash"], "text": row["text"],
            "score": round(score, 6), "index": "keyword-v1",
        } for score, row in scored[:limit]]


_search_index: SearchIndex = KeywordIndex()


def set_search_index(index: SearchIndex) -> None:
    global _search_index
    _search_index = index


def search(query: str, *, limit: int = 10, current_only: bool = True) -> list[dict[str, Any]]:
    return _search_index.search(query, limit=limit, current_only=current_only)
