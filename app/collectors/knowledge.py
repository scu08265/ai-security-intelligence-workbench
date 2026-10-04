"""Collectors for the knowledge-base layer: papers, standards and policy.

These feed the corpus the competition asks for alongside vulnerability
monitoring, but they are *background* material rather than vulnerability
events, so they are stored as `kind="knowledge"` and counted separately.
A preprint is labelled `preprint`; it is not presented as a peer-reviewed
finding.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any

from .. import normalize, rag_corpus, storage
from ..sources import SourceSpec
from . import CollectOutcome, FetchError, curl_text, http_request, record_snapshot

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_MAX_RESULTS = 40
ARXIV_ACCEPT = "application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.1"
OPENALEX_MAX_RESULTS = 50
OPENALEX_QUERY = (
    "prompt injection OR adversarial machine learning OR model poisoning "
    "OR large language model security OR AI agent security "
    "OR model extraction OR membership inference OR supply chain attack"
)

# AI-security oriented arXiv query: category-bounded, then topic-filtered.
ARXIV_QUERY = (
    '(cat:cs.CR OR cat:cs.LG OR cat:cs.AI) AND '
    '(abs:"prompt injection" OR abs:"adversarial example" OR abs:"model poisoning" '
    'OR (abs:"large language model" AND abs:security) OR abs:"membership inference" '
    'OR abs:"jailbreak" OR abs:"AI agent security" OR abs:"supply chain attack" '
    'OR abs:"model extraction" OR abs:"backdoor attack")'
)

_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_BLOCK = re.compile(r"</(p|div|li|h[1-6]|tr|section|article)>", re.I)
_ALL_TAGS = re.compile(r"<[^>]+>")
PAGE_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _strip_html(html: str) -> str:
    text = _TAG.sub(" ", html)
    text = _BLOCK.sub("\n", text)
    text = _ALL_TAGS.sub(" ", text)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
        .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    )
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


# --------------------------------------------------------------------------
# arXiv
# --------------------------------------------------------------------------

def collect_arxiv(spec: SourceSpec, since: str | None) -> CollectOutcome:
    outcome = CollectOutcome(source_id=spec.id, status="ok", cursor=_now().isoformat(timespec="milliseconds"))
    params = {
        "search_query": ARXIV_QUERY,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": ARXIV_MAX_RESULTS,
    }
    response = http_request(
        "GET", spec.url, params=params, timeout=60,
        headers={"Accept": ARXIV_ACCEPT},
    )
    if response.status_code >= 400:
        raise FetchError(f"HTTP {response.status_code}")
    raw = response.text
    outcome.snapshot_hash = record_snapshot(spec.id, raw, suffix="xml")

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise FetchError(f"arXiv 返回的 XML 无法解析：{exc}") from exc

    cutoff = _parse_iso(since) or (_now() - timedelta(days=14))
    entries = root.findall(f"{ATOM}entry")
    outcome.fetched = len(entries)
    skipped_old = 0
    for entry in entries:
        published = _parse_iso(entry.findtext(f"{ATOM}published"))
        if published and published < cutoff:
            skipped_old += 1
            continue
        record = {
            "id": entry.findtext(f"{ATOM}id"),
            "title": entry.findtext(f"{ATOM}title"),
            "summary": entry.findtext(f"{ATOM}summary"),
            "published": entry.findtext(f"{ATOM}published"),
            "link": entry.findtext(f"{ATOM}id"),
            "categories": [
                c.get("term") for c in entry.findall(f"{ATOM}category") if c.get("term")
            ],
            "primary_category": (
                entry.find(f"{ATOM}primary_category").get("term")
                if entry.find(f"{ATOM}primary_category") is not None else None
            ),
        }
        event = normalize.arxiv_entry_to_event(record)
        if event is None or not (event.get("ai_relevance") or {}).get("included"):
            outcome.filtered += 1
            continue
        # This is only a *candidate* full-text location.  It is visible as
        # pending until the separate, bounded paper tool has downloaded and
        # parsed a real PDF; an abstract must never be presented as full text.
        raw_id = str(record.get("id") or "").strip()
        arxiv_id = re.sub(r"^https?://(?:www\.)?arxiv\.org/abs/", "", raw_id).strip("/")
        if re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?", arxiv_id, re.I):
            event["paper"] = {
                "arxiv_id": arxiv_id,
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}",
                "full_text": {"status": "not_attempted", "has_full_text": False},
            }
        outcome.events.append(event)
    outcome.notes.append(
        f"arXiv 查询返回 {outcome.fetched} 条：{skipped_old} 条早于窗口起点 {cutoff:%Y-%m-%d}，"
        f"{outcome.filtered} 条判定与 AI 无关，{len(outcome.events)} 条入库"
    )
    return outcome


# --------------------------------------------------------------------------
# OpenAlex
# --------------------------------------------------------------------------

def collect_openalex(spec: SourceSpec, since: str | None) -> CollectOutcome:
    """Collect AI-security papers from OpenAlex without requiring a token."""
    outcome = CollectOutcome(source_id=spec.id, status="ok", cursor=_now().isoformat(timespec="milliseconds"))
    cutoff = _parse_iso(since) or (_now() - timedelta(days=30))
    params = {
        "search": OPENALEX_QUERY,
        "filter": f"from_publication_date:{cutoff.date().isoformat()},is_retracted:false",
        "sort": "publication_date:desc",
        "per-page": OPENALEX_MAX_RESULTS,
    }
    mailto = os.getenv("OPENALEX_MAILTO", "").strip()
    if mailto:
        params["mailto"] = mailto
    response = http_request(
        "GET", spec.url, params=params, timeout=60,
        headers={"Accept": "application/json"},
    )
    if response.status_code >= 400:
        raise FetchError(f"HTTP {response.status_code}")
    raw = response.text
    outcome.snapshot_hash = record_snapshot(spec.id, raw, suffix="json")
    try:
        payload = response.json()
    except ValueError as exc:
        raise FetchError(f"OpenAlex 响应不是有效 JSON：{exc}") from exc

    works = payload.get("results") or []
    outcome.fetched = len(works)
    for work in works:
        event = normalize.openalex_work_to_event(work)
        if event is None or not (event.get("ai_relevance") or {}).get("included"):
            outcome.filtered += 1
            continue
        outcome.events.append(event)
    outcome.notes.append(
        f"OpenAlex 查询返回 {outcome.fetched} 条，"
        f"{outcome.filtered} 条判定与 AI 安全无关，{len(outcome.events)} 条入库"
    )
    return outcome


# --------------------------------------------------------------------------
# RSS / Atom feeds
# --------------------------------------------------------------------------

def collect_rss(spec: SourceSpec, since: str | None) -> CollectOutcome:
    outcome = CollectOutcome(source_id=spec.id, status="ok", cursor=_now().isoformat(timespec="milliseconds"))
    if spec.id == "freebuf":
        # Aliyun WAF fingerprints httpx/OpenSSL and returns a JavaScript shell.
        # The system curl client is accepted by the same upstream endpoint.
        raw = curl_text(spec.url, timeout=45)
    else:
        response = http_request("GET", spec.url, timeout=45)
        if response.status_code >= 400:
            raise FetchError(f"HTTP {response.status_code}")
        raw = response.text
    outcome.snapshot_hash = record_snapshot(spec.id, raw, suffix="xml")

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise FetchError(f"订阅源返回的 XML 无法解析：{exc}") from exc

    items = root.findall(".//item") or root.findall(f".//{ATOM}entry")
    outcome.fetched = len(items)
    lookback = getattr(spec, "lookback_days", 30) or 30
    cutoff = _parse_iso(since) or (_now() - timedelta(days=lookback))
    kept = 0
    skipped_old = 0
    for item in items:
        published_raw = (
            item.findtext("pubDate") or item.findtext(f"{ATOM}published")
            or item.findtext(f"{ATOM}updated")
        )
        published = _parse_iso(published_raw) or _parse_rfc822(published_raw)
        if published and published < cutoff:
            skipped_old += 1
            continue
        link = item.findtext("link")
        if not link:
            link_el = item.find(f"{ATOM}link")
            link = link_el.get("href") if link_el is not None else None
        record = {
            "id": item.findtext("guid") or item.findtext(f"{ATOM}id") or link,
            "title": item.findtext("title") or (
                item.findtext(f"{ATOM}title")
            ),
            "summary": item.findtext("description") or item.findtext(f"{ATOM}summary"),
            "link": link,
            "published": published_raw,
        }
        event = normalize.feed_entry_to_event(
            record, source_key=spec.id, publisher=spec.name, trust=spec.trust,
            tags=[spec.category],
        )
        if event is None or not (event.get("ai_relevance") or {}).get("included"):
            outcome.filtered += 1
            continue
        outcome.events.append(event)
        kept += 1
    outcome.notes.append(
        f"订阅源返回 {outcome.fetched} 条：{skipped_old} 条早于窗口起点 {cutoff:%Y-%m-%d}，"
        f"{outcome.filtered} 条判定与 AI 无关，{kept} 条入库"
    )
    return outcome


def _parse_rfc822(value: str | None) -> datetime | None:
    if not value:
        return None
    from email.utils import parsedate_to_datetime

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# Single pages (standards)
# --------------------------------------------------------------------------

def collect_page(spec: SourceSpec, since: str | None) -> CollectOutcome:
    """Fetch one registered page and record it only when its content changed."""
    outcome = CollectOutcome(source_id=spec.id, status="ok")
    response = http_request("GET", spec.url, timeout=45, headers=PAGE_BROWSER_HEADERS)
    if response.status_code >= 400:
        raise FetchError(f"HTTP {response.status_code}")
    raw = response.text
    outcome.fetched = 1
    outcome.snapshot_hash = record_snapshot(spec.id, raw, suffix="html")

    text = _strip_html(raw)
    title_match = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
    title = _strip_html(title_match.group(1)).strip() if title_match else spec.name
    if not text:
        outcome.status = "failed"
        outcome.error = "页面正文为空，未生成事件"
        return outcome

    state = storage.source_state(spec.id)
    previous = state.get("last_hash")
    if previous and previous == outcome.snapshot_hash and int(state.get("events_count") or 0) > 0:
        outcome.notes.append("内容哈希与上次一致，未产生新事件")
        return outcome

    event = normalize.page_to_event(
        source_key=spec.id, url=spec.url, title=title or spec.name,
        text=text, publisher=spec.name, trust=spec.trust, tags=[spec.category],
    )
    if (event.get("ai_relevance") or {}).get("included"):
        outcome.events.append(event)
        outcome.notes.append(f"页面内容较上次发生变化（{len(text)} 字符），已生成知识条目")
    else:
        outcome.filtered += 1
        outcome.notes.append(
            f"页面内容较上次发生变化（{len(text)} 字符），但未命中 AI 安全相关术语，未入库"
        )
    return outcome


def collect_document(spec: SourceSpec, since: str | None) -> CollectOutcome:
    """Collect a fixed official PDF, preserve its bytes, and index full text."""
    outcome = CollectOutcome(source_id=spec.id, status="ok")
    response = http_request(
        "GET", spec.url, timeout=90,
        headers={
            **PAGE_BROWSER_HEADERS,
            "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        },
    )
    if response.status_code >= 400:
        raise FetchError(f"HTTP {response.status_code}")
    raw = response.content
    if not raw:
        raise FetchError("官方文档响应为空")
    outcome.fetched = 1
    outcome.snapshot_hash = storage.save_snapshot(spec.id, raw, suffix="pdf")
    try:
        sections, _encoding = rag_corpus.parse_document(raw, "application/pdf")
    except (OSError, ValueError) as exc:
        raise FetchError(f"官方 PDF 无法解析：{exc}") from exc
    text = "\n\n".join(section.text for section in sections if section.text).strip()
    if not text:
        raise FetchError("官方 PDF 未提取出可检索正文")
    event = normalize.page_to_event(
        source_key=spec.id, url=spec.url, title=spec.name,
        text=text, publisher=spec.name, trust=spec.trust, tags=[spec.category],
    )
    ingestion = rag_corpus.ingest_bytes(
        raw, source_id=spec.id, document_key=f"official:{spec.id}",
        title=spec.name, canonical_url=spec.url, media_type="application/pdf",
        snapshot_hash=outcome.snapshot_hash,
        metadata={"source_type": "official_policy", "mode": "pdf"},
    )
    event["document_ingestion"] = {
        key: ingestion[key]
        for key in ("document_id", "version_id", "chunks", "characters", "sections")
    }
    if (event.get("ai_relevance") or {}).get("included"):
        outcome.events.append(event)
    else:
        outcome.filtered += 1
    outcome.notes.append(
        f"官方 PDF 已保存并提取 {ingestion['characters']} 字符、"
        f"{ingestion['sections']} 个章节、{ingestion['chunks']} 个检索块"
    )
    return outcome
