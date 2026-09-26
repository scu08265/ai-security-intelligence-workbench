"""Three-layer deduplication and cross-source merging.

Layer 1 merges records that share an identifier (CVE/GHSA/alias).  Layer 2
treats identical content hashes as the same upstream text.  Layer 3 only ever
*proposes* a link based on component and title similarity -- it never merges,
because two different vulnerabilities in the same product usually look similar
and silently collapsing them would destroy real findings.

Merging keeps provenance: every affected range and every severity keeps the
`source_id` it came from, and disagreements between sources are recorded in
`conflicts` rather than resolved by picking a winner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import storage

SEVERITY_ORDER = ["none", "low", "medium", "high", "critical"]
SIMILARITY_THRESHOLD = 0.62

# Preferred primary identifier, most authoritative first.
ID_PREFERENCE = ("CVE-", "GHSA-", "PYSEC-", "GO-", "MSRC-", "OSV-")

_STOPWORDS = {
    "the", "a", "an", "in", "of", "and", "or", "to", "for", "with", "via", "on",
    "vulnerability", "issue", "flaw", "bug", "security", "improper", "allows",
    "before", "after", "version", "versions", "attacker", "could", "may",
}


@dataclass
class DedupeResult:
    action: str  # new | updated | merged | unchanged
    event: dict
    merged_ids: list[str] = field(default_factory=list)
    candidate_ids: list[str] = field(default_factory=list)


def _normalize_component(value: str | None) -> str:
    return re.sub(r"[\s_.\-/]+", "", (value or "").casefold())


def _tokens(text: str | None) -> set[str]:
    words = re.findall(r"[a-z0-9]{3,}", (text or "").casefold())
    return {w for w in words if w not in _STOPWORDS}


def _similarity(left: dict, right: dict) -> float:
    """Title Jaccard restricted to same-component records."""
    if _normalize_component(left.get("component")) != _normalize_component(right.get("component")):
        return 0.0
    if not _normalize_component(left.get("component")):
        return 0.0
    a, b = _tokens(left.get("title")), _tokens(right.get("title"))
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _identifiers(event: dict) -> set[str]:
    values = {str(event.get("id") or "")}
    values.update(str(a) for a in event.get("aliases") or [])
    return {v for v in values if v}


def _better_title(left: str | None, right: str | None) -> str:
    left, right = (left or "").strip(), (right or "").strip()
    if not left:
        return right
    if not right:
        return left
    return right if len(right) > len(left) else left


def _pick_primary(left: dict, right: dict) -> tuple[str, list[str]]:
    identifiers = list(_identifiers(left) | _identifiers(right))
    for prefix in ID_PREFERENCE:
        for identifier in identifiers:
            if identifier.startswith(prefix):
                return identifier, [i for i in identifiers if i != identifier]
    primary = str(left.get("id") or right.get("id") or "")
    return primary, [i for i in identifiers if i != primary]


def _merge_affected(left: list[dict], right: list[dict]) -> tuple[list[dict], list[dict]]:
    """Union ranges, keeping provenance; flag ranges that disagree."""
    merged: dict[tuple[str, str], dict] = {}
    for item in [*(left or []), *(right or [])]:
        key = (_normalize_component(item.get("package")), str(item.get("range") or ""))
        if key not in merged:
            merged[key] = dict(item)
            merged[key]["source_ids"] = [item.get("source_id")] if item.get("source_id") else []
        elif item.get("source_id") and item["source_id"] not in merged[key]["source_ids"]:
            merged[key]["source_ids"].append(item["source_id"])

    conflicts: list[dict] = []
    by_package: dict[str, list[dict]] = {}
    for item in merged.values():
        by_package.setdefault(_normalize_component(item.get("package")), []).append(item)
    for package, items in by_package.items():
        distinct = {str(i.get("range")) for i in items}
        if len(distinct) > 1 and package:
            conflicts.append({
                "field": "affected.range",
                "package": items[0].get("package"),
                "values": sorted(distinct),
                "note": "不同来源给出的受影响区间不一致，系统并列保留，未做取舍",
            })
    return list(merged.values()), conflicts


def _merge_cvss(left: list[dict], right: list[dict]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    for item in [*(left or []), *(right or [])]:
        key = (str(item.get("version") or ""), str(item.get("vector") or ""))
        if key not in merged:
            merged[key] = dict(item)
        elif merged[key].get("score") is None and item.get("score") is not None:
            # Same vector, but this source supplies a real number.
            merged[key]["score"] = item["score"]
            merged[key]["source_id"] = item.get("source_id")
    return list(merged.values())


def merge_events(left: dict, right: dict) -> dict:
    """Combine two records describing the same vulnerability."""
    primary_id, other_ids = _pick_primary(left, right)
    affected, conflicts = _merge_affected(left.get("affected"), right.get("affected"))

    severities = {s for s in [left.get("severity"), right.get("severity")] if s}
    if len(severities) > 1:
        conflicts.append({
            "field": "severity",
            "values": sorted(severities),
            "note": "不同来源的严重性评级不一致，按更保守（更高）的一档展示",
        })
    severity = max(severities, key=lambda s: SEVERITY_ORDER.index(s)
                   if s in SEVERITY_ORDER else 0) if severities else None

    merged = dict(left)
    merged.update({
        "id": primary_id,
        "aliases": sorted(
            (set(other_ids) | set(left.get("aliases") or []) | set(right.get("aliases") or []))
            - {primary_id}
        ),
        "title": _better_title(left.get("title"), right.get("title")),
        "summary": _better_title(left.get("summary"), right.get("summary")),
        "component": left.get("component") or right.get("component"),
        "ecosystem": left.get("ecosystem") or right.get("ecosystem"),
        "published_at": min(
            [x for x in [left.get("published_at"), right.get("published_at")] if x], default=None
        ),
        "modified_at": max(
            [x for x in [left.get("modified_at"), right.get("modified_at")] if x], default=None
        ),
        "withdrawn": bool(left.get("withdrawn") or right.get("withdrawn")),
        "affected": affected,
        "conditions": _merge_simple(left.get("conditions"), right.get("conditions"), "name"),
        "severity": severity,
        "cvss": _merge_cvss(left.get("cvss"), right.get("cvss")),
        "cwes": sorted(set(left.get("cwes") or []) | set(right.get("cwes") or [])),
        "sources": _merge_simple(left.get("sources"), right.get("sources"), "id"),
        "references": sorted(set(left.get("references") or []) | set(right.get("references") or [])),
        "poc": _merge_simple(left.get("poc"), right.get("poc"), "url"),
        "tags": sorted(set(left.get("tags") or []) | set(right.get("tags") or [])),
        "relationships": _merge_simple(left.get("relationships"), right.get("relationships"), None),
        "ai_relevance": left.get("ai_relevance") or right.get("ai_relevance"),
        "monitoring": right.get("monitoring") or left.get("monitoring"),
        "monitoring_observations": _merge_simple(
            left.get("monitoring_observations"), right.get("monitoring_observations"), None
        ),
    })
    statuses = {left.get("status"), right.get("status")}
    if "withdrawn" in statuses:
        merged["status"] = "withdrawn"
    elif "needs_review" in statuses:
        merged["status"] = "needs_review"
    else:
        merged["status"] = "confirmed"
    if conflicts:
        merged["conflicts"] = conflicts
    # Preserve research-grade annotations when either side carries them.
    for key in ("evidence_grade", "unknown_fields", "poc_executed"):
        if key in right and key not in merged:
            merged[key] = right[key]
    return merged


def _merge_simple(left: list | None, right: list | None, key: str | None) -> list:
    if key is None:
        return [*(left or []), *(right or [])]
    merged: dict[str, dict] = {}
    for item in [*(left or []), *(right or [])]:
        if not isinstance(item, dict):
            continue
        marker = str(item.get(key) or "")
        if marker and marker in merged:
            continue
        if marker:
            merged[marker] = item
        else:
            merged[f"_anon{len(merged)}"] = item
    return list(merged.values())


def resolve(event: dict) -> DedupeResult:
    """Fold an incoming event into the store."""
    event_id = str(event.get("id") or "")
    if not event_id:
        raise ValueError("event requires an id")

    existing = storage.get_event(event_id)
    if existing is None:
        for identifier in sorted(_identifiers(event)):
            existing = storage.find_event_by_identifier(identifier)
            if existing is not None:
                break

    if existing is not None and str(existing.get("id")) != event_id:
        merged = merge_events(existing, event)
        return DedupeResult("merged", merged, merged_ids=[str(existing.get("id")), event_id])

    if existing is not None:
        # Same identifier: fold in new sources and ranges rather than replace.
        merged = merge_events(existing, event)
        changed = merged.get("content_hash") != existing.get("content_hash") or len(
            merged.get("sources") or []
        ) != len(existing.get("sources") or [])
        action = "updated" if changed else "unchanged"
        return DedupeResult(action, merged)

    # Layers 2 and 3 need the current corpus; load it once.
    known, _ = storage.list_events(limit=400)

    # Layer 2: identical upstream text under a different identifier.
    digest = event.get("content_hash")
    if digest:
        for other in known:
            if other.get("id") == event_id:
                continue
            if other.get("content_hash") and other["content_hash"] == digest:
                return DedupeResult(
                    "unchanged", other, merged_ids=[str(other.get("id"))]
                )

    # Layer 3: propose, never merge.
    candidates: list[str] = []
    for other in known:
        if other.get("id") == event_id:
            continue
        score = _similarity(event, other)
        if score >= SIMILARITY_THRESHOLD:
            candidates.append(str(other.get("id")))
            storage.save_duplicate_candidate(
                event_id, str(other.get("id")),
                f"组件相同且标题相似度 {score:.2f}，仅作候选，需人工确认是否同一漏洞", score,
            )
    return DedupeResult("new", event, candidate_ids=candidates)
