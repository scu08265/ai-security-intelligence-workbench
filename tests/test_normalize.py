"""Normalization must never invent a value it could not read."""

from __future__ import annotations

import json
from pathlib import Path

from app import normalize

from fixtures import (
    GHSA_SYNTHETIC, KEV_SYNTHETIC, NVD_ITEM_SYNTHETIC, NVD_SYNTHETIC,
    OSV_GIT_RANGE_SYNTHETIC, OSV_OPEN_ENDED_SYNTHETIC, OSV_SYNTHETIC,
)

CONTRACT_KEYS = {
    "id", "kind", "aliases", "title", "summary", "component", "ecosystem",
    "published_at", "modified_at", "collected_at", "withdrawn", "status",
    "affected", "conditions", "severity", "cvss", "cwes", "sources",
    "references", "poc", "ai_relevance", "tags", "relationships", "content_hash",
}

import re


def _norm(value) -> str:
    return re.sub(r"[\s_.\-/]+", "", ("" if value is None else str(value)).casefold())


def test_every_event_carries_the_full_contract_key_set():
    for event in (normalize.osv_to_event(OSV_SYNTHETIC),
                  normalize.nvd_to_event(NVD_ITEM_SYNTHETIC)):
        assert event is not None
        assert CONTRACT_KEYS <= set(event), CONTRACT_KEYS - set(event)


def test_osv_introduced_fixed_becomes_a_specifier():
    specifiers, complete = normalize.osv_ranges_to_specifiers(
        [{"type": "ECOSYSTEM", "events": [{"introduced": "0.8.3"}, {"fixed": "0.14.1"}]}]
    )
    assert complete is True
    assert specifiers == [">= 0.8.3, < 0.14.1"]


def test_osv_zero_introduced_reads_as_an_upper_bound_only():
    specifiers, complete = normalize.osv_ranges_to_specifiers(
        [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "0.17.1"}]}]
    )
    assert complete is True
    assert specifiers == ["< 0.17.1"]


def test_osv_open_ended_range_keeps_being_affected():
    specifiers, _ = normalize.osv_ranges_to_specifiers(
        [{"type": "ECOSYSTEM", "events": [{"introduced": "1.0"}]}]
    )
    assert specifiers == [">= 1.0"]


def test_git_ranges_are_not_treated_as_versions():
    """Commit hashes are not comparable versions; the range must stay unknown."""
    specifiers, complete = normalize.osv_ranges_to_specifiers(
        [{"type": "GIT", "events": [{"introduced": "deadbeef"}]}]
    )
    assert complete is False
    assert specifiers == []

    event = normalize.osv_to_event(OSV_GIT_RANGE_SYNTHETIC)
    assert event["affected"][0]["range"] == normalize.UNKNOWN_RANGE


def test_unknown_event_type_invalidates_the_whole_range():
    """An unrecognised event kind must invalidate the range, not be skipped.

    The parsed specifiers are discarded by the caller when `complete` is False,
    so the flag is the guarantee that matters.
    """
    _specifiers, complete = normalize.osv_ranges_to_specifiers(
        [{"type": "ECOSYSTEM", "events": [{"introduced": "1.0"}, {"surprise": "x"}, {"fixed": "2.0"}]}]
    )
    assert complete is False


def test_osv_cvss_vector_is_not_stored_as_a_numeric_score():
    """OSV publishes a vector; storing it in `score` would fabricate a number."""
    event = normalize.osv_to_event(OSV_SYNTHETIC)
    entry = event["cvss"][0]
    assert entry["vector"].startswith("CVSS:3.1/")
    assert entry["score"] is None
    assert event["severity"] is None


def test_nvd_numeric_score_is_kept_and_mapped_to_a_label():
    event = normalize.nvd_to_event(NVD_ITEM_SYNTHETIC)
    assert event["cvss"][0]["score"] == 9.8
    assert event["severity"] == "critical"


def test_excerpt_is_verbatim_upstream_text():
    event = normalize.osv_to_event(OSV_SYNTHETIC)
    assert event["sources"][0]["excerpt"] == OSV_SYNTHETIC["details"]
    assert event["sources"][0]["content_hash"]


def test_component_and_affected_package_agree():
    """`assess_asset` matches on both, so they must not diverge."""
    for event in (
        normalize.osv_to_event(OSV_SYNTHETIC),
        normalize.nvd_to_event(NVD_ITEM_SYNTHETIC),
        normalize.ghsa_to_event(GHSA_SYNTHETIC[0]),
    ):
        assert event["affected"], event["id"]
        assert _norm(event["component"]) in {
            _norm(item["package"]) for item in event["affected"]
        }


def test_kev_entries_carry_no_invented_version_range():
    event = normalize.kev_to_event(KEV_SYNTHETIC["vulnerabilities"][0])
    assert event["affected"][0]["range"] == normalize.UNKNOWN_RANGE
    assert "known_exploited" in event["tags"]
    relationship = event["relationships"][0]
    assert relationship["predicate"] == "known_exploited"
    assert relationship["evidence_ids"] == [event["sources"][0]["id"]]
    assert event["poc"] == []


def test_kev_marks_the_exploitation_fact_in_the_excerpt():
    event = normalize.kev_to_event(KEV_SYNTHETIC["vulnerabilities"][0])
    assert "dateAdded" not in event["sources"][0]["excerpt"]
    assert event["sources"][0]["publisher"] == "CISA"


def test_withdrawn_records_are_flagged_not_dropped():
    payload = json.loads(json.dumps(OSV_SYNTHETIC))
    event = normalize.osv_to_event(payload)
    assert event["withdrawn"] is False

    nvd_payload = json.loads(json.dumps(NVD_ITEM_SYNTHETIC))
    nvd_payload["cve"]["vulnStatus"] = "Rejected"
    rejected = normalize.nvd_to_event(nvd_payload)
    assert rejected["withdrawn"] is True
    assert rejected["status"] == "withdrawn"


def test_research_cases_file_normalizes_with_real_evidence():
    path = Path(__file__).resolve().parent.parent / "research" / "cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    assert cases, "the verified research file should not be empty"
    for case in cases:
        event = normalize.research_case_to_event(case)
        assert event["id"] == case["id"]
        assert event["sources"], f"{case['id']} must keep its evidence links"
        assert event["ai_relevance"]["included"] is True
        # The ecosystem package identifier is retained in tags, not lost.
        assert any(tag.startswith("pkg:") for tag in event["tags"])


def test_osv_open_ended_record_normalizes_conservatively():
    event = normalize.osv_to_event(OSV_OPEN_ENDED_SYNTHETIC)
    assert event["affected"][0]["range"] == "< 0.17.1"


def test_ancient_upstream_timestamp_is_treated_as_missing():
    assert normalize._iso("0001-01-01T00:00:00Z") is None


def test_mitre_range_expression_is_not_double_prefixed():
    event = normalize.mitre_to_event({
        "cveMetadata": {
            "cveId": "CVE-2099-99999",
            "datePublished": "2099-01-01T00:00:00Z",
            "state": "PUBLISHED",
        },
        "containers": {"cna": {
            "descriptions": [{"lang": "en", "value": "prompt injection"}],
            "affected": [{
                "product": "vllm",
                "versions": [{"version": ">= 0.8.3, < 0.14.1"}],
            }],
        }},
    })
    assert event["affected"][0]["range"] == ">= 0.8.3, < 0.14.1"
