"""Small, auditable retrieval layer for source documents.

The rest of the application stores normalized events as JSON.  This module
projects those events into immutable text documents and chunks at query time,
so P1 retrieval does not require a storage migration.  A citation always
points at the exact string searched: document id, chunk id, character range,
verbatim quote and SHA-256 snapshot hash travel together.

The built-in ranker is deliberately deterministic BM25 plus identifier and
phrase bonuses.  ``reranker`` is a replaceable interface; a future embedding
or cross-encoder implementation can be plugged in without changing citation
or refusal semantics.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field, replace
from typing import Any, Callable, Iterable, Protocol, Sequence


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


_EXPANSIONS = {
    "提示词注入": ("prompt", "injection"),
    "远程代码执行": ("remote", "code", "execution", "rce"),
    "拒绝服务": ("denial", "service", "dos"),
    "修复": ("fix", "fixed", "patched", "remediation"),
    "缓解": ("mitigation", "remediation"),
    "漏洞": ("vulnerability", "cve"),
    "供应链": ("supply", "chain"),
    "检测": ("detect", "detects", "detection", "identify", "monitor"),
    "标题": ("title", "paper", "study"),
    "论文": ("paper", "study", "arxiv"),
    "模型": ("model", "models"),
    "攻击": ("attack", "attacks"),
    "风险": ("risk", "risks"),
    "资产": ("asset", "assets"),
}

_GENERIC_SECURITY_TERMS = {
    "vulnerability", "cve", "fix", "fixed", "patched", "remediation",
    "mitigation", "security", "risk",
}

_EXPANSION_REQUIREMENTS = {
    "提示词注入": (("prompt",), ("injection",)),
    "远程代码执行": (("remote",), ("code", "execution", "rce")),
    "拒绝服务": (("denial",), ("service", "dos")),
}


def terms(value: str) -> list[str]:
    """Tokenize mixed Chinese/English security text without external models."""
    lowered = _text(value).casefold()
    # '.', ':', '/', '+', '-', '_' 允许出现在词**内部**（0.28.0、cve-2026-41106、
    # vllm-project/vllm），但不允许挂在词尾。正文标题里的 "JevOut:" 会被切成
    # "jevout:"，与查询中的 "jevout" 永远对不上——该专名因此检索不到。
    tokens = [
        stripped
        for stripped in (raw.strip("_.:/+-") for raw in re.findall(r"[a-z0-9][a-z0-9_.:/+-]*", lowered))
        if stripped
    ]
    for phrase, additions in _EXPANSIONS.items():
        if phrase in lowered:
            tokens.extend(additions)
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", lowered)
    for run in chinese_runs:
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[index:index + 2] for index in range(len(run) - 1))
    return tokens


@dataclass(frozen=True)
class Document:
    document_id: str
    text: str
    title: str = ""
    source_id: str = ""
    url: str = ""
    snapshot_hash: str = ""
    snapshot_origin: str = "derived_document_text"
    provenance: str = "unknown"
    corpus_class: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.document_id:
            raise ValueError("document_id is required")
        if not self.text:
            raise ValueError("document text is required")
        if not self.snapshot_hash:
            object.__setattr__(self, "snapshot_hash", _sha256(self.text))


@dataclass(frozen=True)
class Chunk:
    document_id: str
    chunk_id: str
    text: str
    char_start: int
    char_end: int
    snapshot_hash: str
    snapshot_origin: str
    source_id: str = ""
    title: str = ""
    url: str = ""
    provenance: str = "unknown"
    corpus_class: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    score: float
    matched_terms: tuple[str, ...] = ()
    rank: int = 0


class Reranker(Protocol):
    def __call__(self, query: str, hits: Sequence[SearchHit]) -> Sequence[SearchHit]: ...


def _corpus_class(event: dict, source: dict) -> str:
    explicit = _text(source.get("corpus_class") or event.get("corpus_class"))
    if explicit:
        return explicit
    url = _text(source.get("url"))
    if event.get("is_demo") or source.get("is_demo") or source.get("trust") == "fixture" or ".invalid" in url:
        return "synthetic"
    return "collected_source"


def events_to_documents(events: Iterable[dict]) -> list[Document]:
    """Project normalized events to independently citable source documents.

    ``sources[].excerpt`` is the verbatim upstream text guaranteed by the
    normalizer.  Explicit ``documents``/``full_text`` fields are also accepted
    for the forthcoming full-text ingestion step.  Summaries are used only
    when an event has no source text at all and are labelled normalized data.
    """
    documents: list[Document] = []
    for event in events or []:
        event_id = _text(event.get("id"))
        title = _text(event.get("title"))
        explicit_docs = event.get("documents") or []
        for index, item in enumerate(explicit_docs):
            body = _text(item.get("text") or item.get("content") or item.get("full_text"))
            if not body:
                continue
            document_id = _text(item.get("document_id") or item.get("id")) or f"{event_id}:document:{index}"
            supplied_hash = _text(item.get("snapshot_hash"))
            documents.append(Document(
                document_id=document_id, text=body,
                title=_text(item.get("title")) or title,
                source_id=_text(item.get("source_id")), url=_text(item.get("url")),
                # This digest always names the exact searchable text.  A raw
                # payload hash may name a larger XML/HTML envelope and cannot
                # be used for character offsets in this document.
                snapshot_hash=_sha256(body), snapshot_origin="document_text_sha256",
                provenance=_text(item.get("provenance")) or "fulltext",
                corpus_class=_corpus_class(event, item),
                metadata={"event_id": event_id, "kind": event.get("kind"),
                          "upstream_snapshot_hash": supplied_hash or None},
            ))

        for index, source in enumerate(event.get("sources") or []):
            body = _text(source.get("full_text") or source.get("text") or source.get("content") or source.get("excerpt"))
            if not body:
                continue
            source_id = _text(source.get("id")) or f"source-{index}"
            # Existing normalized sources carry content_hash.  It hashes the
            # exact excerpt, so it is safe as a text snapshot identifier even
            # though the raw collector payload may have a different hash.
            supplied_hash = _text(source.get("snapshot_hash") or source.get("content_hash"))
            has_fulltext = any(source.get(key) for key in ("full_text", "text", "content"))
            documents.append(Document(
                document_id=_text(source.get("document_id")) or f"{event_id}:{source_id}",
                text=body, title=_text(source.get("title")) or title,
                source_id=source_id, url=_text(source.get("url")),
                snapshot_hash=_sha256(body), snapshot_origin="document_text_sha256",
                provenance="fulltext" if has_fulltext else "source_excerpt",
                corpus_class=_corpus_class(event, source),
                metadata={"event_id": event_id, "kind": event.get("kind"),
                          "publisher": source.get("publisher"),
                          "upstream_snapshot_hash": supplied_hash or None},
            ))

        if not explicit_docs and not (event.get("sources") or []):
            body = _text(event.get("full_text") or event.get("body") or event.get("content") or event.get("summary"))
            if body:
                supplied_hash = _text(event.get("snapshot_hash") or event.get("content_hash"))
                documents.append(Document(
                    document_id=event_id or f"event-{len(documents)}", text=body,
                    title=title, snapshot_hash=_sha256(body),
                    snapshot_origin="document_text_sha256", provenance="summary_fallback",
                    corpus_class=_corpus_class(event, {}),
                    metadata={"event_id": event_id, "kind": event.get("kind"),
                              "upstream_snapshot_hash": supplied_hash or None},
                ))
    # Stable de-duplication keeps repeat sources from overweighting BM25.
    unique: dict[tuple[str, str], Document] = {}
    for document in documents:
        unique.setdefault((document.document_id, document.snapshot_hash), document)
    return list(unique.values())


def chunk_documents(
    documents: Iterable[Document], *, chunk_size: int = 900, overlap: int = 120,
) -> list[Chunk]:
    if chunk_size < 80:
        raise ValueError("chunk_size must be at least 80 characters")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")
    chunks: list[Chunk] = []
    step = chunk_size - overlap
    for document in documents:
        text = document.text
        for index, start in enumerate(range(0, len(text), step)):
            end = min(len(text), start + chunk_size)
            if start and len(text) - start < 40:
                break
            chunks.append(Chunk(
                document_id=document.document_id,
                chunk_id=f"{document.document_id}#chunk-{index:04d}",
                text=text[start:end], char_start=start, char_end=end,
                snapshot_hash=document.snapshot_hash,
                snapshot_origin=document.snapshot_origin,
                source_id=document.source_id, title=document.title, url=document.url,
                provenance=document.provenance, metadata=document.metadata,
                corpus_class=document.corpus_class,
            ))
            if end == len(text):
                break
    return chunks


def chunks_from_records(records: Iterable[dict]) -> list[Chunk]:
    """Read persisted chunk dictionaries without requiring a storage schema.

    Storage adapters may keep these records in SQLite, JSONL or another index.
    ``answer_with_rag`` prefers them over its event compatibility projection.
    The contract is intentionally plain dictionaries to keep that adapter
    replaceable.
    """
    chunks: list[Chunk] = []
    for item in records or []:
        # `char_start`/`char_end` address the text exactly as it was stored, so
        # the audit check below must use that text verbatim.  `_text()` is only
        # used to decide whether the record is populated at all: using the
        # stripped string for the length check rejected every record whose text
        # ends with a newline, silently discarding roughly half of the corpus.
        # `or` (not `is None`) keeps the pre-existing fallback: an empty `text`
        # still falls back to `quote`.
        raw_text = item.get("text") or item.get("quote")
        text = "" if raw_text is None else str(raw_text)
        body = _text(raw_text)
        document_id = _text(item.get("document_id"))
        chunk_id = _text(item.get("chunk_id"))
        snapshot_hash = _text(item.get("snapshot_hash"))
        if not body or not document_id or not chunk_id or not snapshot_hash:
            continue
        try:
            start = int(item.get("char_start") or 0)
            end = int(item.get("char_end") if item.get("char_end") is not None else start + len(text))
        except (TypeError, ValueError):
            continue
        if start < 0 or end != start + len(text):
            # A persisted quote whose range does not match cannot be audited.
            continue
        chunks.append(Chunk(
            document_id=document_id, chunk_id=chunk_id, text=text,
            char_start=start, char_end=end, snapshot_hash=snapshot_hash,
            snapshot_origin=_text(item.get("snapshot_origin")) or "persisted_chunk_record",
            source_id=_text(item.get("source_id")), title=_text(item.get("title")),
            url=_text(item.get("url")), provenance=_text(item.get("provenance")) or "fulltext",
            corpus_class=_text(item.get("corpus_class")) or "unknown",
            metadata=dict(item.get("metadata") or {}),
        ))
    return chunks


def _apply_reranker(query: str, hits: list[SearchHit], reranker: Reranker | None) -> list[SearchHit]:
    if reranker is None:
        return hits
    reranked = list(reranker(query, tuple(hits)))
    allowed = {hit.chunk.chunk_id for hit in hits}
    seen: set[str] = set()
    clean: list[SearchHit] = []
    for hit in reranked:
        if not isinstance(hit, SearchHit) or hit.chunk.chunk_id not in allowed or hit.chunk.chunk_id in seen:
            continue
        clean.append(hit)
        seen.add(hit.chunk.chunk_id)
    # A faulty reranker may not silently discard evidence.
    clean.extend(hit for hit in hits if hit.chunk.chunk_id not in seen)
    return clean


def retrieve_chunks(
    query: str,
    chunks: Sequence[Chunk],
    *,
    limit: int = 8,
    min_score: float = 0.15,
    reranker: Reranker | None = None,
) -> list[SearchHit]:
    """BM25/keyword retrieval with an optional replaceable reranking stage."""
    query_terms = terms(query)
    if not query_terms or not chunks or limit <= 0:
        return []
    doc_terms = [terms(" ".join((chunk.title, chunk.text))) for chunk in chunks]
    avg_len = sum(len(item) for item in doc_terms) / max(1, len(doc_terms))
    unique_query = set(query_terms)
    df = {term: sum(1 for item in doc_terms if term in set(item)) for term in unique_query}
    identifiers = {
        item.casefold() for item in re.findall(r"(?:cve-\d{4}-\d{4,}|ghsa-[a-z0-9-]+|arxiv-\d{4}\.\d+)", query, re.I)
    }
    scored: list[SearchHit] = []
    lowered_query = _text(query).casefold()
    for chunk, tokens in zip(chunks, doc_terms):
        token_set = set(tokens)
        matched = tuple(sorted(unique_query & token_set))
        if any(
            phrase in lowered_query
            and not all(any(term in token_set for term in alternatives) for alternatives in groups)
            for phrase, groups in _EXPANSION_REQUIREMENTS.items()
        ):
            continue
        metadata_text = " ".join((chunk.document_id, chunk.source_id, chunk.title, _text(chunk.metadata.get("event_id")))).casefold()
        exact_identifier = any(identifier in metadata_text or identifier in chunk.text.casefold() for identifier in identifiers)
        # Real webpage parsers also encounter menu labels and bibliography
        # stubs.  Very short fragments are useful for navigation, but too weak
        # to support a natural-language answer by themselves.
        if (chunk.provenance == "fulltext" and chunk.corpus_class == "collected_source"
                and len(chunk.text.strip()) < 120 and not exact_identifier):
            continue
        if not matched and not exact_identifier:
            continue
        if not exact_identifier and set(matched) <= _GENERIC_SECURITY_TERMS:
            continue
        # Long natural-language questions often contain a generic word such
        # as "漏洞"/"vulnerability".  A single generic overlap must not turn
        # an otherwise unknown subject into a confident retrieval result.
        if not exact_identifier and len(unique_query) >= 4 and len(matched) < 2:
            # A long natural-language question with only one overlapping term
            # is weak evidence -- unless that term is *discriminative*.  A rare
            # term (low document frequency) carries the subject of the query,
            # whereas a ubiquitous word such as "ai" does not.  Chinese question
            # wording contributes many n-grams that never occur in an English
            # corpus; counting those as unmet requirements rejected every
            # "English proper noun + Chinese question" query.
            only_match = matched[0] if len(matched) == 1 else None
            # 阈值按实际语料标定（3639 分块）：
            #   distillguard 0.6% / auroc 4.2% / multi-agent 8.1% / kernel-level 9.0%
            # 都是可以单独承载查询的技术词；而 ai 35.8% / model 20.0% /
            # security 13.9% 属于"遍布语料"的通用词，单独命中不足以支撑结论。
            # 10% 这条线能分开这两组（N/20 会把 multi-agent、kernel-level 一起拒掉）。
            if only_match is None or df.get(only_match, 0) > max(1, len(chunks) // 10):
                continue
        score = 8.0 if exact_identifier else 0.0
        for term in query_terms:
            frequency = tokens.count(term)
            if not frequency:
                continue
            inverse = math.log(1 + (len(chunks) - df.get(term, 0) + 0.5) / (df.get(term, 0) + 0.5))
            score += inverse * (frequency * 2.2) / (
                frequency + 1.2 * (1 - 0.75 + 0.75 * len(tokens) / max(avg_len, 1))
            )
        if score >= min_score:
            scored.append(SearchHit(chunk=chunk, score=score, matched_terms=matched))
    scored.sort(key=lambda hit: (-hit.score, hit.chunk.document_id, hit.chunk.char_start))
    reranked = _apply_reranker(query, scored, reranker)
    return [replace(hit, rank=index + 1) for index, hit in enumerate(reranked[:limit])]


def citation_from_hit(hit: SearchHit) -> dict[str, Any]:
    chunk = hit.chunk
    return {
        "document_id": chunk.document_id,
        "chunk_id": chunk.chunk_id,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "quote": chunk.text,
        "snapshot_hash": chunk.snapshot_hash,
        "snapshot_origin": chunk.snapshot_origin,
        "source_id": chunk.source_id,
        "title": chunk.title,
        "url": chunk.url,
        "provenance": chunk.provenance,
        "corpus_class": chunk.corpus_class,
        "score": round(hit.score, 6),
        "rank": hit.rank,
    }


def assemble_context(
    hits: Sequence[SearchHit], *, max_chars: int = 4000, max_chunks: int = 6,
) -> dict[str, Any]:
    """Fit ranked evidence into a strict character budget.

    The returned quote and ``char_end`` are adjusted together if the final
    chunk must be truncated, so every range remains directly verifiable.
    """
    if max_chars < 1 or max_chunks < 1:
        return {"text": "", "citations": [], "used_chars": 0, "budget_chars": max_chars, "truncated": bool(hits)}
    citations: list[dict[str, Any]] = []
    blocks: list[str] = []
    remaining = max_chars
    truncated = False
    for hit in hits[:max_chunks]:
        separator = "\n\n" if blocks else ""
        if remaining <= len(separator):
            truncated = True
            break
        remaining -= len(separator)
        prefix = f"[{hit.chunk.chunk_id}] "
        if remaining <= len(prefix):
            truncated = True
            break
        quote = hit.chunk.text[:remaining - len(prefix)]
        if not quote:
            truncated = True
            break
        citation = citation_from_hit(hit)
        citation["quote"] = quote
        citation["char_end"] = citation["char_start"] + len(quote)
        citations.append(citation)
        block = prefix + quote
        blocks.append(block)
        remaining -= len(block)
        if len(quote) < len(hit.chunk.text):
            truncated = True
            break
    if len(citations) < min(len(hits), max_chunks) or len(hits) > max_chunks:
        truncated = True
    text = "\n\n".join(blocks)
    return {
        "text": text,
        "citations": citations,
        "used_chars": len(text),
        "budget_chars": max_chars,
        "truncated": truncated,
    }


Generator = Callable[[str, str, Sequence[dict[str, Any]]], str]


_ANSWER_SENTENCE_RE = re.compile(r"(?<=[.!?。！？])(?:\s+|(?=[\u4e00-\u9fff]))|\n+")


def _answer_sentences(text: str, *, max_chars: int = 420) -> list[str]:
    """Split quoted evidence into short, directly citable answer units."""
    result: list[str] = []
    for raw in _ANSWER_SENTENCE_RE.split(_text(text)):
        sentence = re.sub(r"\s+", " ", raw).strip(" \t-•")
        if not sentence:
            continue
        if len(sentence) > max_chars:
            sentence = sentence[:max_chars].rstrip()
        if len(sentence) >= 16:
            result.append(sentence)
    return result or ([_text(text)[:max_chars].rstrip()] if _text(text) else [])


def _answer_sentence_candidates(
    question: str, citations: Sequence[dict[str, Any]],
) -> list[tuple[float, dict[str, Any], str]]:
    query_terms = set(terms(question))
    candidates: list[tuple[float, dict[str, Any], str]] = []
    for citation in citations:
        for index, sentence in enumerate(_answer_sentences(str(citation.get("quote") or ""))):
            sentence_terms = set(terms(sentence))
            overlap = query_terms & sentence_terms
            specific = overlap - _GENERIC_SECURITY_TERMS
            score = float(len(overlap) * 2 + len(specific) * 2)
            if index == 0:
                score += 0.25
            if query_terms and not overlap:
                score -= 1.0
            candidates.append((score, citation, sentence))
    return candidates


def _extractive_answer(
    question: str, citations: Sequence[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Build a concise answer from exact evidence sentences.

    The function deliberately does not paraphrase.  It selects the sentences
    that overlap the user's terms most strongly and keeps the source/chunk id
    beside each sentence, so every claim remains directly auditable.
    """
    candidates = _answer_sentence_candidates(question, citations)
    if not candidates:
        return "", []
    candidates.sort(key=lambda item: (-item[0], item[1].get("rank") or 999))
    asks_multiple = bool(re.search(
        r"哪些|有哪些|列出|分别|对比|比较|list\b|which\s+(?:ones|documents)|compare",
        question, re.I,
    ))
    selected: list[tuple[float, dict[str, Any], str]] = []
    seen_sentences: set[str] = set()
    used_documents: set[str] = set()
    for candidate in candidates:
        score, citation, sentence = candidate
        normalized = sentence.casefold()
        if normalized in seen_sentences:
            continue
        document_id = _text(citation.get("document_id"))
        if not asks_multiple and document_id and document_id in used_documents:
            continue
        selected.append(candidate)
        seen_sentences.add(normalized)
        if document_id:
            used_documents.add(document_id)
        if len(selected) >= (4 if asks_multiple else 3):
            break
    if not selected:
        return "", []
    if re.search(r"哪些|有哪些|列出|list\b|which\s+(?:ones|documents)", question, re.I):
        lead = "检索到的相关原文证据如下："
    elif re.search(r"是什么|什么是|检测什么|做什么|what\s+(?:is|does)", question, re.I):
        lead = "检索到的原文直接证据："
    else:
        lead = "根据检索到的原文证据："
    lines = [lead]
    claims: list[dict[str, Any]] = []
    for _, citation, sentence in selected:
        label = _text(citation.get("title") or citation.get("source_id") or citation.get("document_id"))
        chunk_id = _text(citation.get("chunk_id"))
        suffix = f" [{label} · {chunk_id}]" if label or chunk_id else ""
        lines.append(f"- “{sentence}”{suffix}")
        claims.append({
            "text": sentence,
            "evidence_ids": [chunk_id] if chunk_id else [],
        })
    return "\n".join(lines), claims


