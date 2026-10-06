"""NVD CVSS backfill: an event that arrived without CVSS must gain it.

A CVE can enter the corpus through OSV/MITRE/KEV carrying no CVSS of its own.
The NVD backfill is the only path that can supply one; if it drops the CVSS
metrics, the `cvss` relation dimension has nothing to extract for those events
(this is the false-negative source found in the 2026-10-04 gold set).
"""

from __future__ import annotations

from app import normalize, storage


def _nvd_payload(cve_id: str, vector: str, score: float) -> dict:
    return {
        "cve": {
            "id": cve_id,
            "descriptions": [{"lang": "en", "value": "synthetic fixture"}],
            "metrics": {
                "cvssMetricV31": [{
                    "cvssData": {
                        "version": "3.1",
                        "vectorString": vector,
                        "baseScore": score,
                    },
                    "baseSeverity": "CRITICAL",
                }],
            },
            "references": [],
            "configurations": [],
        }
    }


def test_event_without_cvss_gains_it_from_the_nvd_backfill():
    cve = "CVE-2099-CVSS-1"
    vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:L/A:N"
    # Arrived from a non-NVD source, so it carries no CVSS of its own.
    storage.upsert_event({
        "id": cve, "kind": "vulnerability", "status": "published",
        "title": "fixture", "sources": [{"id": "osv:abc"}],
    })
    assert not (storage.get_event(cve).get("cvss") or [])

    event = normalize.nvd_to_event(_nvd_payload(cve, vector, 9.3))
    assert event["cvss"], "nvd_to_event must extract CVSS from metrics"
    assert storage.merge_event_cvss(cve, event["cvss"]) is True

    stored = storage.get_event(cve)
    assert len(stored["cvss"]) == 1
    assert stored["cvss"][0]["vector"] == vector
    assert stored["cvss"][0]["source_id"].startswith("nvd:")


def test_repeated_backfill_is_idempotent():
    cve = "CVE-2099-CVSS-2"
    vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    storage.upsert_event({"id": cve, "kind": "vulnerability", "status": "published",
                          "title": "fixture", "sources": []})
    event = normalize.nvd_to_event(_nvd_payload(cve, vector, 9.8))
    assert storage.merge_event_cvss(cve, event["cvss"]) is True
    assert storage.merge_event_cvss(cve, event["cvss"]) is False
    assert len(storage.get_event(cve)["cvss"]) == 1


def test_same_vector_from_a_different_source_stays_distinct():
    cve = "CVE-2099-CVSS-3"
    vector = "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"
    storage.upsert_event({
        "id": cve, "kind": "vulnerability", "status": "published", "title": "fixture",
        "sources": [],
        "cvss": [{"version": "3.1", "score": 9.8, "vector": vector, "source_id": "mitre:xyz"}],
    })
    merged = storage.merge_event_cvss(cve, [{
        "version": "3.1", "score": 9.8, "vector": vector, "source_id": "nvd:abc",
    }])
    assert merged is True
    assert len(storage.get_event(cve)["cvss"]) == 2


def test_backfill_does_not_touch_a_missing_event():
    assert storage.merge_event_cvss("CVE-2099-DOES-NOT-EXIST", [{"vector": "x"}]) is False
