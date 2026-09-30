"""Collectors for the vulnerability-monitoring layer.

Each collector returns a `CollectOutcome` describing what actually happened:
how many records were scanned, how many were dropped as not AI-relevant, how
many became events, and any partial-completion caveat.  A collector that hits
its fetch budget reports `partial` rather than quietly truncating.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from .. import normalize, relevance, storage
from ..sources import SourceSpec
from . import MAX_DETAIL_FETCHES, CollectOutcome, FetchError, get_json, post_json, record_snapshot

# Per-run work budgets.  These bound how long one collection may take; a
# collector that hits its budget reports `partial` rather than silently
# truncating.
NVD_MAX_PAGES = int(os.getenv("NVD_MAX_PAGES", "100") or 100)
NVD_PAGE_SIZE = 200
NVD_PAGE_DELAY_SECONDS = float(os.getenv("NVD_PAGE_DELAY_SECONDS", "6.0") or 6.0)
OSV_DETAIL_BUDGET = 12
MITRE_BUDGET = 10
MSRC_RELEASES = 1

# Packages queried against OSV.  Kept deliberately narrower than the full
# AI_PACKAGES keyword list: these are the ecosystems that actually publish
# advisories through OSV and are known to be deployed widely.
OSV_SCOPE: tuple[tuple[str, str], ...] = (
    ("vllm", "PyPI"), ("transformers", "PyPI"), ("langchain", "PyPI"),
    ("langchain-core", "PyPI"), ("llama-index", "PyPI"), ("gradio", "PyPI"),
    ("diffusers", "PyPI"), ("accelerate", "PyPI"), ("sentence-transformers", "PyPI"),
    ("torch", "PyPI"), ("tensorflow", "PyPI"), ("onnx", "PyPI"), ("onnxruntime", "PyPI"),
    ("mlflow", "PyPI"), ("ray", "PyPI"), ("xgboost", "PyPI"), ("scikit-learn", "PyPI"),
    ("open-webui", "PyPI"), ("comfyui", "PyPI"), ("autogen", "PyPI"), ("crewai", "PyPI"),
    ("llama-cpp-python", "PyPI"), ("ollama", "PyPI"), ("huggingface-hub", "PyPI"),
    ("triton", "PyPI"), ("pytorch", "PyPI"), ("keras", "PyPI"), ("jax", "PyPI"),
    ("dspy", "PyPI"), ("haystack-ai", "PyPI"), ("peft", "PyPI"), ("datasets", "PyPI"),
    ("github.com/ollama/ollama", "Go"), ("github.com/triton-inference-server/server", "Go"),
    ("github.com/huggingface/transformers", "Go"), ("github.com/ray-project/ray", "Go"),
    ("ollama", "npm"), ("@huggingface/transformers", "npm"), ("langchain", "npm"),
    ("@langchain/core", "npm"), ("openai", "npm"), ("@anthropic-ai/sdk", "npm"),
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _default_since(days: int = 7) -> str:
    return (_now() - timedelta(days=days)).isoformat(timespec="milliseconds")


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _keep(event: dict | None, outcome: CollectOutcome) -> None:
    """Common accept/reject accounting for every collector."""
    if event is None or not (event.get("ai_relevance") or {}).get("included"):
        outcome.filtered += 1
        return
    event.setdefault("sources", [])
    outcome.events.append(event)


# --------------------------------------------------------------------------
# NVD
# --------------------------------------------------------------------------

def collect_nvd(spec: SourceSpec, since: str | None) -> CollectOutcome:
    start = _parse_iso(since) or (_now() - timedelta(days=7))
    start = (start - timedelta(hours=6)).replace(microsecond=0)  # overlap window
    end = _now().replace(microsecond=0)
    outcome = CollectOutcome(source_id=spec.id, status="ok")

    scanned = 0
    pages = 0
    start_index = 0
    hashes: list[str] = []
    total = 0
    complete = False
    api_key = os.getenv("NVD_API_KEY", "").strip()
    while NVD_MAX_PAGES <= 0 or pages < NVD_MAX_PAGES:
        params = {
            "lastModStartDate": start.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "lastModEndDate": end.strftime("%Y-%m-%dT%H:%M:%S.000"),
            "resultsPerPage": NVD_PAGE_SIZE,
            "startIndex": start_index,
        }
        if api_key:
            params["apiKey"] = api_key
        payload, raw = get_json(spec.url, params=params, timeout=45)
        hashes.append(record_snapshot(spec.id, raw))
        page = payload.get("vulnerabilities") or []
        total = int(payload.get("totalResults") or total or 0)
        outcome.fetched += len(page)
        scanned += len(page)
        for item in page:
            _keep(normalize.nvd_to_event(item), outcome)
        pages += 1
        start_index += NVD_PAGE_SIZE
        if start_index >= total or not page:
            complete = True
            break
        if NVD_PAGE_DELAY_SECONDS > 0:
            time.sleep(NVD_PAGE_DELAY_SECONDS)
    else:
        outcome.status = "partial"
        outcome.notes.append(
            f"NVD 在窗口内共 {total} 条，本次仅扫描 {scanned} 条（上限 {NVD_MAX_PAGES} 页）"
        )

    if complete:
        outcome.cursor = end.isoformat(timespec="milliseconds")
    outcome.snapshot_hash = hashes[-1] if hashes else None
    outcome.notes.append(
        f"窗口 {start:%Y-%m-%d %H:%M} → {end:%Y-%m-%d %H:%M}，"
        f"共 {total} 条，分 {pages} 页扫描 {scanned} 条"
    )
    return outcome


def _cve_candidates(limit: int = MITRE_BUDGET) -> list[tuple[str, dict]]:
    """Events that carry a CVE id but no MITRE record yet."""
    events, _ = storage.list_events(limit=200)
    out = []
    for event in events:
        if not str(event.get("id", "")).startswith("CVE-"):
            continue
        if any(s.get("publisher") == "MITRE CVE Program" for s in event.get("sources") or []):
            continue
        out.append((event["id"], event))
        if len(out) >= limit:
            break
    return out


# --------------------------------------------------------------------------
# MITRE CVE Services
# --------------------------------------------------------------------------

def collect_mitre_cve(spec: SourceSpec, since: str | None) -> CollectOutcome:
    """Cross-verify CVE records we already hold against the authoritative record.

    CVE Services has no bulk 'recent changes' feed, so this is deliberately an
    enrichment pass over known CVE ids rather than a discovery source.
    """
    outcome = CollectOutcome(source_id=spec.id, status="ok")
    candidates = _cve_candidates()
    if not candidates:
        outcome.status = "skipped"
        outcome.notes.append("库中没有待交叉核验的 CVE 编号（需先由其它来源发现）")
        return outcome
    hashes: list[str] = []
    for cve_id, _ in candidates:
        payload, raw = get_json(f"{spec.url}/{cve_id}", timeout=30)
        hashes.append(record_snapshot(spec.id, raw, suffix="json"))
        outcome.fetched += 1
        _keep(normalize.mitre_to_event(payload), outcome)
    outcome.snapshot_hash = hashes[-1] if hashes else None
    outcome.notes.append(f"逐条核验 {outcome.fetched} 个已有 CVE 记录（单次上限 {MITRE_BUDGET}）")
    return outcome


# --------------------------------------------------------------------------
# OSV
# --------------------------------------------------------------------------

def collect_osv(spec: SourceSpec, since: str | None) -> CollectOutcome:
    """Query OSV in one batched request, then fetch details for new records only."""
    outcome = CollectOutcome(source_id=spec.id, status="ok", cursor=_now().isoformat(timespec="milliseconds"))
    queries = [{"package": {"name": name, "ecosystem": ecosystem}} for name, ecosystem in OSV_SCOPE]
    payload, raw = post_json(spec.url, {"queries": queries}, timeout=60)
    outcome.snapshot_hash = record_snapshot(spec.id, raw)

    cutoff = _parse_iso(since)
    discovered: dict[str, datetime | None] = {}
    for result in payload.get("results") or []:
        for vuln in result.get("vulns") or []:
            vid = str(vuln.get("id") or "")
            if vid:
                discovered[vid] = _parse_iso(vuln.get("modified"))
    outcome.fetched = len(discovered)
    outcome.notes.append(f"批量查询 {len(queries)} 个包，命中 {len(discovered)} 条 OSV 记录")

    fresh = [
        (vid, modified) for vid, modified in discovered.items()
        if cutoff is None or (modified and modified >= cutoff)
    ]
    fresh.sort(key=lambda item: item[1] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    if not fresh:
        outcome.notes.append("本次窗口内没有新增或变更的 OSV 记录")
        return outcome

    budget = fresh[:OSV_DETAIL_BUDGET]
    if len(fresh) > len(budget):
        outcome.status = "partial"
        outcome.notes.append(
            f"窗口内共 {len(fresh)} 条更新，本次取最新 {len(budget)} 条（单次上限 {OSV_DETAIL_BUDGET}）"
        )

    # Detail lookups are independent, so fetch them concurrently.  The budget
    # still bounds how many are made.
    def fetch_detail(entry: tuple[str, Any]) -> tuple[dict | None, str | None]:
        vid, _ = entry
        try:
            detail, detail_raw = get_json(f"https://api.osv.dev/v1/vulns/{vid}", timeout=30)
        except FetchError:
            return None, None
        record_snapshot(spec.id, detail_raw)
        return normalize.osv_to_event(detail), None

    with ThreadPoolExecutor(max_workers=6) as pool:
        for event, _ in pool.map(fetch_detail, budget):
            _keep(event, outcome)
    outcome.notes.append(f"已取详细记录 {len(budget)} 条（并发 6 路）")
    return outcome


# --------------------------------------------------------------------------
# GitHub Advisory Database
# --------------------------------------------------------------------------

def collect_ghsa(spec: SourceSpec, since: str | None) -> CollectOutcome:
    import os

    outcome = CollectOutcome(source_id=spec.id, status="ok", cursor=_now().isoformat(timespec="milliseconds"))
    token = os.getenv(spec.requires_token_env or "", "").strip()
    start = (_parse_iso(since) or (_now() - timedelta(days=7))) - timedelta(hours=6)
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    per_page = 100
    page = 1
    hashes: list[str] = []
    while page <= 3:
        params = {
            "per_page": per_page,
            "page": page,
            "sort": "updated",
            "direction": "desc",
            "updated": f">={start.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        }
        payload, raw = get_json(spec.url, params=params, headers=headers, timeout=45)
        hashes.append(record_snapshot(spec.id, raw))
        batch = payload if isinstance(payload, list) else payload.get("items") or []
        outcome.fetched += len(batch)
        for item in batch:
            _keep(normalize.ghsa_to_event(item), outcome)
        if len(batch) < per_page:
            break
        page += 1
    else:
        outcome.status = "partial"
        outcome.notes.append("达到 3 页上限，可能仍有更早的增量未采集")

    outcome.snapshot_hash = hashes[-1] if hashes else None
    outcome.notes.append(f"按 updated>={start:%Y-%m-%d} 增量拉取，共扫描 {outcome.fetched} 条")
    return outcome


# --------------------------------------------------------------------------
# CISA KEV
# --------------------------------------------------------------------------

def collect_cisa_kev(spec: SourceSpec, since: str | None) -> CollectOutcome:
    outcome = CollectOutcome(source_id=spec.id, status="ok")
    payload, raw = get_json(spec.url, timeout=60)
    outcome.snapshot_hash = record_snapshot(spec.id, raw)
    entries = payload.get("vulnerabilities") or []
    outcome.fetched = len(entries)
    catalog_version = payload.get("catalogVersion")
    released = payload.get("dateReleased")

    cutoff = _parse_iso(since)
    added = 0
    for entry in entries:
        added_date = _parse_iso(entry.get("dateAdded"))
        if cutoff and added_date and added_date < cutoff:
            continue
        before = len(outcome.events)
        _keep(normalize.kev_to_event(entry), outcome)
        if len(outcome.events) > before:
            added += 1
    outcome.cursor = _now().isoformat(timespec="milliseconds")
    outcome.notes.append(
        f"KEV 目录版本 {catalog_version}（发布 {released}），全量 {len(entries)} 条，窗口内新增 {added} 条"
    )
    return outcome


# --------------------------------------------------------------------------
# Microsoft MSRC
# --------------------------------------------------------------------------

_MSRC_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], start=1
)}


def _msrc_doc_order(doc_id: str) -> tuple[int, int] | None:
    parts = doc_id.split("-")
    if len(parts) != 2 or not parts[0].isdigit() or parts[1] not in _MSRC_MONTHS:
        return None
    return int(parts[0]), _MSRC_MONTHS[parts[1]]


AI_VENDOR_PRODUCTS = (
    "azure openai", "azure ai", "azure machine learning", "cognitive services",
    "copilot", "machine learning", "onnx", "windows ml", "directml", "ai builder",
    "azure bot", "language understanding", "computer vision", "face api",
    "speech services", "translator", "document intelligence", "ai studio",
)


def collect_msrc(spec: SourceSpec, since: str | None) -> CollectOutcome:
    """Read the most recent monthly CVRF documents and keep AI-related CVEs."""
    outcome = CollectOutcome(source_id=spec.id, status="ok")
    index, index_raw = get_json(spec.url, timeout=45, headers={"Accept": "application/json"})
    outcome.snapshot_hash = record_snapshot(spec.id, index_raw)

    docs = [
        doc for doc in (index.get("value") or [])
        if _msrc_doc_order(str(doc.get("ID", ""))) and doc.get("CvrfUrl")
    ]
    # Order by the document ID (YYYY-Mon), not CurrentReleaseDate: old releases
    # are occasionally re-published, which would otherwise float them to the top.
    docs.sort(key=lambda d: _msrc_doc_order(str(d.get("ID", ""))), reverse=True)
    selected = docs[:MSRC_RELEASES]
    outcome.notes.append(
        f"更新索引共 {len(docs)} 份月度文档，本次解析最新 {len(selected)} 份（ID：{', '.join(str(d.get('ID')) for d in selected)}）"
    )

    for doc in selected:
        payload, raw = get_json(doc["CvrfUrl"], timeout=90, headers={"Accept": "application/json"})
        outcome.snapshot_hash = record_snapshot(spec.id, raw)
        products = _msrc_products(payload)
        vulns = payload.get("Vulnerability") or []
        outcome.fetched += len(vulns)
        for vuln in vulns:
            cve_id = str(vuln.get("CVE") or "")
            if not cve_id:
                continue
            names = [
                _msrc_product_name(products, str(pid))
                for status in vuln.get("ProductStatuses") or []
                for pid in status.get("ProductID") or []
            ]
            names = [n for n in names if n]
            tokens = " ".join([cve_id, str(vuln.get("Title") or ""), *names]).casefold()
            if not any(term in tokens for term in AI_VENDOR_PRODUCTS):
                outcome.filtered += 1
                continue
            record = dict(vuln)
            record["CVE"] = cve_id
            record["DocumentID"] = str(doc.get("ID") or "")
            record["DocumentTitle"] = str((payload.get("DocumentTitle") or {}).get("Value") or doc.get("ID"))
            notes = vuln.get("Notes") or []
            description = next(
                (n.get("Value") for n in notes if "description" in str(n.get("Title", "")).casefold()),
                "",
            )
            record["Description"] = description
            record["Severity"] = _msrc_severity(vuln)
            record["ProductTree"] = {"FullProductName": [{"Value": n} for n in names]}
            _keep(normalize.msrc_to_event(record), outcome)
    return outcome


def _msrc_products(payload: dict) -> dict[str, str]:
    """Flatten the CVRF product tree, including nested branches."""
    products: dict[str, str] = {}

    def walk(node: dict) -> None:
        for product in node.get("FullProductName") or []:
            pid = str(product.get("ProductID") or "")
            if pid:
                products[pid] = str(product.get("Value") or "")
        for branch in node.get("Branch") or []:
            walk(branch)

    walk(payload.get("ProductTree") or {})
    return products


def _msrc_product_name(products: dict[str, str], pid: str) -> str:
    """Resolve a ProductStatuses id.

    MSRC uses composite ids such as `20296-17084` in ProductStatuses while the
    product tree keys on the trailing `17084`, so try both forms.
    """
    if pid in products:
        return products[pid]
    for part in reversed(pid.split("-")):
        if part in products:
            return products[part]
    return ""


def _msrc_severity(vuln: dict) -> str | None:
    for threat in vuln.get("Threats") or []:
        if "severity" in str(threat.get("Type")).casefold():
            value = threat.get("Description")
            if isinstance(value, dict):
                return str(value.get("Value") or "")
            if value:
                return str(value)
    return None