def answer_with_rag(
    question: str,
    events: Sequence[dict] = (),
    *,
    chunks: Sequence[Chunk] | Sequence[dict] | None = None,
    focus_document_ids: Sequence[str] | None = None,
    required_terms: Sequence[str] | None = None,
    max_context_chars: int = 4000,
    max_chunks: int = 6,
    reranker: Reranker | None = None,
    generator: Generator | None = None,
) -> dict[str, Any]:
    """Retrieve bounded context and answer only when a citation exists."""
    documents: list[Document] = []
    if chunks is not None:
        search_chunks = (
            list(chunks) if all(isinstance(item, Chunk) for item in chunks)
            else chunks_from_records(item for item in chunks if isinstance(item, dict))
        )
        input_mode = "persisted_chunks"
    else:
        documents = events_to_documents(events)
        search_chunks = chunk_documents(documents)
        input_mode = "event_compatibility_projection"
    focus_ids = {str(item) for item in (focus_document_ids or []) if str(item)}
    focused_chunks = [item for item in search_chunks if item.document_id in focus_ids] if focus_ids else []
    focused_retrieval = bool(focused_chunks)
    hits = retrieve_chunks(
        question,
        focused_chunks if focused_chunks else search_chunks,
        limit=max_chunks * 2,
        reranker=reranker,
    )
    focus_fallback = bool(focus_ids and not hits)
    if focus_fallback:
        hits = retrieve_chunks(question, search_chunks, limit=max_chunks * 2, reranker=reranker)
    required = {str(term).casefold() for term in (required_terms or []) if str(term)}
    if required:
        hits = [
            hit for hit in hits
            if any(
                term in set(terms(" ".join((hit.chunk.title, hit.chunk.text))))
                for term in required
            )
        ]
    context = assemble_context(hits, max_chars=max_context_chars, max_chunks=max_chunks)
    citations = context["citations"]
    if not citations:
        return {
            "answer": "现有文档中没有找到能够支持回答的原文证据，系统拒绝作答。",
            "refused": True,
            "refusal_reason": "no_retrievable_evidence",
            "citations": [],
            "context_chunks": [],
            "context": {key: value for key, value in context.items() if key != "text"},
            "retrieval": {"documents": len(documents), "chunks": len(search_chunks), "hits": 0,
                          "ranker": "bm25_keyword", "input_mode": input_mode,
                          "focused_document_ids": sorted(focus_ids),
                          "focused_retrieval": focused_retrieval,
                          "focus_fallback": focus_fallback,
                          "required_terms": sorted(required)},
        }
    if generator is not None:
        answer = _text(generator(question, context["text"], citations))
        if not answer:
            answer = "生成器未返回答案；请直接核对所附原文证据。"
        claims: list[dict[str, Any]] = []
    else:
        answer, claims = _extractive_answer(question, citations)
        if not answer:
            answer = "根据命中的原文证据：\n" + "\n".join(
                f"- {item['quote']}" for item in citations[:3]
            )
    return {
        "answer": answer,
        "refused": False,
        "refusal_reason": None,
        "citations": citations,
        "claims": claims,
        "context_chunks": citations,
        "context": {key: value for key, value in context.items() if key != "text"},
        "retrieval": {
            "documents": len(documents), "chunks": len(search_chunks), "hits": len(hits),
            "ranker": "bm25_keyword", "reranked": reranker is not None,
            "input_mode": input_mode,
            "focused_document_ids": sorted(focus_ids),
            "focused_retrieval": focused_retrieval,
            "focus_fallback": focus_fallback,
            "required_terms": sorted(required),
        },
    }
