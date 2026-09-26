"""Bounded, evidence-preserving full-text ingestion for collected arXiv papers.

This is deliberately a narrow tool.  It resolves only a canonical arXiv
identifier from an already collected record and downloads only from arxiv.org.
It never follows an arbitrary paper, DOI, or user supplied URL.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from . import rag_corpus, storage
from .collectors import FetchError, http_request

ARXIV_HOSTS = {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}
ARXIV_ID_RE = re.compile(
    r"^(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?$", re.I
)
ARXIV_PATH_RE = re.compile(
    r"^/(?:abs|pdf)/(?P<identifier>(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?)(?:\.pdf)?/?$",
    re.I,
)
DEFAULT_MAX_PAPERS_PER_RUN = 5


def arxiv_identifier(value: str) -> str | None:
    """Return a validated arXiv identifier from an ID or arxiv URL.

    A URL on another host is always rejected, including look-alike hosts.  An
    arXiv identifier without a URL is allowed because it originates from the
    registered Atom feed rather than user input.
    """
    candidate = str(value or "").strip()
    if not candidate:
        return None
    if ARXIV_ID_RE.fullmatch(candidate):
        return candidate
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in ARXIV_HOSTS:
        return None
    match = ARXIV_PATH_RE.fullmatch(parsed.path)
    return match.group("identifier") if match else None


def _paper_identity(event: dict[str, Any]) -> str | None:
    paper = event.get("paper") or {}
    for candidate in (paper.get("arxiv_id"), paper.get("pdf_url")):
        identifier = arxiv_identifier(str(candidate or ""))
        if identifier:
            return identifier
    for source in event.get("sources") or []:
        identifier = arxiv_identifier(str((source or {}).get("url") or ""))
        if identifier:
            return identifier
    for candidate in event.get("references") or []:
        identifier = arxiv_identifier(str(candidate or ""))
        if identifier:
            return identifier
    return None


def canonical_urls(identifier: str) -> tuple[str, str]:
    """Make the only two URLs this tool is allowed to fetch/reference."""
    verified = arxiv_identifier(identifier)
    if not verified:
        raise ValueError("不是有效的 arXiv 标识符")
    return (f"https://arxiv.org/abs/{verified}", f"https://arxiv.org/pdf/{verified}")


def ingest_arxiv_paper(event: dict[str, Any]) -> dict[str, Any]:
    """Download and index one collected arXiv PDF, returning an auditable result.

    A raw PDF is snapshotted before parsing.  `status=fulltext` is returned
    only after page text was successfully extracted and versioned.  Failed,
    scanned, encrypted, or malformed files leave no RAG document behind.
    """
    identifier = _paper_identity(event)
    attempted_at = storage.utcnow()
    if not identifier:
        return {
            "status": "failed", "has_full_text": False, "attempted_at": attempted_at,
            "reason": "采集记录没有可验证的 arXiv 标识符，未请求任何外部地址",
        }
    abstract_url, pdf_url = canonical_urls(identifier)
    base = {
        "arxiv_id": identifier, "abstract_url": abstract_url, "pdf_url": pdf_url,
        "attempted_at": attempted_at,
    }
    try:
        response = http_request(
            "GET", pdf_url, timeout=60,
            headers={"Accept": "application/pdf"},
        )
        if response.status_code >= 400:
            return {**base, "status": "failed", "has_full_text": False,
                    "reason": f"PDF下载失败：HTTP {response.status_code}"}
        raw = response.content
        if not raw.startswith(b"%PDF-"):
            return {**base, "status": "failed", "has_full_text": False,
                    "reason": "下载结果不是PDF文件，未入库为全文"}
        snapshot_hash = storage.save_snapshot("arxiv", raw, suffix="pdf")
        ingestion = rag_corpus.ingest_bytes(
            raw, source_id="arxiv", document_key=f"paper:{identifier}",
            title=str(event.get("title") or identifier), canonical_url=abstract_url,
            media_type="application/pdf", snapshot_hash=snapshot_hash,
            metadata={
                "document_type": "academic_paper", "content_scope": "fulltext",
                "publisher": "arXiv", "arxiv_id": identifier, "pdf_url": pdf_url,
                "source_event_id": event.get("id"),
            },
        )
        return {
            **base, "status": "fulltext", "has_full_text": True,
            "snapshot_hash": snapshot_hash, "media_type": "application/pdf",
            "locator": "page + extracted-text character range",
            **ingestion,
        }
    except (FetchError, OSError, ValueError) as exc:
        # `snapshot_hash` is deliberately absent if parsing failed: a caller
        # can still see a raw snapshot only when one was actually created.
        return {**base, "status": "failed", "has_full_text": False,
                "reason": f"PDF全文未入库：{type(exc).__name__}: {exc}"}


def annotate_event(event: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Attach visible ingestion state to a stored paper without hiding failure."""
    updated = dict(event)
    paper = dict(updated.get("paper") or {})
    paper.update({
        "arxiv_id": result.get("arxiv_id") or paper.get("arxiv_id"),
        "pdf_url": result.get("pdf_url") or paper.get("pdf_url"),
        "full_text": {
            key: result.get(key) for key in (
                "status", "has_full_text", "attempted_at", "reason", "snapshot_hash",
                "document_id", "version_id", "chunks", "characters", "locator",
            ) if result.get(key) is not None
        },
    })
    updated["paper"] = paper
    return updated


def ingest_arxiv_papers(events: list[dict[str, Any]], *, limit: int = DEFAULT_MAX_PAPERS_PER_RUN) -> list[dict[str, Any]]:
    """Run the paper tool under a strict per-run budget and deduplicate IDs."""
    if not 1 <= limit <= 20:
        raise ValueError("论文全文采集数量必须在1到20之间")
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in events:
        identifier = _paper_identity(event)
        if not identifier or identifier in seen:
            continue
        seen.add(identifier)
        results.append(ingest_arxiv_paper(event))
        if len(results) >= limit:
            break
    return results
