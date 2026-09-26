"""Turn raw upstream payloads into the canonical event document.

Two properties matter more than coverage here:

* Nothing is invented.  A field that cannot be read from the upstream record is
  `null` or `"unknown"`, never a plausible-looking guess.  In particular an
  unparseable version range stays `"unknown"` so `assess_asset` reports
  `needs_confirmation` instead of clearing an asset.
* `sources[].excerpt` carries upstream text verbatim.  It is the quoted
  evidence a reviewer checks a claim against, so no summarising or model
  wording is allowed into it.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable

from . import relevance, storage

EXCERPT_LIMIT = 700
UNKNOWN_RANGE = "unknown"


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _iso(value: Any) -> str | None:
    """Normalise an upstream timestamp to ISO-8601 UTC, or None if unreadable."""
    raw = _text(value)
    if not raw:
        return None
    candidate = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return raw  # keep the upstream string rather than fabricate a time
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _excerpt(value: Any, limit: int = EXCERPT_LIMIT) -> str:
    raw = re.sub(r"\s+", " ", _text(value)).strip()
    if len(raw) <= limit:
        return raw
    return raw[:limit].rstrip() + "…"


def _source_id(prefix: str, payload: Any) -> str:
    digest = storage.content_hash(
        payload if isinstance(payload, (bytes, str)) else repr(payload)
    )[:10]
    return f"{prefix}:{digest}"


def _severity_label(value: Any) -> str | None:
    label = _text(value).casefold()
    mapping = {
        "critical": "critical", "high": "high", "moderate": "medium", "medium": "medium",
        "low": "low", "none": "none", "info": "low", "informational": "low",
        "严重": "critical", "高危": "high", "中危": "medium", "低危": "low",
        "moderate severity": "medium",
    }
    if label in mapping:
        return mapping[label]
    if label in {"critical", "high", "medium", "low"}:
        return label
    if label.isdigit():
        return _score_to_label(float(label))
    match = re.match(r"^(\d+(?:\.\d+)?)\s*$", label)
    if match:
        return _score_to_label(float(match.group(1)))
    return _text(value) or None


def _score_to_label(score: float) -> str:
    if score >= 9:
        return "critical"
    if score >= 7:
        return "high"
    if score >= 4:
        return "medium"
    if score > 0:
        return "low"
    return "none"


def _cwe_list(values: Iterable[Any] | None) -> list[str]:
    out: list[str] = []
    for item in values or []:
        text = _text(item)
        if not text:
            continue
        match = re.search(r"CWE-\d+", text, re.I)
        out.append(match.group(0).upper() if match else text)
    return list(dict.fromkeys(out))


def canonical_event(
    *,
    event_id: str,
    title: str,
    summary: str,
    component: str | None,
    ecosystem: str | None,
    kind: str = "vulnerability",
    aliases: Iterable[str] | None = None,
    published_at: Any = None,
    modified_at: Any = None,
    withdrawn: bool = False,
    status: str = "confirmed",
    affected: list[dict] | None = None,
    conditions: list[dict] | None = None,
    severity: str | None = None,
    cvss: list[dict] | None = None,
    cwes: list[str] | None = None,
    sources: list[dict] | None = None,
    references: list[str] | None = None,
    poc: list[dict] | None = None,
    tags: Iterable[str] | None = None,
    ai_relevance: dict | None = None,
    relationships: list[dict] | None = None,
    content_hash: str | None = None,
    enrichment: dict | None = None,
) -> dict:
    """Assemble a document with every contract field present.

    Keeping the full key set on every event means downstream code never has to
    distinguish "missing" from "empty", which is exactly the distinction the
    evidence-gap reporting depends on.
    """
    event = {
        "id": _text(event_id),
        "kind": kind,
        "aliases": [a for a in dict.fromkeys(_text(a) for a in (aliases or [])) if a],
        "title": _text(title),
        "summary": _text(summary),
        "component": _text(component),
        "ecosystem": _text(ecosystem),
        "published_at": _iso(published_at),
        "modified_at": _iso(modified_at),
        "collected_at": storage.utcnow(),
        "withdrawn": bool(withdrawn),
        "status": "withdrawn" if withdrawn else status,
        "affected": affected or [],
        "conditions": conditions or [],
        "severity": severity,
        "cvss": cvss or [],
        "cwes": list(cwes or []),
        "sources": sources or [],
        "references": [r for r in dict.fromkeys(_text(r) for r in (references or [])) if r],
        "poc": poc or [],
        "ai_relevance": ai_relevance or {"included": True, "reason": "未分类"},
        "tags": [t for t in dict.fromkeys(_text(t) for t in (tags or [])) if t],
        "relationships": relationships or [],
        "content_hash": content_hash,
    }
    if enrichment is not None:
        event["enrichment"] = enrichment
    return event


def _apply_relevance(event: dict, *extra: str | None) -> dict:
    """Attach the AI-relevance verdict and route weak matches to review."""
    package = None
    affected = event.get("affected") or []
    if affected:
        package = affected[0].get("package")
    # Headline fields are short and focused; the summary and any extra text are
    # free-form and only searched for unambiguous terms.
    verdict = relevance.classify(
        event.get("title"), event.get("component"),
        body=" ".join(x for x in (event.get("summary"), *extra) if x),
        package=package,
    )
    event["ai_relevance"] = {"included": verdict.included, "reason": verdict.reason}
    if verdict.needs_review and event.get("status") == "confirmed":
        event["status"] = "needs_review"
    return event


# --------------------------------------------------------------------------
# OSV
# --------------------------------------------------------------------------

def osv_ranges_to_specifiers(ranges: list[dict] | None) -> tuple[list[str], bool]:
    """Convert OSV range events into contract specifier strings.

    OSV expresses ranges as a list of `{introduced}/{fixed}/{last_affected}`
    events rather than a specifier, so this translation is required.  Returns
    (specifiers, fully_parsed); a `False` flag means at least one range used an
    event type we do not model, and the caller must keep the range `unknown`
    rather than narrowing it.
    """
    specifiers: list[str] = []
    complete = True
    for entry in ranges or []:
        if _text(entry.get("type")).upper() == "GIT":
            # GIT ranges carry commit hashes, which are not comparable versions.
            complete = False
            continue
        introduced: str | None = None
        for raw in entry.get("events") or []:
            if not isinstance(raw, dict) or len(raw) != 1:
                complete = False
                continue
            (kind, value), = raw.items()
            value = _text(value)
            if kind == "introduced":
                introduced = value
            elif kind in {"fixed", "last_affected"}:
                if introduced is None:
                    complete = False
                    continue
                lower = [">= " + introduced] if introduced not in {"", "0"} else []
                upper = ("<= " if kind == "last_affected" else "< ") + value
                specifiers.append(", ".join([*lower, upper]))
                introduced = None
            elif kind == "limit":
                # `limit` is a git-commit bound with no version equivalent.
                complete = False
            else:
                complete = False
        if introduced not in (None, ""):
            # Introduced with no terminating fix: affected from here onwards.
            specifiers.append(">= " + introduced if introduced != "0" else "")
    cleaned = [s for s in dict.fromkeys(specifiers) if s]
    return cleaned, complete


def osv_to_event(raw: dict) -> dict | None:
    """Map an OSV record to a canonical event."""
    event_id = _text(raw.get("id") or raw.get("aliases", [None])[0])
    if not event_id:
        return None
    aliases = [_text(a) for a in raw.get("aliases") or []]
    detail = raw.get("database_specific") or {}

    affected: list[dict] = []
    for entry in raw.get("affected") or []:
        package = ((entry.get("package") or {}).get("name")) or ""
        ecosystem = ((entry.get("package") or {}).get("ecosystem")) or ""
        specifiers, complete = osv_ranges_to_specifiers(entry.get("ranges"))
        fixed_versions = [
            _text(ev.get("fixed"))
            for rng in entry.get("ranges") or []
            for ev in rng.get("events") or []
            if ev.get("fixed")
        ]
        declared = [_text(v) for v in entry.get("versions") or []]
        if specifiers and complete:
            for spec in specifiers:
                affected.append({
                    "package": package, "ecosystem": ecosystem, "range": spec,
                    "fixed_version": (fixed_versions[0] if fixed_versions else None),
                    "source_id": _source_id("osv", f"{event_id}:{package}:{spec}"),
                })
        elif declared:
            # Enumerated versions are exact facts; keep them readable.
            affected.append({
                "package": package, "ecosystem": ecosystem,
                "range": "in " + ", ".join(declared[:40]) if len(declared) <= 40 else UNKNOWN_RANGE,
                "fixed_version": (fixed_versions[0] if fixed_versions else None),
                "source_id": _source_id("osv", f"{event_id}:{package}:versions"),
            })
        else:
            affected.append({
                "package": package, "ecosystem": ecosystem, "range": UNKNOWN_RANGE,
                "fixed_version": (fixed_versions[0] if fixed_versions else None),
                "source_id": _source_id("osv", f"{event_id}:{package}:unknown"),
            })

    cvss: list[dict] = []
    for entry in raw.get("severity") or []:
        vector = _text(entry.get("score"))
        if not vector:
            continue
        version = "3.1"
        match = re.match(r"CVSS:(\d+\.\d+)", vector)
        if match:
            version = match.group(1)
        elif "CVSS_V4" in _text(entry.get("type")):
            version = "4.0"
        numeric = detail.get("cvss")
        cvss.append({
            "version": version,
            # OSV reports a vector, not a number.  Only a genuine upstream
            # number is stored; otherwise the score stays null.
            "score": float(numeric) if isinstance(numeric, (int, float)) else None,
            "vector": vector,
            "source_id": _source_id("osv", f"{event_id}:cvss:{vector}"),
        })

    references = [
        _text(ref.get("url")) for ref in raw.get("references") or [] if ref.get("url")
    ]
    summary = detail.get("summary") or raw.get("summary") or ""
    description = raw.get("details") or summary
    cwes = _cwe_list(detail.get("cwe_ids"))

    trust = "authoritative" if detail.get("github_reviewed") else "aggregated"
    source_entry = {
        "id": _source_id("osv", event_id),
        "url": f"https://osv.dev/vulnerability/{event_id}",
        "title": f"OSV record {event_id}",
        "publisher": "OSV (Google)",
        "source_type": "vulnerability_database",
        "excerpt": _excerpt(description),
        "published_at": _iso(raw.get("published")),
        "collected_at": storage.utcnow(),
        "content_hash": storage.content_hash(_text(description)),
        "trust": trust,
    }

    # OSV publishes no severity label; derive one only from a real number.
    numeric_scores = [c["score"] for c in cvss if c.get("score") is not None]
    severity_label = _score_to_label(max(numeric_scores)) if numeric_scores else None

    event = canonical_event(
        event_id=event_id,
        aliases=aliases,
        title=summary or event_id,
        summary=_excerpt(description, 400),
        component=(affected[0]["package"] if affected else ""),
        ecosystem=(affected[0]["ecosystem"] if affected else ""),
        published_at=raw.get("published"),
        modified_at=raw.get("modified"),
        affected=affected,
        severity=severity_label,
        cvss=cvss,
        cwes=cwes,
        sources=[source_entry],
        references=references,
        tags=[a for a in aliases if a.startswith(("CVE-", "GHSA-", "PYSEC-"))],
        content_hash=storage.content_hash(_text(description)),
    )
    return _apply_relevance(event, description)


# --------------------------------------------------------------------------
# NVD
# --------------------------------------------------------------------------

def nvd_to_event(raw: dict) -> dict | None:
    cve = raw.get("cve") or {}
    event_id = _text(cve.get("id"))
    if not event_id:
        return None
    descriptions = cve.get("descriptions") or []
    description = next((_text(d.get("value")) for d in descriptions if d.get("lang") == "en"), "")
    if not description and descriptions:
        description = _text(descriptions[0].get("value"))

    metrics = cve.get("metrics") or {}
    cvss: list[dict] = []
    severity_label = None
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        for metric in metrics.get(key) or []:
            data = metric.get("cvssData") or {}
            vector = _text(data.get("vectorString"))
            if not vector:
                continue
            version = _text(data.get("version")) or "3.1"
            numeric = data.get("baseScore")
            cvss.append({
                "version": version,
                "score": float(numeric) if isinstance(numeric, (int, float)) else None,
                "vector": vector,
                "source_id": _source_id("nvd", f"{event_id}:cvss:{vector}"),
            })
            severity_label = severity_label or _severity_label(
                metric.get("baseSeverity") or data.get("baseSeverity") or numeric
            )
    if cvss and not severity_label:
        severity_label = _severity_label(cvss[0].get("score"))

    weaknesses = cve.get("weaknesses") or []
    cwes = _cwe_list(
        d.get("value") for w in weaknesses for d in (w.get("description") or [])
    )

    affected: list[dict] = []
    for config in cve.get("configurations") or []:
        for node in config.get("nodes") or []:
            for match in node.get("cpeMatch") or []:
                if not match.get("vulnerable"):
                    continue
                criteria = _text(match.get("criteria"))
                parts = criteria.split(":")
                vendor = parts[3] if len(parts) > 3 else ""
                product = parts[4] if len(parts) > 4 else ""
                start = _text(match.get("versionStartIncluding")) or _text(match.get("versionStartExcluding"))
                end = _text(match.get("versionEndExcluding")) or _text(match.get("versionEndIncluding"))
                lower_op = "> " if match.get("versionStartExcluding") else ">= "
                upper_op = "<= " if match.get("versionEndIncluding") else "< "
                spec = UNKNOWN_RANGE
                if start and end:
                    spec = f"{lower_op}{start}, {upper_op}{end}"
                elif end:
                    spec = f"{upper_op}{end}"
                elif start:
                    spec = f"{lower_op}{start}"
                elif match.get("vulnerable") and not (start or end):
                    spec = UNKNOWN_RANGE
                package = product or vendor or ""
                if not package:
                    continue
                affected.append({
                    "package": package,
                    "ecosystem": "",
                    "range": spec,
                    "fixed_version": None,
                    "source_id": _source_id("nvd", f"{event_id}:{criteria}:{spec}"),
                })
    # Collapse duplicates produced by many CPE rows for the same product.
    seen = set()
    unique_affected = []
    for item in affected:
        key = (item["package"], item["range"])
        if key in seen:
            continue
        seen.add(key)
        unique_affected.append(item)
    affected = unique_affected[:25]

    references = [_text(r.get("url")) for r in cve.get("references") or [] if r.get("url")]
    published = cve.get("published")
    modified = cve.get("lastModified")
    vuln_status = _text(cve.get("vulnStatus"))
    withdrawn = vuln_status.casefold().startswith("rejected") or vuln_status.casefold() == "rejected"

    source_entry = {
        "id": _source_id("nvd", event_id),
        "url": f"https://nvd.nist.gov/vuln/detail/{event_id}",
        "title": f"NVD record {event_id}",
        "publisher": "NIST NVD",
        "source_type": "vulnerability_database",
        "excerpt": _excerpt(description),
        "published_at": _iso(published),
        "collected_at": storage.utcnow(),
        "content_hash": storage.content_hash(_text(description)),
        "trust": "authoritative",
    }

    event = canonical_event(
        event_id=event_id,
        title=_text(cve.get("sourceIdentifier")) or event_id,
        summary=_excerpt(description, 400),
        component=(affected[0]["package"] if affected else ""),
        ecosystem="",
        published_at=published,
        modified_at=modified,
        withdrawn=withdrawn,
        status="withdrawn" if withdrawn else "confirmed",
        affected=affected,
        severity=severity_label,
        cvss=cvss,
        cwes=cwes,
        sources=[source_entry],
        references=references,
        tags=[t for t in [_text(cve.get("sourceIdentifier"))] if t.startswith("CVE-")],
        content_hash=storage.content_hash(_text(description)),
    )
    return _apply_relevance(event, description)


# --------------------------------------------------------------------------
# MITRE CVE Services
# --------------------------------------------------------------------------

def mitre_to_event(raw: dict) -> dict | None:
    meta = raw.get("cveMetadata") or {}
    event_id = _text(meta.get("cveId"))
    if not event_id:
        return None
    cna = (raw.get("containers") or {}).get("cna") or {}
    description = next(
        (_text(d.get("value")) for d in cna.get("descriptions") or [] if d.get("lang") == "en"),
        "",
    )
    if not description and cna.get("descriptions"):
        description = _text(cna["descriptions"][0].get("value"))

    title = _text(cna.get("title")) or event_id
    affected: list[dict] = []
    for entry in cna.get("affected") or []:
        package = _text(entry.get("product")) or _text(entry.get("packageName"))
        for version in entry.get("versions") or []:
            status = _text(version.get("status")).casefold()
            if status in {"unaffected"}:
                continue
            spec = UNKNOWN_RANGE
            if version.get("lessThan") and version.get("version"):
                spec = f">= {_text(version['version'])}, < {_text(version['lessThan'])}"
            elif version.get("lessThanOrEqual") and version.get("version"):
                spec = f">= {_text(version['version'])}, <= {_text(version['lessThanOrEqual'])}"
            elif version.get("version"):
                spec = f"= {_text(version['version'])}"
            affected.append({
                "package": package,
                "ecosystem": _text(entry.get("packageName")),
                "range": spec,
                "fixed_version": None,
                "source_id": _source_id("mitre", f"{event_id}:{package}:{spec}"),
            })
    affected = affected[:25]

    cvss: list[dict] = []
    severity_label = None
    for metric in cna.get("metrics") or []:
        for key, value in metric.items():
            if not isinstance(value, dict):
                continue
            vector = _text(value.get("vectorString"))
            if not vector:
                continue
            version = "3.1"
            match = re.match(r"CVSS:(\d+\.\d+)", vector)
            if match:
                version = match.group(1)
            numeric = value.get("baseScore")
            cvss.append({
                "version": version,
                "score": float(numeric) if isinstance(numeric, (int, float)) else None,
                "vector": vector,
                "source_id": _source_id("mitre", f"{event_id}:cvss:{vector}"),
            })
            severity_label = severity_label or _severity_label(
                value.get("baseSeverity") or numeric
            )

    cwes = _cwe_list(
        d.get("description")
        for p in cna.get("problemTypes") or []
        for d in (p.get("descriptions") or [])
        if _text(d.get("type")).casefold() == "cwe"
    )
    references = [_text(r.get("url")) for r in cna.get("references") or [] if r.get("url")]
    state = _text(meta.get("state")).casefold()
    withdrawn = state == "rejected"

    source_entry = {
        "id": _source_id("mitre", event_id),
        "url": f"https://www.cve.org/CVERecord?id={event_id}",
        "title": f"CVE Program record {event_id}",
        "publisher": "MITRE CVE Program",
        "source_type": "authoritative_record",
        "excerpt": _excerpt(description),
        "published_at": _iso(meta.get("datePublished")),
        "collected_at": storage.utcnow(),
        "content_hash": storage.content_hash(_text(description)),
        "trust": "authoritative",
    }

    event = canonical_event(
        event_id=event_id,
        title=title,
        summary=_excerpt(description, 400),
        component=(affected[0]["package"] if affected else ""),
        ecosystem=(affected[0]["ecosystem"] if affected else ""),
        published_at=meta.get("datePublished"),
        modified_at=meta.get("dateUpdated"),
        withdrawn=withdrawn,
        status="withdrawn" if withdrawn else "confirmed",
        affected=affected,
        severity=severity_label,
        cvss=cvss,
        cwes=cwes,
        sources=[source_entry],
        references=references,
        tags=[event_id],
        content_hash=storage.content_hash(_text(description)),
    )
    return _apply_relevance(event, description)


# --------------------------------------------------------------------------
# GitHub Security Advisories
# --------------------------------------------------------------------------

def ghsa_to_event(raw: dict) -> dict | None:
    ghsa_id = _text(raw.get("ghsa_id"))
    cve_id = _text(raw.get("cve_id"))
    event_id = ghsa_id or cve_id
    if not event_id:
        return None
    aliases = [a for a in [cve_id, ghsa_id] if a and a != event_id]

    affected: list[dict] = []
    for entry in raw.get("vulnerabilities") or []:
        package = (entry.get("package") or {}).get("name") or ""
        ecosystem = (entry.get("package") or {}).get("ecosystem") or ""
        vulnerable_range = _text(entry.get("vulnerable_version_range"))
        spec = UNKNOWN_RANGE
        if vulnerable_range:
            # GHSA ranges are already "< 0.2.0" / ">= 1.0, < 2.0" shaped.
            spec = vulnerable_range
        affected.append({
            "package": package,
            "ecosystem": ecosystem,
            "range": spec,
            "fixed_version": _text(entry.get("first_patched_version")) or None,
            "source_id": _source_id("ghsa", f"{event_id}:{package}:{spec}"),
        })

    cvss: list[dict] = []
    severity_label = _severity_label(raw.get("severity"))
    cvss_entry = raw.get("cvss") or {}
    if cvss_entry.get("vector_string"):
        version = "3.1"
        match = re.match(r"CVSS:(\d+\.\d+)", _text(cvss_entry.get("vector_string")))
        if match:
            version = match.group(1)
        score = cvss_entry.get("score")
        cvss.append({
            "version": version,
            "score": float(score) if isinstance(score, (int, float)) else None,
            "vector": _text(cvss_entry.get("vector_string")),
            "source_id": _source_id("ghsa", f"{event_id}:cvss"),
        })

    description = _text(raw.get("description"))
    source_entry = {
        "id": _source_id("ghsa", event_id),
        "url": _text(raw.get("html_url")) or f"https://github.com/advisories/{ghsa_id}",
        "title": _text(raw.get("summary")) or f"GitHub advisory {event_id}",
        "publisher": "GitHub Advisory Database",
        "source_type": "advisory",
        "excerpt": _excerpt(description),
        "published_at": _iso(raw.get("published_at")),
        "collected_at": storage.utcnow(),
        "content_hash": storage.content_hash(_text(description)),
        "trust": "authoritative",
    }

    event = canonical_event(
        event_id=event_id,
        aliases=aliases,
        title=_text(raw.get("summary")) or event_id,
        summary=_excerpt(description, 400),
        component=(affected[0]["package"] if affected else ""),
        ecosystem=(affected[0]["ecosystem"] if affected else ""),
        published_at=raw.get("published_at"),
        modified_at=raw.get("updated_at"),
        withdrawn=bool(raw.get("withdrawn_at")),
        status="withdrawn" if raw.get("withdrawn_at") else "confirmed",
        affected=affected,
        severity=severity_label,
        cvss=cvss,
        cwes=_cwe_list(raw.get("cwe_ids")),
        sources=[source_entry],
        references=[_text(r) for r in raw.get("references") or [] if r],
        tags=[t for t in [ghsa_id, cve_id] if t],
        content_hash=storage.content_hash(_text(description)),
    )
    return _apply_relevance(event, description)


# --------------------------------------------------------------------------
# CISA KEV
# --------------------------------------------------------------------------

def kev_to_event(raw: dict) -> dict | None:
    """KEV carries exploitation status, not version ranges."""
    event_id = _text(raw.get("cveID"))
    if not event_id:
        return None
    notes = _text(raw.get("notes"))
    required_action = _text(raw.get("requiredAction"))
    description = _text(raw.get("shortDescription"))
    excerpt = _excerpt(
        " ".join(x for x in [description, f"Required action: {required_action}" if required_action else "", notes] if x)
    )
    source_entry = {
        "id": _source_id("kev", event_id),
        "url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        "title": f"CISA KEV entry for {event_id}",
        "publisher": "CISA",
        "source_type": "exploitation_catalog",
        "excerpt": excerpt,
        "published_at": _iso(raw.get("dateAdded")),
        "collected_at": storage.utcnow(),
        "content_hash": storage.content_hash(excerpt),
        "trust": "authoritative",
    }
    event = canonical_event(
        event_id=event_id,
        title=_text(raw.get("vulnerabilityName")) or event_id,
        summary=_excerpt(description, 400),
        component=_text(raw.get("product")),
        ecosystem=_text(raw.get("vendorProject")),
        published_at=raw.get("dateAdded"),
        affected=[{
            "package": _text(raw.get("product")),
            "ecosystem": _text(raw.get("vendorProject")),
            "range": UNKNOWN_RANGE,  # KEV states no version bounds
            "fixed_version": None,
            "source_id": _source_id("kev", f"{event_id}:range"),
        }],
        sources=[source_entry],
        references=[f"https://nvd.nist.gov/vuln/detail/{event_id}"],
        tags=["known_exploited", _text(raw.get("knownRansomwareCampaignUse"))],
        relationships=[{
            "subject": event_id,
            "predicate": "known_exploited",
            "object": "CISA KEV catalog",
            "conditions": {
                "required_action": required_action or "unknown",
                "ransomware_use": _text(raw.get("knownRansomwareCampaignUse")) or "unknown",
                "due_date": _text(raw.get("dueDate")) or "unknown",
            },
            "evidence_ids": [source_entry["id"]],
        }],
        content_hash=storage.content_hash(excerpt),
    )
    return _apply_relevance(event, description, notes)


# --------------------------------------------------------------------------
# Microsoft MSRC
# --------------------------------------------------------------------------

def _nested_value(value: Any) -> str:
    """CVRF wraps strings as {"Value": "..."}; accept either shape."""
    if isinstance(value, dict):
        return _text(value.get("Value"))
    return _text(value)


def msrc_to_event(raw: dict) -> dict | None:
    """Map one MSRC CVRF Vulnerability entry to a canonical event."""
    cve_id = _text(raw.get("CVE"))
    doc_id = _text(raw.get("DocumentID")) or _text(raw.get("ID"))
    if not cve_id and not doc_id:
        return None
    title = _nested_value(raw.get("Title")) or cve_id or doc_id
    description = _text(raw.get("Description")) or title
    released = raw.get("ReleaseDate") or raw.get("ReleasedDate") or raw.get("InitialReleaseDate")

    cvss: list[dict] = []
    for entry in raw.get("CVSSScoreSets") or []:
        vector = _text(entry.get("Vector"))
        if not vector:
            continue
        version = "3.1"
        match = re.match(r"CVSS:(\d+\.\d+)", vector)
        if match:
            version = match.group(1)
        score = entry.get("BaseScore")
        cvss.append({
            "version": version,
            "score": float(score) if isinstance(score, (int, float)) else None,
            "vector": vector,
            "source_id": _source_id("msrc", f"{doc_id}:cvss:{vector}"),
        })

    severity_label = _severity_label(raw.get("Severity"))

    link = (
        f"https://msrc.microsoft.com/update-guide/vulnerability/{cve_id}"
        if cve_id else "https://msrc.microsoft.com/update-guide"
    )
    source_entry = {
        "id": _source_id("msrc", cve_id or doc_id),
        "url": link,
        "title": title,
        "publisher": "Microsoft MSRC",
        "source_type": "vendor_advisory",
        "excerpt": _excerpt(description),
        "published_at": _iso(released),
        "collected_at": storage.utcnow(),
        "content_hash": storage.content_hash(_text(description)),
        "trust": "vendor",
    }
    affected = []
    for product in (raw.get("ProductTree") or {}).get("FullProductName") or []:
        name = _nested_value(product.get("Value")) or _text(product.get("ProductID"))
        if not name:
            continue
        affected.append({
            "package": name, "ecosystem": "Microsoft", "range": UNKNOWN_RANGE,
            "fixed_version": None,
            "source_id": _source_id("msrc", f"{cve_id or doc_id}:{name}"),
        })
    affected = affected[:25]

    event = canonical_event(
        event_id=cve_id or f"MSRC-{doc_id}",
        title=title,
        summary=_excerpt(description, 400),
        component=(affected[0]["package"] if affected else ""),
        ecosystem="Microsoft",
        published_at=released,
        affected=affected,
        severity=severity_label,
        cvss=cvss,
        sources=[source_entry],
        references=[link],
        tags=["vendor_advisory", doc_id] if doc_id else ["vendor_advisory"],
        content_hash=storage.content_hash(_text(description)),
    )
    return _apply_relevance(event, description, title)


# --------------------------------------------------------------------------
# RSS / Atom and plain pages (knowledge base layer)
# --------------------------------------------------------------------------

def feed_entry_to_event(entry: dict, *, source_key: str, publisher: str, trust: str,
                        tags: Iterable[str] = (), kind: str = "knowledge") -> dict | None:
    link = _text(entry.get("link"))
    title = _text(entry.get("title"))
    event_id = _text(entry.get("id")) or (storage.content_hash(link or title)[:16])
    if not title and not link:
        return None
    description = _text(entry.get("summary") or entry.get("description"))
    published = entry.get("published") or entry.get("updated")
    source_entry = {
        "id": _source_id(source_key, event_id),
        "url": link,
        "title": title or link,
        "publisher": publisher,
        "source_type": "article" if kind == "knowledge" else "advisory",
        "excerpt": _excerpt(description),
        "published_at": _iso(published),
        "collected_at": storage.utcnow(),
        "content_hash": storage.content_hash(_text(description or title)),
        "trust": trust,
    }
    event = canonical_event(
        event_id=f"{source_key.upper()}-{event_id}" if not event_id.startswith(("http", source_key)) else event_id,
        title=title or link,
        summary=_excerpt(description, 400),
        component="",
        ecosystem="",
        kind=kind,
        published_at=published,
        sources=[source_entry],
        references=[link] if link else [],
        tags=list(tags),
        content_hash=storage.content_hash(_text(description or title)),
    )
    return _apply_relevance(event, description)


def arxiv_entry_to_event(entry: dict) -> dict | None:
    link = _text(entry.get("link"))
    title = re.sub(r"\s+", " ", _text(entry.get("title"))).strip()
    if not title:
        return None
    abstract = re.sub(r"\s+", " ", _text(entry.get("summary"))).strip()
    categories = entry.get("categories") or []
    primary = _text(entry.get("primary_category")) or (categories[0] if categories else "")
    published = entry.get("published")
    source_entry = {
        "id": _source_id("arxiv", link or title),
        "url": link,
        "title": title,
        "publisher": "arXiv",
        "source_type": "preprint",
        "excerpt": _excerpt(abstract),
        "published_at": _iso(published),
        "collected_at": storage.utcnow(),
        "content_hash": storage.content_hash(abstract or title),
        "trust": "preprint",
    }
    # A URL makes a poor primary key; use the arXiv identifier.
    raw_id = _text(entry.get("id")) or link
    short_id = re.sub(r"^https?://arxiv\.org/abs/", "", raw_id).strip("/") or raw_id

    event = canonical_event(
        event_id=f"ARXIV-{short_id}" if short_id else storage.content_hash(title)[:16],
        title=title,
        summary=_excerpt(abstract, 400),
        component=primary,
        ecosystem="arXiv",
        kind="knowledge",
        published_at=published,
        sources=[source_entry],
        references=[link] if link else [],
        tags=["preprint", *categories],
        content_hash=storage.content_hash(abstract or title),
    )
    return _apply_relevance(event, abstract, primary)


def _openalex_abstract(work: dict) -> str:
    inverted = work.get("abstract_inverted_index")
    if not isinstance(inverted, dict):
        return ""
    positions: dict[int, str] = {}
    for token, offsets in inverted.items():
        for offset in offsets or []:
            if isinstance(offset, int):
                positions[offset] = str(token)
    return " ".join(positions[index] for index in sorted(positions))


def openalex_work_to_event(work: dict) -> dict | None:
    """Convert one OpenAlex work into the project's knowledge-event contract."""
    title = re.sub(r"\s+", " ", _text(work.get("display_name") or work.get("title"))).strip()
    if not title:
        return None
    abstract = re.sub(r"\s+", " ", _text(work.get("abstract") or _openalex_abstract(work))).strip()
    primary_location = work.get("primary_location") or {}
    best_location = work.get("best_oa_location") or {}
    landing_url = _text(
        best_location.get("landing_page_url")
        or primary_location.get("landing_page_url")
        or work.get("doi")
        or work.get("id")
    )
    pdf_url = _text(best_location.get("pdf_url") or primary_location.get("pdf_url"))
    openalex_id = _text(work.get("id"))
    short_id = openalex_id.rstrip("/").rsplit("/", 1)[-1] or storage.content_hash(title)[:16]
    topics = [
        _text(item.get("display_name"))
        for item in (work.get("topics") or [])
        if isinstance(item, dict) and item.get("display_name")
    ]
    primary_topic = (work.get("primary_topic") or {}).get("display_name") if isinstance(
        work.get("primary_topic"), dict
    ) else ""
    tags = list(dict.fromkeys(["scholarly_index", primary_topic, *topics]))
    source_entry = {
        "id": _source_id("openalex", openalex_id or landing_url or title),
        "url": landing_url,
        "title": title,
        "publisher": "OpenAlex",
        "source_type": "scholarly_index",
        "excerpt": _excerpt(abstract or title),
        "published_at": _iso(work.get("publication_date")),
        "collected_at": storage.utcnow(),
        "content_hash": storage.content_hash(abstract or title),
        "trust": "scholarly_index",
    }
    references = [url for url in (landing_url, pdf_url) if url]
    event = canonical_event(
        event_id=f"OPENALEX-{short_id}",
        title=title,
        summary=_excerpt(abstract or title, 400),
        component=primary_topic or (topics[0] if topics else ""),
        ecosystem="OpenAlex",
        kind="knowledge",
        published_at=work.get("publication_date"),
        sources=[source_entry],
        references=references,
        tags=tags,
        content_hash=storage.content_hash(abstract or title),
    )
    if pdf_url:
        event["paper"] = {
            "openalex_id": short_id,
            "pdf_url": pdf_url,
            "full_text": {"status": "not_attempted", "has_full_text": False},
        }
    return _apply_relevance(event, abstract, " ".join(tags))


