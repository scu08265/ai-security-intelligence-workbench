"""Deduplication: merge on identifiers, propose on similarity."""

from __future__ import annotations

from app import dedupe, storage


def _event(event_id, **updates):
    base = {
        "id": event_id, "kind": "vulnerability", "status": "confirmed",
        "title": "Synthetic fixture issue", "summary": "Synthetic.",
        "component": "vllm", "ecosystem": "PyPI",
        "published_at": "2099-01-01T00:00:00Z", "collected_at": storage.utcnow(),
        "withdrawn": False, "aliases": [], "affected": [], "conditions": [],
        "severity": None, "cvss": [], "cwes": [], "sources": [], "references": [],
        "poc": [], "relationships": [], "tags": [],
        "ai_relevance": {"included": True, "reason": "synthetic"},
        "content_hash": f"hash-{event_id}",
    }
    base.update(updates)
    return base


def test_new_event_is_reported_as_new():
    result = dedupe.resolve(_event("CVE-2099-00001"))
    assert result.action == "new"


def test_alias_match_merges_into_the_preferred_identifier():
    storage.upsert_event(_event("CVE-2099-00001", aliases=["GHSA-synth-1111"]))
    incoming = _event("GHSA-synth-1111", content_hash="hash-other")
    result = dedupe.resolve(incoming)
    assert result.action == "merged"
    assert result.event["id"] == "CVE-2099-00001"
    assert "GHSA-synth-1111" in result.event["aliases"]


def test_primary_identifier_never_appears_in_its_own_aliases():
    storage.upsert_event(_event("CVE-2099-00001"))
    result = dedupe.resolve(_event("GHSA-synth-2222", aliases=["CVE-2099-00001"]))
    assert result.event["id"] == "CVE-2099-00001"
    assert "CVE-2099-00001" not in result.event["aliases"]


def test_conflicting_ranges_are_kept_side_by_side_with_provenance():
    storage.upsert_event(_event(
        "CVE-2099-00001",
        affected=[{"package": "vllm", "ecosystem": "PyPI", "range": "<= 0.8.5",
                   "fixed_version": None, "source_id": "src-research"}],
    ))
    incoming = _event(
        "GHSA-synth-3333", aliases=["CVE-2099-00001"],
        affected=[{"package": "vllm", "ecosystem": "PyPI", "range": ">= 0.8.5, < 0.24.0",
                   "fixed_version": "0.24.0", "source_id": "src-osv"}],
    )
    result = dedupe.resolve(incoming)
    ranges = {item["range"] for item in result.event["affected"]}
    assert ranges == {"<= 0.8.5", ">= 0.8.5, < 0.24.0"}
    conflicts = result.event.get("conflicts") or []
    assert conflicts and conflicts[0]["field"] == "affected.range"
    assert "并列保留" in conflicts[0]["note"]


def test_provenance_is_preserved_for_each_range():
    storage.upsert_event(_event(
        "CVE-2099-00001",
        affected=[{"package": "vllm", "range": ">= 1.0, < 2.0", "source_id": "src-a"}],
    ))
    result = dedupe.resolve(_event(
        "GHSA-synth-4444", aliases=["CVE-2099-00001"],
        affected=[{"package": "vllm", "range": ">= 1.0, < 2.0", "source_id": "src-b"}],
    ))
    combined = result.event["affected"][0]
    assert set(combined["source_ids"]) == {"src-a", "src-b"}


def test_severity_conflict_is_recorded_and_resolved_upward():
    storage.upsert_event(_event("CVE-2099-00001", severity="medium"))
    result = dedupe.resolve(_event("GHSA-synth-5555", aliases=["CVE-2099-00001"],
                                   severity="critical"))
    assert result.event["severity"] == "critical"
    assert any(c["field"] == "severity" for c in result.event.get("conflicts") or [])


def test_withdrawn_wins_over_confirmed():
    storage.upsert_event(_event("CVE-2099-00001", withdrawn=True, status="withdrawn"))
    result = dedupe.resolve(_event("GHSA-synth-6666", aliases=["CVE-2099-00001"]))
    assert result.event["withdrawn"] is True
    assert result.event["status"] == "withdrawn"


def test_identical_content_under_a_new_id_is_not_stored_twice():
    storage.upsert_event(_event("CVE-2099-00001", content_hash="same-bytes"))
    result = dedupe.resolve(_event("CVE-2099-00009", content_hash="same-bytes"))
    assert result.action == "unchanged"
    assert result.event["id"] == "CVE-2099-00001"


def test_similar_titles_are_only_proposed_never_merged():
    storage.upsert_event(_event(
        "CVE-2099-00001",
        title="Heap out-of-bounds read in the GGUF model loader",
        content_hash="hash-a",
    ))
    incoming = _event(
        "CVE-2099-00002",
        title="Heap out-of-bounds read in the GGUF model parser",
        content_hash="hash-b",
    )
    result = dedupe.resolve(incoming)
    assert result.action == "new", "similar titles must never auto-merge"
    assert "CVE-2099-00001" in result.candidate_ids
    candidates = storage.list_duplicate_candidates()
    assert candidates and candidates[0]["event_id"] == "CVE-2099-00002"
    assert "仅作候选" in candidates[0]["reason"]


def test_different_components_are_never_even_candidates():
    storage.upsert_event(_event("CVE-2099-00001", component="vllm",
                                title="Heap out-of-bounds read in the model loader"))
    result = dedupe.resolve(_event("CVE-2099-00002", component="nginx",
                                   title="Heap out-of-bounds read in the model loader"))
    assert result.candidate_ids == []


def test_merging_unions_sources_without_duplicating():
    storage.upsert_event(_event("CVE-2099-00001", sources=[
        {"id": "src-a", "url": "https://example.invalid/a", "publisher": "A"}]))
    result = dedupe.resolve(_event("GHSA-synth-7777", aliases=["CVE-2099-00001"], sources=[
        {"id": "src-a", "url": "https://example.invalid/a", "publisher": "A"},
        {"id": "src-b", "url": "https://example.invalid/b", "publisher": "B"},
    ]))
    assert {s["id"] for s in result.event["sources"]} == {"src-a", "src-b"}