def page_to_event(*, source_key: str, url: str, title: str, text: str,
                  publisher: str, trust: str, tags: Iterable[str] = ()) -> dict:
    source_entry = {
        "id": _source_id(source_key, url),
        "url": url,
        "title": title,
        "publisher": publisher,
        "source_type": "standard",
        "excerpt": _excerpt(text),
        "published_at": None,
        "collected_at": storage.utcnow(),
        "content_hash": storage.content_hash(text),
        "trust": trust,
    }
    event = canonical_event(
        event_id=f"{source_key.upper()}-{storage.content_hash(url)[:10]}",
        title=title,
        summary=_excerpt(text, 400),
        component="",
        ecosystem="",
        kind="knowledge",
        sources=[source_entry],
        references=[url],
        tags=list(tags),
        content_hash=storage.content_hash(text),
    )
    return _apply_relevance(event, text, title)


# --------------------------------------------------------------------------
# Seed data from the verified research file
# --------------------------------------------------------------------------

def research_case_to_event(case: dict) -> dict:
    """Convert a `research/cases.json` entry into a canonical event.

    These are the three cases a human verified against official sources, so
    they carry the strongest evidence grade in the corpus and seed the
    evaluation gold standard.
    """
    event_id = _text(case.get("id"))
    severity = case.get("severity") or {}
    cvss_version = severity.get("cvss_version")
    score = severity.get("score")
    cvss = []
    if cvss_version or score is not None:
        cvss.append({
            "version": _text(cvss_version) or "",
            "score": float(score) if isinstance(score, (int, float)) else None,
            "vector": "",  # the research file records a score, not a vector
            "source_id": _source_id("research", f"{event_id}:cvss"),
        })

    affected = []
    range_text = _text(case.get("affected_versions"))
    if range_text:
        # `assess_asset` matches an asset by comparing the asset's `component`
        # against both the event `component` and each `affected[].package`, so
        # those two must agree.  The ecosystem identifier (a Go module path,
        # say) is kept in `tags` instead of breaking that match.
        affected.append({
            "package": _text(case.get("component")),
            "ecosystem": _text(case.get("ecosystem")),
            "range": range_text,
            "fixed_version": _text(case.get("patched_versions")) or None,
            "source_id": _source_id("research", f"{event_id}:range"),
        })

    conditions = [
        {
            "name": f"prerequisite_{index + 1}",
            "value": True,
            "description": _text(text),
            "source_id": _source_id("research", f"{event_id}:prereq:{index}"),
        }
        for index, text in enumerate(case.get("prerequisites") or [])
    ]

    sources = []
    for item in case.get("evidence") or []:
        url = _text(item.get("url"))
        if not url:
            continue
        sources.append({
            "id": _source_id("research", url),
            "url": url,
            "title": _text(case.get("title")) or event_id,
            "publisher": _text(item.get("publisher")),
            "source_type": _text(item.get("type")),
            "excerpt": _excerpt(case.get("impact")),
            "published_at": _iso(case.get("published_date")),
            "collected_at": storage.utcnow(),
            "content_hash": storage.content_hash(url),
            "trust": "authoritative",
        })

    summary = " ".join(x for x in [_text(case.get("title")), _text(case.get("impact"))] if x)
    event = canonical_event(
        event_id=event_id,
        aliases=case.get("aliases") or [],
        title=_text(case.get("title")) or event_id,
        summary=_excerpt(summary, 400),
        component=_text(case.get("component")),
        ecosystem=_text(case.get("ecosystem")),
        published_at=case.get("published_date"),
        modified_at=case.get("reviewed_date"),
        affected=affected,
        conditions=conditions,
        severity=_severity_label(severity.get("label")),
        cvss=cvss,
        cwes=_cwe_list(case.get("cwe")),
        sources=sources,
        references=[_text(e.get("url")) for e in case.get("evidence") or [] if e.get("url")],
        tags=[
            "verified_research",
            _text(case.get("evidence_grade")),
            f"pkg:{_text(case.get('package'))}",
        ],
        content_hash=storage.content_hash(summary),
    )
    event["ai_relevance"] = {
        "included": True,
        "reason": f"研究负责人已核验的 AI 基础设施漏洞案例（{_text(case.get('component'))}）",
    }
    event["evidence_grade"] = _text(case.get("evidence_grade"))
    event["unknown_fields"] = list(case.get("unknown_fields") or [])
    event["poc_executed"] = bool(case.get("poc_executed"))
    return event
